.. -*- coding: utf-8 -*-

.. _Concepts:

The Core Concepts of |cubicweb|
===============================

This section defines some terms and core concepts of the |cubicweb| framework. To
avoid confusion while reading this book, take time to go through the following
definitions and use this section as a reference during your reading.


.. _Cube:

Cubes
-----

A cube is a software component made of three parts:

- its data model (:mod:`schema`),
- its logic (:mod:`entities`) and
- its user interface (:mod:`views`).

A cube can use other cubes as building blocks and assemble them to provide a
whole with richer functionnalities than its parts. The cubes `cubicweb-blog`_ and
`cubicweb-comment`_ could be used to make a cube named *myblog* with commentable
blog entries.

The `CubicWeb.org Forge`_ offers a large number of cubes developed by the community
and available under a free software license.

.. note::

   The command :command:`cubicweb-ctl list` displays the list of available cubes.

.. _`CubicWeb.org Forge`: http://www.cubicweb.org/project/
.. _`cubicweb-blog`: http://www.cubicweb.org/project/cubicweb-blog
.. _`cubicweb-comment`: http://www.cubicweb.org/project/cubicweb-comment


.. _Instance:

Instances
---------

An instance is a runnable application installed on a computer and
based on one or more cubes.

The instance directory contains the configuration files. Several
instances can be created and based on the same cube. For example,
several software forges can be set up on one computer system based on
the `cubicweb-forge`_ cube.

.. _`cubicweb-forge`: http://www.cubicweb.org/project/cubicweb-forge

The command :command:`cubicweb-ctl list` also displays the list of instances
installed on your system.

.. note::

  The term application is used to refer to "something that should do something as
  a whole", eg more like a project and so can refer to an instance or to a cube,
  depending on the context. This book will try to use *application*, *cube* and
  *instance* as appropriate.


.. _RepositoryIntro:

Data Repository
---------------

The data repository [1]_ encapsulates and groups an access to one or
more data sources (including SQL databases, LDAP repositories, other
|cubicweb| instance repositories, filesystems, Google AppEngine's
DataStore, etc).

All interactions with the repository are done using the `Relation Query Language`
(:ref:`RQL`). The repository federates the data sources and hides them from the
querier, which does not realize when a query spans several data sources
and requires running sub-queries and merges to complete.

Application logic can be mapped to data events happenning within the
repository, like creation of entities, deletion of relations,
etc. This is used for example to send email notifications when the
state of an object changes. See :ref:`HookIntro` below.

.. [1] not to be confused with a Mercurial repository or a Debian repository.
.. _`Python Remote Objects`: http://pythonhosted.org/Pyro4/

.. _WebEngineIntro:

Web Engine
----------

The web engine replies to http requests and runs the user interface.

By default the web engine provides a `CRUD`_ user interface based on
the data model of the instance. Entities can be created, displayed,
updated and deleted. As the default user interface is not very fancy,
it is usually necessary to develop your own.

.. _`CRUD`: http://en.wikipedia.org/wiki/Create,_read,_update_and_delete

.. _SchemaIntro:

Schema (Data Model)
-------------------

The data model of a cube is described as an entity-relationship schema using a
comprehensive language made of Python classes imported from the yams_ library.

.. _yams: http://www.logilab.org/project/yams/

An `entity type` defines a sequence of attributes. Attributes may be
of the following types: `String`, `Int`, `Float`, `Boolean`, `Date`,
`Time`, `Datetime`, `Interval`, `Password`, `Bytes`, `RichString`.

A `relation type` is used to define an oriented binary relation
between entity types.  The left-hand part of a relation is named the
`subject` and the right-hand part is named the `object`.

A `relation definition` is a triple (*subject entity type*, *relation type*, *object
entity type*) associated with a set of properties such as cardinality,
constraints, etc.

Permissions can be set on entity types or relation definition to control who
will be able to create, read, update or delete entities and relations. Permissions
are granted to groups (to which users may belong) or using rql expressions (if the
rql expression returns some results, the permission is granted).

Some meta-data necessary to the system are added to the data model. That includes
entities like users and groups, the entities used to store the data model
itself and attributes like unique identifier, creation date, creator, etc.

When you create a new |cubicweb| instance, the schema is stored in the database.
When the cubes the instance is based on evolve, they may change their data model
and provide migration scripts that will be executed when the administrator will
run the upgrade process for the instance.


