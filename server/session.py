# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Repository users' and internal' sessions."""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
import threading
from time import time
from uuid import uuid4
from warnings import warn

from logilab.common.deprecation import deprecated
from rql import CoercionError
from rql.nodes import ETYPE_PYOBJ_MAP, etype_from_pyobj
from yams import BASE_TYPES

from cubicweb import Binary, UnknownEid, QueryError, schema
from cubicweb.req import RequestSessionBase
from cubicweb.dbapi import ConnectionProperties
from cubicweb.utils import make_uid, RepeatList
from cubicweb.rqlrewrite import RQLRewriter
from cubicweb.server.edition import EditedEntity

ETYPE_PYOBJ_MAP[Binary] = 'Bytes'

NO_UNDO_TYPES = schema.SCHEMA_TYPES.copy()
NO_UNDO_TYPES.add('CWCache')
# is / is_instance_of are usually added by sql hooks except when using
# dataimport.NoHookRQLObjectStore, and we don't want to record them
# anyway in the later case
NO_UNDO_TYPES.add('is')
NO_UNDO_TYPES.add('is_instance_of')
NO_UNDO_TYPES.add('cw_source')
# XXX rememberme,forgotpwd,apycot,vcsfile

def _make_description(selected, args, solution):
    """return a description for a result set"""
    description = []
    for term in selected:
        description.append(term.get_type(solution, args))
    return description


class hooks_control(object):
    """context manager to control activated hooks categories.

    If mode is session.`HOOKS_DENY_ALL`, given hooks categories will
    be enabled.

    If mode is session.`HOOKS_ALLOW_ALL`, given hooks categories will
    be disabled.

    .. sourcecode:: python

       with hooks_control(self.session, self.session.HOOKS_ALLOW_ALL, 'integrity'):
           # ... do stuff with all but 'integrity' hooks activated

       with hooks_control(self.session, self.session.HOOKS_DENY_ALL, 'integrity'):
           # ... do stuff with none but 'integrity' hooks activated
    """
    def __init__(self, session, mode, *categories):
        self.session = session
        self.mode = mode
        self.categories = categories

    def __enter__(self):
        self.oldmode = self.session.set_hooks_mode(self.mode)
        if self.mode is self.session.HOOKS_DENY_ALL:
            self.changes = self.session.enable_hook_categories(*self.categories)
        else:
            self.changes = self.session.disable_hook_categories(*self.categories)

    def __exit__(self, exctype, exc, traceback):
        if self.changes:
            if self.mode is self.session.HOOKS_DENY_ALL:
                self.session.disable_hook_categories(*self.changes)
            else:
                self.session.enable_hook_categories(*self.changes)
        self.session.set_hooks_mode(self.oldmode)

INDENT = ''
class security_enabled(object):
    """context manager to control security w/ session.execute, since by
    default security is disabled on queries executed on the repository
    side.
    """
    def __init__(self, session, read=None, write=None):
        self.session = session
        self.read = read
        self.write = write

    def __enter__(self):
#        global INDENT
        if self.read is not None:
            self.oldread = self.session.set_read_security(self.read)
#            print INDENT + 'read', self.read, self.oldread
        if self.write is not None:
            self.oldwrite = self.session.set_write_security(self.write)
#            print INDENT + 'write', self.write, self.oldwrite
#        INDENT += '  '

    def __exit__(self, exctype, exc, traceback):
#        global INDENT
#        INDENT = INDENT[:-2]
        if self.read is not None:
            self.session.set_read_security(self.oldread)
#            print INDENT + 'reset read to', self.oldread
        if self.write is not None:
            self.session.set_write_security(self.oldwrite)
#            print INDENT + 'reset write to', self.oldwrite


class TransactionData(object):
    def __init__(self, txid):
        self.transactionid = txid

