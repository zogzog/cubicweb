.. -*- coding: utf-8 -*-

.. _dataimport:

Dataimport
==========

*CubicWeb* is designed to easily manipulate large amounts of data, and provides
utilities to make imports simple.

The main entry point is :mod:`cubicweb.dataimport.importer` which defines an
:class:`ExtEntitiesImporter` class responsible for importing data from an external source in the
form :class:`ExtEntity` objects. An :class:`ExtEntity` is a transitional representation of an
entity to be imported in the CubicWeb instance; building this representation is usually
domain-specific -- e.g. dependent of the kind of data source (RDF, CSV, etc.) -- and is thus the
responsibility of the end-user.

Along with the importer, a *store* must be selected, which is responsible for insertion of data into
the database. There exists different kind of stores_, allowing to insert data within different
levels of the *CubicWeb* API and with different speed/security tradeoffs. Those keeping all the
*CubicWeb* hooks and security will be slower but the possible errors in insertion (bad data types,
integrity error, ...) will be handled.


Example
-------

Consider the following schema snippet.

.. code-block:: python

    class Person(EntityType):
        name = String(required=True)

    class knows(RelationDefinition):
        subject = 'Person'
        object = 'Person'

along with some data in a ``people.csv`` file::

    # uri,name,knows
    http://www.example.org/alice,Alice,
    http://www.example.org/bob,Bob,http://www.example.org/alice

The following code (using a shell context) defines a function `extentities_from_csv` to read
`Person` external entities coming from a CSV file and calls the :class:`ExtEntitiesImporter` to
insert corresponding entities and relations into the CubicWeb instance.

.. code-block:: python

    from cubicweb.dataimport import ucsvreader, RQLObjectStore
    from cubicweb.dataimport.importer import ExtEntity, ExtEntitiesImporter

    def extentities_from_csv(fpath):
        """Yield Person ExtEntities read from `fpath` CSV file."""
        with open(fpath) as f:
            for uri, name, knows in ucsvreader(f, skipfirst=True, skip_empty=False):
                yield ExtEntity('Person', uri,
                                {'name': set([name]), 'knows': set([knows])})

    extenties = extentities_from_csv('people.csv')
    store = RQLObjectStore(cnx)
    importer = ExtEntitiesImporter(schema, store)
    importer.import_entities(extenties)
    commit()
    rset = cnx.execute('String N WHERE X name N, X knows Y, Y name "Alice"')
    assert rset[0][0] == u'Bob', rset

Importer API
------------

.. automodule:: cubicweb.dataimport.importer


Stores
~~~~~~

.. automodule:: cubicweb.dataimport.stores


SQLGenObjectStore
-----------------

This store relies on *COPY FROM*/execute many sql commands to directly push data using SQL commands
rather than using the whole *CubicWeb* API. For now, **it only works with PostgresSQL** as it requires
the *COPY FROM* command.
