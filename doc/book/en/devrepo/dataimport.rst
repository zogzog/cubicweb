.. -*- coding: utf-8 -*-

.. _dataimport:

Dataimport
==========

*CubicWeb* is designed to manipulate huge of amount of data, and provides utilities to do so.

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
                yield ExtEntity('Personne', uri,
                                {'nom': set([name]), 'connait': set([knows])})

    extenties = extentities_from_csv('people.csv')
    store = RQLObjectStore(cnx)
    importer = ExtEntitiesImporter(schema, store)
    importer.import_entities(extenties)
    commit()
    rset = cnx.execute('String N WHERE X nom N, X connait Y, Y nom "Alice"')
    assert rset[0][0] == u'Bob', rset

Importer API
------------

.. automodule:: cubicweb.dataimport.importer


Stores
~~~~~~

Stores are responsible to insert properly formatted entities and relations into the database. They
have the following API::

    >>> user_eid = store.prepare_insert_entity('CWUser', login=u'johndoe')
    >>> group_eid = store.prepare_insert_entity('CWUser', name=u'unknown')
    >>> store.relate(user_eid, 'in_group', group_eid)
    >>> store.flush()
    >>> store.commit()
    >>> store.finish()

Some stores **require a flush** to copy data in the database, so if you want to have store
independent code you should explicitly call it. (There may be multiple flushes during the
process, or only one at the end if there is no memory issue). This is different from the
commit which validates the database transaction. At last, the `finish()` method should be called in
case the store requires additional work once everything is done.

* ``prepare_insert_entity(<entity type>, **kwargs) -> eid``: given an entity
  type, attributes and inlined relations, return the eid of the entity to be
  inserted, *with no guarantee that anything has been inserted in database*.

* ``prepare_update_entity(<entity type>, eid, **kwargs) -> None``: given an
  entity type and eid, promise for update given attributes and inlined
  relations *with no guarantee that anything has been inserted in database*.

* ``prepare_insert_relation(eid_from, rtype, eid_to) -> None``: indicate that a
  relation ``rtype`` should be added between entities with eids ``eid_from``
  and ``eid_to``. Similar to ``prepare_insert_entity()``, *there is no
  guarantee that the relation has been inserted in database*.

* ``flush() -> None``: flush any temporary data to database. May be called
  several times during an import.

* ``commit() -> None``: commit the database transaction.

* ``finish() -> None``: additional stuff to do after import is terminated.

ObjectStore
-----------

This store keeps objects in memory for *faster* validation. It may be useful in development
mode. However, as it will not enforce the constraints of the schema nor insert anything in the
database, so it may miss some problems.


RQLObjectStore
--------------

This store works with an actual RQL repository, and it may be used in production mode.


NoHookRQLObjectStore
--------------------

This store works similarly to the *RQLObjectStore* but bypasses some *CubicWeb* hooks to be faster.


SQLGenObjectStore
-----------------

This store relies on *COPY FROM*/execute many sql commands to directly push data using SQL commands
rather than using the whole *CubicWeb* API. For now, **it only works with PostgresSQL** as it requires
the *COPY FROM* command.
