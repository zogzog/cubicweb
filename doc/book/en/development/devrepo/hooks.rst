.. -*- coding: utf-8 -*-

.. _hooks:

Hooks and Operations
====================

Generalities
------------

Paraphrasing the `emacs`_ documentation, let us say that hooks are an
important mechanism for customizing an application. A hook is
basically a list of functions to be called on some well-defined
occasion (this is called `running the hook`).

.. _`emacs`: http://www.gnu.org/software/emacs/manual/html_node/emacs/Hooks.html

In CubicWeb, hooks are subclasses of the Hook class in
`server/hook.py`, implementing their own `call` method, and selected
over a set of pre-defined `events` (and possibly more conditions,
hooks being selectable AppObjects like views and components).

There are two families of events: data events and server events. In a
typical application, most of the Hooks are defined over data
events.

The purpose of data hooks is to complement the data model as defined
in the schema.py, which is static by nature, with dynamic or value
driven behaviours. It is functionally equivalent to a `database
trigger`_, except that database triggers definition languages are not
standardized, hence not portable (for instance, PL/SQL works with
Oracle and PostgreSQL but not SqlServer nor Sqlite).

.. _`database trigger`: http://en.wikipedia.org/wiki/Database_trigger

Data hooks can serve the following purposes:

* enforcing constraints that the static schema cannot express
  (spanning several entities/relations, exotic value ranges and
  cardinalities, etc.)

* implement computed attributes

Operations are Hook-like objects that may be created by Hooks and
scheduled to happen just before (or after) the `commit` event. Hooks
being fired immediately on data operations, it is sometime necessary
to delay the actual work down to a time where all other Hooks have
run, for instance a validation check which needs that all relations be
already set on an entity. Also while the order of execution of Hooks
is data dependant (and thus hard to predict), it is possible to force
an order on Operations.

Operations also may be used to process various side effects associated
with a transaction such as filesystem udpates, mail notifications,
etc.

Operations are subclasses of the Operation class in `server/hook.py`,
implementing `precommit_event` and other standard methods (wholly
described in :ref:`operations_api`).

Events
------

Hooks are mostly defined and used to handle `dataflow`_ operations. It
means as data gets in (entities added, updated, relations set or
unset), specific events are issued and the Hooks matching these events
are called.

.. _`dataflow`: http://en.wikipedia.org/wiki/Dataflow

Below comes a list of the dataflow events related to entities operations:

* before_add_entity

* before_update_entity

* before_delete_entity

* after_add_entity

* after_update_entity

* after_delete_entity

These define ENTTIES HOOKS. RELATIONS HOOKS are defined
over the following events:

* after_add_relation

* after_delete_relation

* before_add_relation

* before_delete_relation

This is an occasion to remind us that relations support the add/delete
operation, but no update.

Non data events also exist. These are called SYSTEM HOOKS.

* server_startup

* server_shutdown

* server_maintenance

* server_backup

* server_restore

* session_open

* session_close


Using dataflow Hooks
--------------------

Dataflow hooks either automate data operations or maintain the
consistency of the data model. In the later case, we must use a
specific exception named ValidationError

Validation Errors
~~~~~~~~~~~~~~~~~

When a condition is not met in a Hook/Operation, it must raise a
`ValidationError`. Raising anything but a (subclass of)
ValidationError is a programming error. Raising a ValidationError
entails aborting the current transaction.

The ValidationError exception is used to convey enough information up
to the user interface. Hence its constructor is different from the
default Exception constructor. It accepts, positionally:

* an entity eid,

* a dict whose keys represent attribute (or relation) names and values
  an end-user facing message (hence properly translated) relating the
  problem.

An entity hook
~~~~~~~~~~~~~~

We will use a very simple example to show hooks usage. Let us start
with the following schema.

.. sourcecode:: python

   class Person(EntityType):
       age = Int(required=True)

We would like to add a range constraint over a person's age. Let's
write an hook. It shall be placed into mycube/hooks.py. If this file
were to grow too much, we can easily have a mycube/hooks/... package
containing hooks in various modules.

