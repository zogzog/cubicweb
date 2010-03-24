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

Server start/stop hooks (eg server_startup, server_shutdown) have a `repo`
attribute, but *their `_cw` attribute is None*.

Backup/restore hooks (eg server_backup, server_restore) have a `repo` and a
`timestamp` attributes, but *their `_cw` attribute is None*.

Session hooks (eg session_open, session_close) have no special attribute.


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from __future__ import with_statement

__docformat__ = "restructuredtext en"

from warnings import warn
from logging import getLogger
from itertools import chain

from logilab.common.decorators import classproperty
from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods

from cubicweb.cwvreg import CWRegistry, VRegistry
from cubicweb.selectors import (objectify_selector, lltrace, ExpectedValueSelector,
                                implements)
from cubicweb.appobject import AppObject
from cubicweb.server.session import security_enabled

ENTITIES_HOOKS = set(('before_add_entity',    'after_add_entity',
                      'before_update_entity', 'after_update_entity',
                      'before_delete_entity', 'after_delete_entity'))
RELATIONS_HOOKS = set(('before_add_relation',   'after_add_relation' ,
                       'before_delete_relation','after_delete_relation'))
SYSTEM_HOOKS = set(('server_backup', 'server_restore',
                    'server_startup', 'server_shutdown',
                    'session_open', 'session_close'))
ALL_HOOKS = ENTITIES_HOOKS | RELATIONS_HOOKS | SYSTEM_HOOKS


class HooksRegistry(CWRegistry):

    def register(self, obj, **kwargs):
        try:
            iter(obj.events)
        except AttributeError:
            raise
        except:
            raise Exception('bad .events attribute %s on %s.%s' % (
                obj.events, obj.__module__, obj.__name__))
        for event in obj.events:
            if event not in ALL_HOOKS:
                raise Exception('bad event %s on %s.%s' % (
                    event, obj.__module__, obj.__name__))
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

VRegistry.REGISTRY_FACTORY['hooks'] = HooksRegistry

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
    return oldvalue, newvalue


# some hook specific selectors #################################################

@objectify_selector
@lltrace
def _bw_is_enabled(cls, req, **kwargs):
    if cls.enabled:
        return 1
    warn('[3.6] %s: enabled is deprecated' % cls)
    return 0

@objectify_selector
@lltrace
def match_event(cls, req, **kwargs):
    if kwargs.get('event') in cls.events:
        return 1
    return 0

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
    __registry__ = 'hooks'
    __select__ = match_event() & enabled_category() & _bw_is_enabled()
    # set this in derivated classes
    events = None
    category = None
    order = 0
    # XXX deprecated
    enabled = True

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
                    cls.__select__ = cls.__select__ & implements(ertype)
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
            warn('[3.6] %s.%s: call is deprecated, implements __call__'
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


# base classes for relation propagation ########################################

class PropagateSubjectRelationHook(Hook):
    """propagate some `main_rtype` relation on entities linked as object of
    `subject_relations` or as subject of `object_relations` (the watched
    relations).

    This hook ensure that when one of the watched relation is added, the
    `main_rtype` relation is added to the target entity of the relation.
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
            'SET E %s P WHERE X %s P, X eid %%(x)s, E eid %%(e)s, NOT E %s P'\
            % (self.main_rtype, self.main_rtype, self.main_rtype),
            {'x': meid, 'e': seid}, ('x', 'e'))


class PropagateSubjectRelationAddHook(Hook):
    """propagate to entities at the end of watched relations when a `main_rtype`
    relation is added
    """
    events = ('after_add_relation',)

    # to set in concrete class
    subject_relations = None
    object_relations = None

    def __call__(self):
        eschema = self._cw.vreg.schema.eschema(self._cw.describe(self.eidfrom)[0])
        execute = self._cw.execute
        for rel in self.subject_relations:
            if rel in eschema.subjrels:
                execute('SET R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'X %s R, NOT R %s P' % (self.rtype, rel, self.rtype),
                        {'x': self.eidfrom, 'p': self.eidto}, 'x')
        for rel in self.object_relations:
            if rel in eschema.objrels:
                execute('SET R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'R %s X, NOT R %s P' % (self.rtype, rel, self.rtype),
                        {'x': self.eidfrom, 'p': self.eidto}, 'x')


class PropagateSubjectRelationDelHook(Hook):
    """propagate to entities at the end of watched relations when a `main_rtype`
    relation is deleted
    """
    events = ('after_delete_relation',)

    # to set in concrete class
    subject_relations = None
    object_relations = None

    def __call__(self):
        eschema = self._cw.vreg.schema.eschema(self._cw.describe(self.eidfrom)[0])
        execute = self._cw.execute
        for rel in self.subject_relations:
            if rel in eschema.subjrels:
                execute('DELETE R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'X %s R' % (self.rtype, rel),
                        {'x': self.eidfrom, 'p': self.eidto}, 'x')
        for rel in self.object_relations:
            if rel in eschema.objrels:
                execute('DELETE R %s P WHERE X eid %%(x)s, P eid %%(p)s, '
                        'R %s X' % (self.rtype, rel),
                        {'x': self.eidfrom, 'p': self.eidto}, 'x')


# abstract classes for operation ###############################################

class Operation(object):
    """an operation is triggered on connections pool events related to
    commit / rollback transations. Possible events are:

    precommit:
      the pool is preparing to commit. You shouldn't do anything things which
      has to be reverted if the commit fail at this point, but you can freely
      do any heavy computation or raise an exception if the commit can't go.
      You can add some new operation during this phase but their precommit
      event won't be triggered

    commit:
      the pool is preparing to commit. You should avoid to do to expensive
      stuff or something that may cause an exception in this event

    revertcommit:
      if an operation failed while commited, this event is triggered for
      all operations which had their commit event already to let them
      revert things (including the operation which made fail the commit)

    rollback:
      the transaction has been either rollbacked either
      * intentionaly
      * a precommit event failed, all operations are rollbacked
      * a commit event failed, all operations which are not been triggered for
        commit are rollbacked

    order of operations may be important, and is controlled according to:
    * operation's class
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
