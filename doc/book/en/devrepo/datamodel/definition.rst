 .. -*- coding: utf-8 -*-

.. _datamodel_definition:

Yams *schema*
-------------

The **schema** is the core piece of a *CubicWeb* instance as it
defines and handles the data model. It is based on entity types that
are either already defined in `Yams`_ and the *CubicWeb* standard
library; or more specific types defined in cubes. The schema for a
cube is defined in a `schema` python module or package.

.. _`Yams`: http://www.logilab.org/project/yams

.. _datamodel_overview:

Overview
~~~~~~~~

The core idea of the yams schema is not far from the classical
`Entity-relationship`_ model. But while an E/R model (or `logical
model`) traditionally has to be manually translated to a lower-level
data description language (such as the SQL `create table`
sublanguage), also often described as the `physical model`, no such
step is required with |yams| and |cubicweb|.

.. _`Entity-relationship`: http://en.wikipedia.org/wiki/Entity-relationship_model

This is because in addition to high-level, logical |yams| models, one
uses the |rql| data manipulation language to query, insert, update and
delete data. |rql| abstracts as much of the underlying SQL database as
a |yams| schema abstracts from the physical layout. The vagaries of
SQL are avoided.

As a bonus point, such abstraction make it quite comfortable to build
or use different backends to which |rql| queries apply.

So, as in the E/R formalism, the building blocks are ``entities``
(:ref:`EntityType`), ``relationships`` (:ref:`RelationType`,
:ref:`RelationDefinition`) and ``attributes`` (handled like relation
with |yams|).

Let us detail a little the divergences between E/R and |yams|:

* all relationship are binary which means that to represent a
  non-binary relationship, one has to use an entity,
