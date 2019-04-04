Importing relational data into a CubicWeb instance
==================================================

Introduction
~~~~~~~~~~~~

This tutorial explains how to import data from an external source (e.g. a collection of files)
into a CubicWeb cube instance.

First, once we know the format of the data we wish to import, we devise a
*data model*, that is, a CubicWeb (Yams) schema which reflects the way the data
is structured. This schema is implemented in the ``schema.py`` file.
In this tutorial, we will describe such a schema for a particular data set,
the Diseasome data (see below).

Once the schema is defined, we create a cube and an instance.
The cube is a specification of an application, whereas an instance
is the application per se.

Once the schema is defined and the instance is created, the import can be performed, via
the following steps:

1. Build a custom parser for the data to be imported. Thus, one obtains a Python
   memory representation of the data.

2. Map the parsed data to the data model defined in ``schema.py``.

3. Perform the actual import of the data. This comes down to "populating"
   the data model with the memory representation obtained at 1, according to
   the mapping defined at 2.

This tutorial illustrates all the above steps in the context of relational data
stored in the RDF format.

More specifically, we describe the import of Diseasome_ RDF/OWL data.

.. _Diseasome: http://datahub.io/dataset/fu-berlin-diseasome

Building a data model
~~~~~~~~~~~~~~~~~~~~~

The first thing to do when using CubicWeb for creating an application from scratch
is to devise a *data model*, that is, a relational representation of the problem to be
modeled or of the structure of the data to be imported.

In such a schema, we define
an entity type (``EntityType`` objects) for each type of entity to import. Each such type
has several attributes. If the attributes are of known CubicWeb (Yams) types, viz. numbers,
strings or characters, then they are defined as attributes, as e.g. ``attribute = Int()``
for an attribute named ``attribute`` which is an integer.

Each such type also has a set of
relations, which are defined like the attributes, except that they represent, in fact,
relations between the entities of the type under discussion and the objects of a type which
is specified in the relation definition.

For example, for the Diseasome data, we have two types of entities, genes and diseases.
Thus, we create two classes which inherit from ``EntityType``::

    class Disease(EntityType):
        # Corresponds to http://www.w3.org/2000/01/rdf-schema#label
        label = String(maxsize=512, fulltextindexed=True)
        ...

        #Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/diseasome/associatedGene
        associated_genes = SubjectRelation('Gene', cardinality='**')
        ...

        #Corresponds to 'http://www4.wiwiss.fu-berlin.de/diseasome/resource/diseasome/chromosomalLocation'
        chromosomal_location = SubjectRelation('ExternalUri', cardinality='?*', inlined=True)


    class Gene(EntityType):
        ...

In this schema, there are attributes whose values are numbers or strings. Thus, they are
defined by using the CubicWeb / Yams primitive types, e.g., ``label = String(maxsize=12)``.
These types can have several constraints or attributes, such as ``maxsize``.
There are also relations, either between the entity types themselves, or between them
and a CubicWeb type, ``ExternalUri``. The latter defines a class of URI objects in
CubicWeb. For instance, the ``chromosomal_location`` attribute is a relation between
a ``Disease`` entity and an ``ExternalUri`` entity. The relation is marked by the CubicWeb /
Yams ``SubjectRelation`` method. The latter can have several optional keyword arguments, such as
``cardinality`` which specifies the number of subjects and objects related by the relation type
specified. For example, the ``'?*'`` cardinality in the ``chromosomal_relation`` relation type says
that zero or more ``Disease`` entities are related to zero or one ``ExternalUri`` entities.
In other words, a ``Disease`` entity is related to at most one ``ExternalUri`` entity via the
``chromosomal_location`` relation type, and that we can have zero or more ``Disease`` entities in the
data base.
For a relation between the entity types themselves, the ``associated_genes`` between a ``Disease``
entity and a ``Gene`` entity is defined, so that any number of ``Gene`` entities can be associated
to a ``Disease``, and there can be any number of ``Disease`` s if a ``Gene`` exists.

Of course, before being able to use the CubicWeb / Yams built-in objects, we need to import them::


    from yams.buildobjs import EntityType, SubjectRelation, String, Int
    from cubicweb.schemas.base import ExternalUri

Building a custom data parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The data we wish to import is structured in the RDF format,
as a text file containing a set of lines.
On each line, there are three fields.
The first two fields are URIs ("Universal Resource Identifiers").
The third field is either an URI or a string. Each field bares a particular meaning:

- the leftmost field is an URI that holds the entity to be imported.
  Note that the entities defined in the data model (i.e., in ``schema.py``) should
  correspond to the entities whose URIs are specified in the import file.

- the middle field is an URI that holds a relation whose subject is the  entity
  defined by the leftmost field. Note that this should also correspond
  to the definitions in the data model.

- the rightmost field is either an URI or a string. When this field is an URI,
  it gives the object of the relation defined by the middle field.
  When the rightmost field is a string, the middle field is interpreted as an attribute
  of the subject (introduced by the leftmost field) and the rightmost field is
  interpreted as the value of the attribute.

Note however that some attributes (i.e. relations whose objects are strings)
have their objects defined as strings followed by ``^^`` and by another URI;
we ignore this part.

Let us show some examples:

- of line holding an attribute definition:
  ``<http://www4.wiwiss.fu-berlin.de/diseasome/resource/genes/CYP17A1>
  <http://www.w3.org/2000/01/rdf-schema#label> "CYP17A1" .``
  The line contains the definition of the ``label`` attribute of an
  entity of type ``gene``. The value of ``label`` is '``CYP17A1``'.

- of line holding a relation definition:
  ``<http://www4.wiwiss.fu-berlin.de/diseasome/resource/diseases/1>
  <http://www4.wiwiss.fu-berlin.de/diseasome/resource/diseasome/associatedGene>
  <http://www4.wiwiss.fu-berlin.de/diseasome/resource/genes/HADH2> .``
  The line contains the definition of the ``associatedGene`` relation between
  a ``disease`` subject entity identified by ``1`` and a ``gene`` object
  entity defined by ``HADH2``.

Thus, for parsing the data, we can (:note: see the ``diseasome_parser`` module):

1. define a couple of regular expressions for parsing the two kinds of lines,
   ``RE_ATTS`` for parsing the attribute definitions, and ``RE_RELS`` for parsing
   the relation definitions.

2. define a function that iterates through the lines of the file and retrieves
   (``yield`` s) a (subject, relation, object) tuple for each line.
   We called it ``_retrieve_structure`` in the ``diseasome_parser`` module.
   The function needs the file name and the types for which information
   should be retrieved.

Alternatively, instead of hand-making the parser, one could use the RDF parser provided
in the ``dataio`` cube.

.. XXX To further study and detail the ``dataio`` cube usage.

Once we get to have the (subject, relation, object) triples, we need to map them into
the data model.


Mapping the data to the schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the case of diseasome data, we can just define two dictionaries for mapping
the names of the relations as extracted by the parser, to the names of the relations
as defined in the ``schema.py`` data model. In the ``diseasome_parser`` module
they are called ``MAPPING_ATTS`` and ``MAPPING_RELS``.
Given that the relation and attribute names are given in CamelCase in the original data,
mappings are necessary if we follow the PEP08 when naming the attributes in the data model.
For example, the RDF relation ``chromosomalLocation`` is mapped into the schema relation
``chromosomal_location``.

Once these mappings have been defined, we just iterate over the (subject, relation, object)
tuples provided by the parser and we extract the entities, with their attributes and relations.
For each entity, we thus have a dictionary with two keys, ``attributes`` and ``relations``.
The value associated to the ``attributes`` key is a dictionary containing (attribute: value)
pairs, where "value" is a string, plus the ``cwuri`` key / attribute holding the URI of
the entity itself.
The value associated to the ``relations`` key is a dictionary containing (relation: value)
pairs, where "value" is an URI.
This is implemented in the ``entities_from_rdf`` interface function of the module
``diseasome_parser``. This function provides an iterator on the dictionaries containing
the ``attributes`` and ``relations`` keys for all entities.

However, this is a simple case. In real life, things can get much more complicated, and the
mapping can be far from trivial, especially when several data sources (which can follow
different formatting and even structuring conventions) must be mapped into the same data model.

Importing the data
~~~~~~~~~~~~~~~~~~

The data import code should be placed in a Python module. Let us call it
``diseasome_import.py``. Then, this module should be called via
``cubicweb-ctl``, as follows::

    cubicweb-ctl shell diseasome_import.py -- <other arguments e.g. data file>

In the import module, we should use a *store* for doing the import.
A store is an object which provides three kinds of methods for
importing data:

- a method for importing the entities, along with the values
  of their attributes.
- a method for importing the relations between the entities.
- a method for committing the imports to the database.

In CubicWeb, we have four stores:

1. ``ObjectStore`` base class for the stores in CubicWeb.
   It only provides a skeleton for all other stores and
   provides the means for creating the memory structures
   (dictionaries) that hold the entities and the relations
   between them.

2. ``RQLObjectStore``: store which uses the RQL language for performing
   database insertions and updates. It relies on all the CubicWeb hooks
   machinery, especially for dealing with security issues (database access
   permissions).

2. ``NoHookRQLObjectStore``: store which uses the RQL language for
   performing database insertions and updates, but for which
   all hooks are deactivated. This implies that
   certain checks with respect to the CubicWeb / Yams schema
   (data model) are not performed. However, all SQL queries
   obtained from the RQL ones are executed in a sequential
   manner, one query per inserted entity.

4. ``SQLGenObjectStore``: store which uses the SQL language directly.
   It inserts entities either sequentially, by executing an SQL query
   for each entity, or directly by using one PostGRES ``COPY FROM``
   query for a set of similarly structured entities.

For really massive imports (millions or billions of entities), there
is a cube ``dataio`` which contains another store, called
``MassiveObjectStore``. This store is similar to ``SQLGenObjectStore``,
except that anything related to CubicWeb is bypassed. That is, even the
CubicWeb EID entity identifiers are not handled. This store is the fastest,
but has a slightly different API from the other four stores mentioned above.
Moreover, it has an important limitation, in that it doesn't insert inlined [#]_
relations in the database.

