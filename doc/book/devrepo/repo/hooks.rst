.. -*- coding: utf-8 -*-
.. _hooks:

Hooks and Operations
====================

.. automodule:: cubicweb.server.hook


Example using dataflow hooks
----------------------------

We will use a very simple example to show hooks usage. Let us start with the
following schema.

.. sourcecode:: python

   class Person(EntityType):
       age = Int(required=True)

We would like to add a range constraint over a person's age. Let's write an hook
(supposing yams can not handle this natively, which is wrong). It shall be placed
into `mycube/hooks.py`. If this file were to grow too much, we can easily have a
`mycube/hooks/... package` containing hooks in various modules.

.. sourcecode:: python

   from cubicweb import ValidationError
   from cubicweb.predicates import is_instance
   from cubicweb.server.hook import Hook

   class PersonAgeRange(Hook):
        __regid__ = 'person_age_range'
        __select__ = Hook.__select__ & is_instance('Person')
        events = ('before_add_entity', 'before_update_entity')

        def __call__(self):
            if 'age' in self.entity.cw_edited:
                if 0 <= self.entity.age <= 120:
                   return
                msg = self._cw._('age must be between 0 and 120')
                raise ValidationError(self.entity.eid, {'age': msg})

In our example the base `__select__` is augmented with an `is_instance` selector
matching the desired entity type.

The `events` tuple is used to specify that our hook should be called before the
entity is added or updated.

Then in the hook's `__call__` method, we:

* check if the 'age' attribute is edited
* if so, check the value is in the range
* if not, raise a validation error properly

Now let's augment our schema with a new `Company` entity type with some relation to
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

    from cubicweb.server.hook import Hook, DataOperationMixIn, Operation, match_rtype

    def check_cycle(session, eid, rtype, role='subject'):
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
:func:`get_instance` class method.

.. sourcecode:: python

   class CheckSubsidiaryCycleHook(Hook):
       __regid__ = 'check_no_subsidiary_cycle'
       events = ('after_add_relation',)
       __select__ = Hook.__select__ & match_rtype('subsidiary_of')

       def __call__(self):
           CheckSubsidiaryCycleOp.get_instance(self._cw).add_data(self.eidto)

   class CheckSubsidiaryCycleOp(DataOperationMixIn, Operation):

       def precommit_event(self):
           for eid in self.get_data():
               check_cycle(self.session, eid, self.rtype)


Here, we call :func:`add_data` so that we will simply accumulate eids of
entities to check at the end in a single `CheckSubsidiaryCycleOp`
operation. Values are stored in a set associated to the
'check_no_subsidiary_cycle' transaction data key. The set initialization and
operation creation are handled nicely by :func:`add_data`.

A more realistic example can be found in the advanced tutorial chapter
:ref:`adv_tuto_security_propagation`.


Inter-instance communication
----------------------------

If your application consists of several instances, you may need some means to
communicate between them.  Cubicweb provides a publish/subscribe mechanism
using ØMQ_.  In order to use it, use
:meth:`~cubicweb.server.cwzmq.ZMQComm.add_subscription` on the
`repo.app_instances_bus` object.  The `callback` will get the message (as a
list).  A message can be sent by calling
:meth:`~cubicweb.server.cwzmq.ZMQComm.publish` on `repo.app_instances_bus`.
The first element of the message is the topic which is used for filtering and
dispatching messages.

.. _ØMQ: http://www.zeromq.org/

.. sourcecode:: python

  class FooHook(hook.Hook):
      events = ('server_startup',)
      __regid__ = 'foo_startup'

      def __call__(self):
          def callback(msg):
              self.info('received message: %s', ' '.join(msg))
          self.repo.app_instances_bus.add_subscription('hello', callback)

.. sourcecode:: python

  def do_foo(self):
      actually_do_foo()
      self._cw.repo.app_instances_bus.publish(['hello', 'world'])

The `zmq-address-pub` configuration variable contains the address used
by the instance for sending messages, e.g. `tcp://*:1234`.  The
`zmq-address-sub` variable contains a comma-separated list of addresses
to listen on, e.g. `tcp://localhost:1234, tcp://192.168.1.1:2345`.


Hooks writing tips
------------------

Reminder
~~~~~~~~

You should never use the `entity.foo = 42` notation to update an entity. It will
not do what you expect (updating the database). Instead, use the
:meth:`~cubicweb.entity.Entity.cw_set` method or direct access to entity's
:attr:`cw_edited` attribute if you're writing a hook for 'before_add_entity' or
'before_update_entity' event.


How to choose between a before and an after event ?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`before_*` hooks give you access to the old attribute (or relation)
values. You can also intercept and update edited values in the case of
entity modification before they reach the database.

Else the question is: should I need to do things before or after the actual
modification ? If the answer is "it doesn't matter", use an 'after' event.


Validation Errors
~~~~~~~~~~~~~~~~~

When a hook which is responsible to maintain the consistency of the
data model detects an error, it must use a specific exception named
:exc:`~cubicweb.ValidationError`. Raising anything but a (subclass of)
:exc:`~cubicweb.ValidationError` is a programming error. Raising it
entails aborting the current transaction.

This exception is used to convey enough information up to the user
interface. Hence its constructor is different from the default Exception
constructor. It accepts, positionally:

* an entity eid (**not the entity itself**),

* a dict whose keys represent attribute (or relation) names and values
  an end-user facing message (hence properly translated) relating the
  problem.

.. sourcecode:: python

  raise ValidationError(earth.eid, {'sea_level': self._cw._('too high'),
                                    'temperature': self._cw._('too hot')})


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

This may have some side effect, for instance when creating an entity
and setting an inlined relation in the same rql query, then at
`before_add_relation` time, the relation will already exist in the
database (it is otherwise not the case).
