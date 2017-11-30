# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""

from __future__ import print_function

from warnings import warn
from itertools import chain
from contextlib import contextmanager
from logging import getLogger

from six.moves import range, queue

from logilab.common.decorators import cached, clear_cache
from logilab.common.deprecation import deprecated

from yams import BadSchemaDefinition
from rql.utils import rqlvar_maker

from cubicweb import (CW_MIGRATION_MAP,
                      UnknownEid, AuthenticationError, ExecutionError,
                      UniqueTogetherError, ViolatedConstraint)
from cubicweb import set_log_methods
from cubicweb import cwvreg, schema, server
from cubicweb.server import utils, hook, querier, sources
from cubicweb.server.session import InternalManager, Connection


NO_CACHE_RELATIONS = set([
    ('owned_by', 'object'),
    ('created_by', 'object'),
    ('cw_source', 'object'),
])


def prefill_entity_caches(entity):
    cnx = entity._cw
    # prefill entity relation caches
    for rschema in entity.e_schema.subject_relations():
        rtype = str(rschema)
        if rtype in schema.VIRTUAL_RTYPES or (rtype, 'subject') in NO_CACHE_RELATIONS:
            continue
        if rschema.final:
            entity.cw_attr_cache.setdefault(rtype, None)
        else:
            entity.cw_set_relation_cache(rtype, 'subject',
                                         cnx.empty_rset())
    for rschema in entity.e_schema.object_relations():
        rtype = str(rschema)
        if rtype in schema.VIRTUAL_RTYPES or (rtype, 'object') in NO_CACHE_RELATIONS:
            continue
        entity.cw_set_relation_cache(rtype, 'object', cnx.empty_rset())


def del_existing_rel_if_needed(cnx, eidfrom, rtype, eidto):
    """delete existing relation when adding a new one if card is 1 or ?

    have to be done once the new relation has been inserted to avoid having
    an entity without a relation for some time

    this kind of behaviour has to be done in the repository so we don't have
    hooks order hazardness
    """
    # skip that if integrity explicitly disabled
    if not cnx.is_hook_category_activated('activeintegrity'):
        return
    rdef = cnx.rtype_eids_rdef(rtype, eidfrom, eidto)
    card = rdef.cardinality
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
    if card[0] in '1?':
        with cnx.security_enabled(read=False):
            cnx.execute('DELETE X %s Y WHERE X eid %%(x)s, '
                        'NOT Y eid %%(y)s' % rtype,
                        {'x': eidfrom, 'y': eidto})
    if card[1] in '1?':
        with cnx.security_enabled(read=False):
            cnx.execute('DELETE X %s Y WHERE Y eid %%(y)s, '
                        'NOT X eid %%(x)s' % rtype,
                        {'x': eidfrom, 'y': eidto})


def preprocess_inlined_relations(cnx, entity):
    """when an entity is added, check if it has some inlined relation which
    requires to be extrated for proper call hooks
    """
    relations = []
    activeintegrity = cnx.is_hook_category_activated('activeintegrity')
    eschema = entity.e_schema
    for attr in entity.cw_edited:
        rschema = eschema.subjrels[attr]
        if not rschema.final:  # inlined relation
            value = entity.cw_edited[attr]
            relations.append((attr, value))
            cnx.update_rel_cache_add(entity.eid, attr, value)
            rdef = cnx.rtype_eids_rdef(attr, entity.eid, value)
            if rdef.cardinality[1] in '1?' and activeintegrity:
                with cnx.security_enabled(read=False):
                    cnx.execute('DELETE X %s Y WHERE Y eid %%(y)s' % attr,
                                {'x': entity.eid, 'y': value})
    return relations