* relationships do not support attributes (yet, see:
  http://www.cubicweb.org/ticket/341318), hence the need to reify it
  as an entity if need arises,
* all entities have an `eid` attribute (an integer) that is its
  primary key (but it is possible to declare uniqueness on other
  attributes)

Also |yams| supports the notions of:

* entity inheritance (quite experimental yet, and completely
  undocumented),
* relation type: that is, relationships can be established over a set
  of couple of entity types (henre the distinction made between
  `RelationType` and `RelationDefinition` below)

Finally |yams| has a few concepts of its own:

* relationships being oriented and binary, we call the left hand
  entity type the `subject` and the right hand entity type the
  `object`

.. note::

   The |yams| schema is available at run time through the .schema
   attribute of the `vregistry`.  It's an instance of
   :class:`cubicweb.schema.Schema`, which extends
   :class:`yams.schema.Schema`.

.. _EntityType:

Entity type
~~~~~~~~~~~

An entity type is an instance of :class:`yams.schema.EntitySchema`. Each entity type has
a set of attributes and relations, and some permissions which define who can add, read,
update or delete entities of this type.

The following built-in types are available: ``String``,
``Int``, ``Float``, ``Decimal``, ``Boolean``,
``Date``, ``Datetime``, ``Time``, ``Interval``, ``Byte`` and
``Password``. They can only be used as attributes of an other entity
type.

There is also a `RichString` kindof type:

 .. autoclass:: yams.buildobjs.RichString


You can find more base entity types in
:ref:`pre_defined_entity_types`.

.. XXX yams inheritance

.. _RelationType:

Relation type
~~~~~~~~~~~~~

A relation type is an instance of
:class:`yams.schema.RelationSchema`. A relation type is simply a
semantic definition of a kind of relationship that may occur in an
application.

It may be referenced by zero, one or more relation definitions.

It is important to choose a good name, at least to avoid conflicts
with some semantically different relation defined in other cubes
(since there's only a shared name space for these names).

A relation type holds the following properties (which are hence shared
between all relation definitions of that type):

* `inlined`: boolean handling the physical optimization for archiving
  the relation in the subject entity table, instead of creating a specific
  table for the relation. This applies to relations where cardinality
  of subject->relation->object is 0..1 (`?`) or 1..1 (`1`) for *all* its relation
  definitions.

* `symmetric`: boolean indicating that the relation is symmetrical, which
  means that `X relation Y` implies `Y relation X`.

.. _RelationDefinition:

Relation definition
~~~~~~~~~~~~~~~~~~~

A relation definition is an instance of
:class:`yams.schema.RelationDefinition`. It is a complete triplet
"<subject entity type> <relation type> <object entity type>".

When creating a new instance of that class, the corresponding
:class:`RelationType` instance is created on the fly if necessary.

Properties
``````````

The available properties for relation definitions are enumerated
here. There are several kind of properties, as some relation
definitions are actually attribute definitions, and other are not.

Some properties may be completely optional, other may have a default
value.

Common properties for attributes and relations:

* `description`: an unicode string describing an attribute or a
  relation. By default this string will be used in the editing form of
  the entity, which means that it is supposed to help the end-user and
  should be flagged by the function `_` to be properly
  internationalized.

* `constraints`: a list of conditions/constraints that the relation has to
  satisfy (c.f. `Constraints`_)

* `cardinality`: a two character string specifying the cardinality of
  the relation. The first character defines the cardinality of the
  relation on the subject, and the second on the object. When a
  relation can have multiple subjects or objects, the cardinality
  applies to all, not on a one-to-one basis (so it must be
  consistent...). Default value is '**'. The possible values are
  inspired from regular expression syntax:

    * `1`: 1..1
    * `?`: 0..1
    * `+`: 1..n
    * `*`: 0..n

Attributes properties:

* `unique`: boolean indicating if the value of the attribute has to be
  unique or not within all entities of the same type (false by
  default)

* `indexed`: boolean indicating if an index needs to be created for
  this attribute in the database (false by default). This is useful
  only if you know that you will have to run numerous searches on the
  value of this attribute.

* `default`: default value of the attribute. In case of date types, the values
  which could be used correspond to the RQL keywords `TODAY` and `NOW`.

* `metadata`: Is also accepted as an argument of the attribute contructor. It is
  not really an attribute property. see `Metadata`_ for details.

Properties for `String` attributes:

* `fulltextindexed`: boolean indicating if the attribute is part of
  the full text index (false by default) (*applicable on the type
  `Byte` as well*)

* `internationalizable`: boolean indicating if the value of the
  attribute is internationalizable (false by default)

Relation properties:

* `composite`: string indicating that the subject (composite ==
  'subject') is composed of the objects of the relations. For the
  opposite case (when the object is composed of the subjects of the
  relation), we just set 'object' as value. The composition implies
  that when the relation is deleted (so when the composite is deleted,
  at least), the composed are also deleted.

* `fulltext_container`: string indicating if the value if the full
  text indexation of the entity on one end of the relation should be
  used to find the entity on the other end. The possible values are
  'subject' or 'object'. For instance the use_email relation has that
  property set to 'subject', since when performing a full text search
  people want to find the entity using an email address, and not the
  entity representing the email address.

Constraints
```````````

By default, the available constraint types are:

General Constraints
......................

* `SizeConstraint`: allows to specify a minimum and/or maximum size on
  string (generic case of `maxsize`)

* `BoundaryConstraint`: allows to specify a minimum and/or maximum value
  on numeric types and date

.. sourcecode:: python

   from yams.constraints import BoundaryConstraint, TODAY
   BoundaryConstraint('<=', TODAY())

* `IntervalBoundConstraint`: allows to specify an interval with
  included values

.. sourcecode:: python

     class Node(EntityType):
         latitude = Float(constraints=[IntervalBoundConstraint(-90, +90)])

* `UniqueConstraint`: identical to "unique=True"

* `StaticVocabularyConstraint`: identical to "vocabulary=(...)"

.. XXX Attribute, NOW

RQL Based Constraints
......................

RQL based constraints may take three arguments. The first one is the ``WHERE``
clause of a RQL query used by the constraint. The second argument ``mainvars``
is the ``Any`` clause of the query. By default this include `S` reserved for the
subject of the relation and `O` for the object. Additional variables could be
specified using ``mainvars``. The argument expects a single string with all
variable's name separated by spaces. The last one, ``msg``, is the error message
displayed when the constraint fails. As RQLVocabularyConstraint never fails the
third argument is not available.

* `RQLConstraint`: allows to specify a RQL query that has to be satisfied
  by the subject and/or the object of relation. In this query the variables
  `S` and `O` are reserved for the relation subject and object entities.

* `RQLVocabularyConstraint`: similar to the previous type of constraint except
  that it does not express a "strong" constraint, which means it is only used to
  restrict the values listed in the drop-down menu of editing form, but it does
  not prevent another entity to be selected.

* `RQLUniqueConstraint`: allows to the specify a RQL query that ensure that an
  attribute is unique in a specific context. The Query must **never** return more
  than a single result to be satisfied. In this query the variables `S` is
  reserved for the relation subject entity. The other variables should be
  specified with the second constructor argument (mainvars). This constraints
  should be used when UniqueConstraint doesn't fit. Here is a simple example.

.. sourcecode:: python

    # Check that in the same Workflow each state's name is unique.  Using
    # UniqueConstraint (or unique=True) here would prevent states in different
    # workflows to have the same name.

    # With: State S, Workflow W, String N ; S state_of W, S name N

    RQLUniqueConstraint('S name N, S state_of WF, Y state_of WF, Y name N',
                        mainvars='Y',
                        msg=_('workflow already has a state of that name'))

.. XXX note about how to add new constraint

.. _securitymodel:

The security model
~~~~~~~~~~~~~~~~~~

The security model of `CubicWeb` is based on `Access Control List`.
The main principles are:

* users and groups of users
* a user belongs to at least one group of user
* permissions (read, update, create, delete)
* permissions are assigned to groups (and not to users)

For *CubicWeb* in particular:

* we associate rights at the entities/relations schema level

* the default groups are: `managers`, `users` and `guests`

* users belong to the `users` group

* there is a virtual group called `owners` to which we can associate only
  `delete` and `update` permissions

  * we can not add users to the `owners` group, they are implicitly added to it
    according to the context of the objects they own

  * the permissions of this group are only checked on `update`/`delete` actions
    if all the other groups the user belongs to do not provide those permissions

Setting permissions is done with the attribute `__permissions__` of entities and
relation definition. The value of this attribute is a dictionary where the keys
are the access types (action), and the values are the authorized groups or
expressions.

For an entity type, the possible actions are `read`, `add`, `update` and
`delete`.

For a relation, the possible actions are `read`, `add`, and `delete`.

For an attribute, the possible actions are `read`, `add` and `update`,
and they are a refinement of an entity type permission.

For each access type, a tuple indicates the name of the authorized groups and/or
one or multiple RQL expressions to satisfy to grant access. The access is
provided if the user is in one of the listed groups or if one of the RQL condition
is satisfied.

Default permissions
```````````````````

The default permissions for ``EntityType`` are:

.. sourcecode:: python

   __permissions__ = {
        'read': ('managers', 'users', 'guests',),
        'update': ('managers', 'owners',),
        'delete': ('managers', 'owners'),
        'add': ('managers', 'users',)
        }

The default permissions for relations are:

.. sourcecode:: python

   __permissions__ = {'read': ('managers', 'users', 'guests',),
                    'delete': ('managers', 'users'),
                    'add': ('managers', 'users',)}

The default permissions for attributes are:

.. sourcecode:: python

   __permissions__ = {'read': ('managers', 'users', 'guests',),
                      'add': ('managers', ERQLExpression('U has_add_permission X'),
                      'update': ('managers', ERQLExpression('U has_update_permission X')),}

The standard user groups
````````````````````````

* `guests`

* `users`

* `managers`

* `owners`: virtual group corresponding to the entity's owner.
  This can only be used for the actions `update` and `delete` of an entity
  type.

It is also possible to use specific groups if they are defined in the precreate
script of the cube (``migration/precreate.py``). Defining groups in postcreate
script or later makes them unavailable for security purposes (in this case, an
`sync_schema_props_perms` command has to be issued in a CubicWeb shell).


Use of RQL expression for write permissions
```````````````````````````````````````````

It is possible to define RQL expression to provide update permission (`add`,
`delete` and `update`) on entity type / relation definitions. An rql expression
is a piece of query (corresponds to the WHERE statement of an RQL query), and the
expression will be considered as satisfied if it returns some results. They can
not be used in `read` permission.

To use RQL expression in entity type permission:

* you have to use the class :class:`~cubicweb.schema.ERQLExpression`

* in this expression, the variables `X` and `U` are pre-defined references
  respectively on the current entity (on which the action is verified) and on the
  user who send the request

For RQL expressions on a relation type, the principles are the same except for
the following:

* you have to use the class :class:`~cubicweb.schema.RRQLExpression` instead of
  :class:`~cubicweb.schema.ERQLExpression`

* in the expression, the variables `S`, `O` and `U` are pre-defined references to
  respectively the subject and the object of the current relation (on which the
  action is being verified) and the user who executed the query

To define security for attributes of an entity (non-final relation), you have to
use the class :class:`~cubicweb.schema.ERQLExpression` in which `X` represents
the entity the attribute belongs to.

It is possible to use in those expression a special relation
`has_<ACTION>_permission` where the subject is the user (eg 'U') and the object
is any variable representing an entity (usually 'X' in
:class:`~cubicweb.schema.ERQLExpression`, 'S' or 'O' in
:class:`~cubicweb.schema.RRQLExpression`), meaning that the user needs to have
permission to execute the action <ACTION> on the entities represented by this
variable. It's recommanded to use this feature whenever possible since it
simplify greatly complex security definition and upgrade.


.. sourcecode:: python

  class my_relation(RelationDefinition):
    __permissions__ = {'read': ('managers', 'users'),
                       'add': ('managers', RRQLExpression('U has_update_permission S')),
                       'delete': ('managers', RRQLExpression('U has_update_permission S'))
		       }

In the above example, user will be allowed to add/delete `my_relation` if he has
the `update` permission on the subject of the relation.

.. note::

  Potentially, the `use of an RQL expression to add an entity or a relation` can
  cause problems for the user interface, because if the expression uses the
  entity or the relation to create, we are not able to verify the permissions
  before we actually added the entity (please note that this is not a problem for
  the RQL server at all, because the permissions checks are done after the
  creation). In such case, the permission check methods
  (CubicWebEntitySchema.check_perm and has_perm) can indicate that the user is
  not allowed to create this entity while it would obtain the permission.  To
  compensate this problem, it is usually necessary in such case to use an action
  that reflects the schema permissions but which check properly the permissions
  so that it would show up only if possible.


Use of RQL expression for reading rights
````````````````````````````````````````

The principles are the same but with the following restrictions:

* you can not use rql expression for the `read` permission of relations and
  attributes,

* you can not use special `has_<ACTION>_permission` relation in the rql
  expression.


Important notes about write permissions checking
````````````````````````````````````````````````

Write permissions (e.g. 'add', 'update', 'delete') are checked in core hooks.

When a permission is checked slightly vary according to if it's an entity or
relation, and if the relation is an attribute relation or not). It's important to
understand that since according to when a permission is checked, values returned
by rql expressions may changes, hence the permission being granted or not.

Here are the current rules:

1. permission to add/update entity and its attributes are checked on
   commit

2. permission to delete an entity is checked in 'before_delete_entity' hook

3. permission to add a relation is checked either:

   - in 'before_add_relation' hook if the relation type is in the
     `BEFORE_ADD_RELATIONS` set

   - else at commit time if the relation type is in the `ON_COMMIT_ADD_RELATIONS`
     set

   - else in 'after_add_relation' hook (the default)

4. permission to delete a relation is checked in 'before_delete_relation' hook

Last but not least, remember queries issued from hooks and operation are by
default 'unsafe', eg there are no read or write security checks.

See :mod:`cubicweb.hooks.security` for more details.


.. _yams_example:

Defining your schema using yams
-------------------------------

Entity type definition
~~~~~~~~~~~~~~~~~~~~~~

An entity type is defined by a Python class which inherits from
:class:`yams.buildobjs.EntityType`.  The class definition contains the
description of attributes and relations for the defined entity type.
The class name corresponds to the entity type name. It is expected to
be defined in the module ``mycube.schema``.

:Note on schema definition:

 The code in ``mycube.schema`` is not meant to be executed. The class
 EntityType mentioned above is different from the EntitySchema class
 described in the previous chapter. EntityType is a helper class to
 make Entity definition easier. Yams will process EntityType classes
 and create EntitySchema instances from these class definitions. Similar
 manipulation happen for relations.

When defining a schema using python files, you may use the following shortcuts:

- `required`: boolean indicating if the attribute is required, ed subject cardinality is '1'

- `vocabulary`: specify static possible values of an attribute

- `maxsize`: integer providing the maximum size of a string (no limit by default)

For example:

.. sourcecode:: python

  class Person(EntityType):
    """A person with the properties and the relations necessary for my
    application"""

    last_name = String(required=True, fulltextindexed=True)
    first_name = String(required=True, fulltextindexed=True)
    title = String(vocabulary=('Mr', 'Mrs', 'Miss'))
    date_of_birth = Date()
    works_for = SubjectRelation('Company', cardinality='?*')


The entity described above defines three attributes of type String,
last_name, first_name and title, an attribute of type Date for the date of
birth and a relation that connects a `Person` to another entity of type
`Company` through the semantic `works_for`.



:Naming convention:

 Entity class names must start with an uppercase letter. The common
 usage is to use ``CamelCase`` names.

 Attribute and relation names must start with a lowercase letter. The
 common usage is to use ``underscore_separated_words``. Attribute and
 relation names starting with a single underscore are permitted, to
 denote a somewhat "protected" or "private" attribute.

 In any case, identifiers starting with "CW" or "cw" are reserved for
 internal use by the framework.

 .. _Metadata:

 Some attribute using the name of another attribute as prefix are considered
 metadata.  For example, if an EntityType have both a ``data`` and
 ``data_format`` attribute, ``data_format`` is view as the ``format`` metadata
 of ``data``. Later the :meth:`cw_attr_metadata` method will allow you to fetch
 metadata related to an attribute. There are only three valid metadata names:
 ``format``, ``encoding`` and ``name``.


The name of the Python attribute corresponds to the name of the attribute
or the relation in *CubicWeb* application.

An attribute is defined in the schema as follows::

    attr_name = AttrType(*properties, metadata={})

where

* `AttrType`: is one of the type listed in EntityType_,

* `properties`: is a list of the attribute needs to satisfy (see `Properties`_
  for more details),

* `metadata`: is a dictionary of meta attributes related to ``attr_name``.
  Dictionary keys are the name of the meta attribute. Dictionary values
  attributes objects (like the content of ``AttrType``). For each entry of the
  metadata dictionary a ``<attr_name>_<key> = <value>`` attribute is
  automaticaly added to the EntityType.  see `Metadata`_ section for details
  about valid key.


 ---

While building your schema

* it is possible to use the attribute `meta` to flag an entity type as a `meta`
  (e.g. used to describe/categorize other entities)

.. XXX the paragraph below needs clarification and / or moving out in
.. another place

*Note*: if you end up with an `if` in the definition of your entity, this probably
means that you need two separate entities that implement the `ITree` interface and
get the result from `.children()` which ever entity is concerned.

.. Inheritance
.. ```````````
.. XXX feed me


Definition of relations
~~~~~~~~~~~~~~~~~~~~~~~

.. XXX add note about defining relation type / definition

A relation is defined by a Python class heriting `RelationType`. The name
of the class corresponds to the name of the type. The class then contains
a description of the properties of this type of relation, and could as well
contain a string for the subject and a string for the object. This allows to create
new definition of associated relations, (so that the class can have the
definition properties from the relation) for example ::

  class locked_by(RelationType):
    """relation on all entities indicating that they are locked"""
    inlined = True
    cardinality = '?*'
    subject = '*'
    object = 'CWUser'

If provided, the `subject` and `object` attributes denote the subject
and object of the various relation definitions related to the relation
type. Allowed values for these attributes are:

* a string corresponding to an entity type
* a tuple of string corresponding to multiple entity types
* the '*' special string, meaning all types of entities

When a relation is not inlined and not symmetrical, and it does not require
specific permissions, it can be defined using a `SubjectRelation`
attribute in the EntityType class. The first argument of `SubjectRelation` gives
the entity type for the object of the relation.

:Naming convention:

 Although this way of defining relations uses a Python class, the
 naming convention defined earlier prevails over the PEP8 conventions
 used in the framework: relation type class names use
 ``underscore_separated_words``.

:Historical note:

   It has been historically possible to use `ObjectRelation` which
   defines a relation in the opposite direction. This feature is
   deprecated and therefore should not be used in newly written code.

:Future deprecation note:

  In an even more remote future, it is quite possible that the
  SubjectRelation shortcut will become deprecated, in favor of the
  RelationType declaration which offers some advantages in the context
  of reusable cubes.

  


Handling schema changes
~~~~~~~~~~~~~~~~~~~~~~~

Also, it should be clear that to properly handle data migration, an
instance's schema is stored in the database, so the python schema file
used to defined it is only read when the instance is created or
upgraded.

.. XXX complete me
