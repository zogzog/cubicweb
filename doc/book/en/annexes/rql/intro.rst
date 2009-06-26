
Introduction
------------

Goals of RQL
~~~~~~~~~~~~

The goal is to have a language emphasizing the way of browsing
relations. As such, attributes will be regarded as cases of
special relations (in terms of implementation, the language
user should see virtually no difference between an attribute and a
relation).

RQL is inspired by SQL but is the highest level. A knowledge of the
*CubicWeb* schema defining the application is necessary.

Comparison with existing languages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SQL
```
RQL builds on the features of SQL but is at a higher level
(the current implementation of RQL generates SQL). For that it is limited
to the way of browsing relations and introduces variables.
The user does not need to know the model underlying SQL, but the *CubicWeb*
schema defining the application.

Versa
`````
We should look in more detail, but here are already some ideas for
the moment ... Versa_ is the language most similar to what we wanted
to do, but the model underlying data being RDF, there is some
number of things such as namespaces or handling of the RDF types which
does not interest us. On the functionality level, Versa_ is very comprehensive
including through many functions of conversion and basic types manipulation,
which may need to be guided at one time or another.
Finally, the syntax is a little esoteric.

Sparql
``````
The query language most similar to RQL is SPARQL_, defined by the W3C to serve
for the semantic web.


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




.. _Versa: http://uche.ogbuji.net/tech/rdf/versa/
.. _SPARQL: http://www.w3.org/TR/rdf-sparql-query/