.. _VRegistryIntro:

Registries and application objects
----------------------------------

Application objects
~~~~~~~~~~~~~~~~~~~

Besides a few core functionalities, almost every feature of the framework is
achieved by dynamic objects (`application objects` or `appobjects`) stored in a
two-levels registry. Each object is affected to a registry with
an identifier in this registry. You may have more than one object sharing an
identifier in the same registry:

  object's `__registry__` : object's `__regid__` : [list of app objects]

In other words, the `registry` contains several (sub-)registries which hold a
list of appobjects associated to an identifier.

The base class of appobjects is :class:`cubicweb.appobject.AppObject`.

Selectors
~~~~~~~~~

At runtime, appobjects can be selected in a registry according to some
contextual information. Selection is done by comparing the *score*
returned by each appobject's *selector*.

The better the object fits the context, the higher the score. Scores
are the glue that ties appobjects to the data model. Using them
appropriately is an essential part of the construction of well behaved
cubes.

|cubicweb| provides a set of basic selectors that may be parametrized.  Also,
selectors can be combined with the `~` unary operator (negation) and the binary
operators `&` and `|` (respectivly 'and' and 'or') to build more complex
selectors. Of course complex selectors may be combined too. Last but not least, you
can write your own selectors.

The `registry`
~~~~~~~~~~~~~~~

At startup, the `registry` inspects a number of directories looking
for compatible class definitions. After a recording process, the
objects are assigned to registries and become available through the
selection process.

In a cube, application object classes are looked in the following modules or
packages:

- `entities`
- `views`
- `hooks`
- `sobjects`

There are three common ways to look up some application object from a
registry:

* get the most appropriate object by specifying an identifier and
  context objects. The object with the greatest score is
  selected. There should always be a single appobject with a greater
  score than others for a particular context.

* get all objects applying to a context by specifying a registry. A
  list of objects will be returned containing the object with the
  highest score (> 0) for each identifier in that registry.

* get the object within a particular registry/identifier. No selection
  process is involved: the registry will expect to find a single
  object in that cell.


.. _RQLIntro:

The RQL query language
----------------------

No need for a complicated ORM when you have a powerful data
manipulation language.

All the persistent data in a |cubicweb| instance is retrieved and
modified using RQL (see :ref:`rql_intro`).

This query language is inspired by SQL but is on a higher level in order to
emphasize browsing relations.


Result set
~~~~~~~~~~

Every request made (using RQL) to the data repository returns an object we call a
Result Set. It enables easy use of the retrieved data, providing a translation
layer between the backend's native datatypes and |cubicweb| schema's EntityTypes.

Result sets provide access to the raw data, yielding either basic Python data
types, or schema-defined high-level entities, in a straightforward way.


.. _ViewIntro:

Views
-----

**CubicWeb is data driven**

The view system is loosely coupled to data through the selection system explained
above. Views are application objects with a dedicated interface to 'render'
something, eg producing some html, text, xml, pdf, or whatsover that can be
displayed to a user.

Views actually are partitioned into different kind of objects such as
`templates`, `boxes`, `components` and proper `views`, which are more
high-level abstraction useful to build the user interface in an object
oriented way.


.. _HookIntro:

Hooks and operations
--------------------

**CubicWeb provides an extensible data repository**

The data model defined using Yams types allows to express the data
model in a comfortable way. However several aspects of the data model
can not be expressed there. For instance:

* managing computed attributes

* enforcing complicated business rules

* real-world side-effects linked to data events (email notification
  being a prime example)

The hook system is much like the triggers of an SQL database engine,
except that:

* it is not limited to one specific SQL backend (every one of them
  having an idiomatic way to encode triggers), nor to SQL backends at
  all (think about LDAP or a Subversion repository)

* it is well-coupled to the rest of the framework

Hooks are also application objects (in the `hooks` registry) and
selected on events such as after/before add/update/delete on
entities/relations, server startup or shutdown, etc.

`Operations` may be instantiated by hooks to do further processing at different
steps of the transaction's commit / rollback, which usually can not be done
safely at the hook execution time.

Hooks and operation are an essential building block of any moderately complicated
cubicweb application.

.. note::
   RQL queries executed in hooks and operations are *unsafe* by default, i.e. the
   read and write security is deactivated unless explicitly asked.
