.. -*- coding: utf-8 -*-

The Core Concepts of CubicWeb
=============================

.. toctree::
   :maxdepth: 1

------------------------------

This section aims to provide you the keys of success with *CubicWeb*
by clarifying the terms specific to our framework. If you want to do anything
serious with CubicWeb, you should understand concepts in those lines.

*CubicWeb* defines its own terminology. To make sure there is no confusion
while reading this book, we strongly recommand you take time to go through
the following definitions that are the basics to understand while
developing with *CubicWeb*.


.. _Cube:

Cubes
-----
** Construct your application by assembling cubes **

A cube provides a specific functionality, or a complete *CubicWeb*
application usually by assembling other cubes.

It's usually composed of a data model, some logic to manipulate it and some parts
of web interface.

You can decide to write your own set of cubes if you wish to re-use the
entity types you develop or/and if you have specific needs not covered by
cubes are available from the `CubicWeb Forge`_ under a free software license.

Available cubes on your system are defined in the directory
:file:`/usr/share/cubicweb/cubes` when using a system wide installation.  For people
using the mercurial repository of cubicweb, the :file:`/path/to/forest/cubicweb/cubes`
directory is used. You can specify additional location using the :envvar:`CW_CUBES_PATH`
environment variable, using ':' as separator.

.. _`CubicWeb Forge`: http://www.cubicweb.org/project/



Instances
----------
** *CubicWeb* framework is a server/client application framework**

An instance is a specific installation of one or multiple cubes. All the required
configuration files necessary for the well being of your web application are
grouped in an instance. This will refer to the cube(s) your application is based
on.  For example logilab.org and our intranet are two instances of a single cube
`jpl`

We recommand not to define schema, entities or views in the instance
file system itself but in the cube, in order to maintain re-usability of
entities and their views. We strongly recommand to develop cubes which
could be used in other instances (modular approach).

An instance usually usually consists into a web interface which is talking to a
rql repository, itself connected to a SQL database, all into a single
process. You can have some more complicated configurations using several web
front-ends talking to a rql repository using `Pyro`_, databases replication...

.. image:: ../../images/archi_globale.en.png

The term application is sometimes used to talk about an instance and sometimes to
talk of a cube depending on the context.  So we would like to avoid using this
term and try to use *cube* and *instance* instead.

Data Repository
~~~~~~~~~~~~~~~
The repository (Be carefull not to get confused with a Mercurial repository or a
debian repository!) manages all interactions with various data sources by
providing access to them using uniformly using the Relation Query Language (RQL).  The
web interface and the repository communicate using this language.

Usually, the web server and repository sides are integrated in the same process and
interact directly, without the need for distant calls using Pyro. But, it is
important to note that those two sides, client/server, are disjointed and it is
possible to execute a couple of calls in distinct processes to balance the load
of your web site on one or more machines.


A data source is a container of data integrated in the *CubicWeb* repository. A
repository has at least one source, named `system`, which contains the schema of
the application, plain-text index and other vital informations for the
system. You'll find source for SQL databases, LDAP servers, other RQL
repositories and even mercurial /svn repositories or `Google App Engine`'s
datastore.

Web interface
~~~~~~~~~~~~~
By default the web server provides a generated interface based on its schema.
Entities can be created, displayed, updated and deleted. As display views are not
very fancy, it is usually necessary to develop your own.

Instances are defined on your system in the directory :file:`/etc/cubicweb.d` when
using a system wide installation.  For people using the mercurial repository of
cubicweb, the :file:`etc` directory is searched in the user home directory. You can
also specify an alternative directory using the :envvar:`CW_REGISTRY` environment
variable.



Schema
------
** *CubicWeb* is schema driven **

The schema describes the persistent data model using entities and
relations. It is modeled with a comprehensive language made of Python classes based on
the `yams`_ library.

When you create a new cubicweb instance, the schema is stored in the database,
and it will usually evolves as you upgrade cubicweb and used cubes.

*CubicWeb* provides a certain number of system entities included
sytematically (necessary for the core of *CubicWeb*, notably the schema itself).
You will also find a library of cubes which defines more piece of schema for standard needs.
necessary.

