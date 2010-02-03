.. _CWBaseEntityTypes:

Pre-defined entities in the library
-----------------------------------

The library defines a set of entity schemas that are._cwuired by the system
or commonly used in *CubicWeb* instances.


Entity types used to store the schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* _`CWEType`, entity type
* _`CWRType`, relation type
* _`CWRelation`, relation definition
* _`CWAttribute`, attribute relation definition
* _`CWConstraint`,  `CWConstraintType`, `RQLExpression`

Entity types used to manage users and permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* _`CWUser`, system users
* _`CWGroup`, users groups
* _`CWPermission`, used to configure the security of the instance

Entity types used to manage workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* _`Workflow`, workflow entity, linked to some entity types which may use this workflow
* _`State`, workflow state
* _`Transition`, workflow transition
* _`TrInfo`, record of a transition trafic for an entity

Other entity types
~~~~~~~~~~~~~~~~~~
* _`CWCache`, cache entities used to improve performances
* _`CWProperty`, used to configure the instance

* _`EmailAddress`, email address, used by the system to send notifications
  to the users and also used by others optionnals schemas

* _`Bookmark`, an entity type used to allow a user to customize his links within
  the instance

* _`ExternalUri`, used for semantic web site to indicate that an entity is the
  same as another from an external site
