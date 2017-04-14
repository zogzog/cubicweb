# copyright 2003-2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from __future__ import print_function

import functools
import sys
from uuid import uuid4
from warnings import warn
from contextlib import contextmanager
from logging import getLogger

from six import text_type

from logilab.common.deprecation import deprecated
from logilab.common.registry import objectify_predicate

from cubicweb import QueryError, ProgrammingError, schema, server
from cubicweb import set_log_methods
from cubicweb.req import RequestSessionBase
from cubicweb.rqlrewrite import RQLRewriter
from cubicweb.server.edition import EditedEntity


NO_UNDO_TYPES = schema.SCHEMA_TYPES.copy()
NO_UNDO_TYPES.add('CWCache')
NO_UNDO_TYPES.add('CWSession')
NO_UNDO_TYPES.add('CWDataImport')
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


@deprecated('[3.17] use <object>.allow/deny_all_hooks_but instead')
def hooks_control(obj, mode, *categories):
    assert mode in (HOOKS_ALLOW_ALL, HOOKS_DENY_ALL)
    if mode == HOOKS_ALLOW_ALL:
        return obj.allow_all_hooks_but(*categories)
    elif mode == HOOKS_DENY_ALL:
        return obj.deny_all_hooks_but(*categories)


class _hooks_control(object):
    """context manager to control activated hooks categories.

    If mode is `HOOKS_DENY_ALL`, given hooks categories will
    be enabled.

    If mode is `HOOKS_ALLOW_ALL`, given hooks categories will
    be disabled.

    .. sourcecode:: python

       with _hooks_control(cnx, HOOKS_ALLOW_ALL, 'integrity'):
           # ... do stuff with all but 'integrity' hooks activated

       with _hooks_control(cnx, HOOKS_DENY_ALL, 'integrity'):
           # ... do stuff with none but 'integrity' hooks activated

    This is an internal API, you should rather use
    :meth:`~cubicweb.server.session.Connection.deny_all_hooks_but` or
    :meth:`~cubicweb.server.session.Connection.allow_all_hooks_but`
    Connection methods.
    """
    def __init__(self, cnx, mode, *categories):
        assert mode in (HOOKS_ALLOW_ALL, HOOKS_DENY_ALL)
        self.cnx = cnx
        self.mode = mode
        self.categories = set(categories)
        self.old_mode = None
        self.old_categories = None

    def __enter__(self):
        self.old_mode = self.cnx._hooks_mode
        self.old_categories = self.cnx._hooks_categories
        self.cnx._hooks_mode = self.mode
        self.cnx._hooks_categories = self.categories

    def __exit__(self, exctype, exc, traceback):
        self.cnx._hooks_mode = self.old_mode
        self.cnx._hooks_categories = self.old_categories


@deprecated('[3.17] use <object>.security_enabled instead')
def security_enabled(obj, *args, **kwargs):
    return obj.security_enabled(*args, **kwargs)


class _security_enabled(object):
    """context manager to control security w/ session.execute,

    By default security is disabled on queries executed on the repository
    side.
    """
    def __init__(self, cnx, read=None, write=None):
        self.cnx = cnx
        self.read = read
        self.write = write
        self.oldread = None
        self.oldwrite = None

    def __enter__(self):
        if self.read is None:
            self.oldread = None
        else:
            self.oldread = self.cnx.read_security
            self.cnx.read_security = self.read
        if self.write is None:
            self.oldwrite = None
        else:
            self.oldwrite = self.cnx.write_security
            self.cnx.write_security = self.write

    def __exit__(self, exctype, exc, traceback):
        if self.oldread is not None:
            self.cnx.read_security = self.oldread
        if self.oldwrite is not None:
            self.cnx.write_security = self.oldwrite


HOOKS_ALLOW_ALL = object()
HOOKS_DENY_ALL = object()
DEFAULT_SECURITY = object()  # evaluated to true by design


