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
"""
Generalities
------------

Paraphrasing the `emacs`_ documentation, let us say that hooks are an important
mechanism for customizing an application. A hook is basically a list of
functions to be called on some well-defined occasion (this is called `running
the hook`).

.. _`emacs`: http://www.gnu.org/software/emacs/manual/html_node/emacs/Hooks.html

Hooks
~~~~~

In |cubicweb|, hooks are subclasses of the :class:`~cubicweb.server.hook.Hook`
class. They are selected over a set of pre-defined `events` (and possibly more
conditions, hooks being selectable appobjects like views and components).  They
should implement a :meth:`~cubicweb.server.hook.Hook.__call__` method that will
be called when the hook is triggered.

There are two families of events: data events (before / after any individual
update of an entity / or a relation in the repository) and server events (such
as server startup or shutdown).  In a typical application, most of the hooks are
defined over data events.

Also, some :class:`~cubicweb.server.hook.Operation` may be registered by hooks,
which will be fired when the transaction is commited or rollbacked.

The purpose of data event hooks is usually to complement the data model as
defined in the schema, which is static by nature and only provide a restricted
builtin set of dynamic constraints, with dynamic or value driven behaviours.
For instance they can serve the following purposes:

* enforcing constraints that the static schema cannot express (spanning several
  entities/relations, exotic value ranges and cardinalities, etc.)

* implement computed attributes

It is functionally equivalent to a `database trigger`_, except that database
triggers definition languages are not standardized, hence not portable (for
instance, PL/SQL works with Oracle and PostgreSQL but not SqlServer nor Sqlite).

.. _`database trigger`: http://en.wikipedia.org/wiki/Database_trigger


.. hint::

   It is a good practice to write unit tests for each hook. See an example in
   :ref:`hook_test`

Operations
~~~~~~~~~~

Operations are subclasses of the :class:`~cubicweb.server.hook.Operation` class
that may be created by hooks and scheduled to happen just before (or after) the
`precommit`, `postcommit` or `rollback` event. Hooks are being fired immediately
on data operations, and it is sometime necessary to delay the actual work down
to a time where all other hooks have run. Also while the order of execution of
hooks is data dependant (and thus hard to predict), it is possible to force an
order on operations.

Operations may be used to:

* implements a validation check which needs that all relations be already set on
  an entity

* process various side effects associated with a transaction such as filesystem
  udpates, mail notifications, etc.


Events
------

Hooks are mostly defined and used to handle `dataflow`_ operations. It
means as data gets in (entities added, updated, relations set or
unset), specific events are issued and the Hooks matching these events
are called.

You can get the event that triggered a hook by accessing its :attr:event
attribute.

.. _`dataflow`: http://en.wikipedia.org/wiki/Dataflow


Entity modification related events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When called for one of these events, hook will have an `entity` attribute
containing the entity instance.

* `before_add_entity`, `before_update_entity`:

  - on those events, you can check what attributes of the entity are modified in
    `entity.cw_edited` (by definition the database is not yet updated in a before
    event)

  - you are allowed to further modify the entity before database
    operations, using the dictionary notation on `cw_edited`. By doing
    this, you'll avoid the need for a whole new rql query processing,
    the only difference is that the underlying backend query (eg
    usually sql) will contains the additional data. For example:

    .. sourcecode:: python

       self.entity.set_attributes(age=42)

    will set the `age` attribute of the entity to 42. But to do so, it will
    generate a rql query that will have to be processed, then trigger some
    hooks, and so one (potentially leading to infinite hook loops or such
    awkward situations..) You can avoid this by doing the modification that way:

    .. sourcecode:: python

       self.entity.cw_edited['age'] = 42

    Here the attribute will simply be edited in the same query that the
    one that triggered the hook.

    Similarly, removing an attribute from `cw_edited` will cancel its
    modification.

  - on `before_update_entity` event, you can access to old and new values in
    this hook, by using `entity.cw_edited.oldnewvalue(attr)`


* `after_add_entity`, `after_update_entity`

  - on those events, you can still check what attributes of the entity are
    modified in `entity.cw_edited` but you can't get anymore the old value, nor
    modify it.

* `before_delete_entity`, `after_delete_entity`

  - on those events, the entity has no `cw_edited` set.


Relation modification related events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When called for one of these events, hook will have `eidfrom`, `rtype`, `eidto`
attributes containing respectivly the eid of the subject entity, the relation
type and the eid of the object entity.

* `before_add_relation`, `before_delete_relation`

  - on those events, you can still get original relation by issuing a rql query

* `after_add_relation`, `after_delete_relation`

This is an occasion to remind us that relations support the add / delete
operation, but no update.


Non data events
~~~~~~~~~~~~~~~

Hooks called on server start/maintenance/stop event (eg `server_startup`,
`server_maintenance`, `server_shutdown`) have a `repo` attribute, but *their
`_cw` attribute is None*.  The `server_startup` is called on regular startup,
while `server_maintenance` is called on cubicweb-ctl upgrade or shell
commands. `server_shutdown` is called anyway.

Hooks called on backup/restore event (eg 'server_backup', 'server_restore') have
a `repo` and a `timestamp` attributes, but *their `_cw` attribute is None*.

Hooks called on session event (eg `session_open`, `session_close`) have no
special attribute.


API
---

Hooks control
~~~~~~~~~~~~~

It is sometimes convenient to explicitly enable or disable some hooks. For
instance if you want to disable some integrity checking hook.  This can be
controlled more finely through the `category` class attribute, which is a string
giving a category name.  One can then uses the
:class:`~cubicweb.server.session.hooks_control` context manager to explicitly
enable or disable some categories.

.. autoclass:: cubicweb.server.session.hooks_control


The existing categories are:

* ``security``, security checking hooks

* ``worfklow``, workflow handling hooks

* ``metadata``, hooks setting meta-data on newly created entities

* ``notification``, email notification hooks

* ``integrity``, data integrity checking hooks

* ``activeintegrity``, data integrity consistency hooks, that you should **never**
  want to disable

* ``syncsession``, hooks synchronizing existing sessions

* ``syncschema``, hooks synchronizing instance schema (including the physical database)

* ``email``, email address handling hooks

* ``bookmark``, bookmark entities handling hooks


Nothing precludes one to invent new categories and use the
:class:`~cubicweb.server.session.hooks_control` context manager to
filter them in or out. Note that ending the transaction with commit()
or rollback() will restore the hooks.


Hooks specific selector
~~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.server.hook.match_rtype
.. autoclass:: cubicweb.server.hook.match_rtype_sets


Hooks and operations classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.server.hook.Hook
.. autoclass:: cubicweb.server.hook.Operation
.. autoclass:: cubicweb.server.hook.LateOperation
.. autoclass:: cubicweb.server.hook.DataOperationMixIn
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
from cubicweb.vregistry import classid
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

def _iter_kwargs(entities, kwargs):
    if not entities:
        yield kwargs
    else:
        for entity in entities:
            kwargs['entity'] = entity
            yield kwargs


class HooksRegistry(CWRegistry):
    def initialization_completed(self):
        for appobjects in self.values():
            for cls in appobjects:
                if not cls.enabled:
                    warn('[3.6] %s: enabled is deprecated' % classid(cls))
                    self.unregister(cls)

    def register(self, obj, **kwargs):
        obj.check_events()
        super(HooksRegistry, self).register(obj, **kwargs)

    def call_hooks(self, event, session=None, **kwargs):
        """call `event` hooks for an entity or a list of entities (passed
        respectively as the `entity` or ``entities`` keyword argument).
        """
        kwargs['event'] = event
        if session is None: # True for events such as server_start
            for hook in sorted(self.possible_objects(session, **kwargs),
                               key=lambda x: x.order):
                hook()
        else:
            if 'entities' in kwargs:
                assert 'entity' not in kwargs, \
                       'can\'t pass "entities" and "entity" arguments simultaneously'
                entities = kwargs.pop('entities')
            else:
                entities = []
            # by default, hooks are executed with security turned off
            with security_enabled(session, read=False):
                for _kwargs in _iter_kwargs(entities, kwargs):
                    hooks = sorted(self.possible_objects(session, **_kwargs),
                                   key=lambda x: x.order)
                    with security_enabled(session, write=False):
                        for hook in hooks:
                            #print hook.category, hook.__regid__
                            hook()

class HooksManager(object):
    def __init__(self, vreg):
        self.vreg = vreg

    def call_hooks(self, event, session=None, **kwargs):
        try:
            registry = self.vreg['%s_hooks' % event]
        except RegistryNotFound:
            return # no hooks for this event
        registry.call_hooks(event, session, **kwargs)


for event in ALL_HOOKS:
    VRegistry.REGISTRY_FACTORY['%s_hooks' % event] = HooksRegistry

@deprecated('[3.10] use entity.cw_edited.oldnewvalue(attr)')
def entity_oldnewvalue(entity, attr):
    return entity.cw_edited.oldnewvalue(attr)


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
        assert not more, "unexpected kwargs in match_rtype: %s" % more

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
    """accept if the relation type is in one of the sets given as initializer
    argument. The goal of this selector is that it keeps reference to original sets,
    so modification to thoses sets are considered by the selector. For instance

    MYSET = set()

    class Hook1(Hook):
        __regid__ = 'hook1'
        __select__ = Hook.__select__ & match_rtype_sets(MYSET)
        ...

    class Hook2(Hook):
        __regid__ = 'hook2'
        __select__ = Hook.__select__ & match_rtype_sets(MYSET)

    Client code can now change `MYSET`, this will changes the selection criteria
    of :class:`Hook1` and :class:`Hook1`.
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
    """Base class for hook.

    Hooks being appobjects like views, they have a `__regid__` and a `__select__`
    class attribute. Like all appobjects, hooks have the `self._cw` attribute which
    represents the current session. In entity hooks, a `self.entity` attribute is
    also present.

    The `events` tuple is used by the base class selector to dispatch the hook
    on the right events. It is possible to dispatch on multiple events at once
    if needed (though take care as hook attribute may vary as described above).

    .. Note::

      Do not forget to extend the base class selectors as in:

      .. sourcecode:: python

          class MyHook(Hook):
            __regid__ = 'whatever'
            __select__ = Hook.__select__ & is_instance('Person')

      else your hooks will be called madly, whatever the event.
    """
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
        warn('[3.6] %s: please specify an id for your hook' % classid(cls),
             DeprecationWarning)
        return str(id(cls))

    @classmethod
    def __registered__(cls, reg):
        super(Hook, cls).__registered__(reg)
        if getattr(cls, 'accepts', None):
            warn('[3.6] %s: accepts is deprecated, define proper __select__'
                 % classid(cls), DeprecationWarning)
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
            warn('[3.6] %s: call is deprecated, implement __call__'
                 % classid(self.__class__), DeprecationWarning)
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
    Notice there are no default behaviour defined when a watched relation is
    deleted, you'll have to handle this by yourself.

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
    """Base class for operations.

    Operation may be instantiated in the hooks' `__call__` method. It always
    takes a session object as first argument (accessible as `.session` from the
    operation instance), and optionally all keyword arguments needed by the
    operation. These keyword arguments will be accessible as attributes from the
    operation instance.

    An operation is triggered on connections pool events related to
    commit / rollback transations. Possible events are:

    * `precommit`:

      the transaction is being prepared for commit. You can freely do any heavy
      computation, raise an exception if the commit can't go. or even add some
      new operations during this phase. If you do anything which has to be
      reverted if the commit fails afterwards (eg altering the file system for
      instance), you'll have to support the 'revertprecommit' event to revert
      things by yourself

    * `revertprecommit`:

      if an operation failed while being pre-commited, this event is triggered
      for all operations which had their 'precommit' event already fired to let
      them revert things (including the operation which made the commit fail)

    * `rollback`:

      the transaction has been either rollbacked either:

       * intentionaly
       * a 'precommit' event failed, in which case all operations are rollbacked
         once 'revertprecommit'' has been called

    * `postcommit`:

      the transaction is over. All the ORM entities accessed by the earlier
      transaction are invalid. If you need to work on the database, you need to
      start a new transaction, for instance using a new internal session, which
      you will need to commit (and close!).

    For an operation to support an event, one has to implement the `<event
    name>_event` method with no arguments.

    The order of operations may be important, and is controlled according to
    the insert_index's method output (whose implementation vary according to the
    base hook class used).
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
        if event == 'postcommit_event' and hasattr(self, 'commit_event'):
            warn('[3.10] %s: commit_event method has been replaced by postcommit_event'
                 % classid(self.__class__), DeprecationWarning)
            self.commit_event()
        getattr(self, event)()

    def precommit_event(self):
        """the observed connections pool is preparing a commit"""

    def revertprecommit_event(self):
        """an error went when pre-commiting this operation or a later one

        should revert pre-commit's changes but take care, they may have not
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