.. sourcecode:: python

   from cubicweb import ValidationError
   from cubicweb.selectors import implements
   from cubicweb.server.hook import Hook

   class PersonAgeRange(Hook):
        __regid__ = 'person_age_range'
        events = ('before_add_entity', 'before_update_entity')
        __select__ = Hook.__select__ & implements('Person')

        def __call__(self):
            if 0 >= self.entity.age <= 120:
               return
            msg = self._cw._('age must be between 0 and 120')
            raise ValidationError(self.entity.eid, {'age': msg})

Hooks being AppObjects like views, they have a __regid__ and a
__select__ class attribute. The base __select__ is augmented with an
`implements` selector matching the desired entity type. The `events`
tuple is used by the Hook.__select__ base selector to dispatch the
hook on the right events. In an entity hook, it is possible to
dispatch on any entity event (e.g. 'before_add_entity',
'before_update_entity') at once if needed.

Like all appobjects, hooks have the `self._cw` attribute which
represents the current session. In entity hooks, a `self.entity`
attribute is also present.


A relation hook
~~~~~~~~~~~~~~~

Let us add another entity type with a relation to person (in
mycube/schema.py).

.. sourcecode:: python

   class Company(EntityType):
        name = String(required=True)
        boss = SubjectRelation('Person', cardinality='1*')

We would like to constrain the company's bosses to have a minimum
(legal) age. Let's write an hook for this, which will be fired when
the `boss` relation is established.

.. sourcecode:: python

   class CompanyBossLegalAge(Hook):
        __regid__ = 'company_boss_legal_age'
        events = ('before_add_relation',)
        __select__ = Hook.__select__ & match_rtype('boss')

        def __call__(self):
            boss = self._cw.entity_from_eid(self.eidto)
            if boss.age < 18:
                msg = self._cw._('the minimum age for a boss is 18')
                raise ValidationError(self.eidfrom, {'boss': msg})

We use the `match_rtype` selector to select the proper relation type.

The essential difference with respect to an entity hook is that there
is no self.entity, but `self.eidfrom` and `self.eidto` hook attributes
which represent the subject and object eid of the relation.


Using Operations
----------------

Let's augment our example with a new `subsidiary_of` relation on Company.

.. sourcecode:: python

   class Company(EntityType):
        name = String(required=True)
        boss = SubjectRelation('Person', cardinality='1*')
        subsidiary_of = SubjectRelation('Company', cardinality='*?')

Base example
~~~~~~~~~~~~

We would like to check that there is no cycle by the `subsidiary_of`
relation. This is best achieved in an Operation since all relations
are likely to be set at commit time.

.. sourcecode:: python

    def check_cycle(self, session, eid, rtype, role='subject'):
        parents = set([eid])
        parent = session.entity_from_eid(eid)
        while parent.related(rtype, role):
            parent = parent.related(rtype, role)[0]
            if parent.eid in parents:
                msg = session._('detected %s cycle' % rtype)
                raise ValidationError(eid, {rtype: msg})
            parents.add(parent.eid)

    class CheckSubsidiaryCycleOp(Operation):

        def precommit_event(self):
            check_cycle(self.session, self.eidto, 'subsidiary_of')


    class CheckSubsidiaryCycleHook(Hook):
        __regid__ = 'check_no_subsidiary_cycle'
        events = ('after_add_relation',)
        __select__ = Hook.__select__ & match_rtype('subsidiary_of')

        def __call__(self):
            CheckSubsidiaryCycleOp(self._cw, eidto=self.eidto)

The operation is instantiated in the Hook.__call__ method.

An operation always takes a session object as first argument
(accessible as `.session` from the operation instance), and optionally
all keyword arguments needed by the operation. These keyword arguments
will be accessible as attributes from the operation instance.

Like in Hooks, ValidationError can be raised in Operations. Other
exceptions are programming errors.

Notice how our hook will instantiate an operation each time the Hook
is called, i.e. each time the `subsidiary_of` relation is set.

Using set_operation
~~~~~~~~~~~~~~~~~~~

There is an alternative method to schedule an Operation from a Hook,
using the `set_operation` function.

