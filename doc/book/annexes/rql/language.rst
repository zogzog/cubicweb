.. -*- coding: utf-8 -*-

.. _RQL:

RQL syntax
----------

.. _RQLKeywords:

Reserved keywords
~~~~~~~~~~~~~~~~~

::

  AND, ASC, BEING, DELETE, DESC, DISTINCT, EXISTS, FALSE, GROUPBY,
  HAVING, ILIKE, INSERT, LIKE, LIMIT, NOT, NOW, NULL, OFFSET,
  OR, ORDERBY, SET, TODAY, TRUE, UNION, WHERE, WITH

The keywords are not case sensitive. You should not use them when defining your
schema, or as RQL variable names.


.. _RQLCase:

Case
~~~~

* Variables should be all upper-cased.

* Relation should be all lower-cased and match exactly names of relations defined
  in the schema.

* Entity types should start with an upper cased letter and be followed by at least
  a lower cased latter.


.. _RQLVariables:

Variables and typing
~~~~~~~~~~~~~~~~~~~~

Entities and values to browse and/or select are represented in the query by
*variables* that must be written in capital letters.

With RQL, we do not distinguish between entities and attributes. The value of an
attribute is considered as an entity of a particular type (see below), linked to
one (real) entity by a relation called the name of the attribute, where the
entity is the subject and the attribute the object.

The possible type(s) for each variable is derived from the schema according to
the constraints expressed above and thanks to the relations between each
variable.

We can restrict the possible types for a variable using the special relation
**is** in the restrictions.


.. _VirtualRelations:

Virtual relations
~~~~~~~~~~~~~~~~~

Those relations may only be used in RQL query but are not actual attributes of
your entities.

* `has_text`: relation to use to query the full text index (only for entities
  having fulltextindexed attributes).

* `identity`: relation to use to tell that a RQL variable is the same as another
  when you've to use two different variables for querying purpose. On the
  opposite it's also useful together with the ``NOT`` operator to tell that two
  variables should not identify the same entity


.. _RQLLiterals:

Literal expressions
~~~~~~~~~~~~~~~~~~~

Bases types supported by RQL are those supported by yams schema. Literal values
are expressed as explained below:

* string should be between double or single quotes. If the value contains a
  quote, it should be preceded by a backslash '\\'

* floats separator is dot '.'

* boolean values are ``TRUE`` and ``FALSE`` keywords

* date and time should be expressed as a string with ISO notation : YYYY/MM/DD
  [hh:mm], or using keywords ``TODAY`` and ``NOW``

You may also use the ``NULL`` keyword, meaning 'unspecified'.


.. _RQLOperators:

Operators
~~~~~~~~~

.. _RQLLogicalOperators:

Logical operators
`````````````````
::

     AND, OR, NOT, ','

',' is equivalent to 'AND' but with the smallest among the priority of logical
operators (see :ref:`RQLOperatorsPriority`).

.. _RQLMathematicalOperators:

Mathematical operators
``````````````````````

+----------+---------------------+-----------+--------+
| Operator |    Description      | Example   | Result |
+==========+=====================+===========+========+
|  `+`     | addition            | 2 + 3     | 5      |
+----------+---------------------+-----------+--------+
|  `-`     | subtraction         | 2 - 3     | -1     |
+----------+---------------------+-----------+--------+
|  `*`     | multiplication      | 2 * 3     | 6      |
+----------+---------------------+-----------+--------+
|  /       | division            | 4 / 2     | 2      |
+----------+---------------------+-----------+--------+
|  %       | modulo (remainder)  | 5 % 4     | 1      |
+----------+---------------------+-----------+--------+
|  ^       | exponentiation      | 2.0 ^ 3.0 | 8      |
+----------+---------------------+-----------+--------+
|  &       | bitwise AND         | 91 & 15   | 11     |
+----------+---------------------+-----------+--------+
|  `|`     | bitwise OR          | 32 | 3    | 35     |
+----------+---------------------+-----------+--------+
|  #       | bitwise XOR         | 17 # 5    | 20     |
+----------+---------------------+-----------+--------+
|  ~       | bitwise NOT         | ~1        | -2     |
+----------+---------------------+-----------+--------+
|  <<      | bitwise shift left  | 1 << 4    | 16     |
+----------+---------------------+-----------+--------+
|  >>      | bitwise shift right | 8 >> 2    | 2      |
+----------+---------------------+-----------+--------+


Notice integer division truncates results depending on the backend behaviour. For
instance, postgresql does.


.. _RQLComparisonOperators:

Comparison operators
````````````````````
 ::

     =, !=, <, <=, >=, >, IN


The syntax to use comparison operators is:

    `VARIABLE attribute <operator> VALUE`

The `=` operator is the default operator and can be omitted, i.e. :

    `VARIABLE attribute = VALUE`

is equivalent to

    `VARIABLE attribute VALUE`


The operator `IN` provides a list of possible values:

.. sourcecode:: sql

    Any X WHERE X name IN ('chauvat', 'fayolle', 'di mascio', 'thenault')


.. _RQLStringOperators:

String operators
````````````````
::

  LIKE, ILIKE, ~=, REGEXP

The ``LIKE`` string operator can be used with the special character `%` in
a string as wild-card:

.. sourcecode:: sql

     -- match every entity whose name starts with 'Th'
     Any X WHERE X name ~= 'Th%'
     -- match every entity whose name endswith 'lt'
     Any X WHERE X name LIKE '%lt'
     -- match every entity whose name contains a 'l' and a 't'
     Any X WHERE X name LIKE '%l%t%'

``ILIKE`` is the case insensitive version of ``LIKE``. It's not
available on all backend (e.g. sqlite doesn't support it). If not available for
your backend, ``ILIKE`` will behave like ``LIKE``.

`~=` is a shortcut version of ``ILIKE``, or of ``LIKE`` when the
former is not available on the back-end.


The ``REGEXP`` is an alternative to ``LIKE`` that supports POSIX
regular expressions:

.. sourcecode:: sql

   -- match entities whose title starts with a digit
   Any X WHERE X title REGEXP "^[0-9].*"


The underlying SQL operator used is back-end-dependent :

- the ``~`` operator is used for postgresql,
- the ``REGEXP`` operator for mysql and sqlite.

Other back-ends are not supported yet.


.. _RQLOperatorsPriority:

Operators priority
``````````````````

#. `(`, `)`
#. `^`, `<<`, `>>`
#. `*`, `/`, `%`, `&`
#. `+`, `-`, `|`, `#`
#. `NOT`
#. `AND`
#. `OR`
#. `,`


.. _RQLSearchQuery:

Search Query
~~~~~~~~~~~~

Simplified grammar of search query: ::

   [ `DISTINCT`] `Any` V1 (, V2) \*
   [ `GROUPBY` V1 (, V2) \*] [ `ORDERBY` <orderterms>]
   [ `LIMIT` <value>] [ `OFFSET` <value>]
   [ `WHERE` <triplet restrictions>]
   [ `WITH` V1 (, V2)\* BEING (<query>)]
   [ `HAVING` <other restrictions>]
   [ `UNION` <query>]

Selection
`````````

The fist occuring clause is the selection of terms that should be in the result
set.  Terms may be variable, literals, function calls, arithmetic, etc. and each
term is separated by a comma.

There will be as much column in the result set as term in this clause, respecting
order.

Syntax for function call is somewhat intuitive, for instance:

.. sourcecode:: sql

    Any UPPER(N) WHERE P firstname N


Grouping and aggregating
````````````````````````

The ``GROUPBY`` keyword is followed by a list of terms on which results
should be grouped. They are usually used with aggregate functions, responsible to
aggregate values for each group (see :ref:`RQLAggregateFunctions`).

For grouped queries, all selected variables must be either aggregated (i.e. used
by an aggregate function) or grouped (i.e. listed in the ``GROUPBY``
clause).


Sorting
```````

The ``ORDERBY`` keyword if followed by the definition of the selection
order: variable or column number followed by sorting method (``ASC``,
``DESC``), ``ASC`` being the default. If the sorting method is not
specified, then the sorting is ascendant (`ASC`).


