Profiling and performance
=========================

If you feel that one of your pages takes more time than it should to be
generated, chances are that you're making too many RQL queries.  Obviously,
there are other reasons but experience tends to show this is the first thing to
track down. Luckily, CubicWeb provides a configuration option to log RQL
queries. In your ``all-in-one.conf`` file, set the **query-log-file** option::

    # web application query log file
    query-log-file=~/myapp-rql.log

Then restart your application, reload your page and stop your application.
The file ``myapp-rql.log`` now contains the list of RQL queries that were
executed during your test. It's a simple text file containing lines such as::

    Any A WHERE X eid %(x)s, X lastname A {'x': 448} -- (0.002 sec, 0.010 CPU sec)
    Any A WHERE X eid %(x)s, X firstname A {'x': 447} -- (0.002 sec, 0.000 CPU sec)

The structure of each line is::

    <RQL QUERY> <QUERY ARGS IF ANY> -- <TIME SPENT>

CubicWeb also provides the **exlog** command to examine and summarize data found
in such a file:

.. sourcecode:: sh

    $ cubicweb-ctl exlog < ~/myapp-rql.log
    0.07 50 Any A WHERE X eid %(x)s, X firstname A {}
    0.05 50 Any A WHERE X eid %(x)s, X lastname A {}
    0.01 1 Any X,AA ORDERBY AA DESC WHERE E eid %(x)s, E employees X, X modification_date AA {}
    0.01 1 Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s {, }
    0.01 1 Any B,T,P ORDERBY lower(T) WHERE B is Bookmark,B title T, B path P, B bookmarked_by U, U eid %(x)s {}
    0.01 1 Any A,B,C,D WHERE A eid %(x)s,A name B,A creation_date C,A modification_date D {}

This command sorts and uniquifies queries so that it's easy to see where
is the hot spot that needs optimization.

Do not neglect to set the **fetch_attrs** attribute you can define in your
entity classes because it can greatly reduce the number of queries executed (see
:ref:`FetchAttrs`).

You should also know about the **profile** option in the ``all-in-on.conf``. If
set, this option will make your application run in an `hotshot`_ session and
store the results in the specified file.

.. _hotshot: http://docs.python.org/library/hotshot.html#module-hotshot

Last but no least, if you're using the PostgreSQL database backend, VACUUMing
your database can significantly improve the performance of the queries (by
updating the statistics used by the query optimizer). Nowadays, this is done
automatically from time to time, but if you've just imported a large amount of
data in your db, you will want to vacuum it (with the analyse option on). Read
the documentation of your database for more information.
