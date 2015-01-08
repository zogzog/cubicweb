.. _UsingPyro:

Working with a distributed client (using Pyro)
==============================================

In some circumstances, it is practical to split the repository and
web-client parts of the application for load-balancing reasons. Or
one wants to access the repository from independant scripts to consult
or update the database.

Prerequisites
-------------

For this to work, several steps have to be taken in order.

You must first ensure that the appropriate software is installed and
running (see :ref:`ConfigEnv`)::

  pyro-nsd -x -p 6969

Then you have to set appropriate options in your configuration. For
instance::

  pyro-server=yes
  pyro-ns-host=localhost:6969

  pyro-instance-id=myinstancename

Connect to the CubicWeb repository from a python script
-------------------------------------------------------

Assuming pyro-nsd is running and your instance is configured with ``pyro-server=yes``,
you will be able to use :mod:`cubicweb.dbapi` api to initiate the connection.

.. note::
    Regardless of whether your instance is pyro activated or not, you can still
    achieve this by using cubicweb-ctl shell scripts in a simpler way, as by default
    it creates a repository 'in-memory' instead of connecting through pyro. That
    also means you've to be on the host where the instance is running.

Finally, the client (for instance a python script) must connect specifically
as in the following example code:

.. sourcecode:: python

    from cubicweb import dbapi

    cnx = dbapi.connect(database='instance-id', user='admin', password='admin')
    cnx.load_appobjects()
    cur = cnx.cursor()
    for name in (u'Personal', u'Professional', u'Computers'):
        cur.execute('INSERT Tag T: T name %(n)s', {'n': name})
    cnx.commit()

Calling :meth:`cubicweb.dbapi.load_appobjects`, will populate the
cubicweb registries (see :ref:`VRegistryIntro`) with the application
objects installed on the host where the script runs. You'll then be
allowed to use the ORM goodies and custom entity methods and views. Of
course this is optional, without it you can still get the repository
data through the connection but in a roughly way: only RQL cursors
will be available, e.g. you can't even build entity objects from the
result set.
