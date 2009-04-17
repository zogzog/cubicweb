.. -*- coding: utf-8 -*-

Let's learn RQL by practice...

.. contents::

Introduction
------------

RQL has a syntax and principle inspirated from the SQL query language, though
it's at a higher level in order to be more intuitive and suitable to easily make
advanced queries on a schema based database.

* the main idea in RQL is that we'are following relations between entities
* attributes are a special case of relations
* RQL has been inspirated from SQL but is at a higher level
* a knowledge of the application'schema is necessary to build rql queries

To use RQL, you'll have to know the basis of the language as well as a good
knowledge of the application'schema. You can always view it using the "schema"
link in user's dropdown menu (on the top-right of the screen) or by clicking here_.

.. _here: schema


Some bits of théory
-------------------

Variables et types
~~~~~~~~~~~~~~~~~~
Entities and attributes'value to follow and / or select are represented by the
query by *variables* which must be written upper-case.

Possible types for each variable are deducted from the schema according to
constraints in the query.

You can explicitly constrain a variable's type using the special relation "is".

Base types
~~~~~~~~~~
* `String` (literal: between double or simple quotes)
* `Int`, `Float` (using '.' as separator)
* `Date`, `Datetime`, `Time` (literal: string YYYY/MM/DD[ hh:mm] or
  `TODAY` and `NOW` keywords)
* `Boolean` (keywords `TRUE` et `FALSE`)
* keyword `NULL`

Opérateurs
~~~~~~~~~~
* Logical operators : `AND`, `OR`, `,`
* Mathematical operators: `+`, `-`, `*`, `/`
* Comparisons operators: `=`, `<`, `<=`, `>=`, `>`, `~=`, `LIKE`, `IN`

  * `=` is the default comparison operator

  * `LIKE` / `~=` permits use of the special character `%` in a string to tell
    the string must begin or end with a prefix or suffix (as SQL LIKE operator) ::
    
      Any X WHERE X name ~= 'Th%'
      Any X WHERE X name LIKE '%lt'

  * `IN` permits to give a list of possible values ::

      Any X WHERE X name IN ('chauvat', 'fayolle', 'di mascio', 'thenault')

Grammaire des requêtes de recherche
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

  [DISTINCT] <entity type> V1(, V2)*
  [GROUPBY V1(, V2)*]  [ORDERBY <orderterms>]
  [WHERE <restriction>] 
  [LIMIT <value>] [OFFSET <value>]

:entity type:
  Type of the selected variable(s). You'll usually use `Any` type to not specify
  any type.
:restriction:
  List of relations to follow, in the form
    `V1 relation V2|<constant value>`
:orderterms:
  Define a selection order : variable or column number, followed by the sort method
  (`ASC`, `DESC`), with ASC as default when not specified

notice about grouped query (e.g using a `GROUPBY` clause): every selected
variable should be either grouped or used in an aggregat function.


Example schema
--------------

In this document, we will suppose the application's schema is the one described
here. Available entity types are :

:Person:
  ::

	name      (String, required) 
	birthday (Date)


:Company:
  ::

	name   (String)


:Note:
  ::

	diem (Date)
	type (String)


And relations between those entities: ::

	Person  works_for    Company
	Person  evaluated_by Note
	Company evaluated_by Note


Meta-data
~~~~~~~~~
Every entities'type have the following meta-data:

* `eid (Int)`, a unique identifier
* `creation_date (Datetime)`, date on which the entity has been created
* `modification_date (Datetime)`, lastest date on which the entity has been modified

* `created_by (CWUser)`, relation to the user which has created this entity

* `owned_by (CWUser)`, relation to the user()s considered as owner of this
  entity, the entity's creator by default

* `is (Eetype)`, special relation to specify a variable type.

A user's entity has the following schema:

:CWUser:
  ::

	login  	  (String) not null
	password  (Password)
	firstname (String)
	surname   (String)


Basis queries
-------------
0. *Every persons* ::
   
      Person X

   or ::

      Any X WHERE X is Person


1. *The company named Logilab* ::

      Company S WHERE S name 'Logilab'


2. *Every entities with a "name" attribute whose value starts with 'Log'* ::

      Any S WHERE S name LIKE 'Log%'

   or ::

      Any S WHERE S name ~= 'Log%'

   This query may return Person or Company entities.


3. *Every persons working for the Logilab company* ::

      Person P WHERE P works_for S, S name "Logilab"

   or ::

      Person P WHERE P works_for S AND S name "Logilab"


4. *Company named Caesium ou Logilab* ::

      Company S WHERE S name IN ('Logilab','Caesium')

   or ::

      Company S WHERE S name 'Logilab' OR S name 'Caesium'


5. *Every company but ones named Caesium ou Logilab* ::

      Company S WHERE NOT S name IN ('Logilab','Caesium')

   or ::

      Company S WHERE NOT S name 'Logilab' AND NOT S name 'Caesium'


6. *Entities evaluated by the note with eid 43* ::

      Any X WHERE X evaluated_by N, N eid 43


7. *Every persons order by birthday from the youngest to the oldest* ::
   
      Person X ORDERBY D DESC WHERE X birthday D

   Notice you've to define a variable using the birthday relation to use it in the
   sort term. 


8. *Number of persons working for each known company* ::
   
      Any S, COUNT(X) GROUPBY S WHERE X works_for S

   Notice you've that since you're writing a grouped query on S, X have to be
   either grouped as well or used in an aggregat function (as in this example).


   
Advanced
--------
0. *Person with no name specified (i.e NULL)* ::

      Person P WHERE P name NULL


1. *Person which are not working for any company* ::

      Person P WHERE NOT p works_for S


2. *Every company where person named toto isn't working* ::

      Company S WHERE NOT P works_for S , P name 'toto'


3. *Every entity which have been modified between today and yesterday* ::

      Any X WHERE X modification_date <= TODAY, X modification_date >= TODAY - 1


4. *Every note without type, to be done in the next 7 days, ordered by date* ::

      Any N, D where N is Note, N type NULL, N diem D, N diem >= TODAY,
      N diem < today + 7 ORDERBY D


5. *Person with an homonym (without duplicate)* ::

      DISTINCT Person X,Y where X name NX, Y name NX

   or even better (e.g. without both (Xeid, Yeid) and (Yeid, Xeid) in the results) ::

      Person X,Y where X name NX, Y name NX, X eid XE, Y eid > XE
