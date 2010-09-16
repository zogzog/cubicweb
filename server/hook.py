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
"""Hooks management

This module defined the `Hook` class and registry and a set of abstract classes
for operations.


Hooks are called before / after any individual update of entities / relations
in the repository and on special events such as server startup or shutdown.


Operations may be registered by hooks during a transaction, which will  be
fired when the pool is commited or rollbacked.


Entity hooks (eg before_add_entity, after_add_entity, before_update_entity,
after_update_entity, before_delete_entity, after_delete_entity) all have an
`entity` attribute

Relation (eg before_add_relation, after_add_relation, before_delete_relation,
after_delete_relation) all have `eidfrom`, `rtype`, `eidto` attributes.

Server start/maintenance/stop hooks (eg server_startup, server_maintenance,
server_shutdown) have a `repo` attribute, but *their `_cw` attribute is None*.
The `server_startup` is called on regular startup, while `server_maintenance`
is called on cubicweb-ctl upgrade or shell commands. `server_shutdown` is
called anyway.

Backup/restore hooks (eg server_backup, server_restore) have a `repo` and a
`timestamp` attributes, but *their `_cw` attribute is None*.

Session hooks (eg session_open, session_close) have no special attribute.
"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

from warnings import warn
from logging import getLogger
from itertools import chain

from logilab.common.decorators import classproperty
from logilab.common.deprecation import deprecated, class_renamed
from logilab.common.logging_ext import set_log_methods

from cubicweb import RegistryNotFound
from cubicweb.cwvreg import CWRegistry, VRegistry
from cubicweb.selectors import (objectify_selector, lltrace, ExpectedValueSelector,
                                is_instance)
from cubicweb.appobject import AppObject
from cubicweb.server.session import security_enabled

ENTITIES_HOOKS = set(('before_add_entity',    'after_add_entity',
                      'before_update_entity', 'after_update_entity',
                      'before_delete_entity', 'after_delete_entity'))
RELATIONS_HOOKS = set(('before_add_relation',   'after_add_relation' ,
                       'before_delete_relation','after_delete_relation'))
SYSTEM_HOOKS = set(('server_backup', 'server_restore',
                    'server_startup', 'server_maintenance', 'server_shutdown',
                    'session_open', 'session_close'))
ALL_HOOKS = ENTITIES_HOOKS | RELATIONS_HOOKS | SYSTEM_HOOKS


class HooksRegistry(CWRegistry):
    def initialization_completed(self):
        for appobjects in self.values():
            for cls in appobjects:
                if not cls.enabled:
                    warn('[3.6] %s: enabled is deprecated' % cls)
                    self.unregister(cls)

    def register(self, obj, **kwargs):
        obj.check_events()
        super(HooksRegistry, self).register(obj, **kwargs)

    def call_hooks(self, event, session=None, **kwargs):
        kwargs['event'] = event
        if session is None:
            for hook in sorted(self.possible_objects(session, **kwargs),
                               key=lambda x: x.order):
                hook()
        else:
            # by default, hooks are executed with security turned off
            with security_enabled(session, read=False):
                hooks = sorted(self.possible_objects(session, **kwargs),
                               key=lambda x: x.order)
                with security_enabled(session, write=False):
                    for hook in hooks:
                        hook()

class HooksManager(object):
    def __init__(self, vreg):
        self.vreg = vreg

    def call_hooks(self, event, session=None, **kwargs):
        try:
            self.vreg['%s_hooks' % event].call_hooks(event, session, **kwargs)
        except RegistryNotFound:
            pass # no hooks for this event


for event in ALL_HOOKS:
    VRegistry.REGISTRY_FACTORY['%s_hooks' % event] = HooksRegistry

_MARKER = object()
def entity_oldnewvalue(entity, attr):
    """returns the couple (old attr value, new attr value)

    NOTE: will only work in a before_update_entity hook
    """
    # get new value and remove from local dict to force a db query to
    # fetch old value
    newvalue = entity.pop(attr, _MARKER)
    oldvalue = getattr(entity, attr)
    if newvalue is not _MARKER:
        entity[attr] = newvalue
    else:
        newvalue = oldvalue
    return oldvalue, newvalue


# some hook specific selectors #################################################

@objectify_selector
@lltrace
def enabled_category(cls, req, **kwargs):
    if req is None:
        return True # XXX how to deactivate server startup / shutdown event
    return req.is_hook_activated(cls)

@objectify_selector
@lltrace
def from_dbapi_query(cls, req, **kwargs):
    if req.running_dbapi_query:
        return 1
    return 0

class rechain(object):
    def __init__(self, *iterators):
        self.iterators = iterators
    def __iter__(self):
        return iter(chain(*self.iterators))


class match_rtype(ExpectedValueSelector):
    """accept if parameters specified as initializer arguments are specified
    in named arguments given to the selector

    :param *expected: parameters (eg `basestring`) which are expected to be
                      found in named arguments (kwargs)
    """
    def __init__(self, *expected, **more):
        self.expected = expected
        self.frometypes = more.pop('frometypes', None)
        self.toetypes = more.pop('toetypes', None)

    @lltrace
    def __call__(self, cls, req, *args, **kwargs):
        if kwargs.get('rtype') not in self.expected:
            return 0
        if self.frometypes is not None and \
               req.describe(kwargs['eidfrom'])[0] not in self.frometypes:
            return 0
        if self.toetypes is not None and \
               req.describe(kwargs['eidto'])[0] not in self.toetypes:
            return 0
        return 1


class match_rtype_sets(ExpectedValueSelector):
    """accept if parameters specified as initializer arguments are specified
    in named arguments given to the selector
    """

    def __init__(self, *expected):
        self.expected = expected

    @lltrace
    def __call__(self, cls, req, *args, **kwargs):
        for rel_set in self.expected:
            if kwargs.get('rtype') in rel_set:
                return 1
        return 0


# base class for hook ##########################################################

class Hook(AppObject):
    __select__ = enabled_category()
    # set this in derivated classes
    events = None
    category = None
    order = 0
    # XXX deprecated
    enabled = True

    @classmethod
    def check_events(cls):
        try:
            for event in cls.events:
                if event not in ALL_HOOKS:
                    raise Exception('bad event %s on %s.%s' % (
                        event, cls.__module__, cls.__name__))
        except AttributeError:
            raise
        except TypeError:
            raise Exception('bad .events attribute %s on %s.%s' % (
                cls.events, cls.__module__, cls.__name__))

    @classproperty
    def __registries__(cls):
        cls.check_events()
        return ['%s_hooks' % ev for ev in cls.events]

    @classproperty
    def __regid__(cls):
        warn('[3.6] %s.%s: please specify an id for your hook'
             % (cls.__module__, cls.__name__), DeprecationWarning)
        return str(id(cls))

    @classmethod
    def __registered__(cls, reg):
        super(Hook, cls).__registered__(reg)
        if getattr(cls, 'accepts', None):
            warn('[3.6] %s.%s: accepts is deprecated, define proper __select__'
                 % (cls.__module__, cls.__name__), DeprecationWarning)
            rtypes = []
            for ertype in cls.accepts:
                if ertype.islower():
                    rtypes.append(ertype)
                else:
                    cls.__select__ = cls.__select__ & is_instance(ertype)
            if rtypes:
                cls.__select__ = cls.__select__ & match_rtype(*rtypes)
        return cls

    known_args = set(('entity', 'rtype', 'eidfrom', 'eidto', 'repo', 'timestamp'))
    def __init__(self, req, event, **kwargs):
        for arg in self.known_args:
            if arg in kwargs:
                setattr(self, arg, kwargs.pop(arg))
        super(Hook, self).__init__(req, **kwargs)
        self.event = event

    def __call__(self):
        if hasattr(self, 'call'):
            cls = self.__class__
            warn('[3.6] %s.%s: call is deprecated, implement __call__'
                 % (cls.__module__, cls.__name__), DeprecationWarning)
            if self.event.endswith('_relation'):
                self.call(self._cw, self.eidfrom, self.rtype, self.eidto)
            elif 'delete' in self.event:
                self.call(self._cw, self.entity.eid)
            elif self.event.startswith('server_'):
                self.call(self.repo)
            elif self.event.startswith('session_'):
                self.call(self._cw)
            else:
                self.call(self._cw, self.entity)

set_log_methods(Hook, getLogger('cubicweb.hook'))


# abtract hooks for relation propagation #######################################
# See example usage in hooks of the nosylist cube

class PropagateRelationHook(Hook):
    """propagate some `main_rtype` relation on entities linked as object of
    `subject_relations` or as subject of `object_relations` (the watched
    relations).

    This hook ensure that when one of the watched relation is added, the
    `main_rtype` relation is added to the target entity of the relation.

    You usually want to use the :class:`match_rtype_sets` selector on concret
    classes.
    """
    events = ('after_add_relation',)

    # to set in concrete class
    main_rtype = None
    subject_relations = None
    object_relations = None

    def __call__(self):
        assert self.main_rtype
        for eid in (self.eidfrom, self.eidto):
            etype = self._cw.describe(eid)[0]
            if self.main_rtype not in self._cw.vreg.schema.eschema(etype).subjrels:
                return
        if self.rtype in self.subject_relations:
            meid, seid = self.eidfrom, self.eidto
        else:
            assert self.rtype in self.object_relations
            meid, seid = self.eidto, self.eidfrom
        self._cw.execute(
            'SET E %s P WHERE X %s P, X eid %%(x)s, E eid %%(e)s, NOT E %s P'
            % (self.main_rtype, self.main_rtype, self.main_rtype),
            {'x': meid, 'e': seid})


class PropagateRelationAddHook(Hook):
    """Propagate to entities at the end of watched relations when a `main_rtype`
    relation is added.

    `subject_relations` and `object_relations` attributes should be specified on
    subclasses and are usually shared references with attributes of the same
    name on :class:`PropagateRelationHook`.

    Because of those shared references, you can use `skip_subject_relations` and
    `skip_object_relations` attributes when you don't want to propagate to
    entities linked through some particular relations.
    """
    events = ('after_add_relation',)

    # to set in concrete class (mandatory)
    subject_relations = None
    object_relations = None
    # to set in concrete class (optionaly)
    skip_subject_relations = ()
    skip_object_relations = ()

    def __call__(self):
        eschema = self._cw.vreg.schema.eschema(self._cw.describe(self.eidfrom)[0])
        execute = self._cw.execute
        for rel in self.subject_relations:
            if rel in eschema.subjrels and not rel in self.skip_subject_relations:
                execute('SET R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'X %s R, NOT R %s P' % (self.rtype, rel, self.rtype),
                        {'x': self.eidfrom, 'p': self.eidto})
        for rel in self.object_relations:
            if rel in eschema.objrels and not rel in self.skip_object_relations:
                execute('SET R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'R %s X, NOT R %s P' % (self.rtype, rel, self.rtype),
                        {'x': self.eidfrom, 'p': self.eidto})


class PropagateRelationDelHook(PropagateRelationAddHook):
    """Propagate to entities at the end of watched relations when a `main_rtype`
    relation is deleted.

    This is the opposite of the :class:`PropagateRelationAddHook`, see its
    documentation for how to use this class.
    """
    events = ('after_delete_relation',)

    def __call__(self):
        eschema = self._cw.vreg.schema.eschema(self._cw.describe(self.eidfrom)[0])
        execute = self._cw.execute
        for rel in self.subject_relations:
            if rel in eschema.subjrels and not rel in self.skip_subject_relations:
                execute('DELETE R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'X %s R' % (self.rtype, rel),
                        {'x': self.eidfrom, 'p': self.eidto})
        for rel in self.object_relations:
            if rel in eschema.objrels and not rel in self.skip_object_relations:
                execute('DELETE R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'R %s X' % (self.rtype, rel),
                        {'x': self.eidfrom, 'p': self.eidto})


PropagateSubjectRelationHook = class_renamed(
    'PropagateSubjectRelationHook', PropagateRelationHook,
    '[3.9] PropagateSubjectRelationHook has been renamed to PropagateRelationHook')
PropagateSubjectRelationAddHook = class_renamed(
    'PropagateSubjectRelationAddHook', PropagateRelationAddHook,
    '[3.9] PropagateSubjectRelationAddHook has been renamed to PropagateRelationAddHook')
PropagateSubjectRelationDelHook = class_renamed(
    'PropagateSubjectRelationDelHook', PropagateRelationDelHook,
    '[3.9] PropagateSubjectRelationDelHook has been renamed to PropagateRelationDelHook')


# abstract classes for operation ###############################################

class Operation(object):
    """an operation is triggered on connections pool events related to
    commit / rollback transations. Possible events are:

    precommit:
      the pool is preparing to commit. You shouldn't do anything which
      has to be reverted if the commit fails at this point, but you can freely
      do any heavy computation or raise an exception if the commit can't go.
      You can add some new operations during this phase but their precommit
      event won't be triggered

    commit:
      the pool is preparing to commit. You should avoid to do to expensive
      stuff or something that may cause an exception in this event

    revertcommit:
      if an operation failed while commited, this event is triggered for
      all operations which had their commit event already to let them
      revert things (including the operation which made fail the commit)

    rollback:
      the transaction has been either rollbacked either:
       * intentionaly
       * a precommit event failed, all operations are rollbacked
       * a commit event failed, all operations which are not been triggered for
         commit are rollbacked

    postcommit:
      The transaction is over. All the ORM entities are
      invalid. If you need to work on the database, you need to stard
      a new transaction, for instance using a new internal_session,
      which you will need to commit (and close!).

    order of operations may be important, and is controlled according to
    the insert_index's method output
    """

    def __init__(self, session, **kwargs):
        self.session = session
        self.__dict__.update(kwargs)
        self.register(session)
        # execution information
        self.processed = None # 'precommit', 'commit'
        self.failed = False

    def register(self, session):
        session.add_operation(self, self.insert_index())

    def insert_index(self):
        """return the index of  the lastest instance which is not a
        LateOperation instance
        """
        # faster by inspecting operation in reverse order for heavy transactions
        i = None
        for i, op in enumerate(reversed(self.session.pending_operations)):
            if isinstance(op, (LateOperation, SingleLastOperation)):
                continue
            return -i or None
        if i is None:
            return None
        return -(i + 1)

    def handle_event(self, event):
        """delegate event handling to the opertaion"""
        getattr(self, event)()

    def precommit_event(self):
        """the observed connections pool is preparing a commit"""

    def revertprecommit_event(self):
        """an error went when pre-commiting this operation or a later one

        should revert pre-commit's changes but take care, they may have not
        been all considered if it's this operation which failed
        """

    def commit_event(self):
        """the observed connections pool is commiting"""

    def revertcommit_event(self):
        """an error went when commiting this operation or a later one

        should revert commit's changes but take care, they may have not
        been all considered if it's this operation which failed
        """

    def rollback_event(self):
        """the observed connections pool has been rollbacked

        do nothing by default, the operation will just be removed from the pool
        operation list
        """

    def postcommit_event(self):
        """the observed connections pool has committed"""

    @property
    @deprecated('[3.6] use self.session.user')
    def user(self):
        return self.session.user

    @property
    @deprecated('[3.6] use self.session.repo')
    def repo(self):
        return self.session.repo

    @property
    @deprecated('[3.6] use self.session.vreg.schema')
    def schema(self):
        return self.session.repo.schema

    @property
    @deprecated('[3.6] use self.session.vreg.config')
    def config(self):
        return self.session.repo.config

set_log_methods(Operation, getLogger('cubicweb.session'))

def _container_add(container, value):
    {set: set.add, list: list.append}[container.__class__](container, value)

def set_operation(session, datakey, value, opcls, containercls=set, **opkwargs):
    """Search for session.transaction_data[`datakey`] (expected to be a set):

    * if found, simply append `value`

    * else, initialize it to containercls([`value`]) and instantiate the given
      `opcls` operation class with additional keyword arguments. `containercls`
      is a set by default. Give `list` if you want to keep arrival ordering.

    You should use this instead of creating on operation for each `value`,
    since handling operations becomes coslty on massive data import.
    """
    try:
        _container_add(session.transaction_data[datakey], value)
    except KeyError:
        opcls(session, **opkwargs)
        session.transaction_data[datakey] = containercls()
        _container_add(session.transaction_data[datakey], value)


class LateOperation(Operation):
    """special operation which should be called after all possible (ie non late)
    operations
    """
    def insert_index(self):
        """return the index of  the lastest instance which is not a
        SingleLastOperation instance
        """
        # faster by inspecting operation in reverse order for heavy transactions
        i = None
        for i, op in enumerate(reversed(self.session.pending_operations)):
            if isinstance(op, SingleLastOperation):
                continue
            return -i or None
        if i is None:
            return None
        return -(i + 1)


class SingleOperation(Operation):
    """special operation which should be called once"""
    def register(self, session):
        """override register to handle cases where this operation has already
        been added
        """
        operations = session.pending_operations
        index = self.equivalent_index(operations)
        if index is not None:
            equivalent = operations.pop(index)
        else:
            equivalent = None
        session.add_operation(self, self.insert_index())
        return equivalent

    def equivalent_index(self, operations):
        """return the index of the equivalent operation if any"""
        for i, op in enumerate(reversed(operations)):
            if op.__class__ is self.__class__:
                return -(i+1)
        return None


class SingleLastOperation(SingleOperation):
    """special operation which should be called once and after all other
    operations
    """
    def insert_index(self):
        return None


class SendMailOp(SingleLastOperation):
    def __init__(self, session, msg=None, recipients=None, **kwargs):
        # may not specify msg yet, as
        # `cubicweb.sobjects.supervision.SupervisionMailOp`
        if msg is not None:
            assert recipients
            self.to_send = [(msg, recipients)]
        else:
            assert recipients is None
            self.to_send = []
        super(SendMailOp, self).__init__(session, **kwargs)

    def register(self, session):
        previous = super(SendMailOp, self).register(session)
        if previous:
            self.to_send = previous.to_send + self.to_send

    def commit_event(self):
        self.session.repo.threaded_task(self.sendmails)

    def sendmails(self):
        self.session.vreg.config.sendmails(self.to_send)


class RQLPrecommitOperation(Operation):
    def precommit_event(self):
        execute = self.session.execute
        for rql in self.rqls:
            execute(*rql)


class CleanupNewEidsCacheOp(SingleLastOperation):
    """on rollback of a insert query we have to remove from repository's
    type/source cache eids of entities added in that transaction.

    NOTE: querier's rqlst/solutions cache may have been polluted too with
    queries such as Any X WHERE X eid 32 if 32 has been rollbacked however
    generated queries are unpredictable and analysing all the cache probably
    too expensive. Notice that there is no pb when using args to specify eids
    instead of giving them into the rql string.
    """

    def rollback_event(self):
        """the observed connections pool has been rollbacked,
        remove inserted eid from repository type/source cache
        """
        try:
            self.session.repo.clear_caches(
                self.session.transaction_data['neweids'])
        except KeyError:
            pass

class CleanupDeletedEidsCacheOp(SingleLastOperation):
    """on commit of delete query, we have to remove from repository's
    type/source cache eids of entities deleted in that transaction.
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
