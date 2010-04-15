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

A cube is a software component made of three parts: its data model
(:file:`schema`), its logic (:file:`entities`) and its user interface
(:file:`views`).

A cube can use other cubes as building blocks and assemble them to provide a
whole with richer functionnalities than its parts. The cubes `cubicweb-blog`_ and
`cubicweb-comment`_ could be used to make a cube named *myblog* with commentable
blog entries.

The `CubicWeb.org Forge`_ offers a large number of cubes developed by the community
and available under a free software license.

The command :command:`cubicweb-ctl list` displays the list of cubes installed on
your system.

On a Unix system, the available cubes are usually stored in the directory
:file:`/usr/share/cubicweb/cubes`. If you're using the cubicweb forest
(:ref:SourceInstallation), the cubes are searched in the directory
:file:`/path/to/cubicweb_forest/cubes`. The environment variable
:envvar:`CW_CUBES_PATH` gives additionnal locations where to search for cubes.

.. _`CubicWeb.org Forge`: http://www.cubicweb.org/project/
.. _`cubicweb-blog`: http://www.cubicweb.org/project/cubicweb-blog
.. _`cubicweb-comment`: http://www.cubicweb.org/project/cubicweb-comment


.. _Instance:

Instances
---------

An instance is a runnable application installed on a computer and based on a
cube.

The instance directory contains the configuration files. Several instances can be
created and based on the same cube. For exemple, several software forges can be
set up on one computer system based on the `cubicweb-forge`_ cube.

.. _`cubicweb-forge`: http://www.cubicweb.org/project/cubicweb-forge

Instances can be of three different types: all-in-one, web engine or data
repository. For applications that support high traffic, several web (front-end)
and data (back-end) instances can be set-up to share the load.

.. image:: ../images/archi_globale.en.png

The command :command:`cubicweb-ctl list` also displays the list of instances
installed on your system.

On a Unix system, the instances are usually stored in the directory
:file:`/etc/cubicweb.d/`. During development, the :file:`~/etc/cubicweb.d/`
directory is looked up, as well as the paths in :envvar:`CW_INSTANCES_DIR`
environment variable.


.. Note::

  The term application is used to refer to "something that should do something as
  a whole", eg more like a project and so can refer to an instance or to a cube,
  depending on the context. This book will try to use *application*, *cube* and
  *instance* as appropriate.


.. _RepositoryIntro:

Data Repository
---------------

The data repository [1]_ provides access to one or more data sources (including
SQL databases, LDAP repositories, other |cubicweb| instance repositories, GAE's
DataStore, etc).

All interactions with the repository are done using the Relation Query Language
(:ref:`RQL`). The repository federates the data sources and hides them from the
querier, which does not realize when a query spans accross several data sources
and requires running sub-queries and merges to complete.

It is common to run the web engine and the repository in the same process (see
instances of type all-in-one above), but this is not a requirement. A repository
can be set up to be accessed remotely using Pyro (`Python Remote Objects`_) and
act as a server. However, it's important to know if code you're writing is
executed on the repository side, on our client side (the web engine being a
client for instance): you don't have the same abilities on both side. On the
repository side, you can for instance by-pass security checks, which isn't
possible from client code.

Some logic can be attached to events that happen in the repository, like
creation of entities, deletion of relations, etc. This is used for example to
send email notifications when the state of an object changes. See :ref:`HookIntro` below.

.. [1] not to be confused with a Mercurial repository or a Debian repository.
.. _`Python Remote Objects`: http://pyro.sourceforge.net/


.. _WebEngineIntro:

Web Engine
----------

The web engine replies to http requests and runs the user interface
and most of the application logic.

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

An `entity type` defines a set of attributes and is used in some relations.
Attributes may be of the following types: `String`, `Int`, `Float`, `Boolean`,
`Date`, `Time`, `Datetime`, `Interval`, `Password`, `Bytes`, `RichString`.

A `relation type` is used to define an oriented binary relation between two
entity types.  The left-hand part of a relation is named the `subject` and the
right-hand part is named the `object`.

A `relation definition` is a triple (*subject entity type*, *relation type*, *object
entity type*) associated with a set of properties such as cardinality,
constraints, etc.

Permissions can be set on entity types and relation definition to control who
will be able to create, read, update or delete entities and relations. Permissions
are granted to groups (to which users may belong) or using rql expression (if the
rql expression returns some results, the permission is granted).