def _open_only(func):
    """decorator for Connection method that check it is open"""
    @functools.wraps(func)
    def check_open(cnx, *args, **kwargs):
        if not cnx._open:
            raise ProgrammingError('Closed Connection: %s' % cnx)
        return func(cnx, *args, **kwargs)
    return check_open


class Connection(RequestSessionBase):
    """Repository Connection

    Holds all connection related data

    Database connection resources:

      :attr:`hooks_in_progress`, boolean flag telling if the executing
      query is coming from a repoapi connection or is a query from
      within the repository (e.g. started by hooks)

      :attr:`cnxset`, the connections set to use to execute queries on sources.
      If the transaction is read only, the connection set may be freed between
      actual queries. This allows multiple connections with a reasonably low
      connection set pool size.  Control mechanism is detailed below.

    .. automethod:: cubicweb.server.session.Connection.set_cnxset
    .. automethod:: cubicweb.server.session.Connection.free_cnxset

      :attr:`mode`, string telling the connections set handling mode, may be one
      of 'read' (connections set may be freed), 'write' (some write was done in
      the connections set, it can't be freed before end of the transaction),
      'transaction' (we want to keep the connections set during all the
      transaction, with or without writing)

    Shared data:

      :attr:`data` is a dictionary bound to the underlying session,
      who will be present for the life time of the session. This may
      be useful for web clients that rely on the server for managing
      bits of session-scoped data.

      :attr:`transaction_data` is a dictionary cleared at the end of
      the transaction. Hooks and operations may put arbitrary data in
      there.

    Internal state:

      :attr:`pending_operations`, ordered list of operations to be processed on
      commit/rollback

      :attr:`commit_state`, describing the transaction commit state, may be one
      of None (not yet committing), 'precommit' (calling precommit event on
      operations), 'postcommit' (calling postcommit event on operations),
      'uncommitable' (some :exc:`ValidationError` or :exc:`Unauthorized` error
      has been raised during the transaction and so it must be rolled back).

    Hooks controls:

    .. automethod:: cubicweb.server.session.Connection.deny_all_hooks_but
    .. automethod:: cubicweb.server.session.Connection.allow_all_hooks_but

    Security level Management:

      :attr:`read_security` and :attr:`write_security`, boolean flags telling if
      read/write security is currently activated.

    """
    is_request = False
    hooks_in_progress = False

    def __init__(self, repo, user):
        super(Connection, self).__init__(repo.vreg)
        #: connection unique id
        self._open = None

        #: server.Repository object
        self.repo = repo
        self.vreg = self.repo.vreg
        self._execute = self.repo.querier.execute

        # internal (root) session
        self.is_internal_session = isinstance(user, InternalManager)

        #: dict containing arbitrary data cleared at the end of the transaction
        self.transaction_data = {}
        #: ordered list of operations to be processed on commit/rollback
        self.pending_operations = []
        #: (None, 'precommit', 'postcommit', 'uncommitable')
        self.commit_state = None

        # hook control attribute
        # `_hooks_mode`, may be either `HOOKS_ALLOW_ALL` or `HOOKS_DENY_ALL`.
        self._hooks_mode = HOOKS_ALLOW_ALL
        # `_hooks_categories`, when :attr:`_hooks_mode` is `HOOKS_DENY_ALL`,
        # this set contains hooks categories that are enabled ;
        # when :attr:`_hooks_mode` is `HOOKS_ALLOW_ALL`, it contains hooks
        # categories that are disabled.
        self._hooks_categories = set()
        self.pruned_hooks_cache = {}

        # security control attributes
        self._read_security = DEFAULT_SECURITY  # handled by a property
        self.write_security = DEFAULT_SECURITY

        # undo control
        config = repo.config
        if config.creating or config.repairing or self.is_internal_session:
            self.undo_actions = False
        else:
            self.undo_actions = config['undo-enabled']

        # RQLRewriter are not thread safe
        self._rewriter = RQLRewriter(self)

        # other session utility
        if user.login == '__internal_manager__':
            self.user = user
        else:
            self._set_user(user)

    @_open_only
    def get_schema(self):
        """Return the schema currently used by the repository."""
        return self.repo.source_defs()

    @_open_only
    def get_option_value(self, option):
        """Return the value for `option` in the configuration."""
        return self.repo.get_option_value(option)

    # transaction api

    @_open_only
    def undoable_transactions(self, ueid=None, **actionfilters):
        """Return a list of undoable transaction objects by the connection's
        user, ordered by descendant transaction time.

        Managers may filter according to user (eid) who has done the transaction
        using the `ueid` argument. Others will only see their own transactions.

        Additional filtering capabilities is provided by using the following
        named arguments:

        * `etype` to get only transactions creating/updating/deleting entities
          of the given type

        * `eid` to get only transactions applied to entity of the given eid

        * `action` to get only transactions doing the given action (action in
          'C', 'U', 'D', 'A', 'R'). If `etype`, action can only be 'C', 'U' or
          'D'.

        * `public`: when additional filtering is provided, they are by default
          only searched in 'public' actions, unless a `public` argument is given
          and set to false.
        """
        return self.repo.system_source.undoable_transactions(self, ueid,
                                                             **actionfilters)

    @_open_only
    def transaction_info(self, txuuid):
        """Return transaction object for the given uid.

        raise `NoSuchTransaction` if not found or if session's user is
        not allowed (eg not in managers group and the transaction
        doesn't belong to him).
        """
        return self.repo.system_source.tx_info(self, txuuid)

    @_open_only
    def transaction_actions(self, txuuid, public=True):
        """Return an ordered list of actions effectued during that transaction.

        If public is true, return only 'public' actions, i.e. not ones
        triggered under the cover by hooks, else return all actions.

        raise `NoSuchTransaction` if the transaction is not found or
        if the user is not allowed (eg not in managers group).
        """
        return self.repo.system_source.tx_actions(self, txuuid, public)

    @_open_only
    def undo_transaction(self, txuuid):
        """Undo the given transaction. Return potential restoration errors.

        raise `NoSuchTransaction` if not found or if user is not
        allowed (eg not in managers group).
        """
        return self.repo.system_source.undo_transaction(self, txuuid)

    # life cycle handling ####################################################

    def __enter__(self):
        assert not self._open
        self._open = True
        self.cnxset = self.repo.cnxsets.get()
        if self.lang is None:
            self.set_language(self.user.prefered_language())
        return self

    def __exit__(self, exctype=None, excvalue=None, tb=None):
        assert self._open  # actually already open
        self.rollback()
        self._open = False
        self.cnxset.cnxset_freed()
        self.repo.cnxsets.release(self.cnxset)
        self.cnxset = None

    @contextmanager
    def running_hooks_ops(self):
        """this context manager should be called whenever hooks or operations
        are about to be run (but after hook selection)

        It will help the undo logic record pertinent metadata or some
        hooks to run (or not) depending on who/what issued the query.
        """
        prevmode = self.hooks_in_progress
        self.hooks_in_progress = True
        yield
        self.hooks_in_progress = prevmode

    # shared data handling ###################################################

    @property
    @deprecated('[3.25] use transaction_data or req.session.data', stacklevel=3)
    def data(self):
        return self.transaction_data

    @property
    def rql_rewriter(self):
        return self._rewriter

    def clear(self):
        """reset internal data"""
        self.transaction_data = {}
        #: ordered list of operations to be processed on commit/rollback
        self.pending_operations = []
        #: (None, 'precommit', 'postcommit', 'uncommitable')
        self.commit_state = None
        self.pruned_hooks_cache = {}
        self.local_perm_cache.clear()
        self.rewriter = RQLRewriter(self)

    @deprecated('[3.19] cnxset are automatically managed now.'
                ' stop using explicit set and free.')
    def set_cnxset(self):
        pass

    @deprecated('[3.19] cnxset are automatically managed now.'
                ' stop using explicit set and free.')
    def free_cnxset(self, ignoremode=False):
        pass

    @property
    @contextmanager
    @_open_only
    @deprecated('[3.21] a cnxset is automatically set on __enter__ call now.'
                ' stop using .ensure_cnx_set')
    def ensure_cnx_set(self):
        yield

    # Entity cache management #################################################
    #
    # The connection entity cache as held in cnx.transaction_data is removed at the
    # end of the connection (commit and rollback)
    #
    # XXX connection level caching may be a pb with multiple repository
    # instances, but 1. this is probably not the only one :$ and 2. it may be
    # an acceptable risk. Anyway we could activate it or not according to a
    # configuration option

    def set_entity_cache(self, entity):
        """Add `entity` to the connection entity cache"""
        # XXX not using _open_only because before at creation time. _set_user
        # call this function to cache the Connection user.
        if entity.cw_etype != 'CWUser' and not self._open:
            raise ProgrammingError('Closed Connection: %s' % self)
        ecache = self.transaction_data.setdefault('ecache', {})
        ecache.setdefault(entity.eid, entity)

    @_open_only
    def entity_cache(self, eid):
        """get cache entity for `eid`"""
        return self.transaction_data['ecache'][eid]

    @_open_only
    def cached_entities(self):
        """return the whole entity cache"""
        return self.transaction_data.get('ecache', {}).values()

    @_open_only
    def drop_entity_cache(self):
        """Drop the whole entity cache."""
        for entity in self.cached_entities():
            entity.cw_clear_all_caches()
        self.transaction_data.pop('ecache', None)

    # relations handling #######################################################

    @_open_only
    def add_relation(self, fromeid, rtype, toeid):
        """provide direct access to the repository method to add a relation.

        This is equivalent to the following rql query:

          SET X rtype Y WHERE X eid  fromeid, T eid toeid

        without read security check but also all the burden of rql execution.
        You may use this in hooks when you know both eids of the relation you
        want to add.
        """
        self.add_relations([(rtype, [(fromeid, toeid)])])

    @_open_only
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
            for edited in edited_entities.values():
                self.repo.glob_update_entity(self, edited)

    @_open_only
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

    @_open_only
    def update_rel_cache_add(self, subject, rtype, object, symmetric=False):
        self._update_entity_rel_cache_add(subject, rtype, 'subject', object)
        if symmetric:
            self._update_entity_rel_cache_add(object, rtype, 'subject', subject)
        else:
            self._update_entity_rel_cache_add(object, rtype, 'object', subject)

    @_open_only
    def update_rel_cache_del(self, subject, rtype, object, symmetric=False):
        self._update_entity_rel_cache_del(subject, rtype, 'subject', object)
        if symmetric:
            self._update_entity_rel_cache_del(object, rtype, 'object', object)
        else:
            self._update_entity_rel_cache_del(object, rtype, 'object', subject)

    @_open_only
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
            if not isinstance(rset.description, list):  # else description not set
                rset.description = list(rset.description)
            rset.description.append([self.entity_type(targeteid)])
            targetentity = self.entity_from_eid(targeteid)
            if targetentity.cw_rset is None:
                targetentity.cw_rset = rset
                targetentity.cw_row = rset.rowcount
                targetentity.cw_col = 0
            rset.rowcount += 1
            entities.append(targetentity)
            entity._cw_related_cache['%s_%s' % (rtype, role)] = (
                rset, tuple(entities))

    @_open_only
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
            if isinstance(rset.description, list):  # else description not set
                del rset.description[idx]
            del entities[idx]
            rset.rowcount -= 1
            entity._cw_related_cache['%s_%s' % (rtype, role)] = (
                rset, tuple(entities))

    # Tracking of entities added of removed in the transaction ##################

    @_open_only
    def deleted_in_transaction(self, eid):
        """return True if the entity of the given eid is being deleted in the
        current transaction
        """
        return eid in self.transaction_data.get('pendingeids', ())

    @_open_only
    def added_in_transaction(self, eid):
        """return True if the entity of the given eid is being created in the
        current transaction
        """
        return eid in self.transaction_data.get('neweids', ())

    # Operation management ####################################################

    @_open_only
    def add_operation(self, operation, index=None):
        """add an operation to be executed at the end of the transaction"""
        if index is None:
            self.pending_operations.append(operation)
        else:
            self.pending_operations.insert(index, operation)

    # Hooks control ###########################################################

    @_open_only
    def allow_all_hooks_but(self, *categories):
        """Context manager to enable all hooks but those in the given
        categories.
        """
        return _hooks_control(self, HOOKS_ALLOW_ALL, *categories)

    @_open_only
    def deny_all_hooks_but(self, *categories):
        """Context manager to disable all hooks but those in the given
        categories.
        """
        return _hooks_control(self, HOOKS_DENY_ALL, *categories)

    @_open_only
    def is_hook_category_activated(self, category):
        """return a boolean telling if the given category is currently activated
        or not
        """
        if self._hooks_mode is HOOKS_DENY_ALL:
            return category in self._hooks_categories
        return category not in self._hooks_categories

    @_open_only
    def is_hook_activated(self, hook):
        """return a boolean telling if the given hook class is currently
        activated or not
        """
        return self.is_hook_category_activated(hook.category)

    # Security management #####################################################

    @_open_only
    def security_enabled(self, read=None, write=None):
        return _security_enabled(self, read=read, write=write)

    @property
    @_open_only
    def read_security(self):
        return self._read_security

    @read_security.setter
    @_open_only
    def read_security(self, activated):
        self._read_security = activated

    # undo support ############################################################

    @_open_only
    def ertype_supports_undo(self, ertype):
        return self.undo_actions and ertype not in NO_UNDO_TYPES

    @_open_only
    def transaction_uuid(self, set=True):
        uuid = self.transaction_data.get('tx_uuid')
        if set and uuid is None:
            self.transaction_data['tx_uuid'] = uuid = text_type(uuid4().hex)
            self.repo.system_source.start_undoable_transaction(self, uuid)
        return uuid

    @_open_only
    def transaction_inc_action_counter(self):
        num = self.transaction_data.setdefault('tx_action_count', 0) + 1
        self.transaction_data['tx_action_count'] = num
        return num

    # db-api like interface ###################################################

    @_open_only
    def source_defs(self):
        return self.repo.source_defs()

    @_open_only
    def entity_type(self, eid):
        """Return entity type for the entity with id `eid`."""
        return self.repo.type_from_eid(eid, self)

    @deprecated('[3.24] use entity_type(eid) instead')
    @_open_only
    def entity_metas(self, eid):
        """Return a dictionary {type}) for the entity with id `eid`."""
        return {'type': self.repo.type_from_eid(eid, self)}

    # core method #############################################################

    @_open_only
    def execute(self, rql, kwargs=None, build_descr=True):
        """db-api like method directly linked to the querier execute method.

        See :meth:`cubicweb.dbapi.Cursor.execute` documentation.
        """
        rset = self._execute(self, rql, kwargs, build_descr)
        rset.req = self
        return rset

    @_open_only
    def rollback(self, free_cnxset=None, reset_pool=None):
        """rollback the current transaction"""
        if free_cnxset is not None:
            warn('[3.21] free_cnxset is now unneeded',
                 DeprecationWarning, stacklevel=2)
        if reset_pool is not None:
            warn('[3.13] reset_pool is now unneeded',
                 DeprecationWarning, stacklevel=2)
        cnxset = self.cnxset
        assert cnxset is not None
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
                self.debug('rollback for transaction %s done', self)
        finally:
            self.clear()

    @_open_only
    def commit(self, free_cnxset=None, reset_pool=None):
        """commit the current session's transaction"""
        if free_cnxset is not None:
            warn('[3.21] free_cnxset is now unneeded',
                 DeprecationWarning, stacklevel=2)
        if reset_pool is not None:
            warn('[3.13] reset_pool is now unneeded',
                 DeprecationWarning, stacklevel=2)
        assert self.cnxset is not None
        cstate = self.commit_state
        if cstate == 'uncommitable':
            raise QueryError('transaction must be rolled back')
        if cstate == 'precommit':
            self.warn('calling commit in precommit makes no sense; ignoring commit')
            return
        if cstate == 'postcommit':
            self.critical('postcommit phase is not allowed to write to the db; ignoring commit')
            return
        assert cstate is None
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
                    print(self.commit_state, '*' * 20)
                try:
                    with self.running_hooks_ops():
                        while self.pending_operations:
                            operation = self.pending_operations.pop(0)
                            operation.processed = 'precommit'
                            processed.append(operation)
                            if debug:
                                print(operation)
                            operation.handle_event('precommit_event')
                    self.pending_operations[:] = processed
                    self.debug('precommit transaction %s done', self)
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
                        print(self.commit_state, '*' * 20)
                    with self.running_hooks_ops():
                        for operation in reversed(processed):
                            if debug:
                                print(operation)
                            try:
                                operation.handle_event('revertprecommit_event')
                            except BaseException:
                                self.critical('error while reverting precommit',
                                              exc_info=True)
                    # XXX use slice notation since self.pending_operations is a
                    # read-only property.
                    self.pending_operations[:] = processed + self.pending_operations
                    self.rollback()
                    raise
                self.cnxset.commit()
                self.commit_state = 'postcommit'
                if debug:
                    print(self.commit_state, '*' * 20)
                with self.running_hooks_ops():
                    while self.pending_operations:
                        operation = self.pending_operations.pop(0)
                        if debug:
                            print(operation)
                        operation.processed = 'postcommit'
                        try:
                            operation.handle_event('postcommit_event')
                        except BaseException:
                            if self.repo.config.mode == 'test':
                                raise
                            self.critical('error while postcommit',
                                          exc_info=sys.exc_info())
                self.debug('postcommit transaction %s done', self)
                return self.transaction_uuid(set=False)
        finally:
            self.clear()

    # resource accessors ######################################################

    @_open_only
    def call_service(self, regid, **kwargs):
        self.debug('calling service %s', regid)
        service = self.vreg['services'].select(regid, self, **kwargs)
        return service.call(**kwargs)

    @_open_only
    def system_sql(self, sql, args=None, rollback_on_failure=True):
        """return a sql cursor on the system database"""
        source = self.repo.system_source
        try:
            return source.doexec(self, sql, args, rollback=rollback_on_failure)
        except (source.OperationalError, source.InterfaceError):
            if not rollback_on_failure:
                raise
            source.warning("trying to reconnect")
            self.cnxset.reconnect()
            return source.doexec(self, sql, args, rollback=rollback_on_failure)

    @_open_only
    def rtype_eids_rdef(self, rtype, eidfrom, eidto):
        subjtype = self.repo.type_from_eid(eidfrom, self)
        objtype = self.repo.type_from_eid(eidto, self)
        return self.vreg.schema.rschema(rtype).rdefs[(subjtype, objtype)]


class InternalManager(object):
    """a manager user with all access rights used internally for task such as
    bootstrapping the repository or creating regular users according to
    repository content
    """

    def __init__(self, lang='en'):
        self.eid = -1
        self.login = u'__internal_manager__'
        self.properties = {}
        self.groups = set(['managers'])
        self.lang = lang

    def matching_groups(self, groups):
        return 1

    def is_in_group(self, group):
        return True

    def owns(self, eid):
        return True

    def property_value(self, key):
        if key == 'ui.language':
            return self.lang
        return None

    def prefered_language(self, language=None):
        # mock CWUser.prefered_language, mainly for testing purpose
        return self.property_value('ui.language')

    # CWUser compat for notification ###########################################

    def name(self):
        return ''

    class _IEmailable:
        @staticmethod
        def get_email():
            return ''

    def cw_adapt_to(self, iface):
        if iface == 'IEmailable':
            return self._IEmailable
        return None


set_log_methods(Connection, getLogger('cubicweb.session'))
