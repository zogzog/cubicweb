.. -*- coding: utf-8 -*-

.. _RQL:

RQL syntax
----------

Reserved keywords
~~~~~~~~~~~~~~~~~
The keywords are not case sensitive.

::

  AND, ASC, BEING, DELETE, DESC, DISTINCT, EXISTS, FALSE, GROUPBY,
  HAVING, ILIKE, IN, INSERT, LIKE, LIMIT, NOT, NOW, NULL, OFFSET,
  OR, ORDERBY, SET, TODAY, TRUE, UNION, WHERE, WITH


Variables and Typing
~~~~~~~~~~~~~~~~~~~~

With RQL, we do not distinguish between entities and attributes. The
value of an attribute is considered an entity of a particular type (see
below), linked to one (real) entity by a relation called the name of
the attribute.

Entities and values to browse and/or select are represented in
the query by *variables* that must be written in capital letters.

There is a special type **Any**, referring to a non specific type.

We can restrict the possible types for a variable using the
special relation **is** in the constraints.

The possible type(s) for each variable is derived from the schema
according to the constraints expressed above and thanks to the relations
between each variable.

Built-in types
``````````````

The base types supported are string (between double or single quotes),
integers or floats (the separator is '.'), dates and
boolean. We expect to receive a schema in which types String,
Int, Float, Date and Boolean are defined.

* `String` (literal: between double or single quotes).
* `Int`, `Float` (separator being'.').
* `Date`, `Datetime`, `Time` (literal: string YYYY/MM/DD [hh:mm] or keywords
  `TODAY` and `NOW`).
* `Boolean` (keywords `TRUE` and `FALSE`).
* `Keyword` NULL.


Operators
~~~~~~~~~