Some meta-data necessary to the system is added to the data model. That includes
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

Beside a few core functionalities, almost every feature of the framework is
achieved by dynamic objects (`application objects` or `appobjects`) stored in a
two-levels registry (the `vregistry`). Each object is affected to a registry with
an identifier in this registry. You may have more than one object sharing an
identifier in the same registry, At runtime, appobjects are selected in a
registry according to the context. Selection is done by comparing *score*
returned by each appobject's *selector*.

Application objects are stored in the vregistry using a two-level hierarchy :

  object's `__registry__` : object's `__regid__` : [list of app objects]

E.g. The `vregistry` contains several registries which hold a list of
appobjects associated to an identifier.

The base class of appobjects is :class:`cubicweb.appobject.AppObject`.

Selectors
~~~~~~~~~

Each appobject has a selector, that is used to compute how well the object fits a
given context. The better the object fits the context, the higher the score. They
are the glue that tie appobjects to the data model. Using them appropriately is
an essential part of the construction of well behaved cubes.

|cubicweb| provides a set of basic selectors that may be parametrized.  Also,
selectors can be combined with the `~` unary operator (negation) and the binary
operators `&` and `|` (respectivly 'and' and 'or') to build more complex
selector. Of course complex selector may be combined too. Last but not least, you
can write your own selectors.

The `vregistry`
~~~~~~~~~~~~~~~

At startup, the `vregistry` inspects a number of directories looking for
compatible classes definition. After a recording process, the objects are
assigned to registries so that they can be selected dynamically while the
instance is running.

In a cube, application object classes are looked in the following modules or
packages:

- `entities`
- `views`
- `sobjects`
- `hooks`


Once initialized, there are three common ways to retrieve some application object
from a registry:

* get the most appropriate object by specifying an identifier. In that case, the
  object with the greatest score is selected. There should always be a single
  appobject with a greater score than others for a particular context.

* get all objects applying to a context by specifying a registry. In that case, a
  list of objects will be returned containing the object with the highest score
  (> 0) for each identifier in that registry.

* get the object within a particular registry/identifier. In that case no
  selection process is involved, the vregistry will expect to find a single
  object in that cell.


.. _RQLIntro:

The RQL query language
----------------------

**No need for a complicated ORM when you have a powerful query language**

All the persistent data in a |cubicweb| instance is retrieved and modified by
using the Relation Query Language.

This query language is inspired by SQL but is on a higher level in order to
emphasize browsing relations.


db-api
~~~~~~

The repository exposes a `db-api`_ like api but using the RQL instead of SQL.

You basically get a connection using :func:`cubicweb.dbapi.connect` , then
get a cursor to call its `execute` method which will return result set for the
given rql query.

You can also get additional information through the connection, such as the
repository'schema, version configuration, etc.


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

The two main entry points of a view are:

* `call()`, used to render a view on a context with no result set, or on a whole
  result set

* `cell_call(row, col)`, used to render a view on a the cell with index `row` and
  `col` of the context's result set (remember result set may be seen as a two
  dimensions array).

Then view may gets refined into different kind of objects such as `template`,
`boxes`, `components`, which are more high-level abstraction useful to build
the user interface in an object oriented way.


.. _HookIntro:

Hooks and operations
--------------------

**CubicWeb provides an extensible data repository**

The data model defined using Yams types allows to express the data
model in a comfortable way. However several aspects of the data model
can not be expressed there. For instance:

* managing computed attributes

* enforcing complicated structural invariants

* real-world side-effects linked to data events (email notification
  being a prime example)

The hook system is much like the triggers of an SQL database engine,
except that:

* it is not limited to one specific SQL backend (every one of them
  having an idiomatic way to encode triggers), nor to SQL backends at
  all (think about LDAP or a Subversion repository)

* it is well-coupled to the rest of the framework

Hooks are also application objects registered on events such as after/before
add/update/delete on entities/relations, server startup or shutdown, etc. As all
application objects, they have a selector defining when they should be called or
not.

`Operations` may be instantiated by hooks to do further processing at different
steps of the transaction's commit / rollback, which usually can not be done
safely at the hook execution time.

Hooks and operation are an essential building block of any moderately complicated
cubicweb application.

.. Note:
   RQL queries executed in hooks and operations are *unsafe* by default, e.g. the
   read and write security is deactivated unless explicitly asked.

.. |cubicweb| replace:: *CubicWeb*
