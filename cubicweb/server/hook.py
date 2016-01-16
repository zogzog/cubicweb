# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
which will be fired when the transaction is commited or rolled back.

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
that may be created by hooks and scheduled to happen on `precommit`,
`postcommit` or `rollback` event (i.e. respectivly before/after a commit or
before a rollback of a transaction).

Hooks are being fired immediately on data operations, and it is sometime
necessary to delay the actual work down to a time where we can expect all
information to be there, or when all other hooks have run (though take case
since operations may themselves trigger hooks). Also while the order of
execution of hooks is data dependant (and thus hard to predict), it is possible
to force an order on operations.

So, for such case where you may miss some information that may be set later in
the transaction, you should instantiate an operation in the hook.

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

You can get the event that triggered a hook by accessing its `event`
attribute.

.. _`dataflow`: http://en.wikipedia.org/wiki/Dataflow


Entity modification related events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When called for one of these events, hook will have an `entity` attribute
containing the entity instance.

- `before_add_entity`, `before_update_entity`:

  On those events, you can access the modified attributes of the entity using
  the `entity.cw_edited` dictionary. The values can be modified and the old
  values can be retrieved.

  If you modify the `entity.cw_edited` dictionary in the hook, that is before
  the database operations take place, you will avoid the need to process a whole
  new rql query and the underlying backend query (eg usually sql) will contain
  the modified data. For example:

  .. sourcecode:: python

     self.entity.cw_edited['age'] = 42

  will modify the age before it is written to the backend storage.

  Similarly, removing an attribute from `cw_edited` will cancel its
  modification:

  .. sourcecode:: python

     del self.entity.cw_edited['age']

  On a `before_update_entity` event, you can access the old and new values:

  .. sourcecode:: python

     old, new = entity.cw_edited.oldnewvalue('age')

- `after_add_entity`, `after_update_entity`

  On those events, you can get the list of attributes that were modified using
  the `entity.cw_edited` dictionary, but you can not modify it or get the old
  value of an attribute.

- `before_delete_entity`, `after_delete_entity`

  On those events, the entity has no `cw_edited` dictionary.

.. note:: `self.entity.cw_set(age=42)` will set the `age` attribute to
  42. But to do so, it will generate a rql query that will have to be processed,
  hence may trigger some hooks, etc. This could lead to infinitely looping hooks.

Relation modification related events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When called for one of these events, hook will have `eidfrom`, `rtype`, `eidto`
attributes containing respectively the eid of the subject entity, the relation
type and the eid of the object entity.

* `before_add_relation`, `before_delete_relation`

  On those events, you can still get the original relation by issuing a rql query.

* `after_add_relation`, `after_delete_relation`

Specific selectors are shipped for these kinds of events, see in particular
:class:`~cubicweb.server.hook.match_rtype`.

Also note that relations can be added or deleted, but not updated.

Non data events
~~~~~~~~~~~~~~~

Hooks called on server start/maintenance/stop event (e.g.
`server_startup`, `server_maintenance`, `before_server_shutdown`,
`server_shutdown`) have a `repo` attribute, but *their `_cw` attribute
is None*.  The `server_startup` is called on regular startup, while
`server_maintenance` is called on cubicweb-ctl upgrade or shell
commands. `server_shutdown` is called anyway but connections to the
native source is impossible; `before_server_shutdown` handles that.

Hooks called on backup/restore event (eg `server_backup`,
`server_restore`) have a `repo` and a `timestamp` attributes, but
*their `_cw` attribute is None*.

Hooks called on session event (eg `session_open`, `session_close`) have no
special attribute.


API
---

Hooks control
~~~~~~~~~~~~~

It is sometimes convenient to explicitly enable or disable some hooks. For
instance if you want to disable some integrity checking hook. This can be
controlled more finely through the `category` class attribute, which is a string
giving a category name.  One can then uses the
:meth:`~cubicweb.server.session.Connection.deny_all_hooks_but` and
:meth:`~cubicweb.server.session.Connection.allow_all_hooks_but` context managers to
explicitly enable or disable some categories.

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