class Session(RequestSessionBase):
    """tie session id, user, connections pool and other session data all
    together
    """
    is_internal_session = False

    def __init__(self, user, repo, cnxprops=None, _id=None):
        super(Session, self).__init__(repo.vreg)
        self.id = _id or make_uid(user.login.encode('UTF8'))
        cnxprops = cnxprops or ConnectionProperties('inmemory')
        self.user = user
        self.repo = repo
        self.cnxtype = cnxprops.cnxtype
        self.timestamp = time()
        self.default_mode = 'read'
        # support undo for Create Update Delete entity / Add Remove relation
        if repo.config.creating or repo.config.repairing or self.is_internal_session:
            self.undo_actions = ()
        else:
            self.undo_actions = set(repo.config['undo-support'].upper())
            if self.undo_actions - set('CUDAR'):
                raise Exception('bad undo-support string in configuration')
        # short cut to querier .execute method
        self._execute = repo.querier.execute
        # shared data, used to communicate extra information between the client
        # and the rql server
        self.data = {}
        # i18n initialization
        self.set_language(cnxprops.lang)
        # internals
        self._tx_data = {}
        self.__threaddata = threading.local()
        self._threads_in_transaction = set()
        self._closed = False

    def __unicode__(self):
        return '<%ssession %s (%s 0x%x)>' % (
            self.cnxtype, unicode(self.user.login), self.id, id(self))

    def set_tx_data(self, txid=None):
        if txid is None:
            txid = threading.currentThread().getName()
        try:
            self.__threaddata.txdata = self._tx_data[txid]
        except KeyError:
            self.__threaddata.txdata = self._tx_data[txid] = TransactionData(txid)

    @property
    def _threaddata(self):
        try:
            return self.__threaddata.txdata
        except AttributeError:
            self.set_tx_data()
            return self.__threaddata.txdata


    def hijack_user(self, user):
        """return a fake request/session using specified user"""
        session = Session(user, self.repo)
        threaddata = session._threaddata
        threaddata.pool = self.pool
        # share pending_operations, else operation added in the hi-jacked
        # session such as SendMailOp won't ever be processed
        threaddata.pending_operations = self.pending_operations
        # everything in transaction_data should be copied back but the entity
        # type cache we don't want to avoid security pb
        threaddata.transaction_data = self.transaction_data.copy()
        threaddata.transaction_data.pop('ecache', None)
        return session

    def add_relation(self, fromeid, rtype, toeid):
        """provide direct access to the repository method to add a relation.

        This is equivalent to the following rql query:

          SET X rtype Y WHERE X eid  fromeid, T eid toeid

        without read security check but also all the burden of rql execution.
        You may use this in hooks when you know both eids of the relation you
        want to add.
        """
        self.add_relations([(rtype, [(fromeid,  toeid)])])

    def add_relations(self, relations):
        '''set many relation using a shortcut similar to the one in add_relation
        
        relations is a list of 2-uples, the first element of each
        2-uple is the rtype, and the second is a list of (fromeid,
        toeid) tuples
        '''
        edited_entities = {}
        relations_dict = {}
        with security_enabled(self, False, False):
            for rtype, eids in relations:
                if self.vreg.schema[rtype].inlined:
                    for fromeid, toeid in eids:
                        if fromeid not in edited_entities:
                            entity = self.entity_from_eid(fromeid)
                            edited = EditedEntity(entity)
                            edited_entities[fromeid] = edited
                        else:
                            edited = edited_entities[fromeid]
                        edited.edited_attribute(rtype, toeid)
                else:
                    relations_dict[rtype] = eids
            self.repo.glob_add_relations(self, relations_dict)
            for edited in edited_entities.itervalues():
                self.repo.glob_update_entity(self, edited)


    def delete_relation(self, fromeid, rtype, toeid):
        """provide direct access to the repository method to delete a relation.

        This is equivalent to the following rql query:

          DELETE X rtype Y WHERE X eid  fromeid, T eid toeid

        without read security check but also all the burden of rql execution.
        You may use this in hooks when you know both eids of the relation you
        want to delete.
        """
        with security_enabled(self, False, False):
            if self.vreg.schema[rtype].inlined:
                entity = self.entity_from_eid(fromeid)
                entity.cw_attr_cache[rtype] = None
                self.repo.glob_update_entity(self, entity, set((rtype,)))
            else:
                self.repo.glob_delete_relation(self, fromeid, rtype, toeid)

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
        rcache = entity.cw_relation_cached(rtype, role)
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
            entity._cw_related_cache['%s_%s' % (rtype, role)] = (
                rset, tuple(entities))

    def _update_entity_rel_cache_del(self, eid, rtype, role, targeteid):
        try:
            entity = self.entity_cache(eid)
        except KeyError:
            return
        rcache = entity.cw_relation_cached(rtype, role)
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
            entity._cw_related_cache['%s_%s' % (rtype, role)] = (
                rset, tuple(entities))

    # resource accessors ######################################################

    def system_sql(self, sql, args=None, rollback_on_failure=True):
        """return a sql cursor on the system database"""
        if sql.split(None, 1)[0].upper() != 'SELECT':
            self.mode = 'write'
        source = self.pool.source('system')
        try:
            return source.doexec(self, sql, args, rollback=rollback_on_failure)
        except (source.OperationalError, source.InterfaceError):
            if not rollback_on_failure:
                raise
            source.warning("trying to reconnect")
            self.pool.reconnect(source)
            return source.doexec(self, sql, args, rollback=rollback_on_failure)

    def set_language(self, language):
        """i18n configuration for translation"""
        language = language or self.user.property_value('ui.language')
        try:
            gettext, pgettext = self.vreg.config.translations[language]
            self._ = self.__ = gettext
            self.pgettext = pgettext
        except KeyError:
            language = self.vreg.property_value('ui.language')
            try:
                gettext, pgettext = self.vreg.config.translations[language]
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
        """return True if the entity of the given eid is being deleted in the
        current transaction
        """
        return eid in self.transaction_data.get('pendingeids', ())

    def added_in_transaction(self, eid):
        """return True if the entity of the given eid is being created in the
        current transaction
        """
        return eid in self.transaction_data.get('neweids', ())

    def schema_rproperty(self, rtype, eidfrom, eidto, rprop):
        rschema = self.repo.schema[rtype]
        subjtype = self.describe(eidfrom)[0]
        objtype = self.describe(eidto)[0]
        rdef = rschema.rdef(subjtype, objtype)
        return rdef.get(rprop)

    # security control #########################################################

    DEFAULT_SECURITY = object() # evaluated to true by design

    @property
    def read_security(self):
        """return a boolean telling if read security is activated or not"""
        txstore = self._threaddata
        if txstore is None:
            return self.DEFAULT_SECURITY
        try:
            return txstore.read_security
        except AttributeError:
            txstore.read_security = self.DEFAULT_SECURITY
            return txstore.read_security

    def set_read_security(self, activated):
        """[de]activate read security, returning the previous value set for
        later restoration.

        you should usually use the `security_enabled` context manager instead
        of this to change security settings.
        """
        txstore = self._threaddata
        if txstore is None:
            return self.DEFAULT_SECURITY
        oldmode = getattr(txstore, 'read_security', self.DEFAULT_SECURITY)
        txstore.read_security = activated
        # dbapi_query used to detect hooks triggered by a 'dbapi' query (eg not
        # issued on the session). This is tricky since we the execution model of
        # a (write) user query is:
        #
        # repository.execute (security enabled)
        #  \-> querier.execute
        #       \-> repo.glob_xxx (add/update/delete entity/relation)
        #            \-> deactivate security before calling hooks
        #                 \-> WE WANT TO CHECK QUERY NATURE HERE
        #                      \-> potentially, other calls to querier.execute
        #
        # so we can't rely on simply checking session.read_security, but
        # recalling the first transition from DEFAULT_SECURITY to something
        # else (False actually) is not perfect but should be enough
        #
        # also reset dbapi_query to true when we go back to DEFAULT_SECURITY
        txstore.dbapi_query = (oldmode is self.DEFAULT_SECURITY
                               or activated is self.DEFAULT_SECURITY)
        return oldmode

    @property
    def write_security(self):
        """return a boolean telling if write security is activated or not"""
        txstore = self._threaddata
        if txstore is None:
            return self.DEFAULT_SECURITY
        try:
            return txstore.write_security
        except:
            txstore.write_security = self.DEFAULT_SECURITY
            return txstore.write_security

    def set_write_security(self, activated):
        """[de]activate write security, returning the previous value set for
        later restoration.

        you should usually use the `security_enabled` context manager instead
        of this to change security settings.
        """
        txstore = self._threaddata
        if txstore is None:
            return self.DEFAULT_SECURITY
        oldmode = getattr(txstore, 'write_security', self.DEFAULT_SECURITY)
        txstore.write_security = activated
        return oldmode

    @property
    def running_dbapi_query(self):
        """return a boolean telling if it's triggered by a db-api query or by
        a session query.

        To be used in hooks, else may have a wrong value.
        """
        return getattr(self._threaddata, 'dbapi_query', True)

    # hooks activation control #################################################
    # all hooks should be activated during normal execution

    HOOKS_ALLOW_ALL = object()
    HOOKS_DENY_ALL = object()

    @property
    def hooks_mode(self):
        return getattr(self._threaddata, 'hooks_mode', self.HOOKS_ALLOW_ALL)

    def set_hooks_mode(self, mode):
        assert mode is self.HOOKS_ALLOW_ALL or mode is self.HOOKS_DENY_ALL
        oldmode = getattr(self._threaddata, 'hooks_mode', self.HOOKS_ALLOW_ALL)
        self._threaddata.hooks_mode = mode
        return oldmode

    @property
    def disabled_hook_categories(self):
        try:
            return getattr(self._threaddata, 'disabled_hook_cats')
        except AttributeError:
            cats = self._threaddata.disabled_hook_cats = set()
            return cats

    @property
    def enabled_hook_categories(self):
        try:
            return getattr(self._threaddata, 'enabled_hook_cats')
        except AttributeError:
            cats = self._threaddata.enabled_hook_cats = set()
            return cats

    def disable_hook_categories(self, *categories):
        """disable the given hook categories:

        - on HOOKS_DENY_ALL mode, ensure those categories are not enabled
        - on HOOKS_ALLOW_ALL mode, ensure those categories are disabled
        """
        changes = set()
        if self.hooks_mode is self.HOOKS_DENY_ALL:
            enablecats = self.enabled_hook_categories
            for category in categories:
                if category in enablecats:
                    enablecats.remove(category)
                    changes.add(category)
        else:
            disablecats = self.disabled_hook_categories
            for category in categories:
                if category not in disablecats:
                    disablecats.add(category)
                    changes.add(category)
        return tuple(changes)

    def enable_hook_categories(self, *categories):
        """enable the given hook categories:

        - on HOOKS_DENY_ALL mode, ensure those categories are enabled
        - on HOOKS_ALLOW_ALL mode, ensure those categories are not disabled
        """
        changes = set()
        if self.hooks_mode is self.HOOKS_DENY_ALL:
            enablecats = self.enabled_hook_categories
            for category in categories:
                if category not in enablecats:
                    enablecats.add(category)
                    changes.add(category)
        else:
            disablecats = self.disabled_hook_categories
            for category in categories:
                if category in self.disabled_hook_categories:
                    disablecats.remove(category)
                    changes.add(category)
        return tuple(changes)

    def is_hook_category_activated(self, category):
        """return a boolean telling if the given category is currently activated
        or not
        """
        if self.hooks_mode is self.HOOKS_DENY_ALL:
            return category in self.enabled_hook_categories
        return category not in self.disabled_hook_categories

    def is_hook_activated(self, hook):
        """return a boolean telling if the given hook class is currently
        activated or not
        """
        return self.is_hook_category_activated(hook.category)

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
        if self._closed:
            self.reset_pool(True)
            raise Exception('try to access pool on a closed session')
        return getattr(self._threaddata, 'pool', None)

    def set_pool(self):
        """the session need a pool to execute some queries"""
        if self._closed:
            self.reset_pool(True)
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
            self._threads_in_transaction.add(
                (threading.currentThread(), pool) )
        return self._threaddata.pool

    def _free_thread_pool(self, thread, pool, force_close=False):
        try:
            self._threads_in_transaction.remove( (thread, pool) )
        except KeyError:
            # race condition on pool freeing (freed by commit or rollback vs
            # close)
            pass
        else:
            if force_close:
                pool.reconnect()
            else:
                pool.pool_reset()
            # free pool once everything is done to avoid race-condition
            self.repo._free_pool(pool)

    def reset_pool(self, ignoremode=False):
        """the session is no longer using its pool, at least for some time"""
        # pool may be none if no operation has been done since last commit
        # or rollback
        pool = getattr(self._threaddata, 'pool', None)
        if pool is not None and (ignoremode or self.mode == 'read'):
            # even in read mode, we must release the current transaction
            self._free_thread_pool(threading.currentThread(), pool)
            del self._threaddata.pool

    def _touch(self):
        """update latest session usage timestamp and reset mode to read"""
        self.timestamp = time()
        self.local_perm_cache.clear() # XXX simply move in transaction_data, no?

    # shared data handling ###################################################

    def get_shared_data(self, key, default=None, pop=False, txdata=False):
        """return value associated to `key` in session data"""
        if txdata:
            data = self.transaction_data
        else:
            data = self.data
        if pop:
            return data.pop(key, default)
        else:
            return data.get(key, default)

    def set_shared_data(self, key, value, txdata=False):
        """set value associated to `key` in session data"""
        if txdata:
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
        return self.transaction_data['ecache'][eid]

    def cached_entities(self):
        return self.transaction_data.get('ecache', {}).values()

    def drop_entity_cache(self, eid=None):
        if eid is None:
            self.transaction_data.pop('ecache', None)
        else:
            del self.transaction_data['ecache'][eid]

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

    def execute(self, rql, kwargs=None, eid_key=None, build_descr=True):
        """db-api like method directly linked to the querier execute method.

        See :meth:`cubicweb.dbapi.Cursor.execute` documentation.
        """
        if eid_key is not None:
            warn('[3.8] eid_key is deprecated, you can safely remove this argument',
                 DeprecationWarning, stacklevel=2)
        self.timestamp = time() # update timestamp
        rset = self._execute(self, rql, kwargs, build_descr)
        rset.req = self
        return rset

    def _clear_thread_data(self, reset_pool=True):
        """remove everything from the thread local storage, except pool
        which is explicitly removed by reset_pool, and mode which is set anyway
        by _touch
        """
        try:
            txstore = self.__threaddata.txdata
        except AttributeError:
            pass
        else:
            if reset_pool:
                self._tx_data.pop(txstore.transactionid, None)
                try:
                    del self.__threaddata.txdata
                except AttributeError:
                    pass
            else:
                for name in ('commit_state', 'transaction_data',
                             'pending_operations', '_rewriter'):
                    try:
                        delattr(txstore, name)
                    except AttributeError:
                        continue

    def commit(self, reset_pool=True):
        """commit the current session's transaction"""
        if self.pool is None:
            assert not self.pending_operations
            self._clear_thread_data()
            self._touch()
            self.debug('commit session %s done (no db activity)', self.id)
            return
        cstate = self.commit_state
        if cstate == 'uncommitable':
            raise QueryError('transaction must be rollbacked')
        if cstate is not None:
            return
        # on rollback, an operation should have the following state
        # information:
        # - processed by the precommit/commit event or not
        # - if processed, is it the failed operation
        try:
            # by default, operations are executed with security turned off
            with security_enabled(self, False, False):
                processed = []
                self.commit_state = 'precommit'
                try:
                    while self.pending_operations:
                        operation = self.pending_operations.pop(0)
                        operation.processed = 'precommit'
                        processed.append(operation)
                        operation.handle_event('precommit_event')
                    self.pending_operations[:] = processed
                    self.debug('precommit session %s done', self.id)
                except:
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
                    for operation in reversed(processed):
                        try:
                            operation.handle_event('revertprecommit_event')
                        except:
                            self.critical('error while reverting precommit',
                                          exc_info=True)
                    # XXX use slice notation since self.pending_operations is a
                    # read-only property.
                    self.pending_operations[:] = processed + self.pending_operations
                    self.rollback(reset_pool)
                    raise
                self.pool.commit()
                self.commit_state = 'postcommit'
                while self.pending_operations:
                    operation = self.pending_operations.pop(0)
                    operation.processed = 'postcommit'
                    try:
                        operation.handle_event('postcommit_event')
                    except:
                        self.critical('error while postcommit',
                                      exc_info=sys.exc_info())
                self.debug('postcommit session %s done', self.id)
                return self.transaction_uuid(set=False)
        finally:
            self._touch()
            if reset_pool:
                self.reset_pool(ignoremode=True)
            self._clear_thread_data(reset_pool)

    def rollback(self, reset_pool=True):
        """rollback the current session's transaction"""
        # don't use self.pool, rollback may be called with _closed == True
        pool = getattr(self._threaddata, 'pool', None)
        if pool is None:
            self._clear_thread_data()
            self._touch()
            self.debug('rollback session %s done (no db activity)', self.id)
            return
        try:
            # by default, operations are executed with security turned off
            with security_enabled(self, False, False):
                while self.pending_operations:
                    try:
                        operation = self.pending_operations.pop(0)
                        operation.handle_event('rollback_event')
                    except:
                        self.critical('rollback error', exc_info=sys.exc_info())
                        continue
                pool.rollback()
                self.debug('rollback for session %s done', self.id)
        finally:
            self._touch()
            if reset_pool:
                self.reset_pool(ignoremode=True)
            self._clear_thread_data(reset_pool)

    def close(self):
        """do not close pool on session close, since they are shared now"""
        self._closed = True
        # copy since _threads_in_transaction maybe modified while waiting
        for thread, pool in self._threads_in_transaction.copy():
            if thread is threading.currentThread():
                continue
            self.info('waiting for thread %s', thread)
            # do this loop/break instead of a simple join(10) in case thread is
            # the main thread (in which case it will be removed from
            # self._threads_in_transaction but still be alive...)
            for i in xrange(10):
                thread.join(1)
                if not (thread.isAlive() and
                        (thread, pool) in self._threads_in_transaction):
                    break
            else:
                self.error('thread %s still alive after 10 seconds, will close '
                           'session anyway', thread)
                self._free_thread_pool(thread, pool, force_close=True)
        self.rollback()
        del self.__threaddata
        del self._tx_data

    @property
    def closed(self):
        return not hasattr(self, '_tx_data')

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
        if index is None:
            self.pending_operations.append(operation)
        else:
            self.pending_operations.insert(index, operation)

    # undo support ############################################################

    def undoable_action(self, action, ertype):
        return action in self.undo_actions and not ertype in NO_UNDO_TYPES
        # XXX elif transaction on mark it partial

    def transaction_uuid(self, set=True):
        try:
            return self.transaction_data['tx_uuid']
        except KeyError:
            if not set:
                return
            self.transaction_data['tx_uuid'] = uuid = uuid4().hex
            self.repo.system_source.start_undoable_transaction(self, uuid)
            return uuid

    def transaction_inc_action_counter(self):
        num = self.transaction_data.setdefault('tx_action_count', 0) + 1
        self.transaction_data['tx_action_count'] = num
        return num

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
            return RepeatList(len(result), tuple(description))
        # hard, delegate the work :o)
        return self.manual_build_descr(rqlst, args, result)

    def manual_build_descr(self, rqlst, args, result):
        """build a description for a given result by analysing each row

        XXX could probably be done more efficiently during execution of query
        """
        # not so easy, looks for variable which changes from one solution
        # to another
        unstables = rqlst.get_variable_indices()
        basedescr = []
        todetermine = []
        sampleselect = rqlst.children[0]
        samplesols = sampleselect.solutions[0]
        for i, term in enumerate(sampleselect.selection):
            try:
                ttype = term.get_type(samplesols, args)
            except CoercionError:
                ttype = None
                isfinal = True
            else:
                if ttype is None or ttype == 'Any':
                    ttype = None
                    isfinal = True
                else:
                    isfinal = ttype in BASE_TYPES
            if ttype is None or i in unstables:
                basedescr.append(None)
                todetermine.append( (i, isfinal) )
            else:
                basedescr.append(ttype)
        if not todetermine:
            return RepeatList(len(result), tuple(basedescr))
        return self._build_descr(result, basedescr, todetermine)

    def _build_descr(self, result, basedescription, todetermine):
        description = []
        etype_from_eid = self.describe
        for row in result:
            row_descr = basedescription[:]
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
                        self.critical('wrong eid %s in repository, you should '
                                      'db-check the database' % value)
                        row_descr[index] = row[index] = None
            description.append(tuple(row_descr))
        return description

    # deprecated ###############################################################

    @deprecated("[3.7] execute is now unsafe by default in hooks/operation. You"
                " can also control security with the security_enabled context "
                "manager")
    def unsafe_execute(self, rql, kwargs=None, eid_key=None, build_descr=True,
                       propagate=False):
        """like .execute but with security checking disabled (this method is
        internal to the server, it's not part of the db-api)
        """
        with security_enabled(self, read=False, write=False):
            return self.execute(rql, kwargs, eid_key, build_descr)

    @property
    @deprecated("[3.7] is_super_session is deprecated, test "
                "session.read_security and or session.write_security")
    def is_super_session(self):
        return not self.read_security or not self.write_security

    @deprecated("[3.7] session is actual session")
    def actual_session(self):
        """return the original parent session if any, else self"""
        return self

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

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None


class InternalSession(Session):
    """special session created internaly by the repository"""
    is_internal_session = True
    running_dbapi_query = False

    def __init__(self, repo, cnxprops=None):
        super(InternalSession, self).__init__(InternalManager(), repo, cnxprops,
                                              _id='internal')
        self.user._cw = self # XXX remove when "vreg = user._cw.vreg" hack in entity.py is gone
        self.cnxtype = 'inmemory'
        self.disable_hook_categories('integrity')

    @property
    def pool(self):
        """connections pool, set according to transaction mode for each query"""
        if self.repo.shutting_down:
            self.reset_pool(True)
            raise Exception('repository is shutting down')
        return getattr(self._threaddata, 'pool', None)


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
