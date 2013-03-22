# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
__docformat__ = "restructuredtext en"

import sys
import threading
from time import time
from uuid import uuid4
from warnings import warn

from logilab.common.deprecation import deprecated
from logilab.common.textutils import unormalize
from logilab.common.registry import objectify_predicate

from cubicweb import UnknownEid, QueryError, schema, server
from cubicweb.req import RequestSessionBase
from cubicweb.utils import make_uid
from cubicweb.rqlrewrite import RQLRewriter
from cubicweb.server import ShuttingDown
from cubicweb.server.edition import EditedEntity


NO_UNDO_TYPES = schema.SCHEMA_TYPES.copy()
NO_UNDO_TYPES.add('CWCache')
# is / is_instance_of are usually added by sql hooks except when using
# dataimport.NoHookRQLObjectStore, and we don't want to record them
# anyway in the later case
NO_UNDO_TYPES.add('is')
NO_UNDO_TYPES.add('is_instance_of')
NO_UNDO_TYPES.add('cw_source')
# XXX rememberme,forgotpwd,apycot,vcsfile

@objectify_predicate
def is_user_session(cls, req, **kwargs):
    """return 1 when session is not internal.

    This predicate can only be used repository side only. """
    return not req.is_internal_session

@objectify_predicate
def is_internal_session(cls, req, **kwargs):
    """return 1 when session is not internal.

    This predicate can only be used repository side only. """
    return req.is_internal_session

@objectify_predicate
def repairing(cls, req, **kwargs):
    """return 1 when repository is running in repair mode"""
    return req.vreg.config.repairing