Nothing precludes one to invent new categories and use existing mechanisms to
filter them in or out.


Hooks specific predicates
~~~~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.server.hook.match_rtype
.. autoclass:: cubicweb.server.hook.match_rtype_sets


Hooks and operations classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.server.hook.Hook
.. autoclass:: cubicweb.server.hook.Operation
.. autoclass:: cubicweb.server.hook.LateOperation
.. autoclass:: cubicweb.server.hook.DataOperationMixIn
"""
from __future__ import print_function

__docformat__ = "restructuredtext en"

from warnings import warn
from logging import getLogger
from itertools import chain

from logilab.common.decorators import classproperty, cached
from logilab.common.deprecation import deprecated, class_renamed
from logilab.common.logging_ext import set_log_methods
from logilab.common.registry import (NotPredicate, OrPredicate,
                                     objectify_predicate)

from cubicweb import RegistryNotFound, server
from cubicweb.cwvreg import CWRegistry, CWRegistryStore
from cubicweb.predicates import ExpectedValuePredicate, is_instance
from cubicweb.appobject import AppObject

ENTITIES_HOOKS = set(('before_add_entity',    'after_add_entity',
                      'before_update_entity', 'after_update_entity',
                      'before_delete_entity', 'after_delete_entity'))
RELATIONS_HOOKS = set(('before_add_relation',   'after_add_relation' ,
                       'before_delete_relation','after_delete_relation'))
SYSTEM_HOOKS = set(('server_backup', 'server_restore',
                    'server_startup', 'server_maintenance',
                    'server_shutdown', 'before_server_shutdown',
                    'session_open', 'session_close'))
ALL_HOOKS = ENTITIES_HOOKS | RELATIONS_HOOKS | SYSTEM_HOOKS

def _iter_kwargs(entities, eids_from_to, kwargs):
    if not entities and not eids_from_to:
        yield kwargs
    elif entities:
        for entity in entities:
            kwargs['entity'] = entity
            yield kwargs
    else:
        for subject, object in eids_from_to:
            kwargs.update({'eidfrom': subject, 'eidto': object})
            yield kwargs


class HooksRegistry(CWRegistry):

    def register(self, obj, **kwargs):
        obj.check_events()
        super(HooksRegistry, self).register(obj, **kwargs)

    def call_hooks(self, event, cnx=None, **kwargs):
        """call `event` hooks for an entity or a list of entities (passed
        respectively as the `entity` or ``entities`` keyword argument).
        """
        kwargs['event'] = event
        if cnx is None: # True for events such as server_start
            for hook in sorted(self.possible_objects(cnx, **kwargs),
                               key=lambda x: x.order):
                hook()
        else:
            if 'entities' in kwargs:
                assert 'entity' not in kwargs, \
                       'can\'t pass "entities" and "entity" arguments simultaneously'
                assert 'eids_from_to' not in kwargs, \
                       'can\'t pass "entities" and "eids_from_to" arguments simultaneously'
                entities = kwargs.pop('entities')
                eids_from_to = []
            elif 'eids_from_to' in kwargs:
                entities = []
                eids_from_to = kwargs.pop('eids_from_to')
            else:
                entities = []
                eids_from_to = []
            pruned = self.get_pruned_hooks(cnx, event,
                                           entities, eids_from_to, kwargs)

            # by default, hooks are executed with security turned off
            with cnx.security_enabled(read=False):
                for _kwargs in _iter_kwargs(entities, eids_from_to, kwargs):
                    hooks = sorted(self.filtered_possible_objects(pruned, cnx, **_kwargs),
                                   key=lambda x: x.order)
                    debug = server.DEBUG & server.DBG_HOOKS
                    with cnx.security_enabled(write=False):
                        with cnx.running_hooks_ops():
                            for hook in hooks:
                                if debug:
                                    print(event, _kwargs, hook)
                                hook()

    def get_pruned_hooks(self, cnx, event, entities, eids_from_to, kwargs):
        """return a set of hooks that should not be considered by filtered_possible objects

        the idea is to make a first pass over all the hooks in the
        registry and to mark put some of them in a pruned list. The
        pruned hooks are the one which:

        * are disabled at the connection level

        * have a selector containing a :class:`match_rtype` or an
          :class:`is_instance` predicate which does not match the rtype / etype
          of the relations / entities for which we are calling the hooks. This
          works because the repository calls the hooks grouped by rtype or by
          etype when using the entities or eids_to_from keyword arguments

        Only hooks with a simple predicate or an AndPredicate of simple
        predicates are considered for disabling.

        """
        if 'entity' in kwargs:
            entities = [kwargs['entity']]
        if len(entities):
            look_for_selector = is_instance
            etype = entities[0].__regid__
        elif 'rtype' in kwargs:
            look_for_selector = match_rtype
            etype = None
        else: # nothing to prune, how did we get there ???
            return set()
        cache_key = (event, kwargs.get('rtype'), etype)
        pruned = cnx.pruned_hooks_cache.get(cache_key)
        if pruned is not None:
            return pruned
        pruned = set()
        cnx.pruned_hooks_cache[cache_key] = pruned
        if look_for_selector is not None:
            for id, hooks in self.items():
                for hook in hooks:
                    enabled_cat, main_filter = hook.filterable_selectors()
                    if enabled_cat is not None:
                        if not enabled_cat(hook, cnx):
                            pruned.add(hook)
                            continue
                    if main_filter is not None:
                        if isinstance(main_filter, match_rtype) and \
                           (main_filter.frometypes is not None  or \
                            main_filter.toetypes is not None):
                            continue
                        first_kwargs = next(_iter_kwargs(entities, eids_from_to, kwargs))
                        if not main_filter(hook, cnx, **first_kwargs):
                            pruned.add(hook)
        return pruned


    def filtered_possible_objects(self, pruned, *args, **kwargs):
        for appobjects in self.values():
            if pruned:
                filtered_objects = [obj for obj in appobjects if obj not in pruned]
                if not filtered_objects:
                    continue
            else:
                filtered_objects = appobjects
            obj = self._select_best(filtered_objects,
                                    *args, **kwargs)
            if obj is None:
                continue
            yield obj

class HooksManager(object):
    def __init__(self, vreg):
        self.vreg = vreg

    def call_hooks(self, event, cnx=None, **kwargs):
        try:
            registry = self.vreg['%s_hooks' % event]
        except RegistryNotFound:
            return # no hooks for this event
        registry.call_hooks(event, cnx, **kwargs)


for event in ALL_HOOKS:
    CWRegistryStore.REGISTRY_FACTORY['%s_hooks' % event] = HooksRegistry


# some hook specific predicates #################################################

@objectify_predicate
def enabled_category(cls, req, **kwargs):
    if req is None:
        return True # XXX how to deactivate server startup / shutdown event
    return req.is_hook_activated(cls)

@objectify_predicate
def issued_from_user_query(cls, req, **kwargs):
    return 0 if req.hooks_in_progress else 1

from_dbapi_query = class_renamed('from_dbapi_query',
                                 issued_from_user_query,
                                 message='[3.21] ')


class rechain(object):
    def __init__(self, *iterators):
        self.iterators = iterators
    def __iter__(self):
        return iter(chain(*self.iterators))


class match_rtype(ExpectedValuePredicate):
    """accept if the relation type is found in expected ones. Optional
    named parameters `frometypes` and `toetypes` can be used to restrict
    target subject and/or object entity types of the relation.

    :param \*expected: possible relation types
    :param frometypes: candidate entity types as subject of relation
    :param toetypes: candidate entity types as object of relation
    """
    def __init__(self, *expected, **more):
        self.expected = expected
        self.frometypes = more.pop('frometypes', None)
        self.toetypes = more.pop('toetypes', None)
        assert not more, "unexpected kwargs in match_rtype: %s" % more

    def __call__(self, cls, req, *args, **kwargs):
        if kwargs.get('rtype') not in self.expected:
            return 0
        if self.frometypes is not None and \
               req.entity_metas(kwargs['eidfrom'])['type'] not in self.frometypes:
            return 0
        if self.toetypes is not None and \
               req.entity_metas(kwargs['eidto'])['type'] not in self.toetypes:
            return 0
        return 1


class match_rtype_sets(ExpectedValuePredicate):
    """accept if the relation type is in one of the sets given as initializer
    argument. The goal of this predicate is that it keeps reference to original sets,
    so modification to thoses sets are considered by the predicate. For instance

    .. sourcecode:: python

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
    represents the current connection. In entity hooks, a `self.entity` attribute is
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
    # stop pylint from complaining about missing attributes in Hooks classes
    eidfrom = eidto = entity = rtype = repo = None

    @classmethod
    @cached
    def filterable_selectors(cls):
        search = cls.__select__.search_selector
        if search((NotPredicate, OrPredicate)):
            return None, None
        enabled_cat = search(enabled_category)
        main_filter = search((is_instance, match_rtype))
        return enabled_cat, main_filter

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

    @classmethod
    def __registered__(cls, reg):
        cls.check_events()

    @classproperty
    def __registries__(cls):
        if cls.events is None:
            return []
        return ['%s_hooks' % ev for ev in cls.events]

    known_args = set(('entity', 'rtype', 'eidfrom', 'eidto', 'repo', 'timestamp'))
    def __init__(self, req, event, **kwargs):
        for arg in self.known_args:
            if arg in kwargs:
                setattr(self, arg, kwargs.pop(arg))
        super(Hook, self).__init__(req, **kwargs)
        self.event = event

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

    You usually want to use the :class:`match_rtype_sets` predicate on concrete
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
            etype = self._cw.entity_metas(eid)['type']
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
    # to set in concrete class (optionally)
    skip_subject_relations = ()
    skip_object_relations = ()

    def __call__(self):
        eschema = self._cw.vreg.schema.eschema(self._cw.entity_metas(self.eidfrom)['type'])
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
        eschema = self._cw.vreg.schema.eschema(self._cw.entity_metas(self.eidfrom)['type'])
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



