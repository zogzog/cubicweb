
Meta-data
---------

.. index::
   schema: meta-data;
   schema: eid; creation_date; modification_data; cwuri
   schema: created_by; owned_by; is; is_instance;

Each entity type in |cubicweb| has at least the following meta-data attributes and relations:

eid
  entity's identifier which is unique in an instance. We usually call this identifier `eid` for historical reason.

creation_date
  Date and time of the creation of the entity.

modification_date
  Date and time of the latest modification of an entity.

cwuri
  Reference URL of the entity, which is not expected to change.

created_by
  Relation to the :ref:`users <CWUser>` who has created the entity

owned_by
  Relation to :ref:`users <CWUser>` whom the entity belongs; usually the creator but not
  necessary, and it could have multiple owners notably for permission control

is
  Relation to the :ref:`entity type <CWEType>` of which type the entity is.

is_instance
  Relation to the :ref:`entity types <CWEType>` of which type the
  entity is an instance of.


Virtual RQL relations
---------------------
XXX move this to the RQL chapter.

Those relations may only be used in RQL query and are not actual attributes of your entities...

has_text
  Relation to use to query the full text index (only for entities having fulltextindexed attributes).

identity
  Relation to use to tell that a RQL variable should be the same as entity another
  (but you've to use two different rql variables for querying purpose)



.. |cubicweb| replace:: *CubicWeb*