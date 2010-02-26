"""Repository users' and internal' sessions.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
import threading
from time import time

from logilab.common.deprecation import deprecated
from rql.nodes import VariableRef, Function, ETYPE_PYOBJ_MAP, etype_from_pyobj
from yams import BASE_TYPES

from cubicweb import Binary, UnknownEid
from cubicweb.req import RequestSessionBase
from cubicweb.dbapi import ConnectionProperties
from cubicweb.utils import make_uid
from cubicweb.rqlrewrite import RQLRewriter

ETYPE_PYOBJ_MAP[Binary] = 'Bytes'

def is_final(rqlst, variable, args):
    # try to find if this is a final var or not
    for select in rqlst.children:
        for sol in select.solutions:
            etype = variable.get_type(sol, args)
            if etype is None:
                continue
            if etype in BASE_TYPES:
                return True
            return False

def _make_description(selected, args, solution):
    """return a description for a result set"""
    description = []
    for term in selected:
        description.append(term.get_type(solution, args))
    return description


class Session(RequestSessionBase):
    """tie session id, user, connections pool and other session data all
    together
    """

    def __init__(self, user, repo, cnxprops=None, _id=None):
        super(Session, self).__init__(repo.vreg)
        self.id = _id or make_uid(user.login.encode('UTF8'))
        cnxprops = cnxprops or ConnectionProperties('inmemory')
        self.user = user
        self.repo = repo
        self.cnxtype = cnxprops.cnxtype
        self.creation = time()
        self.timestamp = self.creation
        self.is_internal_session = False
        self.is_super_session = False
        self.default_mode = 'read'
        # short cut to querier .execute method
        self._execute = repo.querier.execute
        # shared data, used to communicate extra information between the client
        # and the rql server
        self.data = {}
        # i18n initialization
        self.set_language(cnxprops.lang)
        # internals
        self._threaddata = threading.local()
        self._threads_in_transaction = set()
        self._closed = False

    def __unicode__(self):
        return '<%ssession %s (%s 0x%x)>' % (
            self.cnxtype, unicode(self.user.login), self.id, id(self))

    def hijack_user(self, user):
        """return a fake request/session using specified user"""
        session = Session(user, self.repo)
        session._threaddata = self.actual_session()._threaddata
        return session

    def _super_call(self, __cb, *args, **kwargs):
        if self.is_super_session:
            __cb(self, *args, **kwargs)
            return
        self.is_super_session = True
        try:
            __cb(self, *args, **kwargs)
        finally:
            self.is_super_session = False

    def add_relation(self, fromeid, rtype, toeid):
        """provide direct access to the repository method to add a relation.

        This is equivalent to the following rql query:

          SET X rtype Y WHERE X eid  fromeid, T eid toeid

        without read security check but also all the burden of rql execution.
        You may use this in hooks when you know both eids of the relation you
        want to add.
        """
        if self.vreg.schema[rtype].inlined:
            entity = self.entity_from_eid(fromeid)
            entity[rtype] = toeid
            self._super_call(self.repo.glob_update_entity,
                             entity, set((rtype,)))
        else:
            self._super_call(self.repo.glob_add_relation,
                             fromeid, rtype, toeid)

    def delete_relation(self, fromeid, rtype, toeid):
        """provide direct access to the repository method to delete a relation.

        This is equivalent to the following rql query:

          DELETE X rtype Y WHERE X eid  fromeid, T eid toeid

        without read security check but also all the burden of rql execution.
        You may use this in hooks when you know both eids of the relation you
        want to delete.
        """
        if self.vreg.schema[rtype].inlined:
            entity = self.entity_from_eid(fromeid)
            entity[rtype] = None
            self._super_call(self.repo.glob_update_entity,
                             entity, set((rtype,)))
        else:
            self._super_call(self.repo.glob_delete_relation,
                             fromeid, rtype, toeid)

    # relations cache handling #################################################

    def update_rel_cache_add(self, subject, rtype, object, symmetric=False):
        self._update_entity_rel_cache_add(subject, rtype, 'subject', object)
        if symmetric:
            self._update_entity_rel_cache_add(object, rtype, 'subject', subject)
        else:
            self._update_entity_rel_cache_add(object, rtype, 'object', subject)

    def update_rel_cache_del(self, subject, rtype, object, symmetric=False):
        self._update_entity_rel_cache_del(subject, rtype, 'subject', object)
        if symmetric:
            self._update_entity_rel_cache_del(object, rtype, 'object', object)
        else:
            self._update_entity_rel_cache_del(object, rtype, 'object', subject)

    def _update_entity_rel_cache_add(self, eid, rtype, role, targeteid):
        try:
            entity = self.entity_cache(eid)
        except KeyError:
            return
        rcache = entity.relation_cached(rtype, role)
        if rcache is not None:
            rset, entities = rcache
            rset = rset.copy()
            entities = list(entities)
            rset.rows.append([targeteid])
            if not isinstance(rset.description, list): # else description not set
                rset.description = list(rset.description)
            rset.description.append([self.describe(targeteid)[0]])
            targetentity = self.entity_from_eid(targeteid)
            if targetentity.cw_rset is None:
                targetentity.cw_rset = rset
                targetentity.cw_row = rset.rowcount
                targetentity.cw_col = 0
            rset.rowcount += 1
            entities.append(targetentity)
            entity._related_cache['%s_%s' % (rtype, role)] = (rset, tuple(entities))

    def _update_entity_rel_cache_del(self, eid, rtype, role, targeteid):
        try:
            entity = self.entity_cache(eid)
        except KeyError:
            return
        rcache = entity.relation_cached(rtype, role)
        if rcache is not None:
            rset, entities = rcache
            for idx, row in enumerate(rset.rows):
                if row[0] == targeteid:
                    break
            else:
                # this may occurs if the cache has been filed by a hook
                # after the database update
                self.debug('cache inconsistency for %s %s %s %s', eid, rtype,
                           role, targeteid)
                return
            rset = rset.copy()
            entities = list(entities)
            del rset.rows[idx]
            if isinstance(rset.description, list): # else description not set
                del rset.description[idx]
            del entities[idx]
            rset.rowcount -= 1
            entity._related_cache['%s_%s' % (rtype, role)] = (rset, tuple(entities))

    # resource accessors ######################################################

    def actual_session(self):
        """return the original parent session if any, else self"""
        return self

    def system_sql(self, sql, args=None, rollback_on_failure=True):
        """return a sql cursor on the system database"""
        if not sql.split(None, 1)[0].upper() == 'SELECT':
            self.mode = 'write'
        return self.pool.source('system').doexec(self, sql, args,
                                                 rollback=rollback_on_failure)

    def set_language(self, language):
        """i18n configuration for translation"""
        vreg = self.vreg
        language = language or self.user.property_value('ui.language')
        try:
            gettext, pgettext = vreg.config.translations[language]
            self._ = self.__ = gettext
            self.pgettext = pgettext
        except KeyError:
            language = vreg.property_value('ui.language')
            try:
                gettext, pgettext = vreg.config.translations[language]
                self._ = self.__ = gettext
                self.pgettext = pgettext
            except KeyError:
                self._ = self.__ = unicode
                self.pgettext = lambda x, y: y
        self.lang = language

    def change_property(self, prop, value):
        assert prop == 'lang' # this is the only one changeable property for now
        self.set_language(value)

    def deleted_in_transaction(self, eid):
        return eid in self.transaction_data.get('pendingeids', ())

    def added_in_transaction(self, eid):
        return eid in self.transaction_data.get('neweids', ())

    def schema_rproperty(self, rtype, eidfrom, eidto, rprop):
        rschema = self.repo.schema[rtype]
        subjtype = self.describe(eidfrom)[0]
        objtype = self.describe(eidto)[0]
        rdef = rschema.rdef(subjtype, objtype)
        return rdef.get(rprop)

    # connection management ###################################################

    def keep_pool_mode(self, mode):
        """set pool_mode, e.g. how the session will keep its pool:

        * if mode == 'write', the pool is freed after each ready query, but kept
          until the transaction's end (eg commit or rollback) when a write query
          is detected (eg INSERT/SET/DELETE queries)

        * if mode == 'transaction', the pool is only freed after the
          transaction's end

        notice that a repository has a limited set of pools, and a session has to
        wait for a free pool to run any rql query (unless it already has a pool
        set).
        """
        assert mode in ('transaction', 'write')
        if mode == 'transaction':
            self.default_mode = 'transaction'
        else: # mode == 'write'
            self.default_mode = 'read'

    def get_mode(self):
        return getattr(self._threaddata, 'mode', self.default_mode)
    def set_mode(self, value):
        self._threaddata.mode = value
    mode = property(get_mode, set_mode,
                    doc='transaction mode (read/write/transaction), resetted to'
                    ' default_mode on commit / rollback')

    def get_commit_state(self):
        return getattr(self._threaddata, 'commit_state', None)
    def set_commit_state(self, value):
        self._threaddata.commit_state = value
    commit_state = property(get_commit_state, set_commit_state)

    @property
    def pool(self):
        """connections pool, set according to transaction mode for each query"""
        return getattr(self._threaddata, 'pool', None)

    def set_pool(self, checkclosed=True):
        """the session need a pool to execute some queries"""
        if checkclosed and self._closed:
            raise Exception('try to set pool on a closed session')
        if self.pool is None:
            # get pool first to avoid race-condition
            self._threaddata.pool = pool = self.repo._get_pool()
            try:
                pool.pool_set()
            except:
                self._threaddata.pool = None
                self.repo._free_pool(pool)
                raise
            self._threads_in_transaction.add(threading.currentThread())
        return self._threaddata.pool

    def reset_pool(self, ignoremode=False):
        """the session is no longer using its pool, at least for some time"""
        # pool may be none if no operation has been done since last commit
        # or rollback
        if self.pool is not None and (ignoremode or self.mode == 'read'):
            # even in read mode, we must release the current transaction
            pool = self.pool
            try:
                self._threads_in_transaction.remove(threading.currentThread())
            except KeyError:
                pass
            pool.pool_reset()
            del self._threaddata.pool
            # free pool once everything is done to avoid race-condition
            self.repo._free_pool(pool)

    def _touch(self):
        """update latest session usage timestamp and reset mode to read"""
        self.timestamp = time()
        self.local_perm_cache.clear()
        self._threaddata.mode = self.default_mode

    # shared data handling ###################################################

    def get_shared_data(self, key, default=None, pop=False):
        """return value associated to `key` in session data"""
        if pop:
            return self.data.pop(key, default)
        else:
            return self.data.get(key, default)

    def set_shared_data(self, key, value, querydata=False):
        """set value associated to `key` in session data"""
        if querydata:
            self.transaction_data[key] = value
        else:
            self.data[key] = value

    # request interface #######################################################

    @property
    def cursor(self):
        """return a rql cursor"""
        return self

    def set_entity_cache(self, entity):
        # XXX session level caching may be a pb with multiple repository
        #     instances, but 1. this is probably not the only one :$ and 2. it
        #     may be an acceptable risk. Anyway we could activate it or not
        #     according to a configuration option
        try:
            self.transaction_data['ecache'].setdefault(entity.eid, entity)
        except KeyError:
            self.transaction_data['ecache'] = ecache = {}
            ecache[entity.eid] = entity

    def entity_cache(self, eid):
        try:
            return self.transaction_data['ecache'][eid]
        except:
            raise

    def cached_entities(self):
        return self.transaction_data.get('ecache', {}).values()

    def drop_entity_cache(self, eid=None):
        if eid is None:
            self.transaction_data.pop('ecache', None)
        else:
            del self.transaction_data['ecache'][eid]

    def base_url(self):
        url = self.repo.config['base-url']
        if not url:
            try:
                url = self.repo.config.default_base_url()
            except AttributeError: # default_base_url() might not be available
                self.warning('missing base-url definition in server config')
                url = u''
        return url

    def from_controller(self):
        """return the id (string) of the controller issuing the request (no
        sense here, always return 'view')
        """
        return 'view'

    def source_defs(self):
        return self.repo.source_defs()

    def describe(self, eid):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        return self.repo.type_and_source_from_eid(eid, self)

    # db-api like interface ###################################################

    def source_from_eid(self, eid):
        """return the source where the entity with id <eid> is located"""
        return self.repo.source_from_eid(eid, self)

    def decorate_rset(self, rset, propagate=False):
        rset.vreg = self.vreg
        rset.req = propagate and self or self.actual_session()
        return rset

    @property
    def super_session(self):
        try:
            csession = self.childsession
        except AttributeError:
            if isinstance(self, (ChildSession, InternalSession)):
                csession = self
            else:
                csession = ChildSession(self)
            self.childsession = csession
        # need shared pool set
        self.set_pool(checkclosed=False)
        return csession

    def unsafe_execute(self, rql, kwargs=None, eid_key=None, build_descr=True,
                       propagate=False):
        """like .execute but with security checking disabled (this method is
        internal to the server, it's not part of the db-api)

        if `propagate` is true, the super_session will be attached to the result
        set instead of the parent session, hence further query done through
        entities fetched from this result set will bypass security as well
        """
        return self.super_session.execute(rql, kwargs, eid_key, build_descr,
                                          propagate)

    def execute(self, rql, kwargs=None, eid_key=None, build_descr=True,
                propagate=False):
        """db-api like method directly linked to the querier execute method

        Becare that unlike actual cursor.execute, `build_descr` default to
        false
        """
        rset = self._execute(self, rql, kwargs, eid_key, build_descr)
        return self.decorate_rset(rset, propagate)

    def _clear_thread_data(self):
        """remove everything from the thread local storage, except pool
        which is explicitly removed by reset_pool, and mode which is set anyway
        by _touch
        """
        store = self._threaddata
        for name in ('commit_state', 'transaction_data', 'pending_operations',
                     '_rewriter'):
            try:
                delattr(store, name)
            except AttributeError:
                pass

    def commit(self, reset_pool=True):
        """commit the current session's transaction"""
        if self.pool is None:
            assert not self.pending_operations
            self._clear_thread_data()
            self._touch()
            self.debug('commit session %s done (no db activity)', self.id)
            return
        if self.commit_state:
            return
        # on rollback, an operation should have the following state
        # information:
        # - processed by the precommit/commit event or not
        # - if processed, is it the failed operation
        try:
            for trstate in ('precommit', 'commit'):
                processed = []
                self.commit_state = trstate
                try:
                    while self.pending_operations:
                        operation = self.pending_operations.pop(0)
                        operation.processed = trstate
                        processed.append(operation)
                        operation.handle_event('%s_event' % trstate)
                    self.pending_operations[:] = processed
                    self.debug('%s session %s done', trstate, self.id)
                except:
                    self.exception('error while %sing', trstate)
                    # if error on [pre]commit:
                    #
                    # * set .failed = True on the operation causing the failure
                    # * call revert<event>_event on processed operations
                    # * call rollback_event on *all* operations
                    #
                    # that seems more natural than not calling rollback_event
                    # for processed operations, and allow generic rollback
                    # instead of having to implements rollback, revertprecommit
                    # and revertcommit, that will be enough in mont case.
                    operation.failed = True
                    for operation in processed:
                        operation.handle_event('revert%s_event' % trstate)
                    # XXX use slice notation since self.pending_operations is a
                    # read-only property.
                    self.pending_operations[:] = processed + self.pending_operations 
                    self.rollback(reset_pool)
                    raise
            self.pool.commit()
            self.commit_state = trstate = 'postcommit'
            while self.pending_operations:
                operation = self.pending_operations.pop(0)
                operation.processed = trstate
                try:
                    operation.handle_event('%s_event' % trstate)
                except:
                    self.critical('error while %sing', trstate,
                                  exc_info=sys.exc_info())
            self.info('%s session %s done', trstate, self.id)
        finally:
            self._clear_thread_data()
            self._touch()
            if reset_pool:
                self.reset_pool(ignoremode=True)

    def rollback(self, reset_pool=True):
        """rollback the current session's transaction"""
        if self.pool is None:
            assert not self.pending_operations
            self._clear_thread_data()
            self._touch()
            self.debug('rollback session %s done (no db activity)', self.id)
            return
        try:
            while self.pending_operations:
                try:
                    operation = self.pending_operations.pop(0)
                    operation.handle_event('rollback_event')
                except:
                    self.critical('rollback error', exc_info=sys.exc_info())
                    continue
            self.pool.rollback()
            self.debug('rollback for session %s done', self.id)
        finally:
            self._clear_thread_data()
            self._touch()
            if reset_pool:
                self.reset_pool(ignoremode=True)

    def close(self):
        """do not close pool on session close, since they are shared now"""
        self._closed = True
        # copy since _threads_in_transaction maybe modified while waiting
        for thread in self._threads_in_transaction.copy():
            if thread is threading.currentThread():
                continue
            self.info('waiting for thread %s', thread)
            # do this loop/break instead of a simple join(10) in case thread is
            # the main thread (in which case it will be removed from
            # self._threads_in_transaction but still be alive...)
            for i in xrange(10):
                thread.join(1)
                if not (thread.isAlive() and
                        thread in self._threads_in_transaction):
                    break
            else:
                self.error('thread %s still alive after 10 seconds, will close '
                           'session anyway', thread)
        self.rollback()

    # transaction data/operations management ##################################

    @property
    def transaction_data(self):
        try:
            return self._threaddata.transaction_data
        except AttributeError:
            self._threaddata.transaction_data = {}
            return self._threaddata.transaction_data

    @property
    def pending_operations(self):
        try:
            return self._threaddata.pending_operations
        except AttributeError:
            self._threaddata.pending_operations = []
            return self._threaddata.pending_operations

    def add_operation(self, operation, index=None):
        """add an observer"""
        assert self.commit_state != 'commit'
        if index is not None:
            self.pending_operations.insert(index, operation)
        else:
            self.pending_operations.append(operation)

    # querier helpers #########################################################

    @property
    def rql_rewriter(self):
        # in thread local storage since the rewriter isn't thread safe
        try:
            return self._threaddata._rewriter
        except AttributeError:
            self._threaddata._rewriter = RQLRewriter(self)
            return self._threaddata._rewriter

    def build_description(self, rqlst, args, result):
        """build a description for a given result"""
        if len(rqlst.children) == 1 and len(rqlst.children[0].solutions) == 1:
            # easy, all lines are identical
            selected = rqlst.children[0].selection
            solution = rqlst.children[0].solutions[0]
            description = _make_description(selected, args, solution)
            return [tuple(description)] * len(result)
        # hard, delegate the work :o)
        return self.manual_build_descr(rqlst, args, result)

    def manual_build_descr(self, rqlst, args, result):
        """build a description for a given result by analysing each row

        XXX could probably be done more efficiently during execution of query
        """
        # not so easy, looks for variable which changes from one solution
        # to another
        unstables = rqlst.get_variable_variables()
        basedescription = []
        todetermine = []
        selected = rqlst.children[0].selection # sample selection
        for i, term in enumerate(selected):
            if isinstance(term, Function) and term.descr().rtype is not None:
                basedescription.append(term.get_type(term.descr().rtype, args))
                continue
            for vref in term.get_nodes(VariableRef):
                if vref.name in unstables:
                    basedescription.append(None)
                    todetermine.append( (i, is_final(rqlst, vref.variable, args)) )
                    break
            else:
                # sample etype
                etype = rqlst.children[0].solutions[0]
                basedescription.append(term.get_type(etype, args))
        if not todetermine:
            return [tuple(basedescription)] * len(result)
        return self._build_descr(result, basedescription, todetermine)

    def _build_descr(self, result, basedescription, todetermine):
        description = []
        etype_from_eid = self.describe
        for row in result:
            row_descr = basedescription
            for index, isfinal in todetermine:
                value = row[index]
                if value is None:
                    # None value inserted by an outer join, no type
                    row_descr[index] = None
                    continue
                if isfinal:
                    row_descr[index] = etype_from_pyobj(value)
                else:
                    try:
                        row_descr[index] = etype_from_eid(value)[0]
                    except UnknownEid:
                        self.critical('wrong eid %s in repository, should check database' % value)
                        row_descr[index] = row[index] = None
            description.append(tuple(row_descr))
        return description

    # deprecated ###############################################################

    @property
    @deprecated("[3.6] use session.vreg.schema")
    def schema(self):
        return self.repo.schema

    @deprecated("[3.4] use vreg['etypes'].etype_class(etype)")
    def etype_class(self, etype):
        """return an entity class for the given entity type"""
        return self.vreg['etypes'].etype_class(etype)

    @deprecated('[3.4] use direct access to session.transaction_data')
    def query_data(self, key, default=None, setdefault=False, pop=False):
        if setdefault:
            assert not pop
            return self.transaction_data.setdefault(key, default)
        if pop:
            return self.transaction_data.pop(key, default)
        else:
            return self.transaction_data.get(key, default)

    @deprecated('[3.4] use entity_from_eid(eid, etype=None)')
    def entity(self, eid):
        """return a result set for the given eid"""
        return self.entity_from_eid(eid)


class ChildSession(Session):
    """child (or internal) session are used to hijack the security system
    """
    cnxtype = 'inmemory'

    def __init__(self, parent_session):
        self.id = None
        self.is_internal_session = False
        self.is_super_session = True
        # session which has created this one
        self.parent_session = parent_session
        self.user = InternalManager()
        self.user.req = self # XXX remove when "vreg = user.req.vreg" hack in entity.py is gone
        self.repo = parent_session.repo
        self.vreg = parent_session.vreg
        self.data = parent_session.data
        self.encoding = parent_session.encoding
        self.lang = parent_session.lang
        self._ = self.__ = parent_session._
        # short cut to querier .execute method
        self._execute = self.repo.querier.execute

    @property
    def super_session(self):
        return self

    def get_mode(self):
        return self.parent_session.mode
    def set_mode(self, value):
        self.parent_session.set_mode(value)
    mode = property(get_mode, set_mode)

    def get_commit_state(self):
        return self.parent_session.commit_state
    def set_commit_state(self, value):
        self.parent_session.set_commit_state(value)
    commit_state = property(get_commit_state, set_commit_state)

    @property
    def pool(self):
        return self.parent_session.pool
    @property
    def pending_operations(self):
        return self.parent_session.pending_operations
    @property
    def transaction_data(self):
        return self.parent_session.transaction_data

    def set_pool(self):
        """the session need a pool to execute some queries"""
        self.parent_session.set_pool()

    def reset_pool(self):
        """the session has no longer using its pool, at least for some time
        """
        self.parent_session.reset_pool()

    def actual_session(self):
        """return the original parent session if any, else self"""
        return self.parent_session

    def commit(self, reset_pool=True):
        """commit the current session's transaction"""
        self.parent_session.commit(reset_pool)

    def rollback(self, reset_pool=True):
        """rollback the current session's transaction"""
        self.parent_session.rollback(reset_pool)

    def close(self):
        """do not close pool on session close, since they are shared now"""
        self.rollback()

    def user_data(self):
        """returns a dictionnary with this user's information"""
        return self.parent_session.user_data()


class InternalSession(Session):
    """special session created internaly by the repository"""

    def __init__(self, repo, cnxprops=None):
        super(InternalSession, self).__init__(InternalManager(), repo, cnxprops,
                                              _id='internal')
        self.user.req = self # XXX remove when "vreg = user.req.vreg" hack in entity.py is gone
        self.cnxtype = 'inmemory'
        self.is_internal_session = True
        self.is_super_session = True

    @property
    def super_session(self):
        return self


class InternalManager(object):
    """a manager user with all access rights used internally for task such as
    bootstrapping the repository or creating regular users according to
    repository content
    """
    def __init__(self):
        self.eid = -1
        self.login = u'__internal_manager__'
        self.properties = {}

    def matching_groups(self, groups):
        return 1

    def is_in_group(self, group):
        return True

    def owns(self, eid):
        return True

    def has_permission(self, pname, contexteid=None):
        return True

    def property_value(self, key):
        if key == 'ui.language':
            return 'en'
        return None


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Session, getLogger('cubicweb.session'))