*CubicWeb* add some metadata to every entity type, such as the eid (a global
  identifier, unique into an instance), entity's creation date...


Attributes may be of the following types:
  `String`, `Int`, `Float`, `Boolean`, `Date`, `Time`, `Datetime`,
  `Interval`, `Password`, `Bytes`.

New in 3.2: RichString

see :ref:`yams.BASE_TYPES`

Data level security is defined by setting permissions on entity and relation types.

A schema consist of parts detailed below.


Entity type
~~~~~~~~~~~
An *entity type* defines set of attributes and is used in some relations. It may
have some permissions telling who can read/add/update/delete entities of this type.

Relation type
~~~~~~~~~~~~~
A *relation type* is used to define a semantic relation between two entity types.
It may have some permissions telling who can read/add/delete relation of this type.

In *CubicWeb* relations are ordered and binary: by convention we name the first
item of a relation the `subject` and the second the `object`.

Relation definition
~~~~~~~~~~~~~~~~~~~
A *relation definition* is a 3-uple (*subject entity type*, *relation type*, *object
entity type*), with an associated set of property such as cardinality, constraints...



Dynamic objects for reusable components
---------------------------------------
** Dynamic objects management or how CubicWeb provides really reusable components **

Application objects
~~~~~~~~~~~~~~~~~~~
Beside a few core functionalities, almost every feature of the framework is
acheived by dynamic objects (`application objects` or `appobjects`) stored in a
two-levels registry (the `vregistry`). Each object is affected to a registry with
an identifier in this registry. You may have more than one object sharing an
identifier in the same registry, At runtime, appobjects are selected in the
vregistry according to the context.

Application objects are stored in the registry using a two level hierarchy :

  object's `__registry__` : object's `id` : [list of app objects]

The base class of appobjects is `AppRsetObject` (module `cubicweb.appobject`).

The `vregistry`
~~~~~~~~~~~~~~~
At startup, the `registry` or registers base, inspects a number of directories
looking for compatible classes definition. After a recording process, the objects
are assigned to registers so that they can be selected dynamically while the
application is running.

Selectors
~~~~~~~~~
Each appobject has a selector, which is used to score how well it suits to a
given context by returning a score.  A score of 0 means the object doesn't apply
to the context. The score is used to choose the most pertinent object: the "more"
the appobject suits the context the higher the score.

CubicWeb provides a set of basic selectors which may be parametrized and combined
using binary `&` and `|` operators to provide a custom selector (which can be
itself reused...).

There is 3 current ways to retreive some appobject from the repository:

* get the most appropriate objects by specifying a registry and an identifier. In
  that case, the object with the greatest score is selected. There should always
  be a single appobject with a greater score than others.

* get all appobjects applying to a context by specifying a registry.In
  that case, every objects with the a postive score are selected.

* get the object within a particular registry/identifier. In that case no
  selection process is involved, the vregistry will expect to find a single
  object in that cell.

Selector sets are the glue that tie views to the data model. Using them
appropriately is an essential part of the construction of well behaved cubes.


When no score is higher than the others, an exception is raised in development
mode to let you know that the engine was not able to identify the view to
apply. This error is silented in production mode and one of the objects with the
higher score is picked.

If no object has a positive score, ``NoSelectableObject`` exception is raised.

If no object is found for a particular registry and identifier,
``ObjectNotFound`` exception is raised.

In such cases you would need to review your design and make sure your views are
properly defined.



The RQL query language
----------------------
**No needs for a complicated ORM when you've a powerful query language**

All the persistant data in a CubicWeb application is retreived and modified by using the
Relation Query Language.

This query language is inspired by SQL but is on a higher level in order to
emphasize browsing relations.

db-api
~~~~~~
The repository exposes a `db-api`_ like api but using the RQL instead of SQL.
XXX feed me

Result set
~~~~~~~~~~
XXX feed me


Views
-----
** *CubicWeb* is data driven **

XXX feed me.


Hooks
-----
** *CubicWeb* provides an extensible data repository **

XXX feed me.


.. _`Python Remote Object`: http://pyro.sourceforge.net/
.. _`yams`: http://www.logilab.org/project/yams/