# abstract classes for operation ###############################################

class Operation(object):
    """Base class for operations.

    Operation may be instantiated in the hooks' `__call__` method. It always
    takes a connection object as first argument (accessible as `.cnx` from the
    operation instance), and optionally all keyword arguments needed by the
    operation. These keyword arguments will be accessible as attributes from the
    operation instance.

    An operation is triggered on connections set events related to commit /
    rollback transations. Possible events are:

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

      the transaction has been either rolled back either:

       * intentionally
       * a 'precommit' event failed, in which case all operations are rolled back
         once 'revertprecommit'' has been called

    * `postcommit`:

      the transaction is over. All the ORM entities accessed by the earlier
      transaction are invalid. If you need to work on the database, you need to
      start a new transaction, for instance using a new internal connection,
      which you will need to commit.

    For an operation to support an event, one has to implement the `<event
    name>_event` method with no arguments.

    The order of operations may be important, and is controlled according to
    the insert_index's method output (whose implementation vary according to the
    base hook class used).
    """

    def __init__(self, cnx, **kwargs):
        self.cnx = cnx
        self.__dict__.update(kwargs)
        self.register(cnx)
        # execution information
        self.processed = None # 'precommit', 'commit'
        self.failed = False

    @property
    @deprecated('[3.19] Operation.session is deprecated, use Operation.cnx instead')
    def session(self):
        return self.cnx

    def register(self, cnx):
        cnx.add_operation(self, self.insert_index())

    def insert_index(self):
        """return the index of the latest instance which is not a
        LateOperation instance
        """
        # faster by inspecting operation in reverse order for heavy transactions
        i = None
        for i, op in enumerate(reversed(self.cnx.pending_operations)):
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
        """the observed connections set is preparing a commit"""

    def revertprecommit_event(self):
        """an error went when pre-commiting this operation or a later one

        should revert pre-commit's changes but take care, they may have not
        been all considered if it's this operation which failed
        """

    def rollback_event(self):
        """the observed connections set has been rolled back

        do nothing by default
        """

    def postcommit_event(self):
        """the observed connections set has committed"""

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

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
    will be given to the operation constructor (for obvious reasons those
    parameters should not vary accross different calls to this method for a
    given operation).

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
    def get_instance(cls, cnx, **kwargs):
        # no need to lock: transaction_data already comes from thread's local storage
        try:
            return cnx.transaction_data[cls.data_key]
        except KeyError:
            op = cnx.transaction_data[cls.data_key] = cls(cnx, **kwargs)
            return op

    def __init__(self, *args, **kwargs):
        super(DataOperationMixIn, self).__init__(*args, **kwargs)
        self._container = self._build_container()
        self._processed = False

    def __contains__(self, value):
        return value in self._container

    def _build_container(self):
        return self.containercls()

    def union(self, data):
        """only when container is a set"""
        assert not self._processed, """Trying to add data to a closed operation.
Iterating over operation data closed it and should be reserved to precommit /
postcommit method of the operation."""
        self._container |= data

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
        op = self.cnx.transaction_data.pop(self.data_key)
        assert op is self, "Bad handling of operation data, found %s instead of %s for key %s" % (
            op, self, self.data_key)
        return self._container



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
        for i, op in enumerate(reversed(self.cnx.pending_operations)):
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

    def register(self, cnx):
        """override register to handle cases where this operation has already
        been added
        """
        operations = cnx.pending_operations
        index = self.equivalent_index(operations)
        if index is not None:
            equivalent = operations.pop(index)
        else:
            equivalent = None
        cnx.add_operation(self, self.insert_index())
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
    def __init__(self, cnx, msg=None, recipients=None, **kwargs):
        # may not specify msg yet, as
        # `cubicweb.sobjects.supervision.SupervisionMailOp`
        if msg is not None:
            assert recipients
            self.to_send = [(msg, recipients)]
        else:
            assert recipients is None
            self.to_send = []
        super(SendMailOp, self).__init__(cnx, **kwargs)

    def register(self, cnx):
        previous = super(SendMailOp, self).register(cnx)
        if previous:
            self.to_send = previous.to_send + self.to_send

    def postcommit_event(self):
        self.cnx.repo.threaded_task(self.sendmails)

    def sendmails(self):
        self.cnx.vreg.config.sendmails(self.to_send)


