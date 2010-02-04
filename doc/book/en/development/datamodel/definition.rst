 .. -*- coding: utf-8 -*-

Yams *schema*
-------------

The **schema** is the core piece of a *CubicWeb* instance as it defines
the handled data model. It is based on entity types that are either already
defined in the *CubicWeb* standard library; or more specific types, that
*CubicWeb* expects to find in one or more Python files under the directory
`schema`.

At this point, it is important to make clear the difference between
*relation type* and *relation definition*: a *relation type* is only a relation
name with potentially other additionnal properties (see XXXX), whereas a
*relation definition* is a complete triplet
"<subject entity type> <relation type> <object entity type>".
A relation type could have been implied if none is related to a
relation definition of the schema.


All *CubicWeb* built-in types are available : `String`, `Int`, `Float`,
`Decimal`, `Boolean`, `Date`, `Datetime`, `Time`, `Interval`, `Byte`
and `Password`.
They are implicitely imported (as well as the special the function "_"
for translation :ref:`internationalization`).

The instance schema is defined on all appobjects by a .schema class attribute set
on registration.  It's an instance of :class:`yams.schema.Schema`.

Entity type
~~~~~~~~~~~
It's an instance of :class:`yams.schema.EntitySchema`

XXX meta
XXX permission
XXX yams inheritance

Relation type
~~~~~~~~~~~~~
It's an instance of :class:`yams.schema.RelationSchema`

In addition to the permissions, the properties of the relation types
(shared also by all definition of relation of this type) are :


* `inlined` : boolean handling the physical optimization for archiving
  the relation in the subject entity table, instead of creating a specific
  table for the relation. This applies to the relation when the cardinality
  of subject->relation->object is 0..1 (`?`) or 1..1 (`1`)

* `symmetric` : boolean indicating that the relation is symmetrical, which
  means `X relation Y` implies `Y relation X`

XXX meta
XXX permission


Relation definition
~~~~~~~~~~~~~~~~~~~
Relation definition are represented in yams using an internal structure only exposed through the :mod:`api <yams.schema>`.

Properties
``````````
Properties defined below are accessible through the following api:

  RelationSchema.rproperties()
  RelationSchema.rproperty(subjtype, objtype, property name)

* Optional properties for attributes and relations :

  - `description` : a string describing an attribute or a relation. By default
    this string will be used in the editing form of the entity, which means
    that it is supposed to help the end-user and should be flagged by the
    function `_` to be properly internationalized.

  - `constraints` : a list of conditions/constraints that the relation has to
    satisfy (c.f. `Constraints`_)

  - `cardinality` : a two character string which specify the cardinality of the
    relation. The first character defines the cardinality of the relation on
    the subject, and the second on the object. When a relation can have
    multiple subjects or objects, the cardinality applies to all,
    not on a one-to-one basis (so it must be consistent...). The possible
    values are inspired from regular expression syntax :

    * `1`: 1..1
    * `?`: 0..1
    * `+`: 1..n
    * `*`: 0..n

  - `meta` : boolean indicating that the relation is a meta-relation (false by
    default, will disappear in *CubicWeb* 3.5)

* optional properties for attributes :

  - `required` : boolean indicating if the attribute is required (false by default)

  - `unique` : boolean indicating if the value of the attribute has to be unique
    or not within all entities of the same type (false by default)

  - `indexed` : boolean indicating if an index needs to be created for this
    attribute in the database (false by default). This is useful only if
    you know that you will have to run numerous searches on the value of this
    attribute.

  - `default` : default value of the attribute. In case of date types, the values
    which could be used correspond to the RQL keywords `TODAY` and `NOW`.

  - `vocabulary` : specify static possible values of an attribute

* optional properties of type `String` :

  - `fulltextindexed` : boolean indicating if the attribute is part of
    the full text index (false by default) (*applicable on the type `Byte`
    as well*)

  - `internationalizable` : boolean indicating if the value of the attribute
    is internationalizable (false by default)

  - `maxsize` : integer providing the maximum size of the string (no limit by default)

* optional properties for relations :

  - `composite` : string indicating that the subject (composite == 'subject')
    is composed of the objects of the relations. For the opposite case (when
    the object is composed of the subjects of the relation), we just set
    'object' as value. The composition implies that when the relation
    is deleted (so when the composite is deleted), the composed are also deleted.

  - `fti_container`: XXX feed me