Pagination
``````````

The ``LIMIT`` and ``OFFSET`` keywords may be respectively used to
limit the number of results and to tell from which result line to start (for
instance, use `LIMIT 20` to get the first 20 results, then `LIMIT 20 OFFSET 20`
to get the next 20.


Restrictions
````````````

The ``WHERE`` keyword introduce one of the "main" part of the query, where
you "define" variables and add some restrictions telling what you're interested
in.

It's a list of triplets "subject relation object", e.g. `V1 relation
(V2 | <static value>)`. Triplets are separated using :ref:`RQLLogicalOperators`.

.. note::

  About the negation operator (``NOT``):

  * ``NOT X relation Y`` is equivalent to ``NOT EXISTS(X relation Y)``

  * ``Any X WHERE NOT X owned_by U`` means "entities that have no relation
    ``owned_by``".

  * ``Any X WHERE NOT X owned_by U, U login "syt"`` means "the entity have no
    relation ``owned_by`` with the user syt". They may have a relation "owned_by"
    with another user.

In this clause, you can also use ``EXISTS`` when you want to know if some
expression is true and do not need the complete set of elements that make it
true. Testing for existence is much faster than fetching the complete set of
results, especially when you think about using ``OR`` against several expressions. For instance
if you want to retrieve versions which are in state "ready" or tagged by
"priority", you should write :

.. sourcecode:: sql

    Any X ORDERBY PN,N
    WHERE X num N, X version_of P, P name PN,
          EXISTS(X in_state S, S name "ready")
          OR EXISTS(T tags X, T name "priority")

not

.. sourcecode:: sql

    Any X ORDERBY PN,N
    WHERE X num N, X version_of P, P name PN,
          (X in_state S, S name "ready")
          OR (T tags X, T name "priority")

Both queries aren't at all equivalent :

* the former will retrieve all versions, then check for each one which are in the
  matching state of or tagged by the expected tag,

* the later will retrieve all versions, state and tags (cartesian product!),
  compute join and then exclude each row which are in the matching state or
  tagged by the expected tag. This implies that you won't get any result if the
  in_state or tag tables are empty (ie there is no such relation in the
  application). This is usually NOT what you want.

Another common case where you may want to use ``EXISTS`` is when you
find yourself using ``DISTINCT`` at the beginning of your query to
remove duplicate results. The typical case is when you have a
multivalued relation such as Version version_of Project and you want
to retrieve projects which have a version:

.. sourcecode:: sql

  Any P WHERE V version_of P

will return each project number of versions times. So you may be
tempted to use:

.. sourcecode:: sql

  DISTINCT Any P WHERE V version_of P

This will work, but is not efficient, as it will use the ``SELECT
DISTINCT`` SQL predicate, which needs to retrieve all projects, then
sort them and discard duplicates, which can have a very high cost for
large result sets. So the best way to write this is:

.. sourcecode:: sql

  Any P WHERE EXISTS(V version_of P)


You can also use the question mark (`?`) to mark optional relations. This allows
you to select entities related **or not** to another. It is a similar concept
to `Left outer join`_:

    the result of a left outer join (or simply left join) for table A and B
    always contains all records of the "left" table (A), even if the
    join-condition does not find any matching record in the "right" table (B).

You must use the `?` behind a variable to specify that the relation to
that variable is optional. For instance:

- Bugs of a project attached or not to a version

   .. sourcecode:: sql

       Any X, V WHERE X concerns P, P eid 42, X corrected_in V?

  You will get a result set containing all the project's tickets, with either the
  version in which it's fixed or None for tickets not related to a version.


- All cards and the project they document if any

  .. sourcecode:: sql

       Any C, P WHERE C is Card, P? documented_by C

Notice you may also use outer join:

- on the RHS of attribute relation, e.g.

  .. sourcecode:: sql

       Any X WHERE X ref XR, Y name XR?

  so that Y is outer joined on X by ref/name attributes comparison


- on any side of an ``HAVING`` expression, e.g.

  .. sourcecode:: sql

       Any X WHERE X creation_date XC, Y creation_date YC
       HAVING YEAR(XC)=YEAR(YC)?

  so that Y is outer joined on X by comparison of the year extracted from their
  creation date.

  .. sourcecode:: sql

       Any X WHERE X creation_date XC, Y creation_date YC
       HAVING YEAR(XC)?=YEAR(YC)

  would outer join X on Y instead.


Having restrictions
```````````````````

The ``HAVING`` clause, as in SQL, may be used to restrict a query
according to value returned by an aggregate function, e.g.

.. sourcecode:: sql

    Any X GROUPBY X WHERE X relation Y HAVING COUNT(Y) > 10

It may however be used for something else: In the ``WHERE`` clause, we are
limited to triplet expressions, so some things may not be expressed there. Let's
take an example : if you want to get people whose upper-cased first name equals to
another person upper-cased first name. There is no proper way to express this
using triplet, so you should use something like:

.. sourcecode:: sql

    Any X WHERE X firstname XFN, Y firstname YFN, NOT X identity Y HAVING UPPER(XFN) = UPPER(YFN)

Another example: imagine you want person born in 2000:

.. sourcecode:: sql

    Any X WHERE X birthday XB HAVING YEAR(XB) = 2000

Notice that while we would like this to work without the HAVING clause, this
can't be currently be done because it introduces an ambiguity in RQL's grammar
that can't be handled by Yapps_, the parser's generator we're using.


Sub-queries
```````````

The ``WITH`` keyword introduce sub-queries clause. Each sub-query has the
form:

  V1(,V2) BEING (rql query)

Variables at the left of the ``BEING`` keyword defines into which
variables results from the sub-query will be mapped to into the outer query.
Sub-queries are separated from each other using a comma.

Let's say we want to retrieve for each project its number of versions and its
number of tickets. Due to the nature of relational algebra behind the scene, this
can't be achieved using a single query. You have to write something along the
line of:

.. sourcecode:: sql

  Any X, VC, TC WHERE X identity XX
  WITH X, VC BEING (Any X, COUNT(V) GROUPBY X WHERE V version_of X),
       XX, TC BEING (Any X, COUNT(T) GROUPBY X WHERE T ticket_of X)

Notice that we can't reuse a same variable name as alias for two different
sub-queries, hence the usage of 'X' and 'XX' in this example, which are then
unified using the special `identity` relation (see :ref:`VirtualRelations`).

.. warning::

  Sub-queries define a new variable scope, so even if a variable has the same name
  in the outer query and in the sub-query, they technically **aren't** the same
  variable. So:

  .. sourcecode:: sql

     Any W, REF WITH W, REF BEING
         (Any W, REF WHERE W is Workcase, W ref REF,
                           W concerned_by D, D name "Logilab")

  could be written:

  .. sourcecode:: sql

     Any W, REF WITH W, REF BEING
        (Any W1, REF1 WHERE W1 is Workcase, W1 ref REF1,
                            W1 concerned_by D, D name "Logilab")

  Also, when a variable is coming from a sub-query, you currently can't reference
  its attribute or inlined relations in the outer query, you've to fetch them in
  the sub-query. For instance, let's say we want to sort by project name in our
  first example, we would have to write:

  .. sourcecode:: sql


    Any X, VC, TC ORDERBY XN WHERE X identity XX
    WITH X, XN, VC BEING (Any X, COUNT(V) GROUPBY X,XN WHERE V version_of X, X name XN),
         XX, TC BEING (Any X, COUNT(T) GROUPBY X WHERE T ticket_of X)

  instead of:

  .. sourcecode:: sql

    Any X, VC, TC ORDERBY XN WHERE X identity XX, X name XN,
    WITH X, XN, VC BEING (Any X, COUNT(V) GROUPBY X WHERE V version_of X),
         XX, TC BEING (Any X, COUNT(T) GROUPBY X WHERE T ticket_of X)

  which would result in a SQL execution error.


Union
`````

You may get a result set containing the concatenation of several queries using
the ``UNION``. The selection of each query should have the same number of
columns.

.. sourcecode:: sql

    (Any X, XN WHERE X is Person, X surname XN) UNION (Any X,XN WHERE X is Company, X name XN)


.. _RQLFunctions:

Available functions
~~~~~~~~~~~~~~~~~~~

Below is the list of aggregate and transformation functions that are supported
nativly by the framework. Notice that cubes may define additional functions.

.. _RQLAggregateFunctions:

Aggregate functions
```````````````````
+------------------------+----------------------------------------------------------+
| ``COUNT(Any)``         | return the number of rows                                |
+------------------------+----------------------------------------------------------+
| ``MIN(Any)``           | return the minimum value                                 |
+------------------------+----------------------------------------------------------+
| ``MAX(Any)``           | return the maximum value                                 |
+------------------------+----------------------------------------------------------+
| ``AVG(Any)``           | return the average value                                 |
+------------------------+----------------------------------------------------------+
| ``SUM(Any)``           | return the sum of values                                 |
+------------------------+----------------------------------------------------------+
| ``COMMA_JOIN(String)`` | return each value separated by a comma (for string only) |
+------------------------+----------------------------------------------------------+

All aggregate functions above take a single argument. Take care some aggregate
functions (e.g. ``MAX``, ``MIN``) may return `None` if there is no
result row.

.. _RQLStringFunctions:

String transformation functions
```````````````````````````````

+-----------------------------------------------+-----------------------------------------------------------------+
| ``UPPER(String)``                             | upper case the string                                           |
+-----------------------------------------------+-----------------------------------------------------------------+
| ``LOWER(String)``                             | lower case the string                                           |
+-----------------------------------------------+-----------------------------------------------------------------+
| ``LENGTH(String)``                            | return the length of the string                                 |
+-----------------------------------------------+-----------------------------------------------------------------+
| ``SUBSTRING(String, start, length)``          | extract from the string a string starting at given index and of |
|                                               | given length                                                    |
+-----------------------------------------------+-----------------------------------------------------------------+
| ``LIMIT_SIZE(String, max size)``              | if the length of the string is greater than given max size,     |
|                                               | strip it and add ellipsis ("..."). The resulting string will    |
|                                               | hence have max size + 3 characters                              |
+-----------------------------------------------+-----------------------------------------------------------------+
| ``TEXT_LIMIT_SIZE(String, format, max size)`` | similar to the above, but allow to specify the MIME type of the |
|                                               | text contained by the string. Supported formats are text/html,  |
|                                               | text/xhtml and text/xml. All others will be considered as plain |
|                                               | text. For non plain text format, sgml tags will be first removed|
|                                               | before limiting the string.                                     |
+-----------------------------------------------+-----------------------------------------------------------------+

.. _RQLDateFunctions:

Date extraction functions
`````````````````````````

+----------------------+----------------------------------------+
| ``YEAR(Date)``       | return the year of a date or datetime  |
+----------------------+----------------------------------------+
| ``MONTH(Date)``      | return the month of a date or datetime |
+----------------------+----------------------------------------+
| ``DAY(Date)``        | return the day of a date or datetime   |
+----------------------+----------------------------------------+
| ``HOUR(Datetime)``   | return the hours of a datetime         |
+----------------------+----------------------------------------+
| ``MINUTE(Datetime)`` | return the minutes of a datetime       |
+----------------------+----------------------------------------+
| ``SECOND(Datetime)`` | return the seconds of a datetime       |
+----------------------+----------------------------------------+
| ``WEEKDAY(Date)``    | return the day of week of a date or    |
|                      | datetime.  Sunday == 1, Saturday == 7. |
+----------------------+----------------------------------------+

.. _RQLOtherFunctions:

Other functions
```````````````
+-------------------+--------------------------------------------------------------------+
| ``ABS(num)``      |  return the absolute value of a number                             |
+-------------------+--------------------------------------------------------------------+
| ``RANDOM()``      | return a pseudo-random value from 0.0 to 1.0                       |
+-------------------+--------------------------------------------------------------------+
| ``FSPATH(X)``     | expect X to be an attribute whose value is stored in a             |
|                   | :class:`BFSStorage` and return its path on the file system         |
+-------------------+--------------------------------------------------------------------+
| ``FTIRANK(X)``    | expect X to be an entity used in a has_text relation, and return a |
|                   | number corresponding to the rank order of each resulting entity    |
+-------------------+--------------------------------------------------------------------+
| ``CAST(Type, X)`` | expect X to be an attribute and return it casted into the given    |
|                   | final type                                                         |
+-------------------+--------------------------------------------------------------------+


.. _RQLExamples:

Examples
~~~~~~~~

- *Search for the object of identifier 53*

  .. sourcecode:: sql

        Any X WHERE X eid 53

- *Search material such as comics, owned by syt and available*

  .. sourcecode:: sql

        Any X WHERE X is Document,
                    X occurence_of F, F class C, C name 'Comics',
                    X owned_by U, U login 'syt',
                    X available TRUE

- *Looking for people working for eurocopter interested in training*

  .. sourcecode:: sql

        Any P WHERE P is Person, P work_for S, S name 'Eurocopter',
                    P interested_by T, T name 'training'

- *Search note less than 10 days old written by jphc or ocy*

  .. sourcecode:: sql

        Any N WHERE N is Note, N written_on D, D day> (today -10),
                    N written_by P, P name 'jphc' or P name 'ocy'

- *Looking for people interested in training or living in Paris*

  .. sourcecode:: sql

        Any P WHERE P is Person, EXISTS(P interested_by T, T name 'training') OR
                    (P city 'Paris')

- *The surname and firstname of all people*

  .. sourcecode:: sql

        Any N, P WHERE X is Person, X name N, X firstname P

  Note that the selection of several entities generally force
  the use of "Any" because the type specification applies otherwise
  to all the selected variables. We could write here

  .. sourcecode:: sql

        String N, P WHERE X is Person, X name N, X first_name P


  Note: You can not specify several types with * ... where X is FirstType or X is SecondType*.
  To specify several types explicitly, you have to do


  .. sourcecode:: sql

        Any X WHERE X is IN (FirstType, SecondType)


.. _RQLInsertQuery:

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

  .. sourcecode:: sql

        INSERT Person X: X name 'foo'

- *Insert a new person named 'foo', another called 'nice' and a 'friend' relation
  between them*

  .. sourcecode:: sql

        INSERT Person X, Person Y: X name 'foo', Y name 'nice', X friend Y

- *Insert a new person named 'foo' and a 'friend' relation with an existing
  person called 'nice'*

  .. sourcecode:: sql

        INSERT Person X: X name 'foo', X friend  Y WHERE Y name 'nice'

.. _RQLSetQuery:

Update and relation creation queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    `SET` <assignements>
    [ `WHERE` <restriction>]

Caution, if a restriction is specified, the update is done *for
each result line returned by the restriction*.

- *Renaming of the person named 'foo' to 'bar' with the first name changed*

  .. sourcecode:: sql

        SET X name 'bar', X firstname 'original' WHERE X is Person, X name 'foo'

- *Insert a relation of type 'know' between objects linked by
  the relation of type 'friend'*

  .. sourcecode:: sql

        SET X know Y  WHERE X friend Y


.. _RQLDeleteQuery:

Deletion query
~~~~~~~~~~~~~~

    `DELETE` (<entity type> V) | (V1 relation v2 ),...
    [ `WHERE` <restriction>]

Caution, if a restriction is specified, the deletion is made *for
each line result returned by the restriction*.

- *Deletion of the person named 'foo'*

  .. sourcecode:: sql

        DELETE Person X WHERE X name 'foo'

- *Removal of all relations of type 'friend' from the person named 'foo'*

  .. sourcecode:: sql

        DELETE X friend Y WHERE X is Person, X name 'foo'


.. _Yapps: http://theory.stanford.edu/~amitp/yapps/
.. _Left outer join: http://en.wikipedia.org/wiki/Join_(SQL)#Left_outer_join