class NullEventBus(object):
    def publish(self, msg):
        pass

    def add_subscription(self, topic, callback):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class _CnxSetPool(object):

    def __init__(self, source, size):
        self._cnxsets = []
        if size is not None:
            self._queue = queue.Queue()
            for i in range(size):
                cnxset = source.wrapped_connection()
                self._cnxsets.append(cnxset)
                self._queue.put_nowait(cnxset)
        else:
            self._queue = None
            self._source = source
        super(_CnxSetPool, self).__init__()

    def qsize(self):
        q = self._queue
        if q is None:
            return None
        return q.qsize()

    def get(self):
        q = self._queue
        if q is None:
            return self._source.wrapped_connection()
        try:
            return self._queue.get(True, timeout=5)
        except queue.Empty:
            raise Exception('no connections set available after 5 secs, probably either a '
                            'bug in code (too many uncommited/rolled back '
                            'connections) or too much load on the server (in '
                            'which case you can try to set a bigger '
                            'connections pool size)')

    def release(self, cnxset):
        q = self._queue
        if q is None:
            cnxset.close(True)
        else:
            self._queue.put_nowait(cnxset)

    def __iter__(self):
        for cnxset in self._cnxsets:
            yield cnxset

    def close(self):
        q = self._queue
        if q is not None:
            while not q.empty():
                cnxset = q.get_nowait()
                try:
                    cnxset.close(True)
                except Exception:
                    self.exception('error while closing %s' % cnxset)