Constraints
```````````
By default, the available constraint types are :

* `SizeConstraint` : allows to specify a minimum and/or maximum size on
  string (generic case of `maxsize`)

* `BoundConstraint` : allows to specify a minimum and/or maximum value on
  numeric types

* `UniqueConstraint` : identical to "unique=True"

* `StaticVocabularyConstraint` : identical to "vocabulary=(...)"

* `RQLConstraint` : allows to specify a RQL query that has to be satisfied
  by the subject and/or the object of the relation. In this query the variables
  `S` and `O` are reserved for the entities subject and object of the
  relation.

* `RQLVocabularyConstraint` : similar to the previous type of constraint except
  that it does not express a "strong" constraint, which means it is only used to
  restrict the values listed in the drop-down menu of editing form, but it does
  not prevent another entity to be selected.

XXX note about how to add new constraint


The security model
~~~~~~~~~~~~~~~~~~

The security model of `cubicWeb` is based on `Access Control List`.
The main principles are:

* users and groups of users
* a user belongs to at least one group of user
* permissions (read, update, create, delete)
* permissions are assigned to groups (and not to users)

For *CubicWeb* in particular:

* we associate rights at the enttities/relations schema level
* for each entity, we distinguish four kind of permissions: read,
  add, update and delete
* for each relation, we distinguish three kinds of permissions: read,
  add and delete (we can not modify a relation)
* the basic groups are: Administrators, Users and Guests
* by default, users belong to the group Users
* there is a virtual group called `Owners` to which we
  can associate only deletion and update permissions
* we can not add users to the `Owners` group, they are
  implicitly added to it according to the context of the objects
  they own
* the permissions of this group are only checked on update/deletion
  actions if all the other groups the user belongs to does not provide
  those permissions

Setting permissions is done with the attribute `permissions` of entities and
relation types. It defines a dictionary where the keys are the access types
(action), and the values are the authorized groups or expressions.

For an entity type, the possible actions are `read`, `add`, `update` and
`delete`.

For a relation type, the possible actions are `read`, `add`, and `delete`.

For each access type, a tuple indicates the name of the authorized groups and/or
one or multiple RQL expressions to satisfy to grant access. The access is
provided if the user is in one of the listed groups or one of if the RQL condition
is satisfied.

The standard user groups
````````````````````````

* `guests`

* `users`

* `managers`

* `owners` : virtual group corresponding to the entity's owner.
  This can only be used for the actions `update` and `delete` of an entity
  type.

It is also possible to use specific groups if they are defined in the precreate
of the cube (``migration/precreate.py``).


Use of RQL expression for write permissions
 ```````````````````````````````````````````
It is possible to define RQL expression to provide update permission
(`add`, `delete` and `update`) on relation and entity types.

RQL expression for entity type permission :

* you have to use the class `ERQLExpression`

* the used expression corresponds to the WHERE statement of an RQL query

* in this expression, the variables X and U are pre-defined references
  respectively on the current entity (on which the action is verified) and
  on the user who send the request

* it is possible to use, in this expression, a special relation
  "has_<ACTION>_permission" where the subject is the user and the
  object is any variable, meaning that the user needs to have
  permission to execute the action <ACTION> on the entities related
  to this variable

For RQL expressions on a relation type, the principles are the same except
for the following :

* you have to use the class `RRQLExpression` in the case of a non-final relation

* in the expression, the variables S, O and U are pre-defined references
  to respectively the subject and the object of the current relation (on
  which the action is being verified) and the user who executed the query

* we can also define rights over attributes of an entity (non-final relation),
  knowing that :

  - to define RQL expression, we have to use the class `ERQLExpression`
    in which X represents the entity the attribute belongs to

  - the permissions `add` and `delete` are equivalent. Only `add`/`read`
    are actually taken in consideration.

:Note on the use of RQL expression for `add` permission:

  Potentially, the use of an RQL expression to add an entity or a
  relation can cause problems for the user interface, because if the
  expression uses the entity or the relation to create, then we are
  not able to verify the permissions before we actually add the entity
  (please note that this is not a problem for the RQL server at all,
  because the permissions checks are done after the creation). In such
  case, the permission check methods (CubicWebEntitySchema.check_perm
  and has_perm) can indicate that the user is not allowed to create
  this entity but can obtain the permission.
  To compensate this problem, it is usually necessary, for such case,
  to use an action that reflects the schema permissions but which enables
  to check properly the permissions so that it would show up if necessary.