.. sourcecode:: python

   from cubicweb.server.hook import set_operation

   class CheckSubsidiaryCycleHook(Hook):
       __regid__ = 'check_no_subsidiary_cycle'
       events = ('after_add_relation',)
       __select__ = Hook.__select__ & match_rtype('subsidiary_of')

       def __call__(self):
           set_operation(self._cw, 'subsidiary_cycle_detection', self.eidto,
                         CheckSubsidiaryCycleOp, rtype=self.rtype)

   class CheckSubsidiaryCycleOp(Operation):

       def precommit_event(self):
           for eid in self._cw.transaction_data['subsidiary_cycle_detection']:
               check_cycle(self.session, eid, self.rtype)

Here, we call set_operation with a session object, a specially forged
key, a value that is the actual payload of an individual operation (in
our case, the object of the subsidiary_of relation) , the class of the
Operation, and more optional parameters to give to the operation (here
the rtype which do not vary accross operations).

The body of the operation must then iterate over the values that have
been mapped in the transaction_data dictionary to the forged key.

This mechanism is especially useful on two occasions (not shown in our
example):

* massive data import (reduced memory consumption within a large
  transaction)

* when several hooks need to instantiate the same operation (e.g. an
  entity and a relation hook).

.. note::

  A more realistic example can be found in the advanced tutorial
  chapter :ref:`adv_tuto_security_propagation`.

.. _operations_api:

Operation: a small API overview
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cubicweb.server.hook.Operation
.. autoclass:: cubicweb.server.hook.LateOperation
.. autofunction:: cubicweb.server.hook.set_operation

Hooks writing rules
-------------------

Remainder
~~~~~~~~~

Never, ever use the `entity.foo = 42` notation to update an entity. It
will not work.

How to choose between a before and an after event ?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before hooks give you access to the old attribute (or relation)
values. By definition the database is not yet updated in a before
hook.

To access old and new values in an before_update_entity hook, one can
use the `server.hook.entity_oldnewvalue` function which returns a
tuple of the old and new values. This function takes an entity and an
attribute name as parameters.

In a 'before_add|update_entity' hook the self.entity contains the new
values. One is allowed to further modify them before database
operations, using the dictionary notation.

.. sourcecode:: python

   self.entity['age'] = 42

This is because using self.entity.set_attributes(age=42) will
immediately update the database (which does not make sense in a
pre-database hook), and will trigger any existing
before_add|update_entity hook, thus leading to infinite hook loops or
such awkward situations.

Beyond these specific cases, updating an entity attribute or relation
must *always* be done using `set_attributes` and `set_relations`
methods.

(Of course, ValidationError will always abort the current transaction,
whetever the event).

Peculiarities of inlined relations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Some relations are defined in the schema as `inlined` (see
:ref:`RelationType` for details). In this case, they are inserted in
the database at the same time as entity attributes.

Hence in the case of before_add_relation, such relations already exist
in the database.

Edited attributes
~~~~~~~~~~~~~~~~~

On udpates, it is possible to ask the `entity.edited_attributes`
variable whether one attribute has been updated.

.. sourcecode:: python

  if 'age' not in entity.edited_attribute:
      return

Deleted in transaction
~~~~~~~~~~~~~~~~~~~~~~

The session object has a deleted_in_transaction method, which can help
writing deletion Hooks.

.. sourcecode:: python

   if self._cw.deleted_in_transaction(self.eidto):
      return

Given this predicate, we can avoid scheduling an operation.

Disabling hooks
~~~~~~~~~~~~~~~

It is sometimes convenient to disable some hooks. For instance to
avoid infinite Hook loops. One uses the `hooks_control` context
manager.

This can be controlled more finely through the `category` Hook class
attribute, which is a string.

.. sourcecode:: python

   with hooks_control(self.session, self.session.HOOKS_ALLOW_ALL, <category>):
       # ... do stuff

.. autoclass:: cubicweb.server.session.hooks_control

The existing categories are: ``email``, ``syncsession``,
``syncschema``, ``bookmark``, ``security``, ``worfklow``,
``metadata``, ``notification``, ``integrity``, ``activeintegrity``.

Nothing precludes one to invent new categories and use the
hooks_control context manager to filter them (in or out).