class Repository(object):
    """a repository provides access to a set of persistent storages for
    entities and relations
    """

    def __init__(self, config, scheduler=None, vreg=None):
        self.config = config
        if vreg is None:
            vreg = cwvreg.CWRegistryStore(config)
        self.vreg = vreg
        self._scheduler = scheduler

        self.app_instances_bus = NullEventBus()

        # list of functions to be called at regular interval
        # list of running threads
        self._running_threads = []
        # initial schema, should be build or replaced latter
        self.schema = schema.CubicWebSchema(config.appid)
        self.vreg.schema = self.schema  # until actual schema is loaded...
        # shutdown flag
        self.shutting_down = None
        # sources (additional sources info in the system database)
        self.system_source = self.get_source('native', 'system',
                                             config.system_source_config.copy())
        # querier helper, need to be created after sources initialization
        self.querier = querier.QuerierHelper(self, self.schema)
        # cache eid -> type
        self._type_cache = {}
        # the hooks manager
        self.hm = hook.HooksManager(self.vreg)

    def bootstrap(self):
        self.info('starting repository from %s', self.config.apphome)
        self.shutting_down = False
        config = self.config
        # copy pool size here since config.init_cube() and config.load_schema()
        # reload configuration from file and could reset a manually set pool
        # size.
        if config['connections-pooler-enabled']:
            pool_size, min_pool_size = config['connections-pool-size'], 1
        else:
            pool_size = min_pool_size = None
        # 0. init a cnxset that will be used to fetch bootstrap information from
        #    the database
        self.cnxsets = _CnxSetPool(self.system_source, min_pool_size)
        # 1. set used cubes
        if config.creating or not config.read_instance_schema:
            config.bootstrap_cubes()
        else:
            self.set_schema(self.config.load_bootstrap_schema(), resetvreg=False)
            config.init_cubes(self.get_cubes())
        # 2. load schema
        if config.quick_start:
            # quick start: only to get a minimal repository to get cubes
            # information (eg dump/restore/...)
            #
            # restrict appobject_path to only load hooks and entity classes in
            # the registry
            config.cube_appobject_path = set(('hooks', 'entities'))
            config.cubicweb_appobject_path = set(('hooks', 'entities'))
            # limit connections pool size
            pool_size = min_pool_size
        if config.quick_start or config.creating or not config.read_instance_schema:
            # load schema from the file system
            if not config.creating:
                self.info("set fs instance's schema")
            self.set_schema(config.load_schema(expand_cubes=True))
            if not config.creating:
                # set eids on entities schema
                with self.internal_cnx() as cnx:
                    for etype, eid in cnx.execute('Any XN,X WHERE X is CWEType, X name XN'):
                        try:
                            self.schema.eschema(etype).eid = eid
                        except KeyError:
                            # etype in the database doesn't exist in the fs schema, this may occur
                            # during dev and we shouldn't crash
                            self.warning('No %s entity type in the file system schema', etype)
        else:
            # normal start: load the instance schema from the database
            self.info('loading schema from the repository')
            self.set_schema(self.deserialize_schema())
        # 3. initialize data sources
        if config.creating:
            # call init_creating so that for instance native source can
            # configurate tsearch according to postgres version
            self.system_source.init_creating()
        else:
            self._init_system_source()
            if 'CWProperty' in self.schema:
                self.vreg.init_properties(self.properties())
        # 4. close initialization connection set and reopen fresh ones for
        #    proper initialization
        self.cnxsets.close()
        self.cnxsets = _CnxSetPool(self.system_source, pool_size)
        # 5. call instance level initialisation hooks
        self.hm.call_hooks('server_startup', repo=self)

    def source_by_uri(self, uri):
        with self.internal_cnx() as cnx:
            rset = cnx.find('CWSource', name=uri)
            if not rset:
                raise ValueError('no source with uri %s found' % uri)
            return self._source_from_cwsource(rset.one())

    def source_by_eid(self, eid):
        with self.internal_cnx() as cnx:
            rset = cnx.find('CWSource', eid=eid)
            if not rset:
                raise ValueError('no source with eid %d found' % eid)
            return self._source_from_cwsource(rset.one())

    @property
    def sources_by_uri(self):
        mapping = {'system': self.system_source}
        mapping.update((sourceent.name, source)
                       for sourceent, source in self._sources())
        return mapping

    @property
    @deprecated("[3.25] use source_by_eid(<eid>)")
    def sources_by_eid(self):
        mapping = {self.system_source.eid: self.system_source}
        mapping.update((sourceent.eid, source)
                       for sourceent, source in self._sources())
        return mapping

    def _sources(self):
        if self.config.quick_start:
            return
        with self.internal_cnx() as cnx:
            for sourceent in cnx.execute(
                    'Any S, SN, SA, SC WHERE S is_instance_of CWSource, '
                    'S name SN, S type SA, S config SC, S name != "system"').entities():
                source = self._source_from_cwsource(sourceent)
                yield sourceent, source
        self._clear_source_defs_caches()

    def _source_from_cwsource(self, sourceent):
        source = self.get_source(sourceent.type, sourceent.name,
                                 sourceent.host_config, sourceent.eid)
        if self.config.source_enabled(source):
            # call source's init method to complete their initialisation if
            # needed (for instance looking for persistent configuration using an
            # internal session, which is not possible until connections sets have been
            # initialized)
            source.init(sourceent)
        return source

    # internals ###############################################################

    def _init_system_source(self):
        if self.config.quick_start:
            self.system_source.init_creating()
            return
        with self.internal_cnx() as cnx:
            sourceent = cnx.execute(
                'Any S, SA, SC WHERE S is_instance_of CWSource,'
                ' S name "system", S type SA, S config SC'
            ).one()
            self.system_source.eid = sourceent.eid
            self.system_source.init(sourceent)

    def get_source(self, type, uri, source_config, eid=None):
        # set uri and type in source config so it's available through
        # source_defs()
        source_config['uri'] = uri
        source_config['type'] = type
        return sources.get_source(type, source_config, self, eid)

    def set_schema(self, schema, resetvreg=True):
        self.info('set schema %s %#x', schema.name, id(schema))
        if resetvreg:
            # trigger full reload of all appobjects
            self.vreg.set_schema(schema)
        else:
            self.vreg._set_schema(schema)
        self.querier.set_schema(schema)
        self.system_source.set_schema(schema)
        self.schema = schema

    def deserialize_schema(self):
        """load schema from the database"""
        from cubicweb.server.schemaserial import deserialize_schema
        appschema = schema.CubicWebSchema(self.config.appid)
        self.debug('deserializing db schema into %s %#x', appschema.name, id(appschema))
        with self.internal_cnx() as cnx:
            try:
                deserialize_schema(appschema, cnx)
            except BadSchemaDefinition:
                raise
            except Exception as ex:
                import traceback
                traceback.print_exc()
                raise Exception('Is the database initialised ? (cause: %s)' % ex)
        return appschema

    def has_scheduler(self):
        """Return True if the repository has a scheduler attached and is able
        to register looping tasks.
        """
        return self._scheduler is not None

    def run_scheduler(self):
        """Start repository scheduler after preparing the repository for that.

        * trigger server startup hook,
        * start the scheduler *and block*.

        XXX Other startup related stuffs are done elsewhere. In Repository
        XXX __init__ or in external codes (various server managers).
        """
        assert self.has_scheduler(), \
            "This Repository is not intended to be used as a server"
        self.info(
            'starting repository scheduler with tasks: %s',
            ', '.join(e.action.__name__ for e in self._scheduler.queue))
        self._scheduler.run()

    def looping_task(self, interval, func, *args):
        """register a function to be called every `interval` seconds.

        looping tasks can only be registered during repository initialization,
        once done this method will fail.
        """
        if self.config.repairing:
            return
        if not self.has_scheduler():
            self.warning(
                'looping task %s will not run in this process where repository '
                'has no scheduler; use "cubicweb-ctl scheduler <appid>" to '
                'have it running', func)
            return
        event = utils.schedule_periodic_task(
            self._scheduler, interval, func, *args)
        self.info('scheduled periodic task %s (interval: %.2fs)',
                  event.action.__name__, interval)

    def threaded_task(self, func):
        """start function in a separated thread"""
        utils.RepoThread(func, self._running_threads).start()

    def shutdown(self):
        """called on server stop event to properly close opened sessions and
        connections
        """
        assert not self.shutting_down, 'already shutting down'
        if not (self.config.creating or self.config.repairing
                or self.config.quick_start):
            # then, the system source is still available
            self.hm.call_hooks('before_server_shutdown', repo=self)
        self.shutting_down = True
        self.info('shutting down repository')
        self.system_source.shutdown()
        if not (self.config.creating or self.config.repairing
                or self.config.quick_start):
            self.hm.call_hooks('server_shutdown', repo=self)
        for thread in self._running_threads:
            self.info('waiting thread %s...', thread.getName())
            thread.join()
            self.info('thread %s finished', thread.getName())
        self.cnxsets.close()
        hits, misses = self.querier.rql_cache.cache_hit, self.querier.rql_cache.cache_miss
        try:
            self.info('rql st cache hit/miss: %s/%s (%s%% hits)', hits, misses,
                      (hits * 100) / (hits + misses))
            hits, misses = self.system_source.cache_hit, self.system_source.cache_miss
            self.info('sql cache hit/miss: %s/%s (%s%% hits)', hits, misses,
                      (hits * 100) / (hits + misses))
            nocache = self.system_source.no_cache
            self.info('sql cache usage: %s/%s (%s%%)', hits + misses, nocache,
                      ((hits + misses) * 100) / (hits + misses + nocache))
        except ZeroDivisionError:
            pass

    def check_auth_info(self, cnx, login, authinfo):
        """validate authentication, raise AuthenticationError on failure, return
        associated CWUser's eid on success.
        """
        # iter on sources_by_uri then check enabled source since sources doesn't
        # contain copy based sources
        for source in self.sources_by_uri.values():
            if self.config.source_enabled(source):
                try:
                    return source.authenticate(cnx, login, **authinfo)
                except (NotImplementedError, AuthenticationError):
                    continue
        else:
            raise AuthenticationError('authentication failed with all sources')

    def authenticate_user(self, cnx, login, **authinfo):
        """validate login / password, raise AuthenticationError on failure
        return associated CWUser instance on success
        """
        eid = self.check_auth_info(cnx, login, authinfo)
        cwuser = self._build_user(cnx, eid)
        if self.config.consider_user_state and \
           not cwuser.cw_adapt_to('IWorkflowable').state in cwuser.AUTHENTICABLE_STATES:
            raise AuthenticationError('user is not in authenticable state')
        return cwuser

    def _build_user(self, cnx, eid):
        """return a CWUser entity for user with the given eid"""
        cls = self.vreg['etypes'].etype_class('CWUser')
        st = cls.fetch_rqlst(cnx.user, ordermethod=None)
        st.add_eid_restriction(st.get_variable('X'), 'x', 'Substitute')
        rset = cnx.execute(st.as_string(), {'x': eid})
        assert len(rset) == 1, rset
        return rset.get_entity(0, 0)

    # public (dbapi) interface ################################################

    @deprecated("[3.19] use _cw.call_service('repo_stats')")
    def stats(self):  # XXX restrict to managers session?
        """Return a dictionary containing some statistics about the repository
        resources usage.

        This is a public method, not requiring a session id.

        This method is deprecated in favor of using _cw.call_service('repo_stats')
        """
        with self.internal_cnx() as cnx:
            return cnx.call_service('repo_stats')

    @deprecated("[3.19] use _cw.call_service('repo_gc_stats')")
    def gc_stats(self, nmax=20):
        """Return a dictionary containing some statistics about the repository
        memory usage.

        This is a public method, not requiring a session id.

        nmax is the max number of (most) referenced object returned as
        the 'referenced' result
        """
        with self.internal_cnx() as cnx:
            return cnx.call_service('repo_gc_stats', nmax=nmax)

    def get_schema(self):
        """Return the instance schema.

        This is a public method, not requiring a session id.
        """
        return self.schema

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
        """Return the value for `option` in the configuration.

        This is a public method, not requiring a session id.

        `foreid` argument is deprecated and now useless (as of 3.19).
        """
        if foreid is not None:
            warn('[3.19] foreid argument is deprecated', DeprecationWarning,
                 stacklevel=2)
        # XXX we may want to check we don't give sensible information
        return self.config[option]

    @cached
    def get_versions(self, checkversions=False):
        """Return the a dictionary containing cubes used by this instance
        as key with their version as value, including cubicweb version.

        This is a public method, not requiring a session id.
        """
        from logilab.common.changelog import Version
        vcconf = {}
        with self.internal_cnx() as cnx:
            for pk, version in cnx.execute(
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
        return vcconf

    @cached
    def source_defs(self):
        """Return the a dictionary containing source uris as value and a
        dictionary describing each source as value.

        This is a public method, not requiring a session id.
        """
        sources = {}
        # remove sensitive information
        for uri, source in self.sources_by_uri.items():
            sources[uri] = source.public_config
        return sources

    def _clear_source_defs_caches(self):
        clear_cache(self, 'source_defs')

    def properties(self):
        """Return a result set containing system wide properties.

        This is a public method, not requiring a session id.
        """
        with self.internal_cnx() as cnx:
            # don't use cnx.execute, we don't want rset.req set
            return self.querier.execute(cnx, 'Any K,V WHERE P is CWProperty,'
                                        'P pkey K, P value V, NOT P for_user U',
                                        build_descr=False)

    @deprecated("[3.19] Use session.call_service('register_user') instead'")
    def register_user(self, login, password, email=None, **kwargs):
        """check a user with the given login exists, if not create it with the
        given password. This method is designed to be used for anonymous
        registration on public web site.
        """
        with self.internal_cnx() as cnx:
            cnx.call_service('register_user', login=login, password=password,
                             email=email, **kwargs)
            cnx.commit()

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
        for k in chain(fetch_attrs, query_attrs):
            if k not in cwuserattrs:
                raise Exception('bad input for find_user')
        with self.internal_cnx() as cnx:
            varmaker = rqlvar_maker()
            vars = [(attr, next(varmaker)) for attr in fetch_attrs]
            rql = 'Any %s WHERE X is CWUser, ' % ','.join(var[1] for var in vars)
            rql += ','.join('X %s %s' % (var[0], var[1]) for var in vars) + ','
            rset = cnx.execute(rql + ','.join('X %s %%(%s)s' % (attr, attr)
                                              for attr in query_attrs),
                               query_attrs)
            return rset.rows

    # session handling ########################################################

    @contextmanager
    def internal_cnx(self):
        """Context manager returning a Connection using internal user which have
        every access rights on the repository.

        Internal connections have all hooks beside security enabled.
        """
        with Connection(self, InternalManager()) as cnx:
            cnx.user._cw = cnx  # XXX remove when "vreg = user._cw.vreg" hack in entity.py is gone
            with cnx.security_enabled(read=False, write=False):
                yield cnx

    # data sources handling ###################################################
    # * correspondance between eid and type
    # * correspondance between eid and local id (i.e. specific to a given source)

    def clear_caches(self, eids=None):
        if eids is None:
            self._type_cache = {}
            etypes = None
        else:
            etypes = []
            etcache = self._type_cache
            for eid in eids:
                try:
                    etype = etcache.pop(int(eid))  # may be a string in some cases
                except KeyError:
                    etype = None
                etypes.append(etype)
        self.querier.clear_caches(eids, etypes)
        self.system_source.clear_caches(eids, etypes)

    def type_from_eid(self, eid, cnx):
        """Return the type of the entity with id `eid`"""
        try:
            eid = int(eid)
        except ValueError:
            raise UnknownEid(eid)
        try:
            return self._type_cache[eid]
        except KeyError:
            etype = self.system_source.eid_type(cnx, eid)
            self._type_cache[eid] = etype
            return etype

    def add_info(self, cnx, entity, source):
        """add type and source info for an eid into the system table,
        and index the entity with the full text index
        """
        # begin by inserting eid/type/source into the entities table
        hook.CleanupNewEidsCacheOp.get_instance(cnx).add_data(entity.eid)
        self.system_source.add_info(cnx, entity, source)

    def _delete_cascade_multi(self, cnx, entities):
        """same as _delete_cascade but accepts a list of entities with
        the same etype and belonging to the same source.
        """
        pendingrtypes = cnx.transaction_data.get('pendingrtypes', ())
        # delete remaining relations: if user can delete the entity, he can
        # delete all its relations without security checking
        with cnx.security_enabled(read=False, write=False):
            in_eids = ','.join([str(_e.eid) for _e in entities])
            with cnx.running_hooks_ops():
                for rschema, _, role in entities[0].e_schema.relation_definitions():
                    if rschema.rule:
                        continue  # computed relation
                    rtype = rschema.type
                    if rtype in schema.VIRTUAL_RTYPES or rtype in pendingrtypes:
                        continue
                    if role == 'subject':
                        # don't skip inlined relation so they are regularly
                        # deleted and so hooks are correctly called
                        rql = 'DELETE X %s Y WHERE X eid IN (%s)' % (rtype, in_eids)
                    else:
                        rql = 'DELETE Y %s X WHERE X eid IN (%s)' % (rtype, in_eids)
                    cnx.execute(rql, build_descr=False)

    def init_entity_caches(self, cnx, entity, source):
        """Add entity to connection entities cache and repo's cache."""
        cnx.set_entity_cache(entity)
        self._type_cache[entity.eid] = entity.cw_etype

    def glob_add_entity(self, cnx, edited):
        """add an entity to the repository

        the entity eid should originally be None and a unique eid is assigned to
        the entity instance
        """
        entity = edited.entity
        entity._cw_is_saved = False  # entity has an eid but is not yet saved
        # init edited_attributes before calling before_add_entity hooks
        entity.cw_edited = edited
        source = self.system_source
        # allocate an eid to the entity before calling hooks
        entity.eid = self.system_source.create_eid(cnx)
        # set caches asap
        self.init_entity_caches(cnx, entity, source)
        if server.DEBUG & server.DBG_REPO:
            print('ADD entity', self, entity.cw_etype, entity.eid, edited)
        prefill_entity_caches(entity)
        self.hm.call_hooks('before_add_entity', cnx, entity=entity)
        relations = preprocess_inlined_relations(cnx, entity)
        edited.set_defaults()
        if cnx.is_hook_category_activated('integrity'):
            edited.check(creation=True)
        self.add_info(cnx, entity, source)
        try:
            source.add_entity(cnx, entity)
        except (UniqueTogetherError, ViolatedConstraint) as exc:
            userhdlr = cnx.vreg['adapters'].select(
                'IUserFriendlyError', cnx, entity=entity, exc=exc)
            userhdlr.raise_user_exception()
        edited.saved = entity._cw_is_saved = True
        # trigger after_add_entity after after_add_relation
        self.hm.call_hooks('after_add_entity', cnx, entity=entity)
        # call hooks for inlined relations
        for attr, value in relations:
            self.hm.call_hooks('before_add_relation', cnx,
                               eidfrom=entity.eid, rtype=attr, eidto=value)
            self.hm.call_hooks('after_add_relation', cnx,
                               eidfrom=entity.eid, rtype=attr, eidto=value)
        return entity.eid

    def glob_update_entity(self, cnx, edited):
        """replace an entity in the repository
        the type and the eid of an entity must not be changed
        """
        entity = edited.entity
        if server.DEBUG & server.DBG_REPO:
            print('UPDATE entity', entity.cw_etype, entity.eid,
                  entity.cw_attr_cache, edited)
        hm = self.hm
        eschema = entity.e_schema
        cnx.set_entity_cache(entity)
        orig_edited = getattr(entity, 'cw_edited', None)
        entity.cw_edited = edited
        source = self.system_source
        try:
            only_inline_rels, need_fti_update = True, False
            relations = []
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
                        previous_value = previous_value[0][0]  # got a result set
                        if previous_value == entity.cw_attr_cache[attr]:
                            previous_value = None
                        else:
                            hm.call_hooks('before_delete_relation', cnx,
                                          eidfrom=entity.eid, rtype=attr,
                                          eidto=previous_value)
                    relations.append((attr, edited[attr], previous_value))
            # call hooks for inlined relations
            for attr, value, _t in relations:
                hm.call_hooks('before_add_relation', cnx,
                              eidfrom=entity.eid, rtype=attr, eidto=value)
            if not only_inline_rels:
                hm.call_hooks('before_update_entity', cnx, entity=entity)
            if cnx.is_hook_category_activated('integrity'):
                edited.check()
            try:
                source.update_entity(cnx, entity)
                edited.saved = True
            except (UniqueTogetherError, ViolatedConstraint) as exc:
                userhdlr = cnx.vreg['adapters'].select(
                    'IUserFriendlyError', cnx, entity=entity, exc=exc)
                userhdlr.raise_user_exception()
            self.system_source.update_info(cnx, entity, need_fti_update)
            if not only_inline_rels:
                hm.call_hooks('after_update_entity', cnx, entity=entity)
            for attr, value, prevvalue in relations:
                # if the relation is already cached, update existant cache
                relcache = entity.cw_relation_cached(attr, 'subject')
                if prevvalue is not None:
                    hm.call_hooks('after_delete_relation', cnx,
                                  eidfrom=entity.eid, rtype=attr, eidto=prevvalue)
                    if relcache is not None:
                        cnx.update_rel_cache_del(entity.eid, attr, prevvalue)
                del_existing_rel_if_needed(cnx, entity.eid, attr, value)
                cnx.update_rel_cache_add(entity.eid, attr, value)
                hm.call_hooks('after_add_relation', cnx,
                              eidfrom=entity.eid, rtype=attr, eidto=value)
        finally:
            if orig_edited is not None:
                entity.cw_edited = orig_edited

    def glob_delete_entities(self, cnx, eids):
        """delete a list of  entities and all related entities from the repository"""
        # mark eids as being deleted in cnx info and setup cache update
        # operation (register pending eids before actual deletion to avoid
        # multiple call to glob_delete_entities)
        op = hook.CleanupDeletedEidsCacheOp.get_instance(cnx)
        if not isinstance(eids, (set, frozenset)):
            warn('[3.13] eids should be given as a set', DeprecationWarning,
                 stacklevel=2)
            eids = frozenset(eids)
        eids = eids - op._container
        op._container |= eids
        data_by_etype = {}  # values are [list of entities]
        #
        # WARNING: the way this dictionary is populated is heavily optimized
        # and does not use setdefault on purpose. Unless a new release
        # of the Python interpreter advertises large perf improvements
        # in setdefault, this should not be changed without profiling.
        for eid in eids:
            etype = self.type_from_eid(eid, cnx)
            entity = cnx.entity_from_eid(eid, etype)
            try:
                data_by_etype[etype].append(entity)
            except KeyError:
                data_by_etype[etype] = [entity]
        source = self.system_source
        for etype, entities in data_by_etype.items():
            if server.DEBUG & server.DBG_REPO:
                print('DELETE entities', etype, [e.eid for e in entities])
            self.hm.call_hooks('before_delete_entity', cnx, entities=entities)
            self._delete_cascade_multi(cnx, entities)
            source.delete_entities(cnx, entities)
            source.delete_info_multi(cnx, entities)
            self.hm.call_hooks('after_delete_entity', cnx, entities=entities)
        # don't clear cache here, it is done in a hook on commit

    def glob_add_relation(self, cnx, subject, rtype, object):
        """add a relation to the repository"""
        self.glob_add_relations(cnx, {rtype: [(subject, object)]})

    def glob_add_relations(self, cnx, relations):
        """add several relations to the repository

        relations is a dictionary rtype: [(subj_eid, obj_eid), ...]
        """
        source = self.system_source
        relations_by_rtype = {}
        subjects_by_types = {}
        objects_by_types = {}
        activintegrity = cnx.is_hook_category_activated('activeintegrity')
        for rtype, eids_subj_obj in relations.items():
            if server.DEBUG & server.DBG_REPO:
                for subjeid, objeid in eids_subj_obj:
                    print('ADD relation', subjeid, rtype, objeid)
            for subjeid, objeid in eids_subj_obj:
                relations_by_rtype.setdefault(rtype, []).append((subjeid, objeid))
                if not activintegrity:
                    continue
                # take care to relation of cardinality '?1', as all eids will
                # be inserted later, we've remove duplicated eids since they
                # won't be caught by `del_existing_rel_if_needed`
                rdef = cnx.rtype_eids_rdef(rtype, subjeid, objeid)
                card = rdef.cardinality
                if card[0] in '?1':
                    with cnx.security_enabled(read=False):
                        cnx.execute('DELETE X %s Y WHERE X eid %%(x)s, '
                                    'NOT Y eid %%(y)s' % rtype,
                                    {'x': subjeid, 'y': objeid})
                    subjects = subjects_by_types.setdefault(rdef, {})
                    if subjeid in subjects:
                        del relations_by_rtype[rtype][subjects[subjeid]]
                        subjects[subjeid] = len(relations_by_rtype[rtype]) - 1
                        continue
                    subjects[subjeid] = len(relations_by_rtype[rtype]) - 1
                if card[1] in '?1':
                    with cnx.security_enabled(read=False):
                        cnx.execute('DELETE X %s Y WHERE Y eid %%(y)s, '
                                    'NOT X eid %%(x)s' % rtype,
                                    {'x': subjeid, 'y': objeid})
                    objects = objects_by_types.setdefault(rdef, {})
                    if objeid in objects:
                        del relations_by_rtype[rtype][objects[objeid]]
                        objects[objeid] = len(relations_by_rtype[rtype])
                        continue
                    objects[objeid] = len(relations_by_rtype[rtype])
        for rtype, source_relations in relations_by_rtype.items():
            self.hm.call_hooks('before_add_relation', cnx,
                               rtype=rtype, eids_from_to=source_relations)
        for rtype, source_relations in relations_by_rtype.items():
            source.add_relations(cnx, rtype, source_relations)
            rschema = self.schema.rschema(rtype)
            for subjeid, objeid in source_relations:
                cnx.update_rel_cache_add(subjeid, rtype, objeid, rschema.symmetric)
        for rtype, source_relations in relations_by_rtype.items():
            self.hm.call_hooks('after_add_relation', cnx,
                               rtype=rtype, eids_from_to=source_relations)

    def glob_delete_relation(self, cnx, subject, rtype, object):
        """delete a relation from the repository"""
        if server.DEBUG & server.DBG_REPO:
            print('DELETE relation', subject, rtype, object)
        source = self.system_source
        self.hm.call_hooks('before_delete_relation', cnx,
                           eidfrom=subject, rtype=rtype, eidto=object)
        source.delete_relation(cnx, subject, rtype, object)
        rschema = self.schema.rschema(rtype)
        cnx.update_rel_cache_del(subject, rtype, object, rschema.symmetric)
        self.hm.call_hooks('after_delete_relation', cnx,
                           eidfrom=subject, rtype=rtype, eidto=object)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg, *a, **kw: None


set_log_methods(Repository, getLogger('cubicweb.repository'))
