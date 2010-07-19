.. -*- coding: utf-8 -*-

.. _DEBUGGING:

Debugging RQL
-------------

Available levels
~~~~~~~~~~~~~~~~

:DBG_NONE:
    no debug information (current mode)

:DBG_RQL:
    rql execution information

:DBG_SQL:
    executed sql

:DBG_REPO:
    repository events

:DBG_MS:
    multi-sources

:DBG_MORE:
    more verbosity

:DBG_ALL:
    all level enabled


Enable verbose output
~~~~~~~~~~~~~~~~~~~~~

It may be interested to enable a verboser output to debug your RQL statements:

.. sourcecode:: python

    from cubicweb import server
    server.set_debug(server.DBG_RQL|server.DBG_SQL|server.DBG_ALL)


Detect largest RQL queries
~~~~~~~~~~~~~~~~~~~~~~~~~~~

See `Profiling and performance` chapter (see :ref:`PROFILING`).


API
~~~

.. autofunction:: cubicweb.server.set_debug

.. autoclass:: cubicweb.server.debugged

