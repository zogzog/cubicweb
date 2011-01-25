# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Defines the central class for the CubicWeb RQL server: the repository.

The repository is an abstraction allowing execution of rql queries against
data sources. Most of the work is actually done in helper classes. The
repository mainly:

* brings these classes all together to provide a single access
  point to a cubicweb instance.
* handles session management
* provides method for pyro registration, to call if pyro is enabled
"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
import threading
import Queue
from itertools import chain
from os.path import join
from datetime import datetime
from time import time, localtime, strftime

from logilab.common.decorators import cached, clear_cache
from logilab.common.compat import any
from logilab.common import flatten

from yams import BadSchemaDefinition
from yams.schema import role_name
from rql import RQLSyntaxError
from rql.utils import rqlvar_maker

from cubicweb import (CW_SOFTWARE_ROOT, CW_MIGRATION_MAP, QueryError,
                      UnknownEid, AuthenticationError, ExecutionError,
                      ETypeNotSupportedBySources, MultiSourcesError,
                      BadConnectionId, Unauthorized, ValidationError,
                      RepositoryError, UniqueTogetherError, typed_eid, onevent)
from cubicweb import cwvreg, schema, server
from cubicweb.server import utils, hook, pool, querier, sources
from cubicweb.server.session import Session, InternalSession, InternalManager, \
     security_enabled
from cubicweb.server.ssplanner import EditedEntity

def prefill_entity_caches(entity, relations):
    session = entity._cw
    # prefill entity relation caches
    for rschema in entity.e_schema.subject_relations():
        rtype = str(rschema)
        if rtype in schema.VIRTUAL_RTYPES:
            continue
        if rschema.final:
            entity.cw_attr_cache.setdefault(rtype, None)
        else:
            entity.cw_set_relation_cache(rtype, 'subject',
                                         session.empty_rset())
    for rschema in entity.e_schema.object_relations():
        rtype = str(rschema)
        if rtype in schema.VIRTUAL_RTYPES:
            continue
        entity.cw_set_relation_cache(rtype, 'object', session.empty_rset())
    # set inlined relation cache before call to after_add_entity
    for attr, value in relations:
        session.update_rel_cache_add(entity.eid, attr, value)
        del_existing_rel_if_needed(session, entity.eid, attr, value)

def del_existing_rel_if_needed(session, eidfrom, rtype, eidto):
    """delete existing relation when adding a new one if card is 1 or ?

    have to be done once the new relation has been inserted to avoid having
    an entity without a relation for some time

    this kind of behaviour has to be done in the repository so we don't have
    hooks order hazardness
    """
    # skip that for internal session or if integrity explicitly disabled
    #
    # XXX we should imo rely on the orm to first fetch existing entity if any
    # then delete it.
    if session.is_internal_session \
           or not session.is_hook_category_activated('activeintegrity'):
        return
    card = session.schema_rproperty(rtype, eidfrom, eidto, 'cardinality')
    # one may be tented to check for neweids but this may cause more than one
    # relation even with '1?'  cardinality if thoses relations are added in the
    # same transaction where the entity is being created. This never occurs from
    # the web interface but may occurs during test or dbapi connection (though
    # not expected for this).  So: don't do it, we pretend to ensure repository
    # consistency.
    #
    # notes:
    # * inlined relations will be implicitly deleted for the subject entity
    # * we don't want read permissions to be applied but we want delete
    #   permission to be checked
    if card[0] in '1?' and not session.repo.schema.rschema(rtype).inlined:
        with security_enabled(session, read=False):
            session.execute('DELETE X %s Y WHERE X eid %%(x)s, '
                            'NOT Y eid %%(y)s' % rtype,
                                {'x': eidfrom, 'y': eidto})
    if card[1] in '1?':
        with security_enabled(session, read=False):
            session.execute('DELETE X %s Y WHERE Y eid %%(y)s, '
                            'NOT X eid %%(x)s' % rtype,
                            {'x': eidfrom, 'y': eidto})