class transaction(object):
    """Ensure that the transaction is either commited or rollbacked at exit

    Context manager to enter a transaction for a session: when exiting the
    `with` block on exception, call `session.rollback()`, else call
    `session.commit()` on normal exit
    """
    def __init__(self, session, free_cnxset=True):
        self.session = session
        self.free_cnxset = free_cnxset

    def __enter__(self):
        # ensure session has a cnxset
        self.session.set_cnxset()

    def __exit__(self, exctype, exc, traceback):
        if exctype:
            self.session.rollback(free_cnxset=self.free_cnxset)
        else:
            self.session.commit(free_cnxset=self.free_cnxset)


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

    This is an internal api, you should rather use
    :meth:`~cubicweb.server.session.Session.deny_all_hooks_but` or
    :meth:`~cubicweb.server.session.Session.allow_all_hooks_but` session
    methods.
    """
    def __init__(self, session, mode, *categories):
        self.session = session
        self.mode = mode
        self.categories = categories

    def __enter__(self):
        self.oldmode, self.changes = self.session.init_hooks_mode_categories(
            self.mode, self.categories)

    def __exit__(self, exctype, exc, traceback):
        self.session.reset_hooks_mode_categories(self.oldmode, self.mode, self.changes)


class security_enabled(object):
    """context manager to control security w/ session.execute,

    By default security is disabled on queries executed on the repository
    side.
    """
    def __init__(self, session, read=None, write=None):
        self.session = session
        self.read = read
        self.write = write

    def __enter__(self):
        self.oldread, self.oldwrite = self.session.init_security(
            self.read, self.write)

    def __exit__(self, exctype, exc, traceback):
        self.session.reset_security(self.oldread, self.oldwrite)

HOOKS_ALLOW_ALL = object()
HOOKS_DENY_ALL = object()
DEFAULT_SECURITY = object() # evaluated to true by design

class Transaction(object):
    """Repository Transaction

    Holds all transaction related data

    Database connections resource:

      :attr:`cnxset`, the connections set to use to execute queries on sources.
      If the transaction is read only, the connection set may be freed between
      actual query. This allows multiple transaction with a reasonable low
      connection set pool size. control mechanism is detailed below

      :attr:`mode`, string telling the connections set handling mode, may be one
      of 'read' (connections set may be freed), 'write' (some write was done in
      the connections set, it can't be freed before end of the transaction),
      'transaction' (we want to keep the connections set during all the
      transaction, with or without writing)

    Internal transaction data:

      :attr:`transaction_data`,is a dictionary containing some shared data
      cleared at the end of the transaction. Hooks and operations may put
      arbitrary data in there, and this may also be used as a communication
      channel between the client and the repository.

      :attr:`pending_operations`, ordered list of operations to be processed on
      commit/rollback

      :attr:`commit_state`, describing the transaction commit state, may be one
      of None (not yet committing), 'precommit' (calling precommit event on
      operations), 'postcommit' (calling postcommit event on operations),
      'uncommitable' (some :exc:`ValidationError` or :exc:`Unauthorized` error
      has been raised during the transaction and so it must be rollbacked).

    Hooks controls:

      :attr:`hooks_mode`, may be either `HOOKS_ALLOW_ALL` or `HOOKS_DENY_ALL`.

      :attr:`enabled_hook_categories`, when :attr:`hooks_mode` is
      `HOOKS_DENY_ALL`, this set contains hooks categories that are enabled.

      :attr:`disabled_hook_categories`, when :attr:`hooks_mode` is
      `HOOKS_ALLOW_ALL`, this set contains hooks categories that are disabled.

    Security level Management:

      :attr:`read_security` and :attr:`write_security`, boolean flags telling if
      read/write security is currently activated.

    """

    def __init__(self, txid, mode='read'):
        #: transaction unique id
        self.transactionid = txid
        #: reentrance handling
        self.ctx_count = 0

        #: connection handling mode
        self.mode = mode
        #: connection set used to execute queries on sources
        self.cnxset = None

        #: dict containing arbitrary data cleared at the end of the transaction
        self.transaction_data = {}
        #: ordered list of operations to be processed on commit/rollback
        self.pending_operations = []
        #: (None, 'precommit', 'postcommit', 'uncommitable')
        self.commit_state = None

        ### hook control attribute
        self.hooks_mode = HOOKS_ALLOW_ALL
        self.disabled_hook_cats = set()
        self.enabled_hook_cats = set()
        self.pruned_hooks_cache = {}


        ### security control attributes
        self.read_security = DEFAULT_SECURITY
        self.write_security = DEFAULT_SECURITY


    def clear(self):
        """reset internal data"""
        self.transaction_data = {}
        #: ordered list of operations to be processed on commit/rollback
        self.pending_operations = []
        #: (None, 'precommit', 'postcommit', 'uncommitable')
        self.commit_state = None
        self.pruned_hooks_cache = {}


class Session(RequestSessionBase):
    """Repository user session

    This tie all together:
     * session id,
     * user,
     * connections set,
     * other session data.

    About session storage / transactions
    ------------------------------------

    Here is a description of internal session attributes. Besides :attr:`data`
    and :attr:`transaction_data`, you should not have to use attributes
    described here but higher level APIs.

      :attr:`data` is a dictionary containing shared data, used to communicate
      extra information between the client and the repository

      :attr:`_tx_data` is a dictionary of :class:`TransactionData` instance, one
      for each running transaction. The key is the transaction id. By default
      the transaction id is the thread name but it can be otherwise (per dbapi
      cursor for instance, or per thread name *from another process*).

      :attr:`__threaddata` is a thread local storage whose `txdata` attribute
      refers to the proper instance of :class:`TransactionData` according to the
      transaction.

      :attr:`_threads_in_transaction` is a set of (thread, connections set)
      referencing threads that currently hold a connections set for the session.
    .. automethod:: cubicweb.server.session.transaction

    You should not have to use neither :attr:`_txdata` nor :attr:`__threaddata`,
    simply access transaction data transparently through the :attr:`_threaddata`
    property. Also, you usually don't have to access it directly since current
    transaction's data may be accessed/modified through properties / methods:

      :attr:`transaction_data`, similarly to :attr:`data`, is a dictionary
      containing some shared data that should be cleared at the end of the
      transaction. Hooks and operations may put arbitrary data in there, and
      this may also be used as a communication channel between the client and
      the repository.

    .. automethod:: cubicweb.server.session.Session.get_shared_data
    .. automethod:: cubicweb.server.session.Session.set_shared_data
    .. automethod:: cubicweb.server.session.Session.added_in_transaction
    .. automethod:: cubicweb.server.session.Session.deleted_in_transaction

    Transaction state information:

      :attr:`running_dbapi_query`, boolean flag telling if the executing query
      is coming from a dbapi connection or is a query from within the repository

      :attr:`cnxset`, the connections set to use to execute queries on sources.
      During a transaction, the connection set may be freed so that is may be
      used by another session as long as no writing is done. This means we can
      have multiple sessions with a reasonably low connections set pool size.

    .. automethod:: cubicweb.server.session.set_cnxset
    .. automethod:: cubicweb.server.session.free_cnxset

      :attr:`mode`, string telling the connections set handling mode, may be one
      of 'read' (connections set may be freed), 'write' (some write was done in
      the connections set, it can't be freed before end of the transaction),
      'transaction' (we want to keep the connections set during all the
      transaction, with or without writing)

      :attr:`pending_operations`, ordered list of operations to be processed on
      commit/rollback

      :attr:`commit_state`, describing the transaction commit state, may be one
      of None (not yet committing), 'precommit' (calling precommit event on
      operations), 'postcommit' (calling postcommit event on operations),
      'uncommitable' (some :exc:`ValidationError` or :exc:`Unauthorized` error
      has been raised during the transaction and so it must be rollbacked).

    .. automethod:: cubicweb.server.session.Session.commit
    .. automethod:: cubicweb.server.session.Session.rollback
    .. automethod:: cubicweb.server.session.Session.close
    .. automethod:: cubicweb.server.session.Session.closed

    Security level Management:

      :attr:`read_security` and :attr:`write_security`, boolean flags telling if
      read/write security is currently activated.

    .. automethod:: cubicweb.server.session.Session.set_write_security
    .. automethod:: cubicweb.server.session.Session.set_read_security
    .. automethod:: cubicweb.server.session.Session.init_security
    .. automethod:: cubicweb.server.session.Session.reset_security
    .. automethod:: cubicweb.server.session.Session.security_enabled

    Hooks Management:

      :attr:`hooks_mode`, may be either `HOOKS_ALLOW_ALL` or `HOOKS_DENY_ALL`.

      :attr:`enabled_hook_categories`, when :attr:`hooks_mode` is
      `HOOKS_DENY_ALL`, this set contains hooks categories that are enabled.

      :attr:`disabled_hook_categories`, when :attr:`hooks_mode` is
      `HOOKS_ALLOW_ALL`, this set contains hooks categories that are disabled.

    .. automethod:: cubicweb.server.session.Session.deny_all_hooks_but
    .. automethod:: cubicweb.server.session.Session.allow_all_hooks_but
    .. automethod:: cubicweb.server.session.Session.is_hook_category_activated
    .. automethod:: cubicweb.server.session.Session.is_hook_activated

    Data manipulation:

    .. automethod:: cubicweb.server.session.Session.add_relation
    .. automethod:: cubicweb.server.session.Session.add_relations
    .. automethod:: cubicweb.server.session.Session.delete_relation

    Other:

    .. automethod:: cubicweb.server.session.Session.call_service



    """
    is_request = False
    is_internal_session = False

    def __init__(self, user, repo, cnxprops=None, _id=None):
        super(Session, self).__init__(repo.vreg)
        self.id = _id or make_uid(unormalize(user.login).encode('UTF8'))
        self.user = user
        self.repo = repo
        self.timestamp = time()
        self.default_mode = 'read'
        # undo support
        if repo.config.creating or repo.config.repairing or self.is_internal_session:
            self.undo_actions = False
        else:
            self.undo_actions = repo.config['undo-enabled']
        # short cut to querier .execute method
        self._execute = repo.querier.execute
        # shared data, used to communicate extra information between the client
        # and the rql server
        self.data = {}
        # i18n initialization
        self.set_language(user.prefered_language())
        # internals
        self._tx_data = {}
        # Data local to the thread
        self.__threaddata = threading.local()
        self._threads_in_transaction = set()
        self._closed = False
        self._closed_lock = threading.Lock()

    def __unicode__(self):
        return '<session %s (%s 0x%x)>' % (
            unicode(self.user.login), self.id, id(self))

    def transaction(self, free_cnxset=True):
        """return context manager to enter a transaction for the session: when
        exiting the `with` block on exception, call `session.rollback()`, else
        call `session.commit()` on normal exit.

        The `free_cnxset` will be given to rollback/commit methods to indicate
        wether the connections set should be freed or not.
        """
        return transaction(self, free_cnxset)

    def set_tx_data(self, txid=None):
        if txid is None:
            txid = threading.currentThread().getName()
        try:
            self.__threaddata.txdata = self._tx_data[txid]
        except KeyError:
            tx = Transaction(txid, self.default_mode)
            self.__threaddata.txdata = self._tx_data[txid] = tx

    @property
    def _threaddata(self):
        try:
            return self.__threaddata.txdata
        except AttributeError:
            self.set_tx_data()
            return self.__threaddata.txdata

    def get_option_value(self, option, foreid=None):
        return self.repo.get_option_value(option, foreid)

    def hijack_user(self, user):
        """return a fake request/session using specified user"""
        session = Session(user, self.repo)
        threaddata = session._threaddata
        threaddata.cnxset = self.cnxset
        # we attributed a connections set, need to update ctx_count else it will be freed
        # while undesired
        threaddata.ctx_count = 1
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
        source = self.cnxset.source('system')
        try:
            return source.doexec(self, sql, args, rollback=rollback_on_failure)
        except (source.OperationalError, source.InterfaceError):
            if not rollback_on_failure:
                raise
            source.warning("trying to reconnect")
            self.cnxset.reconnect(source)
            return source.doexec(self, sql, args, rollback=rollback_on_failure)

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

    def rtype_eids_rdef(self, rtype, eidfrom, eidto):
        # use type_and_source_from_eid instead of type_from_eid for optimization
        # (avoid two extra methods call)
        subjtype = self.repo.type_and_source_from_eid(eidfrom, self)[0]
        objtype = self.repo.type_and_source_from_eid(eidto, self)[0]
        return self.vreg.schema.rschema(rtype).rdefs[(subjtype, objtype)]

    # security control #########################################################


    def security_enabled(self, read=None, write=None):
        return security_enabled(self, read=read, write=write)

    def init_security(self, read, write):
        if read is None:
            oldread = None
        else:
            oldread = self.set_read_security(read)
        if write is None:
            oldwrite = None
        else:
            oldwrite = self.set_write_security(write)
        self._threaddata.ctx_count += 1
        return oldread, oldwrite

    def reset_security(self, read, write):
        txstore = self._threaddata
        txstore.ctx_count -= 1
        if txstore.ctx_count == 0:
            self._clear_thread_storage(txstore)
        else:
            if read is not None:
                self.set_read_security(read)
            if write is not None:
                self.set_write_security(write)

    @property
    def read_security(self):
        """return a boolean telling if read security is activated or not"""
        txstore = self._threaddata
        if txstore is None:
            return DEFAULT_SECURITY
        return txstore.read_security

    def set_read_security(self, activated):
        """[de]activate read security, returning the previous value set for
        later restoration.

        you should usually use the `security_enabled` context manager instead
        of this to change security settings.
        """
        txstore = self._threaddata
        if txstore is None:
            return DEFAULT_SECURITY
        oldmode = txstore.read_security
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
        txstore.dbapi_query = (oldmode is DEFAULT_SECURITY
                               or activated is DEFAULT_SECURITY)
        return oldmode

    @property
    def write_security(self):
        """return a boolean telling if write security is activated or not"""
        txstore = self._threaddata
        if txstore is None:
            return DEFAULT_SECURITY
        return txstore.write_security

    def set_write_security(self, activated):
        """[de]activate write security, returning the previous value set for
        later restoration.

        you should usually use the `security_enabled` context manager instead
        of this to change security settings.
        """
        txstore = self._threaddata
        if txstore is None:
            return DEFAULT_SECURITY
        oldmode = txstore.write_security
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

    def allow_all_hooks_but(self, *categories):
        return hooks_control(self, HOOKS_ALLOW_ALL, *categories)
    def deny_all_hooks_but(self, *categories):
        return hooks_control(self, HOOKS_DENY_ALL, *categories)

    @property
    def hooks_mode(self):
        return self._threaddata.hooks_mode

    def set_hooks_mode(self, mode):
        assert mode is HOOKS_ALLOW_ALL or mode is HOOKS_DENY_ALL
        oldmode = self._threaddata.hooks_mode
        self._threaddata.hooks_mode = mode
        return oldmode

    def init_hooks_mode_categories(self, mode, categories):
        oldmode = self.set_hooks_mode(mode)
        if mode is self.HOOKS_DENY_ALL:
            changes = self.enable_hook_categories(*categories)
        else:
            changes = self.disable_hook_categories(*categories)
        self._threaddata.ctx_count += 1
        return oldmode, changes

    def reset_hooks_mode_categories(self, oldmode, mode, categories):
        txstore = self._threaddata
        txstore.ctx_count -= 1
        if txstore.ctx_count == 0:
            self._clear_thread_storage(txstore)
        else:
            try:
                if categories:
                    if mode is self.HOOKS_DENY_ALL:
                        return self.disable_hook_categories(*categories)
                    else:
                        return self.enable_hook_categories(*categories)
            finally:
                self.set_hooks_mode(oldmode)

    @property
    def disabled_hook_categories(self):
        return self._threaddata.disabled_hook_cats

    @property
    def enabled_hook_categories(self):
        return self._threaddata.enabled_hook_cats

    def disable_hook_categories(self, *categories):
        """disable the given hook categories:

        - on HOOKS_DENY_ALL mode, ensure those categories are not enabled
        - on HOOKS_ALLOW_ALL mode, ensure those categories are disabled
        """
        changes = set()
        self.pruned_hooks_cache.clear()
        if self.hooks_mode is HOOKS_DENY_ALL:
            enabledcats = self.enabled_hook_categories
            for category in categories:
                if category in enabledcats:
                    enabledcats.remove(category)
                    changes.add(category)
        else:
            disabledcats = self.disabled_hook_categories
            for category in categories:
                if category not in disabledcats:
                    disabledcats.add(category)
                    changes.add(category)
        return tuple(changes)

    def enable_hook_categories(self, *categories):
        """enable the given hook categories:

        - on HOOKS_DENY_ALL mode, ensure those categories are enabled
        - on HOOKS_ALLOW_ALL mode, ensure those categories are not disabled
        """
        changes = set()
        self.pruned_hooks_cache.clear()
        if self.hooks_mode is HOOKS_DENY_ALL:
            enabledcats = self.enabled_hook_categories
            for category in categories:
                if category not in enabledcats:
                    enabledcats.add(category)
                    changes.add(category)
        else:
            disabledcats = self.disabled_hook_categories
            for category in categories:
                if category in disabledcats:
                    disabledcats.remove(category)
                    changes.add(category)
        return tuple(changes)

    def is_hook_category_activated(self, category):
        """return a boolean telling if the given category is currently activated
        or not
        """
        if self.hooks_mode is HOOKS_DENY_ALL:
            return category in self.enabled_hook_categories
        return category not in self.disabled_hook_categories

    def is_hook_activated(self, hook):
        """return a boolean telling if the given hook class is currently
        activated or not
        """
        return self.is_hook_category_activated(hook.category)

    # connection management ###################################################

    def keep_cnxset_mode(self, mode):
        """set `mode`, e.g. how the session will keep its connections set:

        * if mode == 'write', the connections set is freed after each ready
          query, but kept until the transaction's end (eg commit or rollback)
          when a write query is detected (eg INSERT/SET/DELETE queries)

        * if mode == 'transaction', the connections set is only freed after the
          transaction's end

        notice that a repository has a limited set of connections sets, and a
        session has to wait for a free connections set to run any rql query
        (unless it already has one set).
        """
        assert mode in ('transaction', 'write')
        if mode == 'transaction':
            self.default_mode = 'transaction'
        else: # mode == 'write'
            self.default_mode = 'read'

    def get_mode(self):
        return self._threaddata.mode
    def set_mode(self, value):
        self._threaddata.mode = value
    mode = property(get_mode, set_mode,
                    doc='transaction mode (read/write/transaction), resetted to'
                    ' default_mode on commit / rollback')

    def get_commit_state(self):
        return self._threaddata.commit_state
    def set_commit_state(self, value):
        self._threaddata.commit_state = value
    commit_state = property(get_commit_state, set_commit_state)

    @property
    def cnxset(self):
        """connections set, set according to transaction mode for each query"""
        if self._closed:
            self.free_cnxset(True)
            raise Exception('try to access connections set on a closed session %s' % self.id)
        return getattr(self._threaddata, 'cnxset', None)

    def set_cnxset(self):
        """the session need a connections set to execute some queries"""
        with self._closed_lock:
            if self._closed:
                self.free_cnxset(True)
                raise Exception('try to set connections set on a closed session %s' % self.id)
            if self.cnxset is None:
                # get connections set first to avoid race-condition
                self._threaddata.cnxset = cnxset = self.repo._get_cnxset()
                self._threaddata.ctx_count += 1
                try:
                    cnxset.cnxset_set()
                except Exception:
                    self._threaddata.cnxset = None
                    self.repo._free_cnxset(cnxset)
                    raise
                self._threads_in_transaction.add(
                    (threading.currentThread(), cnxset) )
            return self._threaddata.cnxset

    def _free_thread_cnxset(self, thread, cnxset, force_close=False):
        try:
            self._threads_in_transaction.remove( (thread, cnxset) )
        except KeyError:
            # race condition on cnxset freeing (freed by commit or rollback vs
            # close)
            pass
        else:
            if force_close:
                cnxset.reconnect()
            else:
                cnxset.cnxset_freed()
            # free cnxset once everything is done to avoid race-condition
            self.repo._free_cnxset(cnxset)

    def free_cnxset(self, ignoremode=False):
        """the session is no longer using its connections set, at least for some time"""
        # cnxset may be none if no operation has been done since last commit
        # or rollback
        cnxset = getattr(self._threaddata, 'cnxset', None)
        if cnxset is not None and (ignoremode or self.mode == 'read'):
            # even in read mode, we must release the current transaction
            self._free_thread_cnxset(threading.currentThread(), cnxset)
            del self._threaddata.cnxset
            self._threaddata.ctx_count -= 1

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

    # server-side service call #################################################

    def call_service(self, regid, async=False, **kwargs):
        return self.repo.call_service(self.id, regid, async, **kwargs)


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

    def describe(self, eid, asdict=False):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        metas = self.repo.type_and_source_from_eid(eid, self)
        if asdict:
            return dict(zip(('type', 'source', 'extid', 'asource'), metas))
       # XXX :-1 for cw compat, use asdict=True for full information
        return metas[:-1]

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

    def _clear_thread_data(self, free_cnxset=True):
        """remove everything from the thread local storage, except connections set
        which is explicitly removed by free_cnxset, and mode which is set anyway
        by _touch
        """
        try:
            txstore = self.__threaddata.txdata
        except AttributeError:
            pass
        else:
            if free_cnxset:
                self.free_cnxset()
                if txstore.ctx_count == 0:
                    self._clear_thread_storage(txstore)
                else:
                    self._clear_tx_storage(txstore)
            else:
                self._clear_tx_storage(txstore)

    def _clear_thread_storage(self, txstore):
        self._tx_data.pop(txstore.transactionid, None)
        try:
            del self.__threaddata.txdata
        except AttributeError:
            pass

    def _clear_tx_storage(self, txstore):
        txstore.clear()
        try:
            del txstore._rewriter
        except AttributeError:
            pass

    def commit(self, free_cnxset=True, reset_pool=None):
        """commit the current session's transaction"""
        if reset_pool is not None:
            warn('[3.13] use free_cnxset argument instead for reset_pool',
                 DeprecationWarning, stacklevel=2)
            free_cnxset = reset_pool
        if self.cnxset is None:
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
        debug = server.DEBUG & server.DBG_OPS
        try:
            # by default, operations are executed with security turned off
            with security_enabled(self, False, False):
                processed = []
                self.commit_state = 'precommit'
                if debug:
                    print self.commit_state, '*' * 20
                try:
                    while self.pending_operations:
                        operation = self.pending_operations.pop(0)
                        operation.processed = 'precommit'
                        processed.append(operation)
                        if debug:
                            print operation
                        operation.handle_event('precommit_event')
                    self.pending_operations[:] = processed
                    self.debug('precommit session %s done', self.id)
                except BaseException:
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
                    if debug:
                        print self.commit_state, '*' * 20
                    for operation in reversed(processed):
                        if debug:
                            print operation
                        try:
                            operation.handle_event('revertprecommit_event')
                        except BaseException:
                            self.critical('error while reverting precommit',
                                          exc_info=True)
                    # XXX use slice notation since self.pending_operations is a
                    # read-only property.
                    self.pending_operations[:] = processed + self.pending_operations
                    self.rollback(free_cnxset)
                    raise
                self.cnxset.commit()
                self.commit_state = 'postcommit'
                if debug:
                    print self.commit_state, '*' * 20
                while self.pending_operations:
                    operation = self.pending_operations.pop(0)
                    if debug:
                        print operation
                    operation.processed = 'postcommit'
                    try:
                        operation.handle_event('postcommit_event')
                    except BaseException:
                        self.critical('error while postcommit',
                                      exc_info=sys.exc_info())
                self.debug('postcommit session %s done', self.id)
                return self.transaction_uuid(set=False)
        finally:
            self._touch()
            if free_cnxset:
                self.free_cnxset(ignoremode=True)
            self._clear_thread_data(free_cnxset)

    def rollback(self, free_cnxset=True, reset_pool=None):
        """rollback the current session's transaction"""
        if reset_pool is not None:
            warn('[3.13] use free_cnxset argument instead for reset_pool',
                 DeprecationWarning, stacklevel=2)
            free_cnxset = reset_pool
        # don't use self.cnxset, rollback may be called with _closed == True
        cnxset = getattr(self._threaddata, 'cnxset', None)
        if cnxset is None:
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
                    except BaseException:
                        self.critical('rollback error', exc_info=sys.exc_info())
                        continue
                cnxset.rollback()
                self.debug('rollback for session %s done', self.id)
        finally:
            self._touch()
            if free_cnxset:
                self.free_cnxset(ignoremode=True)
            self._clear_thread_data(free_cnxset)

    def close(self):
        """do not close connections set on session close, since they are shared now"""
        with self._closed_lock:
            self._closed = True
        # copy since _threads_in_transaction maybe modified while waiting
        for thread, cnxset in self._threads_in_transaction.copy():
            if thread is threading.currentThread():
                continue
            self.info('waiting for thread %s', thread)
            # do this loop/break instead of a simple join(10) in case thread is
            # the main thread (in which case it will be removed from
            # self._threads_in_transaction but still be alive...)
            for i in xrange(10):
                thread.join(1)
                if not (thread.isAlive() and
                        (thread, cnxset) in self._threads_in_transaction):
                    break
            else:
                self.error('thread %s still alive after 10 seconds, will close '
                           'session anyway', thread)
                self._free_thread_cnxset(thread, cnxset, force_close=True)
        self.rollback()
        del self.__threaddata
        del self._tx_data

    @property
    def closed(self):
        return not hasattr(self, '_tx_data')

    # transaction data/operations management ##################################

    @property
    def transaction_data(self):
        return self._threaddata.transaction_data

    @property
    def pending_operations(self):
        return self._threaddata.pending_operations

    @property
    def pruned_hooks_cache(self):
        return self._threaddata.pruned_hooks_cache

    def add_operation(self, operation, index=None):
        """add an operation"""
        if index is None:
            self.pending_operations.append(operation)
        else:
            self.pending_operations.insert(index, operation)

    # undo support ############################################################

    def ertype_supports_undo(self, ertype):
        return self.undo_actions  and ertype not in NO_UNDO_TYPES

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

    # deprecated ###############################################################

    @deprecated('[3.13] use getattr(session.rtype_eids_rdef(rtype, eidfrom, eidto), prop)')
    def schema_rproperty(self, rtype, eidfrom, eidto, rprop):
        return getattr(self.rtype_eids_rdef(rtype, eidfrom, eidto), rprop)

    @property
    @deprecated("[3.13] use .cnxset attribute instead of .pool")
    def pool(self):
        return self.cnxset

    @deprecated("[3.13] use .set_cnxset() method instead of .set_pool()")
    def set_pool(self):
        return self.set_cnxset()

    @deprecated("[3.13] use .free_cnxset() method instead of .reset_pool()")
    def reset_pool(self):
        return self.free_cnxset()

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

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

Session.HOOKS_ALLOW_ALL = HOOKS_ALLOW_ALL
Session.HOOKS_DENY_ALL = HOOKS_DENY_ALL
Session.DEFAULT_SECURITY = DEFAULT_SECURITY



class InternalSession(Session):
    """special session created internaly by the repository"""
    is_internal_session = True
    running_dbapi_query = False

    def __init__(self, repo, cnxprops=None, safe=False):
        super(InternalSession, self).__init__(InternalManager(), repo, cnxprops,
                                              _id='internal')
        self.user._cw = self # XXX remove when "vreg = user._cw.vreg" hack in entity.py is gone
        if not safe:
            self.disable_hook_categories('integrity')

    def __enter__(self):
        return self

    def __exit__(self, exctype, excvalue, tb):
        self.close()

    @property
    def cnxset(self):
        """connections set, set according to transaction mode for each query"""
        if self.repo.shutting_down:
            self.free_cnxset(True)
            raise ShuttingDown('repository is shutting down')
        return getattr(self._threaddata, 'cnxset', None)


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

    def property_value(self, key):
        if key == 'ui.language':
            return 'en'
        return None

    def prefered_language(self, language=None):
        # mock CWUser.prefered_language, mainly for testing purpose
        return self.property_value('ui.language')

    # CWUser compat for notification ###########################################

    def name(self):
        return 'cubicweb'

    class _IEmailable:
        @staticmethod
        def get_email():
            return ''

    def cw_adapt_to(self, iface):
        if iface == 'IEmailable':
            return self._IEmailable
        return None

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Session, getLogger('cubicweb.session'))
