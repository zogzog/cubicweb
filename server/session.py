"""Repository users' and internal' sessions.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
import threading
from time import time
from types import NoneType

from rql.nodes import VariableRef, Function, ETYPE_PYOBJ_MAP, etype_from_pyobj
from yams import BASE_TYPES

from cubicweb import RequestSessionMixIn, Binary
from cubicweb.dbapi import ConnectionProperties
from cubicweb.utils import make_uid
from cubicweb.server.rqlrewrite import RQLRewriter

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

from rql import stmts
assert hasattr(stmts.Union, 'get_variable_variables'), "You need RQL > 0.18.3"

class Session(RequestSessionMixIn):
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
        # short cut to querier .execute method
        self._execute = repo.querier.execute
        # shared data, used to communicate extra information between the client
        # and the rql server
        self.data = {}
        # i18n initialization
        self.set_language(cnxprops.lang)
        self._threaddata = threading.local()
        
    def get_mode(self):
        return getattr(self._threaddata, 'mode', 'read')
    def set_mode(self, value):
        self._threaddata.mode = value
    # transaction mode (read/write), resetted to read on commit / rollback
    mode = property(get_mode, set_mode)

    def get_commit_state(self):
        return getattr(self._threaddata, 'commit_state', None)
    def set_commit_state(self, value):
        self._threaddata.commit_state = value
    commit_state = property(get_commit_state, set_commit_state)
    
    # set according to transaction mode for each query
    @property
    def pool(self):
        return getattr(self._threaddata, 'pool', None)
    
    # pending transaction operations
    @property
    def pending_operations(self):
        try:
            return self._threaddata.pending_operations
        except AttributeError:
            self._threaddata.pending_operations = []
            return self._threaddata.pending_operations
    
    # rql rewriter
    @property
    def rql_rewriter(self):
        try:
            return self._threaddata._rewriter
        except AttributeError:
            self._threaddata._rewriter = RQLRewriter(self.repo.querier, self)
            return self._threaddata._rewriter
    
    # transaction queries data
    @property
    def _query_data(self):
        try:
            return self._threaddata._query_data
        except AttributeError:
            self._threaddata._query_data = {}
            return self._threaddata._query_data
    
    def set_language(self, language):
        """i18n configuration for translation"""
        vreg = self.vreg
        language = language or self.user.property_value('ui.language')
        try:
            self._ = self.__ = vreg.config.translations[language]
        except KeyError:
            language = vreg.property_value('ui.language')
            try:
                self._ = self.__ = vreg.config.translations[language]
            except KeyError:
                self._ = self.__ = unicode
        self.lang = language
        
    def change_property(self, prop, value):
        assert prop == 'lang' # this is the only one changeable property for now
        self.set_language(value)

    def __str__(self):
        return '<%ssession %s (%s 0x%x)>' % (self.cnxtype, self.user.login, 
                                             self.id, id(self))

    def etype_class(self, etype):
        """return an entity class for the given entity type"""
        return self.vreg.etype_class(etype)
    
    def entity(self, eid):
        """return a result set for the given eid"""
        return self.eid_rset(eid).get_entity(0, 0)
        
    def _touch(self):
        """update latest session usage timestamp and reset mode to read
        """
        self.timestamp = time()
        self.local_perm_cache.clear()
        self._threaddata.mode = 'read'
        
    def set_pool(self):
        """the session need a pool to execute some queries"""
        if self.pool is None:
            self._threaddata.pool = self.repo._get_pool()
            try:                
                self._threaddata.pool.pool_set(self)
            except:
                self.repo._free_pool(self.pool)
                self._threaddata.pool = None
                raise
        return self._threaddata.pool
            
    def reset_pool(self):
        """the session has no longer using its pool, at least for some time
        """
        # pool may be none if no operation has been done since last commit
        # or rollback
        if self.pool is not None and self.mode == 'read':
            # even in read mode, we must release the current transaction
            self.repo._free_pool(self.pool)
            self.pool.pool_reset(self)
            self._threaddata.pool = None
            
    def system_sql(self, sql, args=None):
        """return a sql cursor on the system database"""
        if not sql.split(None, 1)[0].upper() == 'SELECT':
            self.mode = 'write'
        cursor = self.pool['system']
        self.pool.source('system').doexec(cursor, sql, args)
        return cursor

    def actual_session(self):
        """return the original parent session if any, else self"""
        return self        

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
            self.set_query_data(key, value)
        else:
            self.data[key] = value
        
    # request interface #######################################################
    
    def set_entity_cache(self, entity):
        # no entity cache in the server, too high risk of inconsistency
        # between pre/post hooks
        pass

    def entity_cache(self, eid):
        raise KeyError(eid)

    def base_url(self):
        return self.repo.config['base-url'] or u''
        
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
            csession = self._threaddata.childsession
        except AttributeError:
            if self.is_super_session:
                csession = self
            else:
                csession = ChildSession(self)
            self._threaddata.childsession = csession
        # need shared pool set
        self.set_pool()
        return csession
        
    def unsafe_execute(self, rql, kwargs=None, eid_key=None, build_descr=False,
                       propagate=False):
        """like .execute but with security checking disabled (this method is
        internal to the server, it's not part of the db-api)

        if `propagate` is true, the super_session will be attached to the result
        set instead of the parent session, hence further query done through
        entities fetched from this result set will bypass security as well
        """
        return self.super_session.execute(rql, kwargs, eid_key, build_descr,
                                          propagate)

    @property
    def cursor(self):
        """return a rql cursor"""
        return self
    
    def execute(self, rql, kwargs=None, eid_key=None, build_descr=True,
                propagate=False):
        """db-api like method directly linked to the querier execute method

        Becare that unlike actual cursor.execute, `build_descr` default to
        false
        """
        rset = self._execute(self, rql, kwargs, eid_key, build_descr)
        return self.decorate_rset(rset, propagate)
    
    def commit(self, reset_pool=True):
        """commit the current session's transaction"""
        if self.pool is None:
            assert not self.pending_operations
            self._query_data.clear()
            self._touch()
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
                    operation.failed = True
                    for operation in processed:
                        operation.handle_event('revert%s_event' % trstate)
                    self.rollback(reset_pool)
                    raise
            self.pool.commit()
        finally:
            self._touch()
            self.commit_state = None
            self.pending_operations[:] = []
            self._query_data.clear()
            if reset_pool:
                self.reset_pool()
                        
    def rollback(self, reset_pool=True):
        """rollback the current session's transaction"""
        if self.pool is None:
            assert not self.pending_operations
            self._query_data.clear()
            self._touch()
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
        finally:
            self._touch()
            self.pending_operations[:] = []
            self._query_data.clear()
            if reset_pool:
                self.reset_pool()
        
    def close(self):
        """do not close pool on session close, since they are shared now"""
        self.rollback()
        
    # transaction data/operations management ##################################
    
    def add_query_data(self, key, value):
        self._query_data.setdefault(key, []).append(value)
    
    def set_query_data(self, key, value):
        self._query_data[key] = value
        
    def query_data(self, key, default=None, setdefault=False, pop=False):
        if setdefault:
            assert not pop
            return self._query_data.setdefault(key, default)
        if pop:
            return self._query_data.pop(key, default)
        else:
            return self._query_data.get(key, default)
        
    def add_operation(self, operation, index=None):
        """add an observer"""
        assert self.commit_state != 'commit'
        if index is not None:
            self.pending_operations.insert(index, operation)
        else:
            self.pending_operations.append(operation)
            
    # querier helpers #########################################################
    
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
                    row_descr[index] = etype_from_eid(value)[0]
            description.append(tuple(row_descr))
        return description

    
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
    def _query_data(self):
        return self.parent_session._query_data
        
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
        super(InternalSession, self).__init__(_IMANAGER, repo, cnxprops,
                                              _id='internal')
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

_IMANAGER= InternalManager()

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Session, getLogger('cubicweb.session'))
