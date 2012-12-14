. -*- coding: utf-8 -*-

.. _dataimport:

Dataimport
==========

*CubicWeb* is designed to manipulate huge of amount of data, and provides helper functions to do so.
These functions insert data within different levels of the *CubicWeb* API,
allowing different speed/security tradeoffs. Those keeping all the *CubicWeb* hooks
and security will be slower but the possible errors in insertion
(bad data types, integrity error, ...) will be raised.

These dataimport function are provided in the file `dataimport.py`.

All the stores have the following API::

    >>> store = ObjectStore()
    >>> user = store.create_entity('CWUser', login=u'johndoe')
    >>> group = store.create_entity('CWUser', name=u'unknown')
    >>> store.relate(user.eid, 'in_group', group.eid)


ObjectStore
-----------

This store keeps objects in memory for *faster* validation. It may be useful
in development mode. However, as it will not enforce the constraints of the schema,
it may miss some problems.



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

The API is similar to the other stores, but **it requires a flush** after some imports to copy data
in the database (these flushes may be multiples through the processes, or be done only once at the
end if there is no memory issue)::

    >>> store = SQLGenObjectStore(session)
    >>> store.create_entity('Person', ...)
    >>> store.flush()
