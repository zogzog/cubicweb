.. -*- coding: utf-8 -*-

.. _DEBUGGING:

Debugging RQL
-------------

Available levels
~~~~~~~~~~~~~~~~

Server debugging flags. They may be combined using binary operators.

.. autodata:: cubicweb.server.DBG_NONE
.. autodata:: cubicweb.server.DBG_RQL
.. autodata:: cubicweb.server.DBG_SQL
.. autodata:: cubicweb.server.DBG_REPO
.. autodata:: cubicweb.server.DBG_HOOKS
.. autodata:: cubicweb.server.DBG_OPS
.. autodata:: cubicweb.server.DBG_MORE
.. autodata:: cubicweb.server.DBG_ALL


Enable verbose output
~~~~~~~~~~~~~~~~~~~~~

To debug your RQL statements, it can be useful to enable a verbose output:

.. sourcecode:: python

    from cubicweb import server
    server.set_debug(server.DBG_RQL|server.DBG_SQL|server.DBG_ALL)

.. autofunction:: cubicweb.server.set_debug

Another example showing how to debug hooks at a specific code site:

.. sourcecode:: python

    from cubicweb.server import debugged, DBG_HOOKS
    with debugged(DBG_HOOKS):
        person.cw_set(works_for=company)


Detect largest RQL queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~

See `Profiling and performance` chapter (see :ref:`PROFILING`).


API
~~~

.. autoclass:: cubicweb.server.debugged

