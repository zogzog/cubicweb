"""Defines the central class for the CubicWeb RQL server: the repository.

The repository is an abstraction allowing execution of rql queries against
data sources. Most of the work is actually done in helper classes. The
repository mainly:

* brings these classes all together to provide a single access
  point to a cubicweb application.
* handles session management
* provides method for pyro registration, to call if pyro is enabled


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
import Queue
from os.path import join, exists
from datetime import datetime
from time import time, localtime, strftime

from logilab.common.decorators import cached

from yams import BadSchemaDefinition
from rql import RQLSyntaxError

from cubicweb import (CW_SOFTWARE_ROOT, UnknownEid, AuthenticationError,
                      ETypeNotSupportedBySources, RTypeNotSupportedBySources,
                      BadConnectionId, Unauthorized, ValidationError,
                      ExecutionError, typed_eid,
                      CW_MIGRATION_MAP)
from cubicweb.cwvreg import CubicWebRegistry
from cubicweb.schema import CubicWebSchema

from cubicweb.server.utils import RepoThread, LoopTask
from cubicweb.server.pool import ConnectionsPool, LateOperation, SingleLastOperation
from cubicweb.server.session import Session, InternalSession
from cubicweb.server.querier import QuerierHelper
from cubicweb.server.sources import get_source
from cubicweb.server.hooksmanager import HooksManager
from cubicweb.server.hookhelper import rproperty


class CleanupEidTypeCacheOp(SingleLastOperation):
    """on rollback of a insert query or commit of delete query, we have to
    clear repository's cache from no more valid entries

    NOTE: querier's rqlst/solutions cache may have been polluted too with
    queries such as Any X WHERE X eid 32 if 32 has been rollbacked however
    generated queries are unpredictable and analysing all the cache probably
    too expensive. Notice that there is no pb when using args to specify eids
    instead of giving them into the rql string.
    """

    def commit_event(self):
        """the observed connections pool has been rollbacked,
        remove inserted eid from repository type/source cache
        """
        self.repo.clear_caches(self.session.query_data('pendingeids', ()))

    def rollback_event(self):
        """the observed connections pool has been rollbacked,
        remove inserted eid from repository type/source cache
        """
        self.repo.clear_caches(self.session.query_data('neweids', ()))


class FTIndexEntityOp(LateOperation):
    """operation to delay entity full text indexation to commit

    since fti indexing may trigger discovery of other entities, it should be
    triggered on precommit, not commit, and this should be done after other
    precommit operation which may add relations to the entity
    """

    def precommit_event(self):
        session = self.session
        entity = self.entity
        if entity.eid in session.query_data('pendingeids', ()):
            return # entity added and deleted in the same transaction
        session.repo.system_source.fti_unindex_entity(session, entity.eid)
        for container in entity.fti_containers():
            session.repo.index_entity(session, container)

    def commit_event(self):
        pass

def del_existing_rel_if_needed(session, eidfrom, rtype, eidto):
    """delete existing relation when adding a new one if card is 1 or ?

    have to be done once the new relation has been inserted to avoid having
    an entity without a relation for some time

    this kind of behaviour has to be done in the repository so we don't have
    hooks order hazardness
    """
    # skip delete queries (only?) if session is an internal session. This is
    # hooks responsability to ensure they do not violate relation's cardinality
    if session.is_super_session:
        return
    card = rproperty(session, rtype, eidfrom, eidto, 'cardinality')
    # one may be tented to check for neweids but this may cause more than one
    # relation even with '1?'  cardinality if thoses relations are added in the
    # same transaction where the entity is being created. This never occurs from
    # the web interface but may occurs during test or dbapi connection (though
    # not expected for this).  So: don't do it, we pretend to ensure repository
    # consistency.
    # XXX should probably not use unsafe_execute!
    if card[0] in '1?':
        rschema = session.repo.schema.rschema(rtype)
        if not rschema.inlined:
            session.unsafe_execute(
                'DELETE X %s Y WHERE X eid %%(x)s, NOT Y eid %%(y)s' % rtype,
                {'x': eidfrom, 'y': eidto}, 'x')
    if card[1] in '1?':
        session.unsafe_execute(
            'DELETE X %s Y WHERE NOT X eid %%(x)s, Y eid %%(y)s' % rtype,
            {'x': eidfrom, 'y': eidto}, 'y')


class Repository(object):
    """a repository provides access to a set of persistent storages for
    entities and relations

    XXX protect pyro access
    """

    def __init__(self, config, vreg=None, debug=False):
        self.config = config
        if vreg is None:
            vreg = CubicWebRegistry(config, debug)
        self.vreg = vreg
        self.pyro_registered = False
        self.info('starting repository from %s', self.config.apphome)
        # dictionary of opened sessions
        self._sessions = {}
        # list of functions to be called at regular interval
        self._looping_tasks = []
        # list of running threads
        self._running_threads = []
        # initial schema, should be build or replaced latter
        self.schema = CubicWebSchema(config.appid)
        # querier helper, need to be created after sources initialization
        self.querier = QuerierHelper(self, self.schema)
        # should we reindex in changes?
        self.do_fti = not config['delay-full-text-indexation']
        # sources
        self.sources = []
        self.sources_by_uri = {}
        # FIXME: store additional sources info in the system database ?
        # FIXME: sources should be ordered (add_entity priority)
        for uri, source_config in config.sources().items():
            if uri == 'admin':
                # not an actual source
                continue
            source = self.get_source(uri, source_config)
            self.sources_by_uri[uri] = source
            self.sources.append(source)
        self.system_source = self.sources_by_uri['system']
        # ensure system source is the first one
        self.sources.remove(self.system_source)
        self.sources.insert(0, self.system_source)
        # cache eid -> type / source
        self._type_source_cache = {}
        # cache (extid, source uri) -> eid
        self._extid_cache = {}
        # create the hooks manager
        self.hm = HooksManager(self.schema)
        # open some connections pools
        self._available_pools = Queue.Queue()
        self._available_pools.put_nowait(ConnectionsPool(self.sources))
        if config.read_application_schema:
            # normal start: load the application schema from the database
            self.fill_schema()
        elif config.bootstrap_schema:
            # usually during repository creation
            self.warning("set fs application'schema as bootstrap schema")
            config.bootstrap_cubes()
            self.set_bootstrap_schema(self.config.load_schema())
            # need to load the Any and CWUser entity types
            self.vreg.schema = self.schema
            etdirectory = join(CW_SOFTWARE_ROOT, 'entities')
            self.vreg.init_registration([etdirectory])
            self.vreg.load_file(join(etdirectory, '__init__.py'),
                                'cubicweb.entities.__init__')
            self.vreg.load_file(join(etdirectory, 'authobjs.py'),
                                'cubicweb.entities.authobjs')
        else:
            # test start: use the file system schema (quicker)
            self.warning("set fs application'schema")
            config.bootstrap_cubes()
            self.set_schema(self.config.load_schema())
        if not config.creating:
            if 'CWProperty' in self.schema:
                self.vreg.init_properties(self.properties())
            # call source's init method to complete their initialisation if
            # needed (for instance looking for persistent configuration using an
            # internal session, which is not possible until pools have been
            # initialized)
            for source in self.sources:
                source.init()
            # call application level initialisation hooks
            self.hm.call_hooks('server_startup', repo=self)
            # register a task to cleanup expired session
            self.looping_task(self.config['session-time']/3.,
                              self.clean_sessions)
        else:
            # call init_creating so for instance native source can configurate
            # tsearch according to postgres version
            for source in self.sources:
                source.init_creating()
        # close initialization pool and reopen fresh ones for proper
        # initialization now that we know cubes
        self._get_pool().close(True)
        for i in xrange(config['connections-pool-size']):
            self._available_pools.put_nowait(ConnectionsPool(self.sources))
        self._shutting_down = False

    # internals ###############################################################

    def get_source(self, uri, source_config):
        source_config['uri'] = uri
        return get_source(source_config, self.schema, self)

    def set_schema(self, schema, resetvreg=True):
        schema.rebuild_infered_relations()
        self.info('set schema %s %#x', schema.name, id(schema))
        self.debug(', '.join(sorted(str(e) for e in schema.entities())))
        self.querier.set_schema(schema)
        for source in self.sources:
            source.set_schema(schema)
        self.schema = schema
        if resetvreg:
            # full reload of all appobjects
            self.vreg.reset()
            self.vreg.set_schema(schema)
        self.hm.set_schema(schema)
        self.hm.register_system_hooks(self.config)
        # application specific hooks
        if self.config.application_hooks:
            self.info('loading application hooks')
            self.hm.register_hooks(self.config.load_hooks(self.vreg))

    def fill_schema(self):
        """lod schema from the repository"""
        from cubicweb.server.schemaserial import deserialize_schema
        self.info('loading schema from the repository')
        appschema = CubicWebSchema(self.config.appid)
        self.set_bootstrap_schema(self.config.load_bootstrap_schema())
        self.debug('deserializing db schema into %s %#x', appschema.name, id(appschema))
        session = self.internal_session()
        try:
            try:
                deserialize_schema(appschema, session)
            except BadSchemaDefinition:
                raise
            except Exception, ex:
                import traceback
                traceback.print_exc()
                raise Exception('Is the database initialised ? (cause: %s)' %
                                (ex.args and ex.args[0].strip() or 'unknown')), \
                                None, sys.exc_info()[-1]
            self.info('set the actual schema')
            # XXX have to do this since CWProperty isn't in the bootstrap schema
            #     it'll be redone in set_schema
            self.set_bootstrap_schema(appschema)
            # 2.49 migration
            if exists(join(self.config.apphome, 'vc.conf')):
                session.set_pool()
                if not 'template' in file(join(self.config.apphome, 'vc.conf')).read():
                    # remaning from cubicweb < 2.38...
                    session.execute('DELETE CWProperty X WHERE X pkey "system.version.template"')
                    session.commit()
        finally:
            session.close()
        self.config.init_cubes(self.get_cubes())
        self.set_schema(appschema)

    def set_bootstrap_schema(self, schema):
        """disable hooks when setting a bootstrap schema, but restore
        the configuration for the next time
        """
        config = self.config
        # XXX refactor
        config.core_hooks = False
        config.usergroup_hooks = False
        config.schema_hooks = False
        config.notification_hooks = False
        config.application_hooks = False
        self.set_schema(schema, resetvreg=False)
        config.core_hooks = True
        config.usergroup_hooks = True
        config.schema_hooks = True
        config.notification_hooks = True
        config.application_hooks = True

    def start_looping_tasks(self):
        assert isinstance(self._looping_tasks, list), 'already started'
        for i, (interval, func) in enumerate(self._looping_tasks):
            self._looping_tasks[i] = task = LoopTask(interval, func)
            self.info('starting task %s with interval %.2fs', task.name,
                      interval)
            task.start()
        # ensure no tasks will be further added
        self._looping_tasks = tuple(self._looping_tasks)

    def looping_task(self, interval, func):
        """register a function to be called every `interval` seconds.

        looping tasks can only be registered during repository initialization,
        once done this method will fail.
        """
        try:
            self._looping_tasks.append( (interval, func) )
        except AttributeError:
            raise RuntimeError("can't add looping task once the repository is started")

    def threaded_task(self, func):
        """start function in a separated thread"""
        t = RepoThread(func, self._running_threads)
        t.start()

    #@locked
    def _get_pool(self):
        try:
            return self._available_pools.get(True, timeout=5)
        except Queue.Empty:
            raise Exception('no pool available after 5 secs, probably either a '
                            'bug in code (to many uncommited/rollbacked '
                            'connections) or to much load on the server (in '
                            'which case you can try to set a bigger '
                            'connections pools size)')

    def _free_pool(self, pool):
        pool.rollback()
        self._available_pools.put_nowait(pool)

    def pinfo(self):
        # XXX: session.pool is accessed from a local storage, would be interesting
        #      to see if there is a pool set in any thread specific data)
        import threading
        return '%s: %s (%s)' % (self._available_pools.qsize(),
                                ','.join(session.user.login for session in self._sessions.values()
                                         if session.pool),
                                threading.currentThread())
    def shutdown(self):
        """called on server stop event to properly close opened sessions and
        connections
        """
        self._shutting_down = True
        if isinstance(self._looping_tasks, tuple): # if tasks have been started
            for looptask in self._looping_tasks:
                self.info('canceling task %s...', looptask.name)
                looptask.cancel()
                looptask.join()
                self.info('task %s finished', looptask.name)
        for thread in self._running_threads:
            self.info('waiting thread %s...', thread.name)
            thread.join()
            self.info('thread %s finished', thread.name)
        self.hm.call_hooks('server_shutdown', repo=self)
        self.close_sessions()
        while not self._available_pools.empty():
            pool = self._available_pools.get_nowait()
            try:
                pool.close(True)
            except:
                self.exception('error while closing %s' % pool)
                continue
        if self.pyro_registered:
            pyro_unregister(self.config)
        hits, misses = self.querier.cache_hit, self.querier.cache_miss
        try:
            self.info('rqlt st cache hit/miss: %s/%s (%s%% hits)', hits, misses,
                      (hits * 100) / (hits + misses))
            hits, misses = self.system_source.cache_hit, self.system_source.cache_miss
            self.info('sql cache hit/miss: %s/%s (%s%% hits)', hits, misses,
                      (hits * 100) / (hits + misses))
            nocache  = self.system_source.no_cache
            self.info('sql cache usage: %s/%s (%s%%)', hits+ misses, nocache,
                      ((hits + misses) * 100) / (hits + misses + nocache))
        except ZeroDivisionError:
            pass

    def authenticate_user(self, session, login, password):
        """validate login / password, raise AuthenticationError on failure
        return associated CWUser instance on success
        """
        for source in self.sources:
            if source.support_entity('CWUser'):
                try:
                    eid = source.authenticate(session, login, password)
                    break
                except AuthenticationError:
                    continue
        else:
            raise AuthenticationError('authentication failed with all sources')
        euser = self._build_user(session, eid)
        if self.config.consider_user_state and \
               not euser.state in euser.AUTHENTICABLE_STATES:
            raise AuthenticationError('user is not in authenticable state')
        return euser

    def _build_user(self, session, eid):
        """return a CWUser entity for user with the given eid"""
        cls = self.vreg.etype_class('CWUser')
        rql = cls.fetch_rql(session.user, ['X eid %(x)s'])
        rset = session.execute(rql, {'x': eid}, 'x')
        assert len(rset) == 1, rset
        euser = rset.get_entity(0, 0)
        # pylint: disable-msg=W0104
        # prefetch / cache euser's groups and properties. This is especially
        # useful for internal sessions to avoid security insertions
        euser.groups
        euser.properties
        return euser

    # public (dbapi) interface ################################################

    def get_schema(self):
        """return the application schema. This is a public method, not
        requiring a session id
        """
        try:
            # necessary to support pickling used by pyro
            self.schema.__hashmode__ = 'pickle'
            return self.schema
        finally:
            self.schema.__hashmode__ = None

    def get_cubes(self):
        """return the list of cubes used by this application. This is a
        public method, not requiring a session id.
        """
        versions = self.get_versions(not self.config.creating)
        cubes = list(versions)
        cubes.remove('cubicweb')
        return cubes

    @cached
    def get_versions(self, checkversions=False):
        """return the a dictionary containing cubes used by this application
        as key with their version as value, including cubicweb version. This is a
        public method, not requiring a session id.
        """
        from logilab.common.changelog import Version
        vcconf = {}
        session = self.internal_session()
        try:
            for pk, version in session.execute(
                'Any K,V WHERE P is CWProperty, P value V, P pkey K, '
                'P pkey ~="system.version.%"', build_descr=False):
                cube = pk.split('.')[-1]
                # XXX cubicweb migration
                if cube in CW_MIGRATION_MAP:
                    cube = CW_MIGRATION_MAP[cube]
                version = Version(version)
                vcconf[cube] = version
                if checkversions:
                    if cube != 'cubicweb':
                        fsversion = self.config.cube_version(cube)
                    else:
                        fsversion = self.config.cubicweb_version()
                    if version < fsversion:
                        msg = ('application has %s version %s but %s '
                               'is installed. Run "cubicweb-ctl upgrade".')
                        raise ExecutionError(msg % (cube, version, fsversion))
        finally:
            session.close()
        return vcconf

    @cached
    def source_defs(self):
        sources = self.config.sources().copy()
        # remove manager information
        sources.pop('admin', None)
        # remove sensitive information
        for uri, sourcedef in sources.iteritems():
            sourcedef = sourcedef.copy()
            self.sources_by_uri[uri].remove_sensitive_information(sourcedef)
            sources[uri] = sourcedef
        return sources

    def properties(self):
        """return a result set containing system wide properties"""
        session = self.internal_session()
        try:
            return session.execute('Any K,V WHERE P is CWProperty,'
                                   'P pkey K, P value V, NOT P for_user U',
                                   build_descr=False)
        finally:
            session.close()

    def register_user(self, login, password, email=None, **kwargs):
        """check a user with the given login exists, if not create it with the
        given password. This method is designed to be used for anonymous
        registration on public web site.
        """
        # XXX should not be called from web interface
        session = self.internal_session()
        # for consistency, keep same error as unique check hook (although not required)
        errmsg = session._('the value "%s" is already used, use another one')
        try:
            if (session.execute('CWUser X WHERE X login %(login)s', {'login': login})
                or session.execute('CWUser X WHERE X use_email C, C address %(login)s',
                                   {'login': login})):
                raise ValidationError(None, {'login': errmsg % login})
            # we have to create the user
            user = self.vreg.etype_class('CWUser')(session, None)
            if isinstance(password, unicode):
                # password should *always* be utf8 encoded
                password = password.encode('UTF8')
            kwargs['login'] = login
            kwargs['upassword'] = password
            user.update(kwargs)
            self.glob_add_entity(session, user)
            session.execute('SET X in_group G WHERE X eid %(x)s, G name "users"',
                            {'x': user.eid})
            if email or '@' in login:
                d = {'login': login, 'email': email or login}
                if session.execute('EmailAddress X WHERE X address %(email)s', d):
                    raise ValidationError(None, {'address': errmsg % d['email']})
                session.execute('INSERT EmailAddress X: X address %(email)s, '
                                'U primary_email X, U use_email X WHERE U login %(login)s', d)
            session.commit()
        finally:
            session.close()
        return True

    def connect(self, login, password, cnxprops=None):
        """open a connection for a given user

        base_url may be needed to send mails
        cnxtype indicate if this is a pyro connection or a in-memory connection

        raise `AuthenticationError` if the authentication failed
        raise `ConnectionError` if we can't open a connection
        """
        # use an internal connection
        session = self.internal_session()
        # try to get a user object
        try:
            user = self.authenticate_user(session, login, password)
        finally:
            session.close()
        session = Session(user, self, cnxprops)
        user.req = user.rset.req = session
        user.clear_related_cache()
        self._sessions[session.id] = session
        self.info('opened %s', session)
        self.hm.call_hooks('session_open', session=session)
        # commit session at this point in case write operation has been done
        # during `session_open` hooks
        session.commit()
        return session.id

    def execute(self, sessionid, rqlstring, args=None, eid_key=None, build_descr=True):
        """execute a RQL query

        * rqlstring should be an unicode string or a plain ascii string
        * args the optional parameters used in the query
        * build_descr is a flag indicating if the description should be
          built on select queries
        """
        session = self._get_session(sessionid, setpool=True)
        try:
            try:
                return self.querier.execute(session, rqlstring, args, eid_key,
                                            build_descr)
            except (Unauthorized, RQLSyntaxError):
                raise
            except ValidationError, ex:
                # need ValidationError normalization here so error may pass
                # through pyro
                if hasattr(ex.entity, 'eid'):
                    ex.entity = ex.entity.eid # error raised by yams
                    args = list(ex.args)
                    args[0] = ex.entity
                    ex.args = tuple(args)
                raise
            except:
                # FIXME: check error to catch internal errors
                self.exception('unexpected error')
                raise
        finally:
            session.reset_pool()

    def describe(self, sessionid, eid):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        session = self._get_session(sessionid, setpool=True)
        try:
            return self.type_and_source_from_eid(eid, session)
        finally:
            session.reset_pool()

    def check_session(self, sessionid):
        """raise `BadSessionId` if the connection is no more valid"""
        self._get_session(sessionid, setpool=False)

    def get_shared_data(self, sessionid, key, default=None, pop=False):
        """return the session's data dictionary"""
        session = self._get_session(sessionid, setpool=False)
        return session.get_shared_data(key, default, pop)

    def set_shared_data(self, sessionid, key, value, querydata=False):
        """set value associated to `key` in shared data

        if `querydata` is true, the value will be added to the repository
        session's query data which are cleared on commit/rollback of the current
        transaction, and won't be available through the connexion, only on the
        repository side.
        """
        session = self._get_session(sessionid, setpool=False)
        session.set_shared_data(key, value, querydata)

    def commit(self, sessionid):
        """commit transaction for the session with the given id"""
        self.debug('begin commit for session %s', sessionid)
        try:
            self._get_session(sessionid).commit()
        except (ValidationError, Unauthorized):
            raise
        except:
            self.exception('unexpected error')
            raise

    def rollback(self, sessionid):
        """commit transaction for the session with the given id"""
        self.debug('begin rollback for session %s', sessionid)
        try:
            self._get_session(sessionid).rollback()
        except:
            self.exception('unexpected error')
            raise

    def close(self, sessionid, checkshuttingdown=True):
        """close the session with the given id"""
        session = self._get_session(sessionid, setpool=True,
                                    checkshuttingdown=checkshuttingdown)
        # operation uncommited before close are rollbacked before hook is called
        session.rollback()
        self.hm.call_hooks('session_close', session=session)
        # commit session at this point in case write operation has been done
        # during `session_close` hooks
        session.commit()
        session.close()
        del self._sessions[sessionid]
        self.info('closed session %s for user %s', sessionid, session.user.login)

    def user_info(self, sessionid, props=None):
        """this method should be used by client to:
        * check session id validity
        * update user information on each user's request (i.e. groups and
          custom properties)
        """
        session = self._get_session(sessionid, setpool=False)
        if props:
            # update session properties
            for prop, value in props.items():
                session.change_property(prop, value)
        user = session.user
        return user.eid, user.login, user.groups, user.properties

    # public (inter-repository) interface #####################################

    def entities_modified_since(self, etypes, mtime):
        """function designed to be called from an external repository which
        is using this one as a rql source for synchronization, and return a
        3-uple containing :
        * the local date
        * list of (etype, eid) of entities of the given types which have been
          modified since the given timestamp (actually entities whose full text
          index content has changed)
        * list of (etype, eid) of entities of the given types which have been
          deleted since the given timestamp
        """
        session = self.internal_session()
        updatetime = datetime.now()
        try:
            modentities, delentities = self.system_source.modified_entities(
                session, etypes, mtime)
            return updatetime, modentities, delentities
        finally:
            session.close()

    # session handling ########################################################

    def close_sessions(self):
        """close every opened sessions"""
        for sessionid in self._sessions.keys():
            try:
                self.close(sessionid, checkshuttingdown=False)
            except:
                self.exception('error while closing session %s' % sessionid)

    def clean_sessions(self):
        """close sessions not used since an amount of time specified in the
        configuration
        """
        mintime = time() - self.config['session-time']
        self.debug('cleaning session unused since %s',
                   strftime('%T', localtime(mintime)))
        nbclosed = 0
        for session in self._sessions.values():
            if session.timestamp < mintime:
                self.close(session.id)
                nbclosed += 1
        return nbclosed

    def internal_session(self, cnxprops=None):
        """return a dbapi like connection/cursor using internal user which
        have every rights on the repository. You'll *have to* commit/rollback
        or close (rollback implicitly) the session once the job's done, else
        you'll leak connections pool up to the time where no more pool is
        available, causing irremediable freeze...
        """
        session = InternalSession(self, cnxprops)
        session.set_pool()
        return session

    def _get_session(self, sessionid, setpool=False, checkshuttingdown=True):
        """return the user associated to the given session identifier"""
        if checkshuttingdown and self._shutting_down:
            raise Exception('Repository is shutting down')
        try:
            session = self._sessions[sessionid]
        except KeyError:
            raise BadConnectionId('No such session %s' % sessionid)
        if setpool:
            session.set_pool()
        return session

    # data sources handling ###################################################
    # * correspondance between eid and (type, source)
    # * correspondance between eid and local id (i.e. specific to a given source)
    # * searchable text indexes

    def type_and_source_from_eid(self, eid, session=None):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        try:
            eid = typed_eid(eid)
        except ValueError:
            raise UnknownEid(eid)
        try:
            return self._type_source_cache[eid]
        except KeyError:
            if session is None:
                session = self.internal_session()
                reset_pool = True
            else:
                reset_pool = False
            try:
                etype, uri, extid = self.system_source.eid_type_source(session,
                                                                       eid)
            finally:
                if reset_pool:
                    session.reset_pool()
        self._type_source_cache[eid] = (etype, uri, extid)
        if uri != 'system':
            self._extid_cache[(extid, uri)] = eid
        return etype, uri, extid

    def clear_caches(self, eids):
        etcache = self._type_source_cache
        extidcache = self._extid_cache
        rqlcache = self.querier._rql_cache
        for eid in eids:
            try:
                etype, uri, extid = etcache.pop(typed_eid(eid)) # may be a string in some cases
                rqlcache.pop('%s X WHERE X eid %s' % (etype, eid), None)
                extidcache.pop((extid, uri), None)
            except KeyError:
                etype = None
            rqlcache.pop('Any X WHERE X eid %s' % eid, None)
            for source in self.sources:
                source.clear_eid_cache(eid, etype)

    def type_from_eid(self, eid, session=None):
        """return the type of the entity with id <eid>"""
        return self.type_and_source_from_eid(eid, session)[0]

    def source_from_eid(self, eid, session=None):
        """return the source for the given entity's eid"""
        return self.sources_by_uri[self.type_and_source_from_eid(eid, session)[1]]

    def eid2extid(self, source, eid, session=None):
        """get local id from an eid"""
        etype, uri, extid = self.type_and_source_from_eid(eid, session)
        if source.uri != uri:
            # eid not from the given source
            raise UnknownEid(eid)
        return extid

    def extid2eid(self, source, extid, etype, session=None, insert=True,
                  recreate=False):
        """get eid from a local id. An eid is attributed if no record is found"""
        cachekey = (extid, source.uri)
        try:
            return self._extid_cache[cachekey]
        except KeyError:
            pass
        reset_pool = False
        if session is None:
            session = self.internal_session()
            reset_pool = True
        eid = self.system_source.extid2eid(session, source, extid)
        if eid is not None:
            self._extid_cache[cachekey] = eid
            self._type_source_cache[eid] = (etype, source.uri, extid)
            if recreate:
                entity = source.before_entity_insertion(session, extid, etype, eid)
                entity._cw_recreating = True
                if source.should_call_hooks:
                    self.hm.call_hooks('before_add_entity', etype, session, entity)
                # XXX add fti op ?
                source.after_entity_insertion(session, extid, entity)
                if source.should_call_hooks:
                    self.hm.call_hooks('after_add_entity', etype, session, entity)
            if reset_pool:
                session.reset_pool()
            return eid
        if not insert:
            return
        # no link between extid and eid, create one using an internal session
        # since the current session user may not have required permissions to
        # do necessary stuff and we don't want to commit user session.
        #
        # Moreover, even if session is already an internal session but is
        # processing a commit, we have to use another one
        if not session.is_internal_session:
            session = self.internal_session()
            reset_pool = True
        try:
            eid = self.system_source.create_eid(session)
            self._extid_cache[cachekey] = eid
            self._type_source_cache[eid] = (etype, source.uri, extid)
            entity = source.before_entity_insertion(session, extid, etype, eid)
            if source.should_call_hooks:
                self.hm.call_hooks('before_add_entity', etype, session, entity)
            # XXX call add_info with complete=False ?
            self.add_info(session, entity, source, extid)
            source.after_entity_insertion(session, extid, entity)
            if source.should_call_hooks:
                self.hm.call_hooks('after_add_entity', etype, session, entity)
            else:
                # minimal meta-data
                session.execute('SET X is E WHERE X eid %(x)s, E name %(name)s',
                                {'x': entity.eid, 'name': entity.id}, 'x')
            session.commit(reset_pool)
            return eid
        except:
            session.rollback(reset_pool)
            raise

    def add_info(self, session, entity, source, extid=None, complete=True):
        """add type and source info for an eid into the system table,
        and index the entity with the full text index
        """
        # begin by inserting eid/type/source/extid into the entities table
        self.system_source.add_info(session, entity, source, extid)
        if complete:
            entity.complete(entity.e_schema.indexable_attributes())
        session.add_query_data('neweids', entity.eid)
        # now we can update the full text index
        if self.do_fti:
            FTIndexEntityOp(session, entity=entity)
        CleanupEidTypeCacheOp(session)

    def delete_info(self, session, eid):
        self._prepare_delete_info(session, eid)
        self._delete_info(session, eid)

    def _prepare_delete_info(self, session, eid):
        """prepare the repository for deletion of an entity:
        * update the fti
        * mark eid as being deleted in session info
        * setup cache update operation
        """
        self.system_source.fti_unindex_entity(session, eid)
        pending = session.query_data('pendingeids', set(), setdefault=True)
        pending.add(eid)
        CleanupEidTypeCacheOp(session)

    def _delete_info(self, session, eid):
        """delete system information on deletion of an entity:
        * delete all relations on this entity
        * transfer record from the entities table to the deleted_entities table
        """
        etype, uri, extid = self.type_and_source_from_eid(eid, session)
        self._clear_eid_relations(session, etype, eid)
        self.system_source.delete_info(session, eid, etype, uri, extid)

    def _clear_eid_relations(self, session, etype, eid):
        """when a entity is deleted, build and execute rql query to delete all
        its relations
        """
        rql = []
        eschema = self.schema.eschema(etype)
        for rschema, targetschemas, x in eschema.relation_definitions():
            rtype = rschema.type
            if rtype == 'identity':
                continue
            var = '%s%s' % (rtype.upper(), x.upper())
            if x == 'subject':
                # don't skip inlined relation so they are regularly
                # deleted and so hooks are correctly called
                rql.append('X %s %s' % (rtype, var))
            else:
                rql.append('%s %s X' % (var, rtype))
        rql = 'DELETE %s WHERE X eid %%(x)s' % ','.join(rql)
        # unsafe_execute since we suppose that if user can delete the entity,
        # he can delete all its relations without security checking
        session.unsafe_execute(rql, {'x': eid}, 'x', build_descr=False)

    def index_entity(self, session, entity):
        """full text index a modified entity"""
        alreadydone = session.query_data('indexedeids', set(), setdefault=True)
        if entity.eid in alreadydone:
            self.info('skipping reindexation of %s, already done', entity.eid)
            return
        alreadydone.add(entity.eid)
        self.system_source.fti_index_entity(session, entity)

    def locate_relation_source(self, session, subject, rtype, object):
        subjsource = self.source_from_eid(subject, session)
        objsource = self.source_from_eid(object, session)
        if not (subjsource is objsource and subjsource.support_relation(rtype, 1)):
            source = self.system_source
            if not source.support_relation(rtype, 1):
                raise RTypeNotSupportedBySources(rtype)
        else:
            source = subjsource
        return source

    def locate_etype_source(self, etype):
        for source in self.sources:
            if source.support_entity(etype, 1):
                return source
        else:
            raise ETypeNotSupportedBySources(etype)

    def glob_add_entity(self, session, entity):
        """add an entity to the repository

        the entity eid should originaly be None and a unique eid is assigned to
        the entity instance
        """
        entity = entity.pre_add_hook()
        eschema = entity.e_schema
        etype = str(eschema)
        source = self.locate_etype_source(etype)
        # attribute an eid to the entity before calling hooks
        entity.set_eid(self.system_source.create_eid(session))
        entity._is_saved = False # entity has an eid but is not yet saved
        relations = []
        # if inlined relations are specified, fill entity's related cache to
        # avoid unnecessary queries
        for attr in entity.keys():
            rschema = eschema.subject_relation(attr)
            if not rschema.is_final(): # inlined relation
                entity.set_related_cache(attr, 'subject',
                                         entity.req.eid_rset(entity[attr]))
                relations.append((attr, entity[attr]))
        if source.should_call_hooks:
            self.hm.call_hooks('before_add_entity', etype, session, entity)
        entity.set_defaults()
        entity.check(creation=True)
        source.add_entity(session, entity)
        if source.uri != 'system':
            extid = source.get_extid(entity)
            self._extid_cache[(str(extid), source.uri)] = entity.eid
        else:
            extid = None
        self.add_info(session, entity, source, extid, complete=False)
        entity._is_saved = True # entity has an eid and is saved
        #print 'added', entity#, entity.items()
        # trigger after_add_entity after after_add_relation
        if source.should_call_hooks:
            self.hm.call_hooks('after_add_entity', etype, session, entity)
            # call hooks for inlined relations
            for attr, value in relations:
                self.hm.call_hooks('before_add_relation', attr, session,
                                    entity.eid, attr, value)
                self.hm.call_hooks('after_add_relation', attr, session,
                                    entity.eid, attr, value)
        return entity.eid

    def glob_update_entity(self, session, entity):
        """replace an entity in the repository
        the type and the eid of an entity must not be changed
        """
        #print 'update', entity
        entity.check()
        etype = str(entity.e_schema)
        eschema = entity.e_schema
        only_inline_rels, need_fti_update = True, False
        relations = []
        for attr in entity.keys():
            if attr == 'eid':
                continue
            rschema = eschema.subject_relation(attr)
            if rschema.is_final():
                if eschema.rproperty(attr, 'fulltextindexed'):
                    need_fti_update = True
                only_inline_rels = False
            else:
                # inlined relation
                previous_value = entity.related(attr)
                if previous_value:
                    previous_value = previous_value[0][0] # got a result set
                    self.hm.call_hooks('before_delete_relation', attr, session,
                                       entity.eid, attr, previous_value)
                entity.set_related_cache(attr, 'subject',
                                         entity.req.eid_rset(entity[attr]))
                relations.append((attr, entity[attr], previous_value))
        source = self.source_from_eid(entity.eid, session)
        if source.should_call_hooks:
            # call hooks for inlined relations
            for attr, value, _ in relations:
                self.hm.call_hooks('before_add_relation', attr, session,
                                    entity.eid, attr, value)
            if not only_inline_rels:
                self.hm.call_hooks('before_update_entity', etype, session,
                                    entity)
        source.update_entity(session, entity)
        if not only_inline_rels:
            if need_fti_update and self.do_fti:
                # reindex the entity only if this query is updating at least
                # one indexable attribute
                FTIndexEntityOp(session, entity=entity)
            if source.should_call_hooks:
                self.hm.call_hooks('after_update_entity', etype, session,
                                    entity)
        if source.should_call_hooks:
            for attr, value, prevvalue in relations:
                if prevvalue:
                    self.hm.call_hooks('after_delete_relation', attr, session,
                                       entity.eid, attr, prevvalue)
                del_existing_rel_if_needed(session, entity.eid, attr, value)
                self.hm.call_hooks('after_add_relation', attr, session,
                                    entity.eid, attr, value)

    def glob_delete_entity(self, session, eid):
        """delete an entity and all related entities from the repository"""
        #print 'deleting', eid
        # call delete_info before hooks
        self._prepare_delete_info(session, eid)
        etype, uri, extid = self.type_and_source_from_eid(eid, session)
        source = self.sources_by_uri[uri]
        if source.should_call_hooks:
            self.hm.call_hooks('before_delete_entity', etype, session, eid)
        self._delete_info(session, eid)
        source.delete_entity(session, etype, eid)
        if source.should_call_hooks:
            self.hm.call_hooks('after_delete_entity', etype, session, eid)
        # don't clear cache here this is done in a hook on commit

    def glob_add_relation(self, session, subject, rtype, object):
        """add a relation to the repository"""
        assert subject is not None
        assert rtype
        assert object is not None
        source = self.locate_relation_source(session, subject, rtype, object)
        #print 'adding', subject, rtype, object, 'to', source
        if source.should_call_hooks:
            del_existing_rel_if_needed(session, subject, rtype, object)
            self.hm.call_hooks('before_add_relation', rtype, session,
                               subject, rtype, object)
        source.add_relation(session, subject, rtype, object)
        if source.should_call_hooks:
            self.hm.call_hooks('after_add_relation', rtype, session,
                               subject, rtype, object)

    def glob_delete_relation(self, session, subject, rtype, object):
        """delete a relation from the repository"""
        assert subject is not None
        assert rtype
        assert object is not None
        source = self.locate_relation_source(session, subject, rtype, object)
        #print 'delete rel', subject, rtype, object
        if source.should_call_hooks:
            self.hm.call_hooks('before_delete_relation', rtype, session,
                               subject, rtype, object)
        source.delete_relation(session, subject, rtype, object)
        if self.schema.rschema(rtype).symetric:
            # on symetric relation, we can't now in which sense it's
            # stored so try to delete both
            source.delete_relation(session, object, rtype, subject)
        if source.should_call_hooks:
            self.hm.call_hooks('after_delete_relation', rtype, session,
                               subject, rtype, object)


    # pyro handling ###########################################################

    def pyro_register(self, host=''):
        """register the repository as a pyro object"""
        from Pyro import core
        port = self.config['pyro-port']
        nshost, nsgroup = self.config['pyro-ns-host'], self.config['pyro-ns-group']
        nsgroup = ':' + nsgroup
        core.initServer(banner=0)
        daemon = core.Daemon(host=host, port=port)
        daemon.useNameServer(self.pyro_nameserver(nshost, nsgroup))
        # use Delegation approach
        impl = core.ObjBase()
        impl.delegateTo(self)
        nsid = self.config['pyro-id'] or self.config.appid
        daemon.connect(impl, '%s.%s' % (nsgroup, nsid))
        msg = 'repository registered as a pyro object using group %s and id %s'
        self.info(msg, nsgroup, nsid)
        self.pyro_registered = True
        return daemon

    def pyro_nameserver(self, host=None, group=None):
        """locate and bind the the name server to the daemon"""
        from Pyro import naming, errors
        # locate the name server
        nameserver = naming.NameServerLocator().getNS(host)
        if group is not None:
            # make sure our namespace group exists
            try:
                nameserver.createGroup(group)
            except errors.NamingError:
                pass
        return nameserver

    # multi-sources planner helpers ###########################################

    @cached
    def rel_type_sources(self, rtype):
        return [source for source in self.sources
                if source.support_relation(rtype)
                or rtype in source.dont_cross_relations]

    @cached
    def can_cross_relation(self, rtype):
        return [source for source in self.sources
                if source.support_relation(rtype)
                and rtype in source.cross_relations]

    @cached
    def is_multi_sources_relation(self, rtype):
        return any(source for source in self.sources
                   if not source is self.system_source
                   and source.support_relation(rtype))


def pyro_unregister(config):
    """unregister the repository from the pyro name server"""
    nshost, nsgroup = config['pyro-ns-host'], config['pyro-ns-group']
    appid = config['pyro-id'] or config.appid
    from Pyro import core, naming, errors
    core.initClient(banner=False)
    try:
        nameserver = naming.NameServerLocator().getNS(nshost)
    except errors.PyroError, ex:
        # name server not responding
        config.error('can\'t locate pyro name server: %s', ex)
        return
    try:
        nameserver.unregister(':%s.%s' % (nsgroup, appid))
        config.info('%s unregistered from pyro name server', appid)
    except errors.NamingError:
        config.warning('%s already unregistered from pyro name server', appid)


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Repository, getLogger('cubicweb.repository'))
