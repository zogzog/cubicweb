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
    """Ensure that the transaction is either commited or rolled back at exit

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

@deprecated('[3.17] use <object>.allow/deny_all_hooks_but instead')
def hooks_control(obj, mode, *categories):
    assert mode in  (HOOKS_ALLOW_ALL, HOOKS_DENY_ALL)
    if mode == HOOKS_ALLOW_ALL:
        return obj.allow_all_hooks_but(*categories)
    elif mode == HOOKS_DENY_ALL:
        return obj.deny_all_hooks_but(*categories)


class _hooks_control(object):
    """context manager to control activated hooks categories.

    If mode is session.`HOOKS_DENY_ALL`, given hooks categories will
    be enabled.

    If mode is session.`HOOKS_ALLOW_ALL`, given hooks categories will
    be disabled.

    .. sourcecode:: python

       with _hooks_control(self.session, self.session.HOOKS_ALLOW_ALL, 'integrity'):
           # ... do stuff with all but 'integrity' hooks activated

       with _hooks_control(self.session, self.session.HOOKS_DENY_ALL, 'integrity'):
           # ... do stuff with none but 'integrity' hooks activated

    This is an internal api, you should rather use
    :meth:`~cubicweb.server.session.Session.deny_all_hooks_but` or
    :meth:`~cubicweb.server.session.Session.allow_all_hooks_but` session
    methods.
    """
    def __init__(self, session, mode, *categories):
        assert mode in (HOOKS_ALLOW_ALL, HOOKS_DENY_ALL)
        self.session = session
        self.tx = session._tx
        self.mode = mode
        self.categories = categories
        self.oldmode = None
        self.changes = ()

    def __enter__(self):
        self.oldmode = self.tx.hooks_mode
        self.tx.hooks_mode = self.mode
        if self.mode is HOOKS_DENY_ALL:
            self.changes = self.tx.enable_hook_categories(*self.categories)
        else:
            self.changes = self.tx.disable_hook_categories(*self.categories)
        self.tx.ctx_count += 1

    def __exit__(self, exctype, exc, traceback):
        self.tx.ctx_count -= 1
        if self.tx.ctx_count == 0:
            self.session._clear_thread_storage(self.tx)
        else:
            try:
                if self.categories:
                    if self.mode is HOOKS_DENY_ALL:
                        self.tx.disable_hook_categories(*self.categories)
                    else:
                        self.tx.enable_hook_categories(*self.categories)
            finally:
                self.tx.hooks_mode = self.oldmode

@deprecated('[3.17] use <object>.security_enabled instead')
def security_enabled(obj, *args, **kwargs):
    return obj.security_enabled(*args, **kwargs)

class _security_enabled(object):
    """context manager to control security w/ session.execute,

    By default security is disabled on queries executed on the repository
    side.
    """
    def __init__(self, session, read=None, write=None):
        self.session = session
        self.tx = session._tx
        self.read = read
        self.write = write
        self.oldread = None
        self.oldwrite = None

    def __enter__(self):
        if self.read is None:
            self.oldread = None
        else:
            self.oldread = self.tx.read_security
            self.tx.read_security = self.read
        if self.write is None:
            self.oldwrite = None
        else:
            self.oldwrite = self.tx.write_security
            self.tx.write_security = self.write
        self.tx.ctx_count += 1

    def __exit__(self, exctype, exc, traceback):
        self.tx.ctx_count -= 1
        if self.tx.ctx_count == 0:
            self.session._clear_thread_storage(self.tx)
        else:
            if self.oldread is not None:
                self.tx.read_security = self.oldread
            if self.oldwrite is not None:
                self.tx.write_security = self.oldwrite

HOOKS_ALLOW_ALL = object()
HOOKS_DENY_ALL = object()
DEFAULT_SECURITY = object() # evaluated to true by design

class SessionClosedError(RuntimeError):
    pass

class CnxSetTracker(object):
    """Keep track of which transaction use which cnxset.

    There should be one of these object per session (including internal sessions).

    Session objects are responsible of creating their CnxSetTracker object.

    Transactions should use the :meth:`record` and :meth:`forget` to inform the
    tracker of cnxsets they have acquired.

    .. automethod:: cubicweb.server.session.CnxSetTracker.record
    .. automethod:: cubicweb.server.session.CnxSetTracker.forget

    Sessions use the :meth:`close` and :meth:`wait` methods when closing.

    .. automethod:: cubicweb.server.session.CnxSetTracker.close
    .. automethod:: cubicweb.server.session.CnxSetTracker.wait

    This object itself is threadsafe. It also requires caller to acquired its
    lock in some situation.
    """

    def __init__(self):
        self._active = True
        self._condition = threading.Condition()
        self._record = {}

    def __enter__(self):
        return self._condition.__enter__()

    def __exit__(self, *args):
        return self._condition.__exit__(*args)

    def record(self, txid, cnxset):
        """Inform the tracker that a txid has acquired a cnxset

        This method is to be used by Transaction objects.

        This method fails when:
        - The txid already has a recorded cnxset.
        - The tracker is not active anymore.

        Notes about the caller:
        (1) It is responsible for retrieving a cnxset.
        (2) It must be prepared to release the cnxset if the
            `cnxsettracker.forget` call fails.
        (3) It should acquire the tracker lock until the very end of the operation.
        (4) However it must only lock the CnxSetTracker object after having
            retrieved the cnxset to prevent deadlock.

        A typical usage look like::

        cnxset = repo._get_cnxset() # (1)
        try:
            with cnxset_tracker: # (3) and (4)
                cnxset_tracker.record(caller.id, cnxset)
                # (3') operation ends when caller is in expected state only
                caller.cnxset = cnxset
        except Exception:
            repo._free_cnxset(cnxset) # (2)
            raise
        """
        # dubious since the caller is supposed to have acquired it anyway.
        with self._condition:
            if not self._active:
                raise SessionClosedError('Closed')
            old = self._record.get(txid)
            if old is not None:
                raise ValueError('transaction "%s" already has a cnx_set (%r)'
                                 % (txid, old))
            self._record[txid] = cnxset

    def forget(self, txid, cnxset):
        """Inform the tracker that a txid have release a cnxset

        This methode is to be used by Transaction object.

        This method fails when:
        - The cnxset for the txid does not match the recorded one.

        Notes about the caller:
        (1) It is responsible for releasing the cnxset.
        (2) It should acquire the tracker lock during the operation to ensure
            the internal tracker state is always accurate regarding its own state.

        A typical usage look like::

        cnxset = caller.cnxset
        try:
            with cnxset_tracker:
                # (2) you can not have caller.cnxset out of sync with
                #     cnxset_tracker state while unlocked
                caller.cnxset = None
                cnxset_tracker.forget(caller.id, cnxset)
        finally:
            cnxset = repo._free_cnxset(cnxset) # (1)
        """
        with self._condition:
            old = self._record.get(txid, None)
            if old is not cnxset:
                raise ValueError('recorded cnxset for "%s" mismatch: %r != %r'
                                 % (txid, old, cnxset))
            self._record.pop(txid)
            self._condition.notify_all()

    def close(self):
        """Marks the tracker as inactive.

        This method is to be used by Session objects.

        An inactive tracker does not accept new records anymore.
        """
        with self._condition:
            self._active = False

    def wait(self, timeout=10):
        """Wait for all recorded cnxsets to be released

        This method is to be used by Session objects.

        Returns a tuple of transaction ids that remain open.
        """
        with self._condition:
            if  self._active:
                raise RuntimeError('Cannot wait on active tracker.'
                                   ' Call tracker.close() first')
            while self._record and timeout > 0:
                start = time()
                self._condition.wait(timeout)
                timeout -= time() - start
            return tuple(self._record)

class Transaction(object):
    """Repository Transaction

    Holds all transaction related data

    Database connection resources:

      :attr:`running_dbapi_query`, boolean flag telling if the executing query
      is coming from a dbapi connection or is a query from within the repository

      :attr:`cnxset`, the connections set to use to execute queries on sources.
      If the transaction is read only, the connection set may be freed between
      actual queries. This allows multiple transactions with a reasonably low
      connection set pool size.  Control mechanism is detailed below.

    .. automethod:: cubicweb.server.session.Transaction.set_cnxset
    .. automethod:: cubicweb.server.session.Transaction.free_cnxset

      :attr:`mode`, string telling the connections set handling mode, may be one
      of 'read' (connections set may be freed), 'write' (some write was done in
      the connections set, it can't be freed before end of the transaction),
      'transaction' (we want to keep the connections set during all the
      transaction, with or without writing)

    Internal transaction data:

      :attr:`data` is a dictionary containing some shared data
      cleared at the end of the transaction. Hooks and operations may put
      arbitrary data in there, and this may also be used as a communication
      channel between the client and the repository.

      :attr:`pending_operations`, ordered list of operations to be processed on
      commit/rollback

      :attr:`commit_state`, describing the transaction commit state, may be one
      of None (not yet committing), 'precommit' (calling precommit event on
      operations), 'postcommit' (calling postcommit event on operations),
      'uncommitable' (some :exc:`ValidationError` or :exc:`Unauthorized` error
      has been raised during the transaction and so it must be rolled back).

    Hooks controls:

      :attr:`hooks_mode`, may be either `HOOKS_ALLOW_ALL` or `HOOKS_DENY_ALL`.

      :attr:`enabled_hook_cats`, when :attr:`hooks_mode` is
      `HOOKS_DENY_ALL`, this set contains hooks categories that are enabled.

      :attr:`disabled_hook_cats`, when :attr:`hooks_mode` is
      `HOOKS_ALLOW_ALL`, this set contains hooks categories that are disabled.

    Security level Management:

      :attr:`read_security` and :attr:`write_security`, boolean flags telling if
      read/write security is currently activated.

    """

    def __init__(self, txid, session, rewriter):
        #: transaction unique id
        self.transactionid = txid
        #: reentrance handling
        self.ctx_count = 0

        #: server.Repository object
        self.repo = session.repo
        self.vreg = self.repo.vreg

        #: connection handling mode
        self.mode = session.default_mode
        #: connection set used to execute queries on sources
        self._cnxset = None
        #: CnxSetTracker used to report cnxset usage
        self._cnxset_tracker = session._cnxset_tracker
        #: is this transaction from a client or internal to the repo
        self.running_dbapi_query = True

        #: dict containing arbitrary data cleared at the end of the transaction
        self.data = {}
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
        self._read_security = DEFAULT_SECURITY # handled by a property
        self.write_security = DEFAULT_SECURITY

        # undo control
        config = session.repo.config
        if config.creating or config.repairing or session.is_internal_session:
            self.undo_actions = False
        else:
            self.undo_actions = config['undo-enabled']

        # RQLRewriter are not thread safe
        self._rewriter = rewriter

    @property
    def transaction_data(self):
        return self.data

    def clear(self):
        """reset internal data"""
        self.data = {}
        #: ordered list of operations to be processed on commit/rollback
        self.pending_operations = []
        #: (None, 'precommit', 'postcommit', 'uncommitable')
        self.commit_state = None
        self.pruned_hooks_cache = {}

    # Connection Set Management ###############################################
    @property
    def cnxset(self):
        return self._cnxset

    @cnxset.setter
    def cnxset(self, new_cnxset):
        with self._cnxset_tracker:
            old_cnxset = self._cnxset
            if new_cnxset is old_cnxset:
                return #nothing to do
            if old_cnxset is not None:
                self._cnxset = None
                self.ctx_count -= 1
                self._cnxset_tracker.forget(self.transactionid, old_cnxset)
            if new_cnxset is not None:
                self._cnxset_tracker.record(self.transactionid, new_cnxset)
                self._cnxset = new_cnxset
                self.ctx_count += 1

    def set_cnxset(self):
        """the transaction need a connections set to execute some queries"""
        if self.cnxset is None:
            cnxset = self.repo._get_cnxset()
            try:
                self.cnxset = cnxset
                try:
                    cnxset.cnxset_set()
                except:
                    self.cnxset = None
                    raise
            except:
                self.repo._free_cnxset(cnxset)
                raise
        return self.cnxset

    def free_cnxset(self, ignoremode=False):
        """the transaction is no longer using its connections set, at least for some time"""
        # cnxset may be none if no operation has been done since last commit
        # or rollback
        cnxset = self.cnxset
        if cnxset is not None and (ignoremode or self.mode == 'read'):
            try:
                self.cnxset = None
            finally:
                cnxset.cnxset_freed()
                self.repo._free_cnxset(cnxset)


    # Entity cache management #################################################
    #
    # The transaction entity cache as held in tx.data is removed at the
    # end of the transaction (commit and rollback)
    #
    # XXX transaction level caching may be a pb with multiple repository
    # instances, but 1. this is probably not the only one :$ and 2. it may be
    # an acceptable risk. Anyway we could activate it or not according to a
    # configuration option

    def set_entity_cache(self, entity):
        """Add `entity` to the transaction entity cache"""
        ecache = self.data.setdefault('ecache', {})
        ecache.setdefault(entity.eid, entity)

    def entity_cache(self, eid):
        """get cache entity for `eid`"""
        return self.data['ecache'][eid]

    def cached_entities(self):
        """return the whole entity cache"""
        return self.data.get('ecache', {}).values()

    def drop_entity_cache(self, eid=None):
        """drop entity from the cache

        If eid is None, the whole cache is dropped"""
        if eid is None:
            self.data.pop('ecache', None)
        else:
            del self.data['ecache'][eid]

    # Tracking of entities added of removed in the transaction ##################

    def deleted_in_transaction(self, eid):
        """return True if the entity of the given eid is being deleted in the
        current transaction
        """
        return eid in self.data.get('pendingeids', ())

    def added_in_transaction(self, eid):
        """return True if the entity of the given eid is being created in the
        current transaction
        """
        return eid in self.data.get('neweids', ())

    # Operation management ####################################################

    def add_operation(self, operation, index=None):
        """add an operation to be executed at the end of the transaction"""
        if index is None:
            self.pending_operations.append(operation)
        else:
            self.pending_operations.insert(index, operation)

    # Hooks control ###########################################################

    def disable_hook_categories(self, *categories):
        """disable the given hook categories:

        - on HOOKS_DENY_ALL mode, ensure those categories are not enabled
        - on HOOKS_ALLOW_ALL mode, ensure those categories are disabled
        """
        changes = set()
        self.pruned_hooks_cache.clear()
        categories = set(categories)
        if self.hooks_mode is HOOKS_DENY_ALL:
            enabledcats = self.enabled_hook_cats
            changes = enabledcats & categories
            enabledcats -= changes # changes is small hence faster
        else:
            disabledcats = self.disabled_hook_cats
            changes = categories - disabledcats
            disabledcats |= changes # changes is small hence faster
        return tuple(changes)

    def enable_hook_categories(self, *categories):
        """enable the given hook categories:

        - on HOOKS_DENY_ALL mode, ensure those categories are enabled
        - on HOOKS_ALLOW_ALL mode, ensure those categories are not disabled
        """
        changes = set()
        self.pruned_hooks_cache.clear()
        categories = set(categories)
        if self.hooks_mode is HOOKS_DENY_ALL:
            enabledcats = self.enabled_hook_cats
            changes = categories - enabledcats
            enabledcats |= changes # changes is small hence faster
        else:
            disabledcats = self.disabled_hook_cats
            changes = disabledcats & categories
            disabledcats -= changes # changes is small hence faster
        return tuple(changes)

    def is_hook_category_activated(self, category):
        """return a boolean telling if the given category is currently activated
        or not
        """
        if self.hooks_mode is HOOKS_DENY_ALL:
            return category in self.enabled_hook_cats
        return category not in self.disabled_hook_cats

    def is_hook_activated(self, hook):
        """return a boolean telling if the given hook class is currently
        activated or not
        """
        return self.is_hook_category_activated(hook.category)

    # Security management #####################################################
    @property
    def read_security(self):
        return self._read_security

    @read_security.setter
    def read_security(self, activated):
        oldmode = self._read_security
        self._read_security = activated
        # running_dbapi_query used to detect hooks triggered by a 'dbapi' query
        # (eg not issued on the session). This is tricky since we the execution
        # model of a (write) user query is:
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
        # also reset running_dbapi_query to true when we go back to
        # DEFAULT_SECURITY
        self.running_dbapi_query = (oldmode is DEFAULT_SECURITY
                                    or activated is DEFAULT_SECURITY)

    # undo support ############################################################

    def ertype_supports_undo(self, ertype):
        return self.undo_actions and ertype not in NO_UNDO_TYPES

    def transaction_uuid(self, set=True):
        uuid = self.data.get('tx_uuid')
        if set and uuid is None:
            raise KeyError
        return uuid

    def transaction_inc_action_counter(self):
        num = self.data.setdefault('tx_action_count', 0) + 1
        self.data['tx_action_count'] = num
        return num

    # db-api like interface ###################################################

    def source_defs(self):
        return self.repo.source_defs()

    def describe(self, eid, asdict=False):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        metas = self.repo.type_and_source_from_eid(eid, self)
        if asdict:
            return dict(zip(('type', 'source', 'extid', 'asource'), metas))
        # XXX :-1 for cw compat, use asdict=True for full information
        return metas[:-1]

    def source_from_eid(self, eid):
        """return the source where the entity with id <eid> is located"""
        return self.repo.source_from_eid(eid, self)

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

    def rtype_eids_rdef(self, rtype, eidfrom, eidto):
        # use type_and_source_from_eid instead of type_from_eid for optimization
        # (avoid two extra methods call)
        subjtype = self.repo.type_and_source_from_eid(eidfrom, self)[0]
        objtype = self.repo.type_and_source_from_eid(eidto, self)[0]
        return self.vreg.schema.rschema(rtype).rdefs[(subjtype, objtype)]


def tx_attr(attr_name, writable=False):
    """return a property to forward attribute access to transaction.

    This is to be used by session"""
    args = {}
    def attr_from_tx(session):
        return getattr(session._tx, attr_name)
    args['fget'] = attr_from_tx
    if writable:
        def write_attr(session, value):
            return setattr(session._tx, attr_name, value)
        args['fset'] = write_attr
    return property(**args)

def tx_meth(meth_name):
    """return a function forwarding calls to transaction.

    This is to be used by session"""
    def meth_from_tx(session, *args, **kwargs):
        return getattr(session._tx, meth_name)(*args, **kwargs)
    meth_from_tx.__doc__ = getattr(Transaction, meth_name).__doc__
    return meth_from_tx


class Session(RequestSessionBase):
    """Repository user session

    This ties all together:
     * session id,
     * user,
     * connections set,
     * other session data.

    **About session storage / transactions**

    Here is a description of internal session attributes. Besides :attr:`data`
    and :attr:`transaction_data`, you should not have to use attributes
    described here but higher level APIs.

      :attr:`data` is a dictionary containing shared data, used to communicate
      extra information between the client and the repository

      :attr:`_txs` is a dictionary of :class:`TransactionData` instance, one
      for each running transaction. The key is the transaction id. By default
      the transaction id is the thread name but it can be otherwise (per dbapi
      cursor for instance, or per thread name *from another process*).

      :attr:`__threaddata` is a thread local storage whose `tx` attribute
      refers to the proper instance of :class:`Transaction` according to the
      transaction.

    You should not have to use neither :attr:`_tx` nor :attr:`__threaddata`,
    simply access transaction data transparently through the :attr:`_tx`
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

      .. automethod:: cubicweb.server.session.Session.set_cnxset
      .. automethod:: cubicweb.server.session.Session.free_cnxset

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
      has been raised during the transaction and so it must be rolled back).

    .. automethod:: cubicweb.server.session.Session.commit
    .. automethod:: cubicweb.server.session.Session.rollback
    .. automethod:: cubicweb.server.session.Session.close
    .. automethod:: cubicweb.server.session.Session.closed

    Security level Management:

      :attr:`read_security` and :attr:`write_security`, boolean flags telling if
      read/write security is currently activated.

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
        # short cut to querier .execute method
        self._execute = repo.querier.execute
        # shared data, used to communicate extra information between the client
        # and the rql server
        self.data = {}
        # i18n initialization
        self.set_language(user.prefered_language())
        ### internals
        # Transaction of this section
        self._txs = {}
        # Data local to the thread
        self.__threaddata = threading.local()
        self._cnxset_tracker = CnxSetTracker()
        self._closed = False
        self._lock = threading.RLock()

    def __unicode__(self):
        return '<session %s (%s 0x%x)>' % (
            unicode(self.user.login), self.id, id(self))

    def get_tx(self, txid):
        """return the <txid> transaction attached to this session

        Transaction is created if necessary"""
        with self._lock: # no transaction exist with the same id
            try:
                if self.closed:
                    raise SessionClosedError('try to access connections set on a closed session %s' % self.id)
                tx = self._txs[txid]
            except KeyError:
                rewriter = RQLRewriter(self)
                tx = Transaction(txid, self, rewriter)
                self._txs[txid] = tx
        return tx

    def set_tx(self, txid=None):
        """set the default transaction of the current thread to <txid>

        Transaction is created if necessary"""
        if txid is None:
            txid = threading.currentThread().getName()
        self.__threaddata.tx = self.get_tx(txid)

    @property
    def _tx(self):
        """default transaction for current session in current thread"""
        try:
            return self.__threaddata.tx
        except AttributeError:
            self.set_tx()
            return self.__threaddata.tx

    def get_option_value(self, option, foreid=None):
        return self.repo.get_option_value(option, foreid)

    def transaction(self, free_cnxset=True):
        """return context manager to enter a transaction for the session: when
        exiting the `with` block on exception, call `session.rollback()`, else
        call `session.commit()` on normal exit.

        The `free_cnxset` will be given to rollback/commit methods to indicate
        whether the connections set should be freed or not.
        """
        return transaction(self, free_cnxset)


    @deprecated('[3.17] do not use hijack_user. create new Session object')
    def hijack_user(self, user):
        """return a fake request/session using specified user"""
        session = Session(user, self.repo)
        tx = session._tx
        tx.cnxset = self.cnxset
        # share pending_operations, else operation added in the hi-jacked
        # session such as SendMailOp won't ever be processed
        tx.pending_operations = self.pending_operations
        # everything in tx.data should be copied back but the entity
        # type cache we don't want to avoid security pb
        tx.data = self._tx.data.copy()
        tx.data.pop('ecache', None)
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
        with self.security_enabled(False, False):
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
        with self.security_enabled(False, False):
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

    system_sql = tx_meth('system_sql')
    deleted_in_transaction = tx_meth('deleted_in_transaction')
    added_in_transaction = tx_meth('added_in_transaction')
    rtype_eids_rdef = tx_meth('rtype_eids_rdef')

    # security control #########################################################


    def security_enabled(self, read=None, write=None):
        return _security_enabled(self, read=read, write=write)

    read_security = tx_attr('read_security', writable=True)
    write_security = tx_attr('write_security', writable=True)
    running_dbapi_query = tx_attr('running_dbapi_query')

    # hooks activation control #################################################
    # all hooks should be activated during normal execution

    def allow_all_hooks_but(self, *categories):
        return _hooks_control(self, HOOKS_ALLOW_ALL, *categories)
    def deny_all_hooks_but(self, *categories):
        return _hooks_control(self, HOOKS_DENY_ALL, *categories)

    hooks_mode = tx_attr('hooks_mode')

    disabled_hook_categories = tx_attr('disabled_hook_cats')
    enabled_hook_categories = tx_attr('enabled_hook_cats')
    disable_hook_categories = tx_meth('disable_hook_categories')
    enable_hook_categories = tx_meth('enable_hook_categories')
    is_hook_category_activated = tx_meth('is_hook_category_activated')
    is_hook_activated = tx_meth('is_hook_activated')

    # connection management ###################################################

    def keep_cnxset_mode(self, mode):
        """set `mode`, e.g. how the session will keep its connections set:

        * if mode == 'write', the connections set is freed after each read
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

    mode = tx_attr('mode', writable=True)
    commit_state = tx_attr('commit_state', writable=True)

    @property
    def cnxset(self):
        """connections set, set according to transaction mode for each query"""
        if self._closed:
            self.free_cnxset(True)
            raise SessionClosedError('try to access connections set on a closed session %s' % self.id)
        return self._tx.cnxset

    def set_cnxset(self):
        """the session need a connections set to execute some queries"""
        with self._lock: # can probably be removed
            if self._closed:
                self.free_cnxset(True)
                raise SessionClosedError('try to set connections set on a closed session %s' % self.id)
            return self._tx.set_cnxset()
    free_cnxset = tx_meth('free_cnxset')

    def _touch(self):
        """update latest session usage timestamp and reset mode to read"""
        self.timestamp = time()
        self.local_perm_cache.clear() # XXX simply move in tx.data, no?

    # shared data handling ###################################################

    def get_shared_data(self, key, default=None, pop=False, txdata=False):
        """return value associated to `key` in session data"""
        if txdata:
            data = self._tx.data
        else:
            data = self.data
        if pop:
            return data.pop(key, default)
        else:
            return data.get(key, default)

    def set_shared_data(self, key, value, txdata=False):
        """set value associated to `key` in session data"""
        if txdata:
            self._tx.data[key] = value
        else:
            self.data[key] = value

    # server-side service call #################################################

    def call_service(self, regid, async=False, **kwargs):
        return self.repo._call_service_with_session(self, regid, async,
                                                    **kwargs)


    # request interface #######################################################

    @property
    def cursor(self):
        """return a rql cursor"""
        return self

    set_entity_cache  = tx_meth('set_entity_cache')
    entity_cache      = tx_meth('entity_cache')
    cache_entities    = tx_meth('cached_entities')
    drop_entity_cache = tx_meth('drop_entity_cache')

    def from_controller(self):
        """return the id (string) of the controller issuing the request (no
        sense here, always return 'view')
        """
        return 'view'

    source_defs = tx_meth('source_defs')
    describe = tx_meth('describe')
    source_from_eid = tx_meth('source_from_eid')


    def execute(self, rql, kwargs=None, build_descr=True):
        """db-api like method directly linked to the querier execute method.

        See :meth:`cubicweb.dbapi.Cursor.execute` documentation.
        """
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
            tx = self.__threaddata.tx
        except AttributeError:
            pass
        else:
            if free_cnxset:
                self.free_cnxset()
                if tx.ctx_count == 0:
                    self._clear_thread_storage(tx)
                else:
                    self._clear_tx_storage(tx)
            else:
                self._clear_tx_storage(tx)

    def _clear_thread_storage(self, tx):
        self._txs.pop(tx.transactionid, None)
        try:
            del self.__threaddata.tx
        except AttributeError:
            pass

    def _clear_tx_storage(self, tx):
        tx.clear()
        tx._rewriter = RQLRewriter(self)

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
            raise QueryError('transaction must be rolled back')
        if cstate is not None:
            return
        # on rollback, an operation should have the following state
        # information:
        # - processed by the precommit/commit event or not
        # - if processed, is it the failed operation
        debug = server.DEBUG & server.DBG_OPS
        try:
            # by default, operations are executed with security turned off
            with self.security_enabled(False, False):
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
                    # save exception context, it may be clutered below by
                    # exception in revert_* event
                    exc_info = sys.exc_info()
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
                    raise exc_info[0], exc_info[1], exc_info[2]
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
        cnxset = self._tx.cnxset
        if cnxset is None:
            self._clear_thread_data()
            self._touch()
            self.debug('rollback session %s done (no db activity)', self.id)
            return
        try:
            # by default, operations are executed with security turned off
            with self.security_enabled(False, False):
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
        # do not close connections set on session close, since they are shared now
        tracker = self._cnxset_tracker
        with self._lock:
            self._closed = True
        tracker.close()
        self.rollback()
        self.debug('waiting for open transaction of session: %s', self)
        timeout = 10
        pendings = tracker.wait(timeout)
        if pendings:
            self.error('%i transaction still alive after 10 seconds, will close '
                       'session anyway', len(pendings))
            for txid in pendings:
                tx = self._txs.get(txid)
                if tx is not None:
                    # drop tx.cnxset
                    with tracker:
                        try:
                            cnxset = tx.cnxset
                            if cnxset is None:
                                continue
                            tx.cnxset = None
                        except RuntimeError:
                            msg = 'issue while force free of cnxset in %s'
                            self.error(msg, tx)
                    # cnxset.reconnect() do an hard reset of the cnxset
                    # it force it to be freed
                    cnxset.reconnect()
                    self.repo._free_cnxset(cnxset)
        del self.__threaddata
        del self._txs

    @property
    def closed(self):
        return not hasattr(self, '_txs')

    # transaction data/operations management ##################################

    transaction_data = tx_attr('data')
    pending_operations = tx_attr('pending_operations')
    pruned_hooks_cache = tx_attr('pruned_hooks_cache')
    add_operation      = tx_meth('add_operation')

    # undo support ############################################################

    ertype_supports_undo = tx_meth('ertype_supports_undo')
    transaction_inc_action_counter = tx_meth('transaction_inc_action_counter')

    def transaction_uuid(self, set=True):
        try:
            return self._tx.transaction_uuid(set=set)
        except KeyError:
            self._tx.data['tx_uuid'] = uuid = uuid4().hex
            self.repo.system_source.start_undoable_transaction(self, uuid)
            return uuid

    # querier helpers #########################################################

    rql_rewriter = tx_attr('_rewriter')

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

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

Session.HOOKS_ALLOW_ALL = HOOKS_ALLOW_ALL
Session.HOOKS_DENY_ALL = HOOKS_DENY_ALL
Session.DEFAULT_SECURITY = DEFAULT_SECURITY



class InternalSession(Session):
    """special session created internally by the repository"""
    is_internal_session = True
    running_dbapi_query = False

    def __init__(self, repo, cnxprops=None, safe=False):
        super(InternalSession, self).__init__(InternalManager(), repo, cnxprops,
                                              _id='internal')
        self.user._cw = self # XXX remove when "vreg = user._cw.vreg" hack in entity.py is gone
        if not safe:
            self.disable_hook_categories('integrity')
        self.disable_hook_categories('security')
        self._tx.ctx_count += 1

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
        return self._tx.cnxset


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