class DataOperationMixIn(object):
    """Mix-in class to ease applying a single operation on a set of data,
    avoiding to create as many as operation as they are individual modification.
    The body of the operation must then iterate over the values that have been
    stored in a single operation instance.

    You should try to use this instead of creating on operation for each
    `value`, since handling operations becomes costly on massive data import.

    Usage looks like:

    .. sourcecode:: python

        class MyEntityHook(Hook):
            __regid__ = 'my.entity.hook'
            __select__ = Hook.__select__ & is_instance('MyEntity')
            events = ('after_add_entity',)

            def __call__(self):
                MyOperation.get_instance(self._cw).add_data(self.entity)


        class MyOperation(DataOperationMixIn, Operation):
            def precommit_event(self):
                for bucket in self.get_data():
                    process(bucket)

    You can modify the `containercls` class attribute, which defines the
    container class that should be instantiated to hold payloads. An instance is
    created on instantiation, and then the :meth:`add_data` method will add the
    given data to the existing container. Default to a `set`. Give `list` if you
    want to keep arrival ordering. You can also use another kind of container
    by redefining :meth:`_build_container` and :meth:`add_data`

    More optional parameters can be given to the `get_instance` operation, that
    will be given to the operation constructer (though those parameters should
    not vary accross different calls to this method for a same operation for
    obvious reason).

    .. Note::
        For sanity reason `get_data` will reset the operation, so that once
        the operation has started its treatment, if some hook want to push
        additional data to this same operation, a new instance will be created
        (else that data has a great chance to be never treated). This implies:

        * you should **always** call `get_data` when starting treatment

        * you should **never** call `get_data` for another reason.
    """
    containercls = set

    @classproperty
    def data_key(cls):
        return ('cw.dataops', cls.__name__)

    @classmethod
    def get_instance(cls, session, **kwargs):
        # no need to lock: transaction_data already comes from thread's local storage
        try:
            return session.transaction_data[cls.data_key]
        except KeyError:
            op = session.transaction_data[cls.data_key] = cls(session, **kwargs)
            return op

    def __init__(self, *args, **kwargs):
        super(DataOperationMixIn, self).__init__(*args, **kwargs)
        self._container = self._build_container()
        self._processed = False

    def __contains__(self, value):
        return value in self._container

    def _build_container(self):
        return self.containercls()

    def add_data(self, data):
        assert not self._processed, """Trying to add data to a closed operation.
Iterating over operation data closed it and should be reserved to precommit /
postcommit method of the operation."""
        _container_add(self._container, data)

    def remove_data(self, data):
        assert not self._processed, """Trying to add data to a closed operation.
Iterating over operation data closed it and should be reserved to precommit /
postcommit method of the operation."""
        self._container.remove(data)

    def get_data(self):
        assert not self._processed, """Trying to get data from a closed operation.
Iterating over operation data closed it and should be reserved to precommit /
postcommit method of the operation."""
        self._processed = True
        op = self.session.transaction_data.pop(self.data_key)
        assert op is self, "Bad handling of operation data, found %s instead of %s for key %s" % (
            op, self, self.data_key)
        return self._container


