
Pre-defined entities in the library
----------------------------------

The library defines a set of entity schemas that are required by the system
or commonly used in *CubicWeb* instances.


Entity types used to store the schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* `CWEType`, entity type
* `CWRType`, relation type
* `CWRelation`, relation definition
* `CWAttribute`, attribute relation definition
* `CWConstraint`,  `CWConstraintType`, `RQLExpression`

Entity types used to manage users and permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* `CWUser`, system users
* `CWGroup`, users groups
* `CWPermission`, used to configure the security of the instance

Entity types used to manage workflows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* `State`, workflow state
* `Transition`, workflow transition
* `TrInfo`, record of a transition trafic for an entity

Other entity types
~~~~~~~~~~~~~~~~~~
* `CWCache`, cache entities used to improve performances
* `CWProperty`, used to configure the instance

* `EmailAddress`, email address, used by the system to send notifications
  to the users and also used by others optionnals schemas

* `Bookmark`, an entity type used to allow a user to customize his links within
  the instance
