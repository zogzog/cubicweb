
.. _rql_intro:

Introduction
------------

Goals of RQL
~~~~~~~~~~~~

The goal is to have a semantic language in order to:

- query relations in a clear syntax
- empowers access to data repository manipulation
- making attributes/relations browsing easy

As such, attributes will be regarded as cases of special relations (in
terms of usage, the user should see no syntactic difference between an
attribute and a relation).

Comparison with existing languages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SQL
```

RQL may remind of SQL but works at a higher abstraction level (the *CubicWeb*
framework generates SQL from RQL to fetch data from relation databases). RQL is
focused on browsing relations. The user needs only to know about the *CubicWeb*
data model he is querying, but not about the underlying SQL model.

Sparql
``````

The query language most similar to RQL is SPARQL_, defined by the W3C to serve
for the semantic web.

Versa
`````

We should look in more detail, but here are already some ideas for the moment
... Versa_ is the language most similar to what we wanted to do, but the model
underlying data being RDF, there are some things such as namespaces or
handling of the RDF types which does not interest us. On the functionality
level, Versa_ is very comprehensive including through many functions of
conversion and basic types manipulation, which we may want to look at one time
or another.  Finally, the syntax is a little esoteric.


The different types of queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Search (`Any`)
   Extract entities and attributes of entities.

Insert entities (`INSERT`)
   Insert new entities or relations in the database.
   It can also directly create relationships for the newly created entities.

Update entities, create relations (`SET`)
   Update existing entities in the database,
   or create relations between existing entities.

Delete entities or relationship (`DELETE`)
   Remove entities or relations existing in the database.


Concepts
~~~~~~~~

Entity type
```````````

RQL manipulates variables that are instances of entities.
Each entity has its own type which are used in backend to improve the query
execution plan.

Restrictions
````````````

They are conditions used to limit the perimeter of the result set.

Relations
`````````
A relation is a `3-expression` defined as follows:

.. image:: Graph-ex.gif
    :alt: <subject> <predicate> <object>
    :align: center

A RQL relation contains three components:

* the subject, which is an entity type
* the predicate, which is an oriented graph
* the object, which is either an attribute or a relation to another entity

In cubicweb, the term `relation` is often found without ambiguity instead of `predicate`.
This predicate is also known as the `property` of the triple in `RDF concepts`_

A relation is always expressed in the order: subject, predicate, object.

It's important to determine if entity type is subject or object to construct a
valid expression. An inversion subject/object is equivalent to an RQL error
since the supposed relation cannot be found in schema. If you don't have access
to the code, you could find the order by looking at the schema image in manager
views (the subject is located at the beginning of the arrow).

.. _SQL: http://www.firstsql.com/tutor5.htm
.. _RDF concepts: http://www.w3.org/TR/rdf-concepts/

Cardinality
```````````
XXX

Cardinality is an important concept to model your business rules.
They determine nu./tutorials/advanced/index.rst

Please refer to the `datamodel definitions`_ for a deep understanding.

`Relations`_ are always expressed by cardinality rules (`**` by default)

.. _datamodel definitions: ./devrepo/datamodel/definition.rst

Transaction
```````````

RQL supports notion of **transactions**; i.e. sequences of RQL statements
without invoking security hooks of the instance's schema.

When you're ready to make persistent the changes, you have to *commit* the
modification in calling `commit()`.

If an error is found (typically in raising a ValidationError), you have the
possibility to roll back the transaction in invoking `rollback()` function; i.e
to come back to the initial state of the transaction.

Please, refer to the :ref:`Migration` chapter if you want more details.



.. _Versa: http://wiki.xml3k.org/Versa
.. _SPARQL: http://www.w3.org/TR/rdf-sparql-query/