class Repository(object):
    """a repository provides access to a set of persistent storages for
    entities and relations

    XXX protect pyro access
    """

    def __init__(self, config, vreg=None):
        self.config = config
        if vreg is None:
            vreg = cwvreg.CubicWebVRegistry(config)
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
        # shutdown flag
        self.shutting_down = False
        # sources (additional sources info in the system database)
        self.system_source = self.get_source('native', 'system',
                                             config.sources()['system'])
        self.sources = [self.system_source]
        self.sources_by_uri = {'system': self.system_source}
        # querier helper, need to be created after sources initialization
        self.querier = querier.QuerierHelper(self, self.schema)
        # cache eid -> type / source
        self._type_source_cache = {}
        # cache (extid, source uri) -> eid
        self._extid_cache = {}
        # open some connections pools
        if config.open_connections_pools:
            self.open_connections_pools()
        @onevent('after-registry-reload', self)
        def fix_user_classes(self):
            usercls = self.vreg['etypes'].etype_class('CWUser')
            for session in self._sessions.values():
                if not isinstance(session.user, InternalManager):
                    session.user.__class__ = usercls

    def open_connections_pools(self):
        config = self.config
        self._available_pools = Queue.Queue()
        self._available_pools.put_nowait(pool.ConnectionsPool(self.sources))
        if config.quick_start:
            # quick start, usually only to get a minimal repository to get cubes
            # information (eg dump/restore/...)
            config._cubes = ()
            # only load hooks and entity classes in the registry
            config.cube_appobject_path = set(('hooks', 'entities'))
            config.cubicweb_appobject_path = set(('hooks', 'entities'))
            self.set_schema(config.load_schema())
            config['connections-pool-size'] = 1
            # will be reinitialized later from cubes found in the database
            config._cubes = None
        elif config.creating:
            # repository creation
            config.bootstrap_cubes()
            self.set_schema(config.load_schema(), resetvreg=False)
            # need to load the Any and CWUser entity types
            etdirectory = join(CW_SOFTWARE_ROOT, 'entities')
            self.vreg.init_registration([etdirectory])
            for modname in ('__init__', 'authobjs', 'wfobjs'):
                self.vreg.load_file(join(etdirectory, '%s.py' % modname),
                                    'cubicweb.entities.%s' % modname)
            hooksdirectory = join(CW_SOFTWARE_ROOT, 'hooks')
            self.vreg.load_file(join(hooksdirectory, 'metadata.py'),
                                'cubicweb.hooks.metadata')
        elif config.read_instance_schema:
            # normal start: load the instance schema from the database
            self.fill_schema()
        else:
            # test start: use the file system schema (quicker)
            self.warning("set fs instance'schema")
            config.bootstrap_cubes()
            self.set_schema(config.load_schema())
        if not config.creating:
            self.init_sources_from_database()
            if 'CWProperty' in self.schema:
                self.vreg.init_properties(self.properties())
            # call source's init method to complete their initialisation if
            # needed (for instance looking for persistent configuration using an
            # internal session, which is not possible until pools have been
            # initialized)
            for source in self.sources:
                source.init()
        else:
            # call init_creating so that for instance native source can
            # configurate tsearch according to postgres version
            for source in self.sources:
                source.init_creating()
        # close initialization pool and reopen fresh ones for proper
        # initialization now that we know cubes
        self._get_pool().close(True)
        # list of available pools (we can't iterate on Queue instance)
        self.pools = []
        for i in xrange(config['connections-pool-size']):
            self.pools.append(pool.ConnectionsPool(self.sources))
            self._available_pools.put_nowait(self.pools[-1])
        if config.quick_start:
            config.init_cubes(self.get_cubes())
        self.hm = hook.HooksManager(self.vreg)

    # internals ###############################################################

    def init_sources_from_database(self):
        self.sources_by_eid = {}
        if self.config.quick_start \
               or not 'CWSource' in self.schema: # # 3.10 migration
            return
        session = self.internal_session()
        try:
            # FIXME: sources should be ordered (add_entity priority)
            for sourceent in session.execute(
                'Any S, SN, SA, SC WHERE S is CWSource, '
                'S name SN, S type SA, S config SC').entities():
                if sourceent.name == 'system':
                    self.system_source.eid = sourceent.eid
                    self.sources_by_eid[sourceent.eid] = self.system_source
                    continue
                self.add_source(sourceent, add_to_pools=False)
        finally:
            session.close()

    def _clear_planning_caches(self):
        for cache in ('source_defs', 'is_multi_sources_relation',
                      'can_cross_relation', 'rel_type_sources'):
            clear_cache(self, cache)

    def add_source(self, sourceent, add_to_pools=True):
        source = self.get_source(sourceent.type, sourceent.name,
                                 sourceent.host_config)
        source.eid = sourceent.eid
        self.sources_by_eid[sourceent.eid] = source
        self.sources_by_uri[sourceent.name] = source
        if self.config.source_enabled(source):
            self.sources.append(source)
            self.querier.set_planner()
            if add_to_pools:
                for pool in self.pools:
                    pool.add_source(source)
        self._clear_planning_caches()

    def remove_source(self, uri):
        source = self.sources_by_uri.pop(uri)
        del self.sources_by_eid[source.eid]
        if self.config.source_enabled(source):
            self.sources.remove(source)
            self.querier.set_planner()
            for pool in self.pools:
                pool.remove_source(source)
        self._clear_planning_caches()

    def get_source(self, type, uri, source_config):
        # set uri and type in source config so it's available through
        # source_defs()
        source_config['uri'] = uri
        source_config['type'] = type
        return sources.get_source(type, source_config, self)

    def set_schema(self, schema, resetvreg=True, rebuildinfered=True):
        if rebuildinfered:
            schema.rebuild_infered_relations()
        self.info('set schema %s %#x', schema.name, id(schema))
        if resetvreg:
            if self.config._cubes is None:
                self.config.init_cubes(self.get_cubes())
            # trigger full reload of all appobjects
            self.vreg.set_schema(schema)
        else:
            self.vreg._set_schema(schema)
        self.querier.set_schema(schema)
        # don't use self.sources, we may want to give schema even to disabled
        # sources
        for source in self.sources_by_uri.values():
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
        if not (self.config.creating or self.config.repairing
                or self.config.quick_start):
            # call instance level initialisation hooks
            self.hm.call_hooks('server_startup', repo=self)
            # register a task to cleanup expired session
            self.cleanup_session_time = self.config['cleanup-session-time'] or 60 * 60 * 24
            assert self.cleanup_session_time > 0
            cleanup_session_interval = min(60*60, self.cleanup_session_time / 3)
            self.looping_task(cleanup_session_interval, self.clean_sessions)
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
                            'bug in code (too many uncommited/rollbacked '
                            'connections) or too much load on the server (in '
                            'which case you can try to set a bigger '
                            'connections pools size)')

    def _free_pool(self, pool):
        self._available_pools.put_nowait(pool)

    def pinfo(self):
        # XXX: session.pool is accessed from a local storage, would be interesting
        #      to see if there is a pool set in any thread specific data)
        return '%s: %s (%s)' % (self._available_pools.qsize(),
                                ','.join(session.user.login for session in self._sessions.values()
                                         if session.pool),
                                threading.currentThread())
    def shutdown(self):
        """called on server stop event to properly close opened sessions and
        connections
        """
        assert not self.shutting_down, 'already shutting down'
        self.shutting_down = True
        self.system_source.shutdown()
        if isinstance(self._looping_tasks, tuple): # if tasks have been started
            for looptask in self._looping_tasks:
                self.info('canceling task %s...', looptask.name)
                looptask.cancel()
                looptask.join()
                self.info('task %s finished', looptask.name)
        for thread in self._running_threads:
            self.info('waiting thread %s...', thread.getName())
            thread.join()
            self.info('thread %s finished', thread.getName())
        if not (self.config.creating or self.config.repairing
                or self.config.quick_start):
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
            self.info('rql st cache hit/miss: %s/%s (%s%% hits)', hits, misses,
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
                                   'M address %(login)s', {'login': login},
                                   build_descr=False)
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
               not cwuser.cw_adapt_to('IWorkflowable').state in cwuser.AUTHENTICABLE_STATES:
            raise AuthenticationError('user is not in authenticable state')
        return cwuser

    def _build_user(self, session, eid):
        """return a CWUser entity for user with the given eid"""
        cls = self.vreg['etypes'].etype_class('CWUser')
        rql = cls.fetch_rql(session.user, ['X eid %(x)s'])
        rset = session.execute(rql, {'x': eid})
        assert len(rset) == 1, rset
        cwuser = rset.get_entity(0, 0)
        # pylint: disable=W0104
        # prefetch / cache cwuser's groups and properties. This is especially
        # useful for internal sessions to avoid security insertions
        cwuser.groups
        cwuser.properties
        return cwuser

    # public (dbapi) interface ################################################

    def stats(self): # XXX restrict to managers session?
        """Return a dictionary containing some statistics about the repository
        resources usage.

        This is a public method, not requiring a session id.
        """
        results = {}
        querier = self.querier
        source = self.system_source
        for size, maxsize, hits, misses, title in (
            (len(querier._rql_cache), self.config['rql-cache-size'],
            querier.cache_hit, querier.cache_miss, 'rqlt_st'),
            (len(source._cache), self.config['rql-cache-size'],
            source.cache_hit, source.cache_miss, 'sql'),
            ):
            results['%s_cache_size' % title] =  '%s / %s' % (size, maxsize)
            results['%s_cache_hit' % title] =  hits
            results['%s_cache_miss' % title] = misses
            results['%s_cache_hit_percent' % title] = (hits * 100) / (hits + misses)
        results['sql_no_cache'] = self.system_source.no_cache
        results['nb_open_sessions'] = len(self._sessions)
        results['nb_active_threads'] = threading.activeCount()
        results['looping_tasks'] = ', '.join(str(t) for t in self._looping_tasks)
        results['available_pools'] = self._available_pools.qsize()
        results['threads'] = ', '.join(sorted(str(t) for t in threading.enumerate()))
        return results

    def get_schema(self):
        """Return the instance schema.

        This is a public method, not requiring a session id.
        """
        try:
            # necessary to support pickling used by pyro
            self.schema.__hashmode__ = 'pickle'
            return self.schema
        finally:
            self.schema.__hashmode__ = None

    def get_cubes(self):
        """Return the list of cubes used by this instance.

        This is a public method, not requiring a session id.
        """
        versions = self.get_versions(not (self.config.creating
                                          or self.config.repairing
                                          or self.config.quick_start
                                          or self.config.mode == 'test'))
        cubes = list(versions)
        cubes.remove('cubicweb')
        return cubes

    def get_option_value(self, option, foreid=None):
        """Return the value for `option` in the configuration. If `foreid` is
        specified, the actual repository to which this entity belongs is
        derefenced and the option value retrieved from it.

        This is a public method, not requiring a session id.
        """
        # XXX we may want to check we don't give sensible information
        if foreid is None:
            return self.config[option]
        _, sourceuri, extid = self.type_and_source_from_eid(foreid)
        if sourceuri == 'system':
            return self.config[option]
        pool = self._get_pool()
        try:
            return pool.connection(sourceuri).get_option_value(option, extid)
        finally:
            self._free_pool(pool)

    @cached
    def get_versions(self, checkversions=False):
        """Return the a dictionary containing cubes used by this instance
        as key with their version as value, including cubicweb version.

        This is a public method, not requiring a session id.
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
        """Return the a dictionary containing source uris as value and a
        dictionary describing each source as value.

        This is a public method, not requiring a session id.
        """
        sources = {}
        # remove sensitive information
        for uri, source in self.sources_by_uri.iteritems():
            sources[uri] = source.public_config
        return sources

    def properties(self):
        """Return a result set containing system wide properties.

        This is a public method, not requiring a session id.
        """
        session = self.internal_session()
        try:
            # don't use session.execute, we don't want rset.req set
            return self.querier.execute(session, 'Any K,V WHERE P is CWProperty,'
                                        'P pkey K, P value V, NOT P for_user U',
                                        build_descr=False)
        finally:
            session.close()

    # XXX protect this method: anonymous should be allowed and registration
    # plugged
    def register_user(self, login, password, email=None, **kwargs):
        """check a user with the given login exists, if not create it with the
        given password. This method is designed to be used for anonymous
        registration on public web site.
        """
        session = self.internal_session()
        # for consistency, keep same error as unique check hook (although not required)
        errmsg = session._('the value "%s" is already used, use another one')
        try:
            if (session.execute('CWUser X WHERE X login %(login)s', {'login': login},
                                build_descr=False)
                or session.execute('CWUser X WHERE X use_email C, C address %(login)s',
                                   {'login': login}, build_descr=False)):
                qname = role_name('login', 'subject')
                raise ValidationError(None, {qname: errmsg % login})
            # we have to create the user
            user = self.vreg['etypes'].etype_class('CWUser')(session)
            if isinstance(password, unicode):
                # password should *always* be utf8 encoded
                password = password.encode('UTF8')
            kwargs['login'] = login
            kwargs['upassword'] = password
            self.glob_add_entity(session, EditedEntity(user, **kwargs))
            session.execute('SET X in_group G WHERE X eid %(x)s, G name "users"',
                            {'x': user.eid})
            if email or '@' in login:
                d = {'login': login, 'email': email or login}
                if session.execute('EmailAddress X WHERE X address %(email)s', d,
                                   build_descr=False):
                    qname = role_name('address', 'subject')
                    raise ValidationError(None, {qname: errmsg % d['email']})
                session.execute('INSERT EmailAddress X: X address %(email)s, '
                                'U primary_email X, U use_email X '
                                'WHERE U login %(login)s', d, build_descr=False)
            session.commit()
        finally:
            session.close()
        return True

    def find_users(self, fetch_attrs, **query_attrs):
        """yield user attributes for cwusers matching the given query_attrs
        (the result set cannot survive this method call)

        This can be used by low-privileges account (anonymous comes to
        mind).

        `fetch_attrs`: tuple of attributes to be fetched
        `query_attrs`: dict of attr/values to restrict the query
        """
        assert query_attrs
        if not hasattr(self, '_cwuser_attrs'):
            cwuser = self.schema['CWUser']
            self._cwuser_attrs = set(str(rschema)
                                     for rschema, _eschema in cwuser.attribute_definitions()
                                     if not rschema.meta)
        cwuserattrs = self._cwuser_attrs
        for k in chain(fetch_attrs, query_attrs.iterkeys()):
            if k not in cwuserattrs:
                raise Exception('bad input for find_user')
        session = self.internal_session()
        try:
            varmaker = rqlvar_maker()
            vars = [(attr, varmaker.next()) for attr in fetch_attrs]
            rql = 'Any %s WHERE X is CWUser, ' % ','.join(var[1] for var in vars)
            rql += ','.join('X %s %s' % (var[0], var[1]) for var in vars) + ','
            rset = session.execute(rql + ','.join('X %s %%(%s)s' % (attr, attr)
                                                  for attr in query_attrs.iterkeys()),
                                   query_attrs)
            return rset.rows
        finally:
            session.close()

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
        user.cw_clear_relation_cache()
        self._sessions[session.id] = session
        self.info('opened session %s for user %s', session.id, login)
        self.hm.call_hooks('session_open', session)
        # commit session at this point in case write operation has been done
        # during `session_open` hooks
        session.commit()
        return session.id

    def execute(self, sessionid, rqlstring, args=None, build_descr=True,
                txid=None):
        """execute a RQL query

        * rqlstring should be an unicode string or a plain ascii string
        * args the optional parameters used in the query
        * build_descr is a flag indicating if the description should be
          built on select queries
        """
        session = self._get_session(sessionid, setpool=True, txid=txid)
        try:
            try:
                rset = self.querier.execute(session, rqlstring, args,
                                            build_descr)
                # NOTE: the web front will (re)build it when needed
                #       e.g in facets
                #       Zeroed to avoid useless overhead with pyro
                rset._rqlst = None
                return rset
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
                self.exception('unexpected error while executing %s with %s', rqlstring, args)
                raise
        finally:
            session.reset_pool()

    def describe(self, sessionid, eid, txid=None):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        session = self._get_session(sessionid, setpool=True, txid=txid)
        try:
            return self.type_and_source_from_eid(eid, session)
        finally:
            session.reset_pool()

    def check_session(self, sessionid):
        """raise `BadConnectionId` if the connection is no more valid, else
        return its latest activity timestamp.
        """
        return self._get_session(sessionid, setpool=False).timestamp

    def get_shared_data(self, sessionid, key, default=None, pop=False, txdata=False):
        """return value associated to key in the session's data dictionary or
        session's transaction's data if `txdata` is true.

        If pop is True, value will be removed from the dictionnary.

        If key isn't defined in the dictionnary, value specified by the
        `default` argument will be returned.
        """
        session = self._get_session(sessionid, setpool=False)
        return session.get_shared_data(key, default, pop, txdata)

    def set_shared_data(self, sessionid, key, value, txdata=False):
        """set value associated to `key` in shared data

        if `txdata` is true, the value will be added to the repository session's
        transaction's data which are cleared on commit/rollback of the current
        transaction.
        """
        session = self._get_session(sessionid, setpool=False)
        session.set_shared_data(key, value, txdata)

    def commit(self, sessionid, txid=None):
        """commit transaction for the session with the given id"""
        self.debug('begin commit for session %s', sessionid)
        try:
            session = self._get_session(sessionid)
            session.set_tx_data(txid)
            return session.commit()
        except (ValidationError, Unauthorized):
            raise
        except:
            self.exception('unexpected error')
            raise

    def rollback(self, sessionid, txid=None):
        """commit transaction for the session with the given id"""
        self.debug('begin rollback for session %s', sessionid)
        try:
            session = self._get_session(sessionid)
            session.set_tx_data(txid)
            session.rollback()
        except:
            self.exception('unexpected error')
            raise

    def close(self, sessionid, txid=None, checkshuttingdown=True):
        """close the session with the given id"""
        session = self._get_session(sessionid, setpool=True, txid=txid,
                                    checkshuttingdown=checkshuttingdown)
        # operation uncommited before close are rollbacked before hook is called
        session.rollback(reset_pool=False)
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
        for prop, value in props.items():
            session.change_property(prop, value)

    def undoable_transactions(self, sessionid, ueid=None, txid=None,
                              **actionfilters):
        """See :class:`cubicweb.dbapi.Connection.undoable_transactions`"""
        session = self._get_session(sessionid, setpool=True, txid=txid)
        try:
            return self.system_source.undoable_transactions(session, ueid,
                                                            **actionfilters)
        finally:
            session.reset_pool()

    def transaction_info(self, sessionid, txuuid, txid=None):
        """See :class:`cubicweb.dbapi.Connection.transaction_info`"""
        session = self._get_session(sessionid, setpool=True, txid=txid)
        try:
            return self.system_source.tx_info(session, txuuid)
        finally:
            session.reset_pool()

    def transaction_actions(self, sessionid, txuuid, public=True, txid=None):
        """See :class:`cubicweb.dbapi.Connection.transaction_actions`"""
        session = self._get_session(sessionid, setpool=True, txid=txid)
        try:
            return self.system_source.tx_actions(session, txuuid, public)
        finally:
            session.reset_pool()

    def undo_transaction(self, sessionid, txuuid, txid=None):
        """See :class:`cubicweb.dbapi.Connection.undo_transaction`"""
        session = self._get_session(sessionid, setpool=True, txid=txid)
        try:
            return self.system_source.undo_transaction(session, txuuid)
        finally:
            session.reset_pool()

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
        mintime = time() - self.cleanup_session_time
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

    def _get_session(self, sessionid, setpool=False, txid=None,
                     checkshuttingdown=True):
        """return the user associated to the given session identifier"""
        if checkshuttingdown and self.shutting_down:
            raise Exception('Repository is shutting down')
        try:
            session = self._sessions[sessionid]
        except KeyError:
            raise BadConnectionId('No such session %s' % sessionid)
        if setpool:
            session.set_tx_data(txid) # must be done before set_pool
            session.set_pool()
        return session

    # data sources handling ###################################################
    # * correspondance between eid and (type, source)
    # * correspondance between eid and local id (i.e. specific to a given source)

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

    def querier_cache_key(self, session, rql, args, eidkeys):
        cachekey = [rql]
        for key in sorted(eidkeys):
            try:
                etype = self.type_from_eid(args[key], session)
            except KeyError:
                raise QueryError('bad cache key %s (no value)' % key)
            except TypeError:
                raise QueryError('bad cache key %s (value: %r)' % (
                    key, args[key]))
            cachekey.append(etype)
            # ensure eid is correctly typed in args
            args[key] = typed_eid(args[key])
        return tuple(cachekey)

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
            # XXX used with extlite (eg vcsfile), probably not needed anymore
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
            if source.should_call_hooks:
                self.hm.call_hooks('before_add_entity', session, entity=entity)
            # XXX call add_info with complete=False ?
            self.add_info(session, entity, source, extid)
            source.after_entity_insertion(session, extid, entity)
            if source.should_call_hooks:
                self.hm.call_hooks('after_add_entity', session, entity=entity)
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
        hook.CleanupNewEidsCacheOp.get_instance(session).add_data(entity.eid)
        self.system_source.add_info(session, entity, source, extid, complete)

    def delete_info(self, session, entity, sourceuri, extid, scleanup=False):
        """called by external source when some entity known by the system source
        has been deleted in the external source
        """
        # mark eid as being deleted in session info and setup cache update
        # operation
        hook.CleanupDeletedEidsCacheOp.get_instance(session).add_data(entity.eid)
        self._delete_info(session, entity, sourceuri, extid, scleanup)

    def delete_info_multi(self, session, entities, sourceuri, extids, scleanup=False):
        """same as delete_info but accepts a list of entities and
        extids with the same etype and belonging to the same source
        """
        # mark eid as being deleted in session info and setup cache update
        # operation
        op = hook.CleanupDeletedEidsCacheOp.get_instance(session)
        for entity in entities:
            op.add_data(entity.eid)
        self._delete_info_multi(session, entities, sourceuri, extids, scleanup)

    def _delete_info(self, session, entity, sourceuri, extid, scleanup=False):
        """delete system information on deletion of an entity:
        * delete all remaining relations from/to this entity
        * call delete info on the system source which will transfer record from
          the entities table to the deleted_entities table
        """
        pendingrtypes = session.transaction_data.get('pendingrtypes', ())
        # delete remaining relations: if user can delete the entity, he can
        # delete all its relations without security checking
        with security_enabled(session, read=False, write=False):
            eid = entity.eid
            for rschema, _, role in entity.e_schema.relation_definitions():
                rtype = rschema.type
                if rtype in schema.VIRTUAL_RTYPES or rtype in pendingrtypes:
                    continue
                if role == 'subject':
                    # don't skip inlined relation so they are regularly
                    # deleted and so hooks are correctly called
                    rql = 'DELETE X %s Y WHERE X eid %%(x)s' % rtype
                else:
                    rql = 'DELETE Y %s X WHERE X eid %%(x)s' % rtype
                if scleanup:
                    # source cleaning: only delete relations stored locally
                    rql += ', NOT (Y cw_source S, S name %(source)s)'
                try:
                    session.execute(rql, {'x': eid, 'source': sourceuri},
                                    build_descr=False)
                except:
                    self.exception('error while cascading delete for entity %s '
                                   'from %s. RQL: %s', entity, sourceuri, rql)
        self.system_source.delete_info(session, entity, sourceuri, extid)

    def _delete_info_multi(self, session, entities, sourceuri, extids, scleanup=False):
        """same as _delete_info but accepts a list of entities with
        the same etype and belinging to the same source.
        """
        pendingrtypes = session.transaction_data.get('pendingrtypes', ())
        # delete remaining relations: if user can delete the entity, he can
        # delete all its relations without security checking
        assert entities and len(entities) == len(extids)
        with security_enabled(session, read=False, write=False):
            eids = [_e.eid for _e in entities]
            in_eids = ','.join((str(eid) for eid in eids))
            for rschema, _, role in entities[0].e_schema.relation_definitions():
                rtype = rschema.type
                if rtype in schema.VIRTUAL_RTYPES or rtype in pendingrtypes:
                    continue
                if role == 'subject':
                    # don't skip inlined relation so they are regularly
                    # deleted and so hooks are correctly called
                    rql = 'DELETE X %s Y WHERE X eid IN (%s)' % (rtype, in_eids)
                else:
                    rql = 'DELETE Y %s X WHERE X eid IN (%s)' % (rtype, in_eids)
                if scleanup:
                    # source cleaning: only delete relations stored locally
                    rql += ', NOT (Y cw_source S, S name %(source)s)'
                try:
                    session.execute(rql, {'source': sourceuri},
                                    build_descr=False)
                except:
                    self.exception('error while cascading delete for entity %s '
                                   'from %s. RQL: %s', entities, sourceuri, rql)
        self.system_source.delete_info_multi(session, entities, sourceuri, extids)

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

    def init_entity_caches(self, session, entity, source):
        """add entity to session entities cache and repo's extid cache.
        Return entity's ext id if the source isn't the system source.
        """
        session.set_entity_cache(entity)
        suri = source.uri
        if suri == 'system':
            extid = None
        else:
            extid = source.get_extid(entity)
            self._extid_cache[(str(extid), suri)] = entity.eid
        self._type_source_cache[entity.eid] = (entity.__regid__, suri, extid)
        return extid

    def glob_add_entity(self, session, edited):
        """add an entity to the repository

        the entity eid should originaly be None and a unique eid is assigned to
        the entity instance
        """
        entity = edited.entity
        entity._cw_is_saved = False # entity has an eid but is not yet saved
        # init edited_attributes before calling before_add_entity hooks
        entity.cw_edited = edited
        eschema = entity.e_schema
        source = self.locate_etype_source(entity.__regid__)
        # allocate an eid to the entity before calling hooks
        entity.eid = self.system_source.create_eid(session)
        # set caches asap
        extid = self.init_entity_caches(session, entity, source)
        if server.DEBUG & server.DBG_REPO:
            print 'ADD entity', self, entity.__regid__, entity.eid, edited
        relations = []
        if source.should_call_hooks:
            self.hm.call_hooks('before_add_entity', session, entity=entity)
        for attr in edited.iterkeys():
            rschema = eschema.subjrels[attr]
            if not rschema.final: # inlined relation
                relations.append((attr, edited[attr]))
        edited.set_defaults()
        if session.is_hook_category_activated('integrity'):
            edited.check(creation=True)
        prefill_entity_caches(entity, relations)
        try:
            source.add_entity(session, entity)
        except UniqueTogetherError, exc:
            userhdlr = session.vreg['adapters'].select(
                'IUserFriendlyError', session, entity=entity, exc=exc)
            userhdlr.raise_user_exception()
        self.add_info(session, entity, source, extid, complete=False)
        edited.saved = entity._cw_is_saved = True
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

    def glob_update_entity(self, session, edited):
        """replace an entity in the repository
        the type and the eid of an entity must not be changed
        """
        entity = edited.entity
        if server.DEBUG & server.DBG_REPO:
            print 'UPDATE entity', entity.__regid__, entity.eid, \
                  entity.cw_attr_cache, edited
        hm = self.hm
        eschema = entity.e_schema
        session.set_entity_cache(entity)
        orig_edited = getattr(entity, 'cw_edited', None)
        entity.cw_edited = edited
        try:
            only_inline_rels, need_fti_update = True, False
            relations = []
            source = self.source_from_eid(entity.eid, session)
            for attr in list(edited):
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
                        if previous_value == entity.cw_attr_cache[attr]:
                            previous_value = None
                        elif source.should_call_hooks:
                            hm.call_hooks('before_delete_relation', session,
                                          eidfrom=entity.eid, rtype=attr,
                                          eidto=previous_value)
                    relations.append((attr, edited[attr], previous_value))
            if source.should_call_hooks:
                # call hooks for inlined relations
                for attr, value, _t in relations:
                    hm.call_hooks('before_add_relation', session,
                                  eidfrom=entity.eid, rtype=attr, eidto=value)
                if not only_inline_rels:
                    hm.call_hooks('before_update_entity', session, entity=entity)
            if session.is_hook_category_activated('integrity'):
                edited.check()
            try:
                source.update_entity(session, entity)
                edited.saved = True
            except UniqueTogetherError, exc:
                etype, rtypes = exc.args
                problems = {}
                for col in rtypes:
                    problems[col] = session._('violates unique_together constraints (%s)') % (','.join(rtypes))
                raise ValidationError(entity.eid, problems)
            self.system_source.update_info(session, entity, need_fti_update)
            if source.should_call_hooks:
                if not only_inline_rels:
                    hm.call_hooks('after_update_entity', session, entity=entity)
                for attr, value, prevvalue in relations:
                    # if the relation is already cached, update existant cache
                    relcache = entity.cw_relation_cached(attr, 'subject')
                    if prevvalue is not None:
                        hm.call_hooks('after_delete_relation', session,
                                      eidfrom=entity.eid, rtype=attr, eidto=prevvalue)
                        if relcache is not None:
                            session.update_rel_cache_del(entity.eid, attr, prevvalue)
                    del_existing_rel_if_needed(session, entity.eid, attr, value)
                    if relcache is not None:
                        session.update_rel_cache_add(entity.eid, attr, value)
                    else:
                        entity.cw_set_relation_cache(attr, 'subject',
                                                     session.eid_rset(value))
                    hm.call_hooks('after_add_relation', session,
                                  eidfrom=entity.eid, rtype=attr, eidto=value)
        finally:
            if orig_edited is not None:
                entity.cw_edited = orig_edited


    def glob_delete_entities(self, session, eids):
        """delete a list of  entities and all related entities from the repository"""
        data_by_etype_source = {} # values are ([list of eids],
                                  #             [list of extid],
                                  #             [list of entities])
        #
        # WARNING: the way this dictionary is populated is heavily optimized
        # and does not use setdefault on purpose. Unless a new release
        # of the Python interpreter advertises large perf improvements
        # in setdefault, this should not be changed without profiling.

        for eid in eids:
            etype, sourceuri, extid = self.type_and_source_from_eid(eid, session)
            entity = session.entity_from_eid(eid, etype)
            _key = (etype, sourceuri)
            if _key not in data_by_etype_source:
                data_by_etype_source[_key] = ([eid], [extid], [entity])
            else:
                _data = data_by_etype_source[_key]
                _data[0].append(eid)
                _data[1].append(extid)
                _data[2].append(entity)
        for (etype, sourceuri), (eids, extids, entities) in data_by_etype_source.iteritems():
            if server.DEBUG & server.DBG_REPO:
                print 'DELETE entities', etype, eids
            #print 'DELETE entities', etype, len(eids)
            source = self.sources_by_uri[sourceuri]
            if source.should_call_hooks:
                self.hm.call_hooks('before_delete_entity', session, entities=entities)
            self._delete_info_multi(session, entities, sourceuri, extids) # xxx
            source.delete_entities(session, entities)
            if source.should_call_hooks:
                self.hm.call_hooks('after_delete_entity', session, entities=entities)
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
        session.update_rel_cache_add(subject, rtype, object, rschema.symmetric)
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
        session.update_rel_cache_del(subject, rtype, object, rschema.symmetric)
        if rschema.symmetric:
            # on symmetric relation, we can't now in which sense it's
            # stored so try to delete both
            source.delete_relation(session, object, rtype, subject)
        if source.should_call_hooks:
            self.hm.call_hooks('after_delete_relation', session,
                               eidfrom=subject, rtype=rtype, eidto=object)


    # pyro handling ###########################################################

    @property
    @cached
    def pyro_appid(self):
        from logilab.common import pyro_ext as pyro
        config = self.config
        appid = '%s.%s' % pyro.ns_group_and_id(
            config['pyro-instance-id'] or config.appid,
            config['pyro-ns-group'])
        # ensure config['pyro-instance-id'] is a full qualified pyro name
        config['pyro-instance-id'] = appid
        return appid

    def pyro_register(self, host=''):
        """register the repository as a pyro object"""
        from logilab.common import pyro_ext as pyro
        daemon = pyro.register_object(self, self.pyro_appid,
                                      daemonhost=self.config['pyro-host'],
                                      nshost=self.config['pyro-ns-host'])
        self.info('repository registered as a pyro object %s', self.pyro_appid)
        self.pyro_registered = True
        # register a looping task to regularly ensure we're still registered
        # into the pyro name server
        self.looping_task(60*10, self._ensure_pyro_ns)
        return daemon

    def _ensure_pyro_ns(self):
        from logilab.common import pyro_ext as pyro
        pyro.ns_reregister(self.pyro_appid, nshost=self.config['pyro-ns-host'])
        self.info('repository re-registered as a pyro object %s',
                  self.pyro_appid)

    # multi-sources planner helpers ###########################################

    @cached
    def rel_type_sources(self, rtype):
        return tuple([source for source in self.sources
                      if source.support_relation(rtype)
                      or rtype in source.dont_cross_relations])

    @cached
    def can_cross_relation(self, rtype):
        return tuple([source for source in self.sources
                      if source.support_relation(rtype)
                      and rtype in source.cross_relations])

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