@deprecated('[3.10] use opcls.get_instance(session, **opkwargs).add_data(value)')
def set_operation(session, datakey, value, opcls, containercls=set, **opkwargs):
    """Function to ease applying a single operation on a set of data, avoiding
    to create as many as operation as they are individual modification. You
    should try to use this instead of creating on operation for each `value`,
    since handling operations becomes coslty on massive data import.

    Arguments are:

    * the `session` object

    * `datakey`, a specially forged key that will be used as key in
      session.transaction_data

    * `value` that is the actual payload of an individual operation

    * `opcls`, the class of the operation. An instance is created on the first
      call for the given key, and then subsequent calls will simply add the
      payload to the container (hence `opkwargs` is only used on that first
      call)

    * `containercls`, the container class that should be instantiated to hold
      payloads.  An instance is created on the first call for the given key, and
      then subsequent calls will add the data to the existing container. Default
      to a set. Give `list` if you want to keep arrival ordering.

    * more optional parameters to give to the operation (here the rtype which do not
      vary accross operations).

    The body of the operation must then iterate over the values that have been mapped
    in the transaction_data dictionary to the forged key, e.g.:

    .. sourcecode:: python

           for value in self._cw.transaction_data.pop(datakey):
               ...

    .. Note::
       **poping** the key from `transaction_data` is not an option, else you may
       get unexpected data loss in some case of nested hooks.
    """
    try:
        # Search for session.transaction_data[`datakey`] (expected to be a set):
        # if found, simply append `value`
        _container_add(session.transaction_data[datakey], value)
    except KeyError:
        # else, initialize it to containercls([`value`]) and instantiate the given
        # `opcls` operation class with additional keyword arguments
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



