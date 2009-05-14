
Meta-data
----------

Each entity type has at least the following meta-relations:

eid
~~~
Each entity in *CubicWeb* has an associated identifier which is unique
in an instance. We usually call this identifier `eid`.

`creation_date` and `modification_date`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Date and time of the creation / lastest modification of an entity.


`created_by`
~~~~~~~~~~~~
relation to the :ref:`users <CWUser>` who has created the entity

`owned_by`
~~~~~~~~~~
relation to :ref:`users <CWUser>` whom the entity belongs; usually the creator but not
necessary, and it could have multiple owners notably for permission control

`is`
~~~~~
relation to the :ref:`entity type <CWEType>` of which type the entity is.

`is_instance`
~~~~~~~~~~~~~
relation to the :ref:`entity types <CWEType>` of which type the entity is an instance of.


Special relations
-----------------
`has_text`
~~~~~~~~~~
query the full text index (only for entities having fulltextindexed attributes)

`identity`
~~~~~~~~~~
XXX