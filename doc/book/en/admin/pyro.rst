Working with a distributed client (using Pyro)
==============================================

In some circumstances, it is practical to split the repository and
web-client parts of the application, for load-balancing reasons. Or
one wants to access the repository from independant scripts to consult
or update the database.

For this to work, several steps have to be taken in order.

You must first ensure that the apropriate software is installed and
running (see ref:`setup`)::

  pyro-nsd -x -p 6969

Then you have to set appropriate options in your configuration. For
instance::

  pyro-server=yes
  pyro-ns-host=localhost:6969

  pyro-instance-id=myinstancename

Finally, the client (for instance in the case of a script) must
connect specifically, as in the following example code:

.. sourcecode:: python

    from cubicweb import dbapi

    def pyro_connect(instname, login, password, pyro_ns_host):
        cnx = dbapi.connect(instname, login, password, pyro_ns_host)
        cnx.load_appobjects()
        return cnx

The 'cnx.load_appobjects()' line is optional. Without it you will get
data through the connection roughly as you would from a DBAPI
connection. With it, provided the cubicweb-client part is installed
and accessible, you get the ORM goodies.
