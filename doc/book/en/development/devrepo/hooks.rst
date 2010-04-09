.. -*- coding: utf-8 -*-

.. _hooks:

Hooks and Operations
====================

Principles
----------

Paraphrasing the `emacs`_ documentation, let us say that hooks are an
important mechanism for customizing an application. A hook is
basically a list of functions to be called on some well-defined
occasion (This is called `running the hook`).

.. _`emacs`: http://www.gnu.org/software/emacs/manual/html_node/emacs/Hooks.html

In CubicWeb, hooks are classes subclassing the Hook class in
`server/hook.py`, implementing their own `call` method, and defined
over pre-defined `events`.

There are two families of events: data events and server events. In a
typical application, most of the Hooks are defined over data
events. There can be a lot of them.

The purpose of data hooks is to complement the data model as defined
in the schema.py, which is static by nature, with dynamic or value
driven behaviours. It is functionally equivalent to a `database
trigger`_, except that database triggers definitions languages are not
standardized, hence not portable (for instance, PL/SQL works with
Oracle and PostgreSQL but not SqlServer nor Sqlite).

.. _`database trigger`: http://en.wikipedia.org/wiki/Database_trigger

Data hooks can serve the following purposes:

* enforcing constraints that the static schema cannot express
  (spanning several entities/relations, exotic cardinalities, etc.)

* implement computed attributes (an example could be the maintenance
  of a relation representing the transitive closure of another relation)

Operations are Hook-like objects that are created by Hooks and
scheduled to happen just before (or after) the `commit` event. Hooks
being fired immediately on data operations, it is sometime necessary
to delay the actual work down to a time where all other Hooks have run
and the application state converges towards consistency. Also while
the order of execution of Hooks is data dependant (and thus hard to
predict), it is possible to force an order on Operations.

Events
------

Hooks are mostly defined and used to handle `dataflow`_ operations. It
means as data gets in (mostly), specific events are issued and the
Hooks matching these events are called.

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


