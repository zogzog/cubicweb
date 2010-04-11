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
  (spanning several entities/relations, specific value ranges, exotic
  cardinalities, etc.)

* implement computed attributes (an example could be the maintenance
  of a relation representing the transitive closure of another relation)

Operations are Hook-like objects that are created by Hooks and
scheduled to happen just before (or after) the `commit` event. Hooks
being fired immediately on data operations, it is sometime necessary
to delay the actual work down to a time where all other Hooks have run
and the application state converges towards consistency. Also while
the order of execution of Hooks is data dependant (and thus hard to
predict), it is possible to force an order on Operations.

Operations are subclasses of the Operation class in `server/hook.py`,
implementing `precommit_event` and other standard methods (wholly
described later in this chapter).

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
operation, but no delete.

Non data events also exist. These are called SYSTEM HOOKS.

* server_startup

* server_shutdown

* server_maintenance

* server_backup

* server_restore

* session_open

* session_close


Using Hooks
-----------

We will use a very simple example to show hooks usage. Let us start
with the following schema.

.. sourcecode:: python

   class Person(EntityType):
       age = Int(required=True)

An entity hook
~~~~~~~~~~~~~~

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
dispatch on any entity event at once if needed.

Like all appobjects, hooks have the self._cw attribute which
represents the current session. In entity hooks, a self.entity
attribute is also present.

When a condition is not met in a Hook, it must raise a
ValidationError. Raising anything but a (subclass of) ValidationError
is a programming error.

The ValidationError exception is used to convey enough information up
to the user interface. Hence its constructor is different from the
default Exception constructor.It accepts, positionally:

* an entity eid,

* a dict whose keys represent attributes and values a message relating
  the problem; such a message will be presented to the end-users;
  hence it must be properly translated.

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


# XXX talk about

dict access to entities in before_[add|update]
set_operation
