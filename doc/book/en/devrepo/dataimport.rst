. -*- coding: utf-8 -*-

.. _dataimport:

Dataimport
==========

*CubicWeb* is designed to manipulate huge of amount of data, and provides utilities to do so.  They
allow to insert data within different levels of the *CubicWeb* API, allowing different
speed/security tradeoffs. Those keeping all the *CubicWeb* hooks and security will be slower but the
possible errors in insertion (bad data types, integrity error, ...) will be raised.

These data import utilities are provided in the package `cubicweb.dataimport`.

The API is built on top of the following concepts:

* `Store`, class responsible for inserting values in the backend database

* `ExtEntity`, some intermediate representation of data to import, using external identifier but no
  eid, and usually with slightly different representation than the associated entity's schema

* `Generator`, class or functions that will yield `ExtEntity` from some data source (eg RDF, CSV)

* `Importer`, class responsible for turning `ExtEntity`'s extid to eid, doing creation or update
  accordingly and may be controlling the insertion order of entities before feeding them to a
  `Store`

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

ExtEntity and Importer
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: cubicweb.dataimport.importer