class RQLPrecommitOperation(Operation):
    # to be defined in concrete classes
    rqls = None

    def precommit_event(self):
        execute = self.cnx.execute
        for rql in self.rqls:
            execute(*rql)


class CleanupNewEidsCacheOp(DataOperationMixIn, SingleLastOperation):
    """on rollback of a insert query we have to remove from repository's
    type/source cache eids of entities added in that transaction.

    NOTE: querier's rqlst/solutions cache may have been polluted too with
    queries such as Any X WHERE X eid 32 if 32 has been rolled back however
    generated queries are unpredictable and analysing all the cache probably
    too expensive. Notice that there is no pb when using args to specify eids
    instead of giving them into the rql string.
    """
    data_key = 'neweids'

    def rollback_event(self):
        """the observed connections set has been rolled back,
        remove inserted eid from repository type/source cache
        """
        try:
            self.cnx.repo.clear_caches(self.get_data())
        except KeyError:
            pass

class CleanupDeletedEidsCacheOp(DataOperationMixIn, SingleLastOperation):
    """on commit of delete query, we have to remove from repository's
    type/source cache eids of entities deleted in that transaction.
    """
    data_key = 'pendingeids'
    def postcommit_event(self):
        """the observed connections set has been rolled back,
        remove inserted eid from repository type/source cache
        """
        try:
            eids = self.get_data()
            self.cnx.repo.clear_caches(eids)
            self.cnx.repo.app_instances_bus.publish(['delete'] + list(str(eid) for eid in eids))
        except KeyError:
            pass