.. [#] An inlined relation is a relation defined in the schema
       with the keyword argument ``inlined=True``. Such a relation
       is inserted in the database as an attribute of the entity
       whose subject it is.

In the following section we will see how to import data by using the stores
in CubicWeb's ``dataimport`` module.

Using the stores in ``dataimport``
++++++++++++++++++++++++++++++++++

``ObjectStore`` is seldom used in real life for importing data, since it is
only the base store for the other stores and it doesn't perform an actual
import of the data. Nevertheless, the other three stores, which import data,
are based on ``ObjectStore`` and provide the same API.

All three stores ``RQLObjectStore``, ``NoHookRQLObjectStore`` and
``SQLGenObjectStore`` provide exactly the same API for importing data, that is
entities and relations, in an SQL database.

Before using a store, one must import the ``dataimport`` module and then initialize
the store, with the current ``session`` as a parameter::

    import cubicweb.dataimport as cwdi
    ...

    store = cwdi.RQLObjectStore(session)

Each such store provides three methods for data import:

#. ``create_entity(Etype, **attributes)``, which allows us to add
   an entity of the Yams type ``Etype`` to the database. This entity's attributes
   are specified in the ``attributes`` dictionary. The method returns the entity
   created in the database. For example, we add two entities,
   a person, of ``Person`` type, and a location, of ``Location`` type::

        person = store.create_entity('Person', name='Toto', age='18', height='190')

        location = store.create_entity('Location', town='Paris', arrondissement='13')

#. ``relate(subject_eid, r_type, object_eid)``, which allows us to add a relation
   of the Yams type ``r_type`` to the database. The relation's subject is an entity
   whose EID is ``subject_eid``; its object is another entity, whose EID is
   ``object_eid``.  For example [#]_::

        store.relate(person.eid(), 'lives_in', location.eid(), **kwargs)

   ``kwargs`` is only used by the ``SQLGenObjectStore``'s ``relate`` method and is here
   to allow us to specify the type of the subject of the relation, when the relation is
   defined as inlined in the schema.

.. [#] The ``eid`` method of an entity defined via ``create_entity`` returns
       the entity identifier as assigned by CubicWeb when creating the entity.
       This only works for entities defined via the stores in the CubicWeb's
       ``dataimport`` module.

   The keyword argument that is understood by ``SQLGenObjectStore`` is called
   ``subjtype`` and holds the type of the subject entity. For the example considered here,
   this comes to having [#]_::

        store.relate(person.eid(), 'lives_in', location.eid(), subjtype=person.cw_etype)

   If ``subjtype`` is not specified, then the store tries to infer the type of the subject.
   However, this doesn't always work, e.g. when there are several possible subject types
   for a given relation type.

.. [#] The ``cw_etype`` attribute of an entity defined via ``create_entity`` holds
       the type of the entity just created. This only works for entities defined via
       the stores in the CubicWeb's ``dataimport`` module. In the example considered
       here, ``person.cw_etype`` holds ``'Person'``.

   All the other stores but ``SQLGenObjectStore`` ignore the ``kwargs`` parameters.

#. ``flush()``, which allows us to perform the actual commit into the database, along
   with some cleanup operations. Ideally, this method should be called as often as
   possible, that is after each insertion in the database, so that database sessions
   are kept as atomic as possible. In practice, we usually call this method twice:
   first, after all the entities have been created, second, after all relations have
   been created.

   Note however that before each commit the database insertions
   have to be consistent with the schema. Thus, if, for instance,
   an entity has an attribute defined through a relation (viz.
   a ``SubjectRelation``) with a ``"1"`` or ``"+"`` object
   cardinality, we have to create the entity under discussion,
   the object entity of the relation under discussion, and the
   relation itself, before committing the additions to the database.

   The ``flush`` method is simply called as::

        store.flush().


Using the ``MassiveObjectStore`` in the ``dataio`` cube
+++++++++++++++++++++++++++++++++++++++++++++++++++++++

This store, available in the ``dataio`` cube, allows us to
fully dispense with the CubicWeb import mechanisms and hence
to interact directly with the database server, via SQL queries.

Moreover, these queries rely on PostGreSQL's ``COPY FROM`` instruction
to create several entities in a single query. This brings tremendous
performance improvements with respect to the RQL-based data insertion
procedures.

However, the API of this store is slightly different from the API of
the stores in CubicWeb's ``dataimport`` module.

Before using the store, one has to import the ``dataio`` cube's
``dataimport`` module, then initialize the store by giving it the
``session`` parameter::

    from cubicweb_dataio import dataimport as mcwdi
    ...

    store = mcwdi.MassiveObjectStore(session)

The ``MassiveObjectStore`` provides six methods for inserting data
into the database:

#. ``init_rtype_table(SubjEtype, r_type, ObjEtype)``, which specifies the
   creation of the tables associated to the relation types in the database.
   Each such table has three column, the type of the subject entity, the
   type of the relation (that is, the name of the attribute in the subject
   entity which is defined via the relation), and the type of the object
   entity. For example::

        store.init_rtype_table('Person', 'lives_in', 'Location')

   Please note that these tables can be created before the entities, since
   they only specify their types, not their unique identifiers.

#. ``create_entity(Etype, **attributes)``, which allows us to add new entities,
   whose attributes are given in the ``attributes`` dictionary.
   Please note however that, by default, this method does *not* return
   the created entity. The method is called, for example, as in::

        store.create_entity('Person', name='Toto', age='18', height='190',
                            uri='http://link/to/person/toto_18_190')
        store.create_entity('Location', town='Paris', arrondissement='13',
                            uri='http://link/to/location/paris_13')

   In order to be able to link these entities via the relations when needed,
   we must provide ourselves a means for uniquely identifying the entities.
   In general, this is done via URIs, stored in attributes like ``uri`` or
   ``cwuri``. The name of the attribute is irrelevant as long as its value is
   unique for each entity.

#. ``relate_by_iid(subject_iid, r_type, object_iid)`` allows us to actually
   relate the entities uniquely identified by ``subject_iid`` and
   ``object_iid`` via a relation of type ``r_type``. For example::

        store.relate_by_iid('http://link/to/person/toto_18_190',
                            'lives_in',
                            'http://link/to/location/paris_13')

   Please note that this method does *not* work for inlined relations!

#. ``convert_relations(SubjEtype, r_type, ObjEtype, subj_iid_attribute,
   obj_iid_attribute)``
   allows us to actually insert
   the relations in the database. At one call of this method, one inserts
   all the relations of type ``rtype`` between entities of given types.
   ``subj_iid_attribute`` and ``object_iid_attribute`` are the names
   of the attributes which store the unique identifiers of the entities,
   as assigned by the user. These names can be identical, as long as
   their values are unique. For example, for inserting all relations
   of type ``lives_in`` between ``People`` and ``Location`` entities,
   we write::

        store.convert_relations('Person', 'lives_in', 'Location', 'uri', 'uri')

#. ``flush()`` performs the actual commit in the database. It only needs
   to be called after ``create_entity`` and ``relate_by_iid`` calls.
   Please note that ``relate_by_iid`` does *not* perform insertions into
   the database, hence calling ``flush()`` for it would have no effect.

#. ``cleanup()`` performs database cleanups, by removing temporary tables.
   It should only be called at the end of the import.



.. XXX to add smth on the store's parameter initialization.



Application to the Diseasome data
+++++++++++++++++++++++++++++++++

Import setup
############

We define an import function, ``diseasome_import``, which does basically four things:

#. creates and initializes the store to be used, via a line such as::

        store = cwdi.SQLGenObjectStore(session)

   where ``cwdi`` is the imported ``cubicweb.dataimport`` or
   ``cubicweb_dataio.dataimport``.

#. calls the diseasome parser, that is, the ``entities_from_rdf`` function in the
   ``diseasome_parser`` module and iterates on its result, in a line such as::

        for entity, relations in parser.entities_from_rdf(filename, ('gene', 'disease')):

   where ``parser`` is the imported ``diseasome_parser`` module, and ``filename`` is the
   name of the file containing the data (with its path), e.g. ``../data/diseasome_dump.nt``.

#. creates the entities to be inserted in the database; for Diseasome, there are two
   kinds of entities:

   #. entities defined in the data model, viz. ``Gene`` and ``Disease`` in our case.
   #. entities which are built in CubicWeb / Yams, viz. ``ExternalUri`` which define
      URIs.

   As we are working with RDF data, each entity is defined through a series of URIs. Hence,
   each "relational attribute" [#]_ of an entity is defined via an URI, that is, in CubicWeb
   terms, via an ``ExternalUri`` entity. The entities are created, in the loop presented above,
   as such::

        ent = store.create_entity(etype, **entity)

   where ``etype`` is the appropriate entity type, either ``Gene`` or ``Disease``.

.. [#] By "relational attribute" we denote an attribute (of an entity) which
       is defined through a relation, e.g. the ``chromosomal_location`` attribute
       of ``Disease`` entities, which is defined through a relation between a
       ``Disease`` and an ``ExternalUri``.

   The ``ExternalUri`` entities are as many as URIs in the data file. For them, we define a unique
   attribute, ``uri``, which holds the URI under discussion::

        extu = store.create_entity('ExternalUri', uri="http://path/of/the/uri")

#. creates the relations between the entities. We have relations between:

   #. entities defined in the schema, e.g. between ``Disease`` and ``Gene``
      entities, such as the ``associated_genes`` relation defined for
      ``Disease`` entities.
   #. entities defined in the schema and ``ExternalUri`` entities, such as ``gene_id``.

   The way relations are added to the database depends on the store:

   - for the stores in the CubicWeb ``dataimport`` module, we only use
     ``store.relate``, in
     another loop, on the relations (that is, a
     loop inside the preceding one, mentioned at step 2)::

        for rtype, rels in relations.iteritems():
            ...

            store.relate(ent.eid(), rtype, extu.eid(), **kwargs)

     where ``kwargs`` is a dictionary designed to accommodate the need for specifying
     the type of the subject entity of the relation, when the relation is inlined and
     ``SQLGenObjectStore`` is used. For example::

            ...
            store.relate(ent.eid(), 'chromosomal_location', extu.eid(), subjtype='Disease')

   - for the ``MassiveObjectStore`` in the ``dataio`` cube's ``dataimport`` module,
     the relations are created in three steps:

     #. first, a table is created for each relation type, as in::

            ...
            store.init_rtype_table(ent.cw_etype, rtype, extu.cw_etype)

        which comes down to lines such as::

            store.init_rtype_table('Disease', 'associated_genes', 'Gene')
            store.init_rtype_table('Gene', 'gene_id', 'ExternalUri')

     #. second, the URI of each entity will be used as its identifier, in the
        ``relate_by_iid`` method, such as::

            disease_uri = 'http://www4.wiwiss.fu-berlin.de/diseasome/resource/diseases/3'
            gene_uri = '<http://www4.wiwiss.fu-berlin.de/diseasome/resource/genes/HSD3B2'
            store.relate_by_iid(disease_uri, 'associated_genes', gene_uri)

     #. third, the relations for each relation type will be added to the database,
        via the ``convert_relations`` method, such as in::

            store.convert_relations('Disease', 'associated_genes', 'Gene', 'cwuri', 'cwuri')

        and::

            store.convert_relations('Gene', 'hgnc_id', 'ExternalUri', 'cwuri', 'uri')

        where ``cwuri`` and ``uri`` are the attributes which store the URIs of the entities
        defined in the data model, and of the ``ExternalUri`` entities, respectively.

#. flushes all relations and entities::

    store.flush()

   which performs the actual commit of the inserted entities and relations in the database.

If the ``MassiveObjectStore`` is used, then a cleanup of temporary SQL tables should be performed
at the end of the import::

    store.cleanup()

Timing benchmarks
#################

In order to time the import script, we just decorate the import function with the ``timed``
decorator::

    from logilab.common.decorators import timed
    ...

    @timed
    def diseasome_import(session, filename):
        ...

After running the import function as shown in the "Importing the data" section, we obtain two time measurements::

    diseasome_import clock: ... / time: ...

Here, the meanings of these measurements are [#]_:

- ``clock`` is the time spent by CubicWeb, on the server side (i.e. hooks and data pre- / post-processing on SQL
  queries),

- ``time`` is the sum between ``clock`` and the time spent in PostGreSQL.

.. [#] The meanings of the ``clock`` and ``time`` measurements, when using the ``@timed``
       decorators, were taken from `a blog post on massive data import in CubicWeb`_.

.. _a blog post on massive data import in CubicWeb: http://www.cubicweb.org/blogentry/2116712

The import function is put in an import module, named ``diseasome_import`` here. The module is called
directly from the CubicWeb shell, as follows::

    cubicweb-ctl shell diseasome_instance diseasome_import.py \
    -- -df diseasome_import_file.nt -st StoreName

The module accepts two arguments:

- the data file, introduced by ``-df [--datafile]``, and
- the store, introduced by ``-st [--store]``.

The timings (in seconds) for different stores are given in the following table, for
importing 4213 ``Disease`` entities and 3919 ``Gene`` entities with the import module
just described:

+--------------------------+------------------------+--------------------------------+------------+
| Store                    | CubicWeb time (clock)  | PostGreSQL time (time - clock) | Total time |
+==========================+========================+================================+============+
| ``RQLObjectStore``       | 225.98                 | 62.05                          | 288.03     |
+--------------------------+------------------------+--------------------------------+------------+
| ``NoHookRQLObjectStore`` | 62.73                  | 51.38                          | 114.11     |
+--------------------------+------------------------+--------------------------------+------------+
| ``SQLGenObjectStore``    | 20.41                  | 11.03                          | 31.44      |
+--------------------------+------------------------+--------------------------------+------------+
| ``MassiveObjectStore``   | 4.84                   | 6.93                           | 11.77      |
+--------------------------+------------------------+--------------------------------+------------+


Conclusions
~~~~~~~~~~~

In this tutorial we have seen how to import data in a CubicWeb application instance. We have first seen how to
create a schema, then how to create a parser of the data and a mapping of the data to the schema.
Finally, we have seen four ways of importing data into CubicWeb.

Three of those are integrated into CubicWeb, namely the ``RQLObjectStore``, ``NoHookRQLObjectStore`` and
``SQLGenObjectStore`` stores, which have a common API:

- ``RQLObjectStore`` is by far the slowest, especially its time spent on the
  CubicWeb side, and so it should be used only for small amounts of
  "sensitive" data (i.e. where security is a concern).

- ``NoHookRQLObjectStore`` slashes by almost four the time spent on the CubicWeb side,
  but is also quite slow; on the PostGres side it is as slow as the previous store.
  It should be used for data where security is not a concern,
  but consistency (with the data model) is.

- ``SQLGenObjectStore`` slashes by three the time spent on the CubicWeb side and by five the time
  spent on the PostGreSQL side. It should be used for relatively great amounts of data, where
  security and data consistency are not a concern. Compared to the previous store, it has the
  disadvantage that, for inlined relations, we must specify their subjects' types.

For really huge amounts of data there is a fourth store, ``MassiveObjectStore``, available
from the ``dataio`` cube. It provides a blazing performance with respect to all other stores:
it is almost 25 times faster than ``RQLObjectStore`` and almost three times faster than
``SQLGenObjectStore``. However, it has a few usage caveats that should be taken into account:

#. it cannot insert relations defined as inlined in the schema,
#. no security or consistency check is performed on the data,
#. its API is slightly different from the other stores.

Hence, this store should be used when security and data consistency are not a concern,
and there are no inlined relations in the schema.