Logical Operators
`````````````````
::

     AND, OR, NOT, ','

  ',' is equivalent to 'AND' but with the smallest among the priority
  of logical operators (see :ref:`PriorityOperators`).

Mathematical Operators
``````````````````````
::

     +, -, *, /

Comparison operators
````````````````````
::

     =, <, <=, >=, >, ~=, IN, LIKE, ILIKE

* Syntax to use comparison operator:

    `VARIABLE relation operator VALUE`

* The operator `=` is the default operator and can be omitted.

* `relation` name is always attended

* The operator `LIKE` equivalent to `~=` can be used with the
  special character `%` in a string to indicate that the chain
  must start or finish by a prefix/suffix:
  ::

     Any X WHERE X name ~= 'Th%'
     Any X WHERE X name LIKE '%lt'

* The operator `ILIKE` is the case insensitive version of `LIKE`.

* The operator `IN` provides a list of possible values:
  ::

    Any X WHERE X name IN ('chauvat', 'fayolle', 'di mascio', 'thenault')


.. XXX nico: "A trick <> 'bar'" wouldn't it be more convenient than "NOT A trick 'bar'" ?

.. _PriorityOperators:

Operators priority
``````````````````

#. "(", ")"
#. '*', '/'
#. '+', '-'
#. 'NOT'
#. 'AND'
#. 'OR'
#. ','


Search Query
~~~~~~~~~~~~

   [ `DISTINCT`] <entity type> V1 (, V2) \ *
   [ `GROUPBY` V1 (V2) \*] [ `ORDERBY` <orderterms>]
   [ `LIMIT` <value>] [ `OFFSET` <value>]
   [ `WHERE` <restriction>]
   [ `WITH` V1 (, V2) \ * BEING (<query>)]
   [ `HAVING` <restriction>]
   [ `UNION` <query>]

:entity type:
   Type of selected variables.
   The special type `Any` is equivalent to not specify a type.
:restriction:
   list of conditions to test successively
     `V1 relation V2 | <static value>`
:orderterms:
   Definition of the selection order: variable or column number followed by
   sorting method ( `ASC`, `DESC`), ASC is the default.
:note for grouped queries:
   For grouped queries (e.g., a clause `GROUPBY`), all
   selected variables must be aggregated or grouped.


Sorting and groups
``````````````````

- For grouped queries (e.g. with a GROUPBY clause), all
  selected variables should be grouped at the right of the keyword.

- If the sorting method (SORT_METHOD) is not specified, then the sorting is
  ascendant (`ASC`).

- Aggregate Functions: COUNT, MIN, MAX, AVG, SUM, GROUP_CONCAT

Having
``````

The HAVING clause, as in SQL, has been originally introduced to restrict a query
according to value returned by an aggregate function, e.g.::

    Any X GROUPBY X WHERE X relation Y HAVING COUNT(Y) > 10

It may however be used for something else...

In the WHERE clause, we are limited to 3-expression, such thing can't be
expressed directly as in the SQL's way. But this can be expressed using HAVING
comparison expression.

For instance, let's say you want to get people whose uppercased first name equals
to another person uppercased first name::

    Person X WHERE X firstname XFN, Y firstname YFN HAVING X > Y, UPPER(XFN) = UPPER(YFN)

This open some new possibilities. Another example::

    Person X WHERE X birthday XB HAVING YEAR(XB) = 2000

That lets you use transformation functions not only in selection but for
restriction as well and to by-pass limitation of the WHERE clause, which was the
major flaw in the RQL language.

Notice that while we would like this to work without the HAVING clause, this
can't be currently be done because it introduces an ambiguity in RQL's grammar
that can't be handled by Yapps_, the parser's generator we're using.

Negation
````````

* A query such as `Document X WHERE NOT X owned_by U` means "the documents have
  no relation `owned_by`".

* But the query `Document X WHERE NOT X owned_by U, U login "syt"` means "the
  documents have no relation `owned_by` with the user syt". They may have a
  relation "owned_by" with another user.

Identity
````````

You can use the special relation `identity` in a query to
add an identity constraint between two variables. This is equivalent
to ``is`` in python::

   Any A WHERE A comments B, A identity B

return all objects that comment themselves. The relation `identity` is
especially useful when defining the rules for securities with `RQLExpressions`.


Limit / offset
``````````````
::

    Any P ORDERBY N LIMIT 5 OFFSET 10 WHERE P is Person, P firstname N


Exists
``````
::

    Any X ORDERBY PN,N
    WHERE X num N, X version_of P, P name PN,
          EXISTS(X in_state S, S name IN ("dev", "ready"))
          OR EXISTS(T tags X, T name "priority")


Optional relations
``````````````````

It is a similar concept that the `Left outer join`_:

    the result of a left outer join (or simply left join) for table A and B
    always contains all records of the "left" table (A), even if the
    join-condition does not find any matching record in the "right" table (B).

* They allow you to select entities related or not to another.

* You must use the `?` behind the variable to specify that the relation
  toward it is optional:

   - Anomalies of a project attached or not to a version ::

       Any X, V WHERE X concerns P, P eid 42, X corrected_in V?

   - All cards and the project they document if necessary ::

       Any C, P WHERE C is Card, P? documented_by C

    Any T,P,V WHERE T is Ticket, T concerns P, T done_in V?


Subqueries
``````````
::

    (Any X WHERE X is Person) UNION (Any X WHERE X is Company)


     DISTINCT Any W, REF
        WITH W, REF BEING
            (
              (Any W, REF WHERE W is Workcase, W ref REF,
                                 W concerned_by D, D name "Logilab")
               UNION
              (Any W, REF WHERE W is Workcase, W ref REF, '
                                W split_into WP, WP name "WP1")
            )

Function calls
``````````````
::

    Any UPPER(N) WHERE P firstname N
    Any LOWER(N) WHERE P firstname N

Functions available on string: `UPPER`, `LOWER`

.. XXX retrieve available function automatically

For a performance issue, you can enrich the RQL dialect by RDMS (Relational database management system) functions.


Examples
~~~~~~~~

- *Search for the object of identifier 53*
  ::

        Any WHERE X
        X eid 53

- *Search material such as comics, owned by syt and available*
  ::

        Any X WHERE X is Document
        X occurence_of F, F class C, C name 'Comics'
        X owned_by U, U login 'syt'
        X available TRUE

- *Looking for people working for eurocopter interested in training*
  ::

        Any P WHERE
        P is Person, P work_for S, S name 'Eurocopter'
        P interested_by T, T name 'training'

- *Search note less than 10 days old written by jphc or ocy*
  ::

        Any N WHERE
        N is Note, N written_on D, D day> (today -10),
        N written_by P, P name 'jphc' or P name 'ocy'

- *Looking for people interested in training or living in Paris*
  ::

        Any P WHERE
        P is Person, (P interested_by T, T name 'training') OR
        (P city 'Paris')

- *The surname and firstname of all people*
  ::

        Any N, P WHERE
        X is Person, X name N, X firstname P

  Note that the selection of several entities generally force
  the use of "Any" because the type specification applies otherwise
  to all the selected variables. We could write here
  ::

        String N, P WHERE
        X is Person, X name N, X first_name P


  Note: You can not specify several types with * ... where X is FirstType or X is SecondType*.
  To specify several types explicitly, you have to do

  ::

        Any X where X is in (FirstType, SecondType)


Insertion query
~~~~~~~~~~~~~~~

    `INSERT` <entity type> V1 (, <entity type> V2) \ * `:` <assignments>
    [ `WHERE` <restriction>]

:assignments:
   list of relations to assign in the form `V1 relationship V2 | <static value>`

The restriction can define variables used in assignments.

Caution, if a restriction is specified, the insertion is done for
*each line result returned by the restriction*.

- *Insert a new person named 'foo'*
  ::

        INSERT Person X: X name 'foo'

- *Insert a new person named 'foo', another called 'nice' and a 'friend' relation
  between them*
  ::

        INSERT Person X, Person Y: X name 'foo', Y name 'nice', X friend Y

- *Insert a new person named 'foo' and a 'friend' relation with an existing
  person called 'nice'*
  ::

        INSERT Person X: X name 'foo', X friend  Y WHERE name 'nice'

Update and relation creation queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    `SET` <assignements>
    [ `WHERE` <restriction>]

Caution, if a restriction is specified, the update is done *for
each result line returned by the restriction*.

- *Renaming of the person named 'foo' to 'bar' with the first name changed*
  ::

        SET X name 'bar', X firstname 'original' WHERE X is Person, X name 'foo'

- *Insert a relation of type 'know' between objects linked by
  the relation of type 'friend'*
  ::

        SET X know Y  WHERE X friend Y


Deletion query
~~~~~~~~~~~~~~

    `DELETE` (<entity type> V) | (V1 relation v2 ),...
    [ `WHERE` <restriction>]

Caution, if a restriction is specified, the deletion is made *for
each line result returned by the restriction*.

- *Deletion of the person named 'foo'*
  ::

        DELETE Person X WHERE X name 'foo'

- *Removal of all relations of type 'friend' from the person named 'foo'*
  ::

        DELETE X friend Y WHERE X is Person, X name 'foo'


Virtual RQL relations
~~~~~~~~~~~~~~~~~~~~~

Those relations may only be used in RQL query and are not actual
attributes of your entities.

* `has_text`: relation to use to query the full text index (only for
  entities having fulltextindexed attributes).

* `identity`: `Identity`_ relation to use to tell that a RQL variable should be
  the same as another (but you've to use two different rql variables
  for querying purpose)

* `is`: relation to enforce possible types for a variable



.. _Yapps: http://theory.stanford.edu/~amitp/yapps/
.. _Left outer join: http://en.wikipedia.org/wiki/Join_(SQL)#Left_outer_join