Use of RQL expression for reading rights
````````````````````````````````````````

The principles are the same but with the following restrictions :

* we can not use `RRQLExpression` on relation types for reading

* special relations "has_<ACTION>_permission" can not be used




Defining your schema using yams
-------------------------------

Entity type definition
~~~~~~~~~~~~~~~~~~~~~~

An entity type is defined by a Python class which inherits from `EntityType`.
The class definition contains the description of attributes and relations
for the defined entity type.
The class name corresponds to the entity type name. It is exepected to be
defined in the module ``mycube.schema``.


For example ::

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

The name of the Python attribute corresponds to the name of the attribute
or the relation in *CubicWeb* application.

An attribute is defined in the schema as follows::

    attr_name = attr_type(properties*)

where `attr_type` is one of the type listed above and `properties` is
a list of the attribute needs to statisfy (see :ref:`properties`
for more details).


* relations can be defined by using `ObjectRelation` or `SubjectRelation`.
  The first argument of `SubjectRelation` or `ObjectRelation` gives respectively
  the object/subject entity type of the relation. This could be :

  * a string corresponding to an entity type

  * a tuple of string corresponding to multiple entity types

  * special string such as follows :

    - "**" : all types of entities
    - "*" : all types of non-meta entities
    - "@" : all types of meta entities but not system entities (e.g. used for
      the basic schema description)

* it is possible to use the attribute `meta` to flag an entity type as a `meta`
  (e.g. used to describe/categorize other entities)

Inheritance
```````````
XXX feed me


Definition of relations
~~~~~~~~~~~~~~~~~~~~~~~

XXX add note about defining relation type / definition

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

In the case of simultaneous relations definitions, `subject` and `object`
can both be equal to the value of the first argument of `SubjectRelation`
and `ObjectRelation`.

When a relation is not inlined and not symmetrical, and it does not require
specific permissions, its definition (by using `SubjectRelation` and
`ObjectRelation`) is all we need.


Definition of permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~

The entity type `CWPermission` from the standard library
allows to build very complex and dynamic security architectures. The schema of
this entity type is as follow : ::

    class CWPermission(MetaEntityType):
	"""entity type that may be used to construct some advanced security configuration"""
	name = String(required=True, indexed=True, internationalizable=True, maxsize=100)
	require_group = SubjectRelation('CWGroup', cardinality='+*',
					description=_('groups to which the permission is granted'))
	require_state = SubjectRelation('State',
                                        description=_("entity's state in which the permission is applicable"))
	# can be used on any entity
	require_permission = ObjectRelation('**', cardinality='*1', composite='subject',
					    description=_("link a permission to the entity. This "
							  "permission should be used in the security "
							  "definition of the entity's type to be useful."))


Example of configuration ::


    ...

    class Version(EntityType):
	"""a version is defining the content of a particular project's release"""

	permissions = {'read':   ('managers', 'users', 'guests',),
		       'update': ('managers', 'logilab', 'owners',),
		       'delete': ('managers', ),
		       'add':    ('managers', 'logilab',
				  ERQLExpression('X version_of PROJ, U in_group G,'
						 'PROJ require_permission P, P name "add_version",'
						 'P require_group G'),)}

    ...

    class version_of(RelationType):
	"""link a version to its project. A version is necessarily linked to one and only one project.
	"""
        subject = 'Version'
        object = 'Project'
        cardinality = '?*'
	permissions = {'read':   ('managers', 'users', 'guests',),
		       'delete': ('managers', ),
		       'add':    ('managers', 'logilab',
				  RRQLExpression('O require_permission P, P name "add_version",'
						 'U in_group G, P require_group G'),)
		       }
	inlined = True

This configuration indicates that an entity `CWPermission` named
"add_version" can be associated to a project and provides rights to create
new versions on this project to specific groups. It is important to notice that :

* in such case, we have to protect both the entity type "Version" and the relation
  associating a version to a project ("version_of")

* because of the genericity of the entity type `CWPermission`, we have to execute
  a unification with the groups and/or the states if necessary in the expression
  ("U in_group G, P require_group G" in the above example)
