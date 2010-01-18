"""Defines the central class for the CubicWeb RQL server: the repository.

The repository is an abstraction allowing execution of rql queries against
data sources. Most of the work is actually done in helper classes. The
repository mainly:

* brings these classes all together to provide a single access
  point to a cubicweb instance.
* handles session management
* provides method for pyro registration, to call if pyro is enabled


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
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
from logilab.common.compat import any

from yams import BadSchemaDefinition
from rql import RQLSyntaxError

from cubicweb import (CW_SOFTWARE_ROOT, CW_MIGRATION_MAP, CW_EVENT_MANAGER,
                      UnknownEid, AuthenticationError, ExecutionError,
                      ETypeNotSupportedBySources, MultiSourcesError,
                      BadConnectionId, Unauthorized, ValidationError,
                      typed_eid)
from cubicweb import cwvreg, schema, server
from cubicweb.server import utils, hook, pool, querier, sources
from cubicweb.server.session import Session, InternalSession


class CleanupEidTypeCacheOp(hook.SingleLastOperation):
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
        try:
            self.session.repo.clear_caches(
                self.session.transaction_data['pendingeids'])
        except KeyError:
            pass

    def rollback_event(self):
        """the observed connections pool has been rollbacked,
        remove inserted eid from repository type/source cache
        """
        try:
            self.session.repo.clear_caches(
                self.session.transaction_data['neweids'])
        except KeyError:
            pass


class FTIndexEntityOp(hook.LateOperation):
    """operation to delay entity full text indexation to commit

    since fti indexing may trigger discovery of other entities, it should be
    triggered on precommit, not commit, and this should be done after other
    precommit operation which may add relations to the entity
    """

    def precommit_event(self):
        session = self.session
        entity = self.entity
        if entity.eid in session.transaction_data.get('pendingeids', ()):
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
    ensure_card_respected(session.unsafe_execute, session, eidfrom, rtype, eidto)


def ensure_card_respected(execute, session, eidfrom, rtype, eidto):
    card = session.schema_rproperty(rtype, eidfrom, eidto, 'cardinality')
    # one may be tented to check for neweids but this may cause more than one
    # relation even with '1?'  cardinality if thoses relations are added in the
    # same transaction where the entity is being created. This never occurs from
    # the web interface but may occurs during test or dbapi connection (though
    # not expected for this).  So: don't do it, we pretend to ensure repository
    # consistency.
    if card[0] in '1?':
        rschema = session.repo.schema.rschema(rtype)
        if not rschema.inlined:
            execute('DELETE X %s Y WHERE X eid %%(x)s,NOT Y eid %%(y)s' % rtype,
                    {'x': eidfrom, 'y': eidto}, 'x')
    if card[1] in '1?':
        execute('DELETE X %s Y WHERE NOT X eid %%(x)s, Y eid %%(y)s' % rtype,
                {'x': eidfrom, 'y': eidto}, 'y')


class Repository(object):
    """a repository provides access to a set of persistent storages for
    entities and relations

    XXX protect pyro access
    """

    def __init__(self, config, vreg=None, debug=False):
        self.config = config
        if vreg is None:
            vreg = cwvreg.CubicWebVRegistry(config, debug)
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
        self.schema = schema.CubicWebSchema(config.appid)
        self.vreg.schema = self.schema # until actual schema is loaded...
        # querier helper, need to be created after sources initialization
        self.querier = querier.QuerierHelper(self, self.schema)
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
        # open some connections pools
        if config.open_connections_pools:
            self.open_connections_pools()

    def _boostrap_hook_registry(self):
        """called during bootstrap since we need the metadata hooks"""
        hooksdirectory = join(CW_SOFTWARE_ROOT, 'hooks')
        self.vreg.init_registration([hooksdirectory])
        self.vreg.load_file(join(hooksdirectory, 'metadata.py'),
                            'cubicweb.hooks.metadata')

    def open_connections_pools(self):
        config = self.config
        self._available_pools = Queue.Queue()
        self._available_pools.put_nowait(pool.ConnectionsPool(self.sources))
        if config.read_instance_schema:
            # normal start: load the instance schema from the database
            self.fill_schema()
        elif config.bootstrap_schema:
            # usually during repository creation
            self.warning("set fs instance'schema as bootstrap schema")
            config.bootstrap_cubes()
            self.set_schema(config.load_schema(), resetvreg=False)
            # need to load the Any and CWUser entity types
            etdirectory = join(CW_SOFTWARE_ROOT, 'entities')
            self.vreg.init_registration([etdirectory])
            for modname in ('__init__', 'authobjs', 'wfobjs'):
                self.vreg.load_file(join(etdirectory, '%s.py' % modname),
                                'cubicweb.entities.%s' % modname)
            self._boostrap_hook_registry()
        else:
            # test start: use the file system schema (quicker)
            self.warning("set fs instance'schema")
            config.bootstrap_cubes()
            self.set_schema(config.load_schema())
        if not config.creating:
            if 'CWProperty' in self.schema:
                self.vreg.init_properties(self.properties())
            # call source's init method to complete their initialisation if
            # needed (for instance looking for persistent configuration using an
            # internal session, which is not possible until pools have been
            # initialized)
            for source in self.sources:
                source.init()
        else:
            # call init_creating so for instance native source can configurate
            # tsearch according to postgres version
            for source in self.sources:
                source.init_creating()
        # close initialization pool and reopen fresh ones for proper
        # initialization now that we know cubes
        self._get_pool().close(True)
        # list of available pools (we can't iterated on Queue instance)
        self.pools = []
        for i in xrange(config['connections-pool-size']):
            self.pools.append(pool.ConnectionsPool(self.sources))
            self._available_pools.put_nowait(self.pools[-1])
        self._shutting_down = False
        self.hm = self.vreg['hooks']
        if not (config.creating or config.repairing):
            # call instance level initialisation hooks
            self.hm.call_hooks('server_startup', repo=self)
            # register a task to cleanup expired session
            self.looping_task(config['session-time']/3., self.clean_sessions)

    # internals ###############################################################

    def get_source(self, uri, source_config):
        source_config['uri'] = uri
        return sources.get_source(source_config, self.schema, self)

    def set_schema(self, schema, resetvreg=True, rebuildinfered=True):
        if rebuildinfered:
            schema.rebuild_infered_relations()
        self.info('set schema %s %#x', schema.name, id(schema))
        if resetvreg:
            if self.config._cubes is None:
                self.config.init_cubes(self.get_cubes())
            # full reload of all appobjects
            self.vreg.reset()
            self.vreg.set_schema(schema)
        else:
            self.vreg._set_schema(schema)
        self.querier.set_schema(schema)
        for source in self.sources:
            source.set_schema(schema)
        self.schema = schema

    def fill_schema(self):
        """lod schema from the repository"""
        from cubicweb.server.schemaserial import deserialize_schema
        self.info('loading schema from the repository')
        appschema = schema.CubicWebSchema(self.config.appid)
        self.set_schema(self.config.load_bootstrap_schema(), resetvreg=False)
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
        finally:
            session.close()
        self.set_schema(appschema)

    def start_looping_tasks(self):
        assert isinstance(self._looping_tasks, list), 'already started'
        for i, (interval, func, args) in enumerate(self._looping_tasks):
            self._looping_tasks[i] = task = utils.LoopTask(interval, func, args)
            self.info('starting task %s with interval %.2fs', task.name,
                      interval)
            task.start()
        # ensure no tasks will be further added
        self._looping_tasks = tuple(self._looping_tasks)

    def looping_task(self, interval, func, *args):
        """register a function to be called every `interval` seconds.

        looping tasks can only be registered during repository initialization,
        once done this method will fail.
        """
        try:
            self._looping_tasks.append( (interval, func, args) )
        except AttributeError:
            raise RuntimeError("can't add looping task once the repository is started")

    def threaded_task(self, func):
        """start function in a separated thread"""
        t = utils.RepoThread(func, self._running_threads)
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

    def _login_from_email(self, login):
        session = self.internal_session()
        try:
            rset = session.execute('Any L WHERE U login L, U primary_email M, '
                                   'M address %(login)s', {'login': login})
            if rset.rowcount == 1:
                login = rset[0][0]
        finally:
            session.close()
        return login

    def authenticate_user(self, session, login, **kwargs):
        """validate login / password, raise AuthenticationError on failure
        return associated CWUser instance on success
        """
        if self.vreg.config['allow-email-login'] and '@' in login:
            login = self._login_from_email(login)
        for source in self.sources:
            if source.support_entity('CWUser'):
                try:
                    eid = source.authenticate(session, login, **kwargs)
                    break
                except AuthenticationError:
                    continue
        else:
            raise AuthenticationError('authentication failed with all sources')
        cwuser = self._build_user(session, eid)
        if self.config.consider_user_state and \
               not cwuser.state in cwuser.AUTHENTICABLE_STATES:
            raise AuthenticationError('user is not in authenticable state')
        return cwuser

    def _build_user(self, session, eid):
        """return a CWUser entity for user with the given eid"""
        cls = self.vreg['etypes'].etype_class('CWUser')
        rql = cls.fetch_rql(session.user, ['X eid %(x)s'])
        rset = session.execute(rql, {'x': eid}, 'x')
        assert len(rset) == 1, rset
        cwuser = rset.get_entity(0, 0)
        # pylint: disable-msg=W0104
        # prefetch / cache cwuser's groups and properties. This is especially
        # useful for internal sessions to avoid security insertions
        cwuser.groups
        cwuser.properties
        return cwuser

    # public (dbapi) interface ################################################

    def get_schema(self):
        """return the instance schema. This is a public method, not
        requiring a session id
        """
        try:
            # necessary to support pickling used by pyro
            self.schema.__hashmode__ = 'pickle'
            return self.schema
        finally:
            self.schema.__hashmode__ = None

    def get_cubes(self):
        """return the list of cubes used by this instance. This is a
        public method, not requiring a session id.
        """
        versions = self.get_versions(not (self.config.creating
                                          or self.config.repairing))
        cubes = list(versions)
        cubes.remove('cubicweb')
        return cubes

    @cached
    def get_versions(self, checkversions=False):
        """return the a dictionary containing cubes used by this instance
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
                        msg = ('instance has %s version %s but %s '
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
            user = self.vreg['etypes'].etype_class('CWUser')(session, None)
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

    def connect(self, login, **kwargs):
        """open a connection for a given user

        base_url may be needed to send mails
        cnxtype indicate if this is a pyro connection or a in-memory connection

        raise `AuthenticationError` if the authentication failed
        raise `ConnectionError` if we can't open a connection
        """
        # use an internal connection
        session = self.internal_session()
        # try to get a user object
        cnxprops = kwargs.pop('cnxprops', None)
        try:
            user = self.authenticate_user(session, login, **kwargs)
        finally:
            session.close()
        session = Session(user, self, cnxprops)
        user._cw = user.cw_rset.req = session
        user.clear_related_cache()
        self._sessions[session.id] = session
        self.info('opened %s', session)
        self.hm.call_hooks('session_open', session)
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
        self.hm.call_hooks('session_close', session)
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
        if props is not None:
            self.set_session_props(sessionid, props)
        user = session.user
        return user.eid, user.login, user.groups, user.properties

    def set_session_props(self, sessionid, props):
        """this method should be used by client to:
        * check session id validity
        * update user information on each user's request (i.e. groups and
          custom properties)
        """
        session = self._get_session(sessionid, setpool=False)
        # update session properties
        for prop, value in props.items():
            session.change_property(prop, value)

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
                    self.hm.call_hooks('before_add_entity', session, entity=entity)
                # XXX add fti op ?
                source.after_entity_insertion(session, extid, entity)
                if source.should_call_hooks:
                    self.hm.call_hooks('after_add_entity', session, entity=entity)
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
            if not hasattr(entity, 'edited_attributes'):
                entity.edited_attributes = set()
            if source.should_call_hooks:
                entity.edited_attributes = set(entity)
                self.hm.call_hooks('before_add_entity', session, entity=entity)
            # XXX call add_info with complete=False ?
            self.add_info(session, entity, source, extid)
            source.after_entity_insertion(session, extid, entity)
            if source.should_call_hooks:
                self.hm.call_hooks('after_add_entity', session, entity=entity)
            else:
                # minimal meta-data
                session.execute('SET X is E WHERE X eid %(x)s, E name %(name)s',
                                {'x': entity.eid, 'name': entity.__regid__}, 'x')
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
        new = session.transaction_data.setdefault('neweids', set())
        new.add(entity.eid)
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
        pending = session.transaction_data.setdefault('pendingeids', set())
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
        pendingrtypes = session.transaction_data.get('pendingrtypes', ())
        for rschema, targetschemas, x in eschema.relation_definitions():
            rtype = rschema.type
            if rtype in schema.VIRTUAL_RTYPES or rtype in pendingrtypes:
                continue
            var = '%s%s' % (rtype.upper(), x.upper())
            if x == 'subject':
                # don't skip inlined relation so they are regularly
                # deleted and so hooks are correctly called
                selection = 'X %s %s' % (rtype, var)
            else:
                selection = '%s %s X' % (var, rtype)
            rql = 'DELETE %s WHERE X eid %%(x)s' % selection
            # unsafe_execute since we suppose that if user can delete the entity,
            # he can delete all its relations without security checking
            session.unsafe_execute(rql, {'x': eid}, 'x', build_descr=False)

    def index_entity(self, session, entity):
        """full text index a modified entity"""
        alreadydone = session.transaction_data.setdefault('indexedeids', set())
        if entity.eid in alreadydone:
            self.info('skipping reindexation of %s, already done', entity.eid)
            return
        alreadydone.add(entity.eid)
        self.system_source.fti_index_entity(session, entity)

    def locate_relation_source(self, session, subject, rtype, object):
        subjsource = self.source_from_eid(subject, session)
        objsource = self.source_from_eid(object, session)
        if not subjsource is objsource:
            source = self.system_source
            if not (subjsource.may_cross_relation(rtype) 
                    and objsource.may_cross_relation(rtype)):
                raise MultiSourcesError(
                    "relation %s can't be crossed among sources"
                    % rtype)
        elif not subjsource.support_relation(rtype):
            source = self.system_source
        else:
            source = subjsource
        if not source.support_relation(rtype, True):
            raise MultiSourcesError(
                "source %s doesn't support write of %s relation"
                % (source.uri, rtype))
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
        # init edited_attributes before calling before_add_entity hooks
        entity._is_saved = False # entity has an eid but is not yet saved
        entity.edited_attributes = set(entity)
        entity = entity.pre_add_hook()
        eschema = entity.e_schema
        etype = str(eschema)
        source = self.locate_etype_source(etype)
        # attribute an eid to the entity before calling hooks
        entity.set_eid(self.system_source.create_eid(session))
        if server.DEBUG & server.DBG_REPO:
            print 'ADD entity', etype, entity.eid, dict(entity)
        relations = []
        if source.should_call_hooks:
            self.hm.call_hooks('before_add_entity', session, entity=entity)
        # XXX use entity.keys here since edited_attributes is not updated for
        # inline relations
        for attr in entity.keys():
            rschema = eschema.subjrels[attr]
            if not rschema.final: # inlined relation
                relations.append((attr, entity[attr]))
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
        # prefill entity relation caches
        session.set_entity_cache(entity)
        for rschema in eschema.subject_relations():
            rtype = str(rschema)
            if rtype in schema.VIRTUAL_RTYPES:
                continue
            if rschema.final:
                entity.setdefault(rtype, None)
            else:
                entity.set_related_cache(rtype, 'subject', session.empty_rset())
        for rschema in eschema.object_relations():
            rtype = str(rschema)
            if rtype in schema.VIRTUAL_RTYPES:
                continue
            entity.set_related_cache(rtype, 'object', session.empty_rset())
        # set inline relation cache before call to after_add_entity
        for attr, value in relations:
            session.update_rel_cache_add(entity.eid, attr, value)
        # trigger after_add_entity after after_add_relation
        if source.should_call_hooks:
            self.hm.call_hooks('after_add_entity', session, entity=entity)
            # call hooks for inlined relations
            for attr, value in relations:
                self.hm.call_hooks('before_add_relation', session,
                                    eidfrom=entity.eid, rtype=attr, eidto=value)
                self.hm.call_hooks('after_add_relation', session,
                                    eidfrom=entity.eid, rtype=attr, eidto=value)
        return entity.eid

    def glob_update_entity(self, session, entity, edited_attributes):
        """replace an entity in the repository
        the type and the eid of an entity must not be changed
        """
        etype = str(entity.e_schema)
        if server.DEBUG & server.DBG_REPO:
            print 'UPDATE entity', etype, entity.eid, \
                  dict(entity), edited_attributes
        entity.edited_attributes = edited_attributes
        entity.check()
        eschema = entity.e_schema
        session.set_entity_cache(entity)
        only_inline_rels, need_fti_update = True, False
        relations = []
        for attr in edited_attributes:
            if attr == 'eid':
                continue
            rschema = eschema.subjrels[attr]
            if rschema.final:
                if getattr(eschema.rdef(attr), 'fulltextindexed', False):
                    need_fti_update = True
                only_inline_rels = False
            else:
                # inlined relation
                previous_value = entity.related(attr) or None
                if previous_value is not None:
                    previous_value = previous_value[0][0] # got a result set
                    if previous_value == entity[attr]:
                        previous_value = None
                    else:
                        self.hm.call_hooks('before_delete_relation', session,
                                           eidfrom=entity.eid, rtype=attr,
                                           eidto=previous_value)
                relations.append((attr, entity[attr], previous_value))
        source = self.source_from_eid(entity.eid, session)
        if source.should_call_hooks:
            # call hooks for inlined relations
            for attr, value, _ in relations:
                self.hm.call_hooks('before_add_relation', session,
                                    eidfrom=entity.eid, rtype=attr, eidto=value)
            if not only_inline_rels:
                self.hm.call_hooks('before_update_entity', session, entity=entity)
        source.update_entity(session, entity)
        if not only_inline_rels:
            if need_fti_update and self.do_fti:
                # reindex the entity only if this query is updating at least
                # one indexable attribute
                FTIndexEntityOp(session, entity=entity)
            if source.should_call_hooks:
                self.hm.call_hooks('after_update_entity', session, entity=entity)
        if source.should_call_hooks:
            for attr, value, prevvalue in relations:
                # if the relation is already cached, update existant cache
                relcache = entity.relation_cached(attr, 'subject')
                if prevvalue is not None:
                    self.hm.call_hooks('after_delete_relation', session,
                                       eidfrom=entity.eid, rtype=attr, eidto=prevvalue)
                    if relcache is not None:
                        session.update_rel_cache_del(entity.eid, attr, prevvalue)
                del_existing_rel_if_needed(session, entity.eid, attr, value)
                if relcache is not None:
                    session.update_rel_cache_add(entity.eid, attr, value)
                else:
                    entity.set_related_cache(attr, 'subject',
                                             session.eid_rset(value))
                self.hm.call_hooks('after_add_relation', session,
                                    eidfrom=entity.eid, rtype=attr, eidto=value)

    def glob_delete_entity(self, session, eid):
        """delete an entity and all related entities from the repository"""
        # call delete_info before hooks
        self._prepare_delete_info(session, eid)
        etype, uri, extid = self.type_and_source_from_eid(eid, session)
        if server.DEBUG & server.DBG_REPO:
            print 'DELETE entity', etype, eid
            if eid == 937:
                server.DEBUG |= (server.DBG_SQL | server.DBG_RQL | server.DBG_MORE)
        source = self.sources_by_uri[uri]
        if source.should_call_hooks:
            entity = session.entity_from_eid(eid)
            self.hm.call_hooks('before_delete_entity', session, entity=entity)
        self._delete_info(session, eid)
        source.delete_entity(session, etype, eid)
        if source.should_call_hooks:
            self.hm.call_hooks('after_delete_entity', session, entity=entity)
        # don't clear cache here this is done in a hook on commit

    def glob_add_relation(self, session, subject, rtype, object):
        """add a relation to the repository"""
        if server.DEBUG & server.DBG_REPO:
            print 'ADD relation', subject, rtype, object
        source = self.locate_relation_source(session, subject, rtype, object)
        if source.should_call_hooks:
            del_existing_rel_if_needed(session, subject, rtype, object)
            self.hm.call_hooks('before_add_relation', session,
                               eidfrom=subject, rtype=rtype, eidto=object)
        source.add_relation(session, subject, rtype, object)
        rschema = self.schema.rschema(rtype)
        session.update_rel_cache_add(subject, rtype, object, rschema.symetric)
        if source.should_call_hooks:
            self.hm.call_hooks('after_add_relation', session,
                               eidfrom=subject, rtype=rtype, eidto=object)

    def glob_delete_relation(self, session, subject, rtype, object):
        """delete a relation from the repository"""
        if server.DEBUG & server.DBG_REPO:
            print 'DELETE relation', subject, rtype, object
        source = self.locate_relation_source(session, subject, rtype, object)
        if source.should_call_hooks:
            self.hm.call_hooks('before_delete_relation', session,
                               eidfrom=subject, rtype=rtype, eidto=object)
        source.delete_relation(session, subject, rtype, object)
        rschema = self.schema.rschema(rtype)
        session.update_rel_cache_del(subject, rtype, object, rschema.symetric)
        if rschema.symetric:
            # on symetric relation, we can't now in which sense it's
            # stored so try to delete both
            source.delete_relation(session, object, rtype, subject)
        if source.should_call_hooks:
            self.hm.call_hooks('after_delete_relation', session,
                               eidfrom=subject, rtype=rtype, eidto=object)


    # pyro handling ###########################################################

    def pyro_register(self, host=''):
        """register the repository as a pyro object"""
        import tempfile
        from logilab.common.pyro_ext import register_object, config
        config.PYRO_STORAGE = tempfile.gettempdir() # XXX until lgc > 0.45.1 is out
        appid = self.config['pyro-instance-id'] or self.config.appid
        daemon = register_object(self, appid, self.config['pyro-ns-group'],
                                 self.config['pyro-host'],
                                 self.config['pyro-ns-host'])
        msg = 'repository registered as a pyro object using group %s and id %s'
        self.info(msg, self.config['pyro-ns-group'], appid)
        self.pyro_registered = True
        return daemon

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
    from logilab.common.pyro_ext import ns_unregister
    appid = config['pyro-instance-id'] or config.appid
    ns_unregister(appid, config['pyro-ns-group'], config['pyro-ns-host'])


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Repository, getLogger('cubicweb.repository'))
