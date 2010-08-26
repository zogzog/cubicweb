.. -*- coding: utf-8 -*-
.. _hooks:

Hooks and Operations
====================

.. autodocstring:: cubicweb.server.hook

Example using dataflow hooks
----------------------------

We will use a very simple example to show hooks usage. Let us start with the
following schema.

.. sourcecode:: python

   class Person(EntityType):
       age = Int(required=True)

We would like to add a range constraint over a person's age. Let's write an hook
(supposing yams can not handle this nativly, which is wrong). It shall be placed
into `mycube/hooks.py`. If this file were to grow too much, we can easily have a
`mycube/hooks/... package` containing hooks in various modules.

.. sourcecode:: python

   from cubicweb import ValidationError
   from cubicweb.selectors import is_instance
   from cubicweb.server.hook import Hook

   class PersonAgeRange(Hook):
        __regid__ = 'person_age_range'
        events = ('before_add_entity', 'before_update_entity')
        __select__ = Hook.__select__ & is_instance('Person')

        def __call__(self):
	    if 'age' in self.entity.cw_edited:
                if 0 <= self.entity.age <= 120:
                   return
		msg = self._cw._('age must be between 0 and 120')
		raise ValidationError(self.entity.eid, {'age': msg})

In our example the base `__select__` is augmented with an `is_instance` selector
matching the desired entity type.

The `events` tuple is used specify that our hook should be called before the
entity is added or updated.

Then in the hook's `__call__` method, we:

* check if the 'age' attribute is edited
* if so, check the value is in the range
* if not, raise a validation error properly

Now Let's augment our schema with new `Company` entity type with some relation to
`Person` (in 'mycube/schema.py').

.. sourcecode:: python

   class Company(EntityType):
        name = String(required=True)
        boss = SubjectRelation('Person', cardinality='1*')
        subsidiary_of = SubjectRelation('Company', cardinality='*?')


We would like to constrain the company's bosses to have a minimum (legal)
age. Let's write an hook for this, which will be fired when the `boss` relation
is established (still supposing we could not specify that kind of thing in the
schema).

.. sourcecode:: python

   class CompanyBossLegalAge(Hook):
        __regid__ = 'company_boss_legal_age'
        __select__ = Hook.__select__ & match_rtype('boss')
        events = ('before_add_relation',)

        def __call__(self):
            boss = self._cw.entity_from_eid(self.eidto)
            if boss.age < 18:
                msg = self._cw._('the minimum age for a boss is 18')
                raise ValidationError(self.eidfrom, {'boss': msg})

.. Note::

    We use the :class:`~cubicweb.server.hook.match_rtype` selector to select the
    proper relation type.

    The essential difference with respect to an entity hook is that there is no
    self.entity, but `self.eidfrom` and `self.eidto` hook attributes which
    represent the subject and object **eid** of the relation.

Suppose we want to check that there is no cycle by the `subsidiary_of`
relation. This is best achieved in an operation since all relations are likely to
be set at commit time.

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
        __select__ = Hook.__select__ & match_rtype('subsidiary_of')
        events = ('after_add_relation',)

        def __call__(self):
            CheckSubsidiaryCycleOp(self._cw, eidto=self.eidto)


Like in hooks, :exc:`~cubicweb.ValidationError` can be raised in operations. Other
exceptions are usually programming errors.

In the above example, our hook will instantiate an operation each time the hook
is called, i.e. each time the `subsidiary_of` relation is set. There is an
alternative method to schedule an operation from a hook, using the
:func:`set_operation` function.

.. sourcecode:: python

   from cubicweb.server.hook import set_operation

   class CheckSubsidiaryCycleHook(Hook):
       __regid__ = 'check_no_subsidiary_cycle'
       events = ('after_add_relation',)
       __select__ = Hook.__select__ & match_rtype('subsidiary_of')

       def __call__(self):
           set_operation(self._cw, 'subsidiary_cycle_detection', self.eidto,
                         CheckSubsidiaryCycleOp)

   class CheckSubsidiaryCycleOp(Operation):

       def precommit_event(self):
           for eid in self._cw.transaction_data.pop('subsidiary_cycle_detection'):
               check_cycle(self.session, eid, 'subsidiary_of')


Here, we call :func:`set_operation` so that we will simply accumulate eids of
entities to check at the end in a single CheckSubsidiaryCycleOp operation.  Value
are stored in a set associated to the 'subsidiary_cycle_detection' transaction
data key. The set initialization and operation creation are handled nicely by
:func:set_operation.

A more realistic example can be found in the advanced tutorial chapter
:ref:`adv_tuto_security_propagation`.


Hooks writing tips
------------------

Reminder
~~~~~~~~

Never, ever use the `entity.foo = 42` notation to update an entity. It will not
work.To updating an entity attribute or relation, uses :meth:`set_attributes` and
:meth:`set_relations` methods.


How to choose between a before and an after event ?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

'before_*' hooks give you access to the old attribute (or relation)
values. You can also hi-jack actually edited stuff in the case of entity
modification. Needing one of this will definitly guide your choice.

Else the question is: should I need to do things before or after the actual
modification. If the answer is "it doesn't matter", use an 'after' event.


Validation Errors
~~~~~~~~~~~~~~~~~

When a hook is responsible to maintain the consistency of the data model detect
an error, it must use a specific exception named
:exc:`~cubicweb.ValidationError`. Raising anything but a (subclass of)
:exc:`~cubicweb.ValidationError` is a programming error. Raising a it entails
aborting the current transaction.

This exception is used to convey enough information up to the user
interface. Hence its constructor is different from the default Exception
constructor. It accepts, positionally:

* an entity eid,

* a dict whose keys represent attribute (or relation) names and values
  an end-user facing message (hence properly translated) relating the
  problem.


Checking for object created/deleted in the current transaction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In hooks, you can use the
:meth:`~cubicweb.server.session.Session.added_in_transaction` or
:meth:`~cubicweb.server.session.Session.deleted_in_transaction` of the session
object to check if an eid has been created or deleted during the hook's
transaction.

This is useful to enable or disable some stuff if some entity is being added or
deleted.

.. sourcecode:: python

   if self._cw.deleted_in_transaction(self.eidto):
      return


Peculiarities of inlined relations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Relations which are defined in the schema as `inlined` (see :ref:`RelationType`
for details) are inserted in the database at the same time as entity attributes.
This may have some side effect, for instance when creating entity and setting an
inlined relation in the same rql query, when 'before_add_relation' for that
relation will be run, the relation will already exist in the database (it's
usually not the case).