class SingleLastOperation(Operation):
    """special operation which should be called once and after all other
    operations
    """

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

    def postcommit_event(self):
        self.session.repo.threaded_task(self.sendmails)

    def sendmails(self):
        self.session.vreg.config.sendmails(self.to_send)


class RQLPrecommitOperation(Operation):
    def precommit_event(self):
        execute = self.session.execute
        for rql in self.rqls:
            execute(*rql)


class CleanupNewEidsCacheOp(DataOperationMixIn, SingleLastOperation):
    """on rollback of a insert query we have to remove from repository's
    type/source cache eids of entities added in that transaction.

    NOTE: querier's rqlst/solutions cache may have been polluted too with
    queries such as Any X WHERE X eid 32 if 32 has been rollbacked however
    generated queries are unpredictable and analysing all the cache probably
    too expensive. Notice that there is no pb when using args to specify eids
    instead of giving them into the rql string.
    """
    data_key = 'neweids'

    def rollback_event(self):
        """the observed connections pool has been rollbacked,
        remove inserted eid from repository type/source cache
        """
        try:
            self.session.repo.clear_caches(self.get_data())
        except KeyError:
            pass

class CleanupDeletedEidsCacheOp(DataOperationMixIn, SingleLastOperation):
    """on commit of delete query, we have to remove from repository's
    type/source cache eids of entities deleted in that transaction.
    """
    data_key = 'pendingeids'
    def postcommit_event(self):
        """the observed connections pool has been rollbacked,
        remove inserted eid from repository type/source cache
        """
        try:
            self.session.repo.clear_caches(self.get_data())
        except KeyError:
            pass
