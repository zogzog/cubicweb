.. -*- coding: utf-8 -*-

.. _ConfigEnv:

Set-up of a *CubicWeb* environment
==================================

You can `configure the database`_ system of your choice:

  - `PostgreSQL configuration`_
  - `MySql configuration`_
  - `SQLServer configuration`_
  - `SQLite configuration`_

For advanced features, have a look to:

  - `Pyro configuration`_
  - `Cubicweb resources configuration`_

.. _`configure the database`: DatabaseInstallation_
.. _`PostgreSQL configuration`: PostgresqlConfiguration_
.. _`MySql configuration`: MySqlConfiguration_
.. _`SQLServer configuration`: SQLServerConfiguration_
.. _`SQLite configuration`: SQLiteConfiguration_
.. _`Pyro configuration`: PyroConfiguration_
.. _`Cubicweb resources configuration`: RessourcesConfiguration_



.. _RessourcesConfiguration:

Cubicweb resources configuration
--------------------------------

.. autodocstring:: cubicweb.cwconfig


.. _DatabaseInstallation:

Databases configuration
-----------------------

Each instance can be configured with its own database connection information,
that will be stored in the instance's :file:`sources` file. The database to use
will be chosen when creating the instance. CubicWeb is known to run with
Postgresql (recommended), MySQL, SQLServer and SQLite.

Other possible sources of data include CubicWeb, Subversion, LDAP and Mercurial,
but at least one relational database is required for CubicWeb to work. You do
not need to install a backend that you do not intend to use for one of your
instances. SQLite is not fit for production use, but it works well for testing
and ships with Python, which saves installation time when you want to get
started quickly.

.. _PostgresqlConfiguration:

PostgreSQL
~~~~~~~~~~

Many Linux distributions ship with the appropriate PostgreSQL packages.
Basically, you need to install the following packages:

* `postgresql` and `postgresql-client`, which will pull the respective
  versioned packages (e.g. `postgresql-9.1` and `postgresql-client-9.1`) and,
  optionally,
* a `postgresql-plpython-X.Y` package with a version corresponding to that of
  the aforementioned packages (e.g. `postgresql-plpython-9.1`).

If you run postgres version prior to 8.3, you'll also need the
`postgresql-contrib-8.X` package for full-text search extension.

If you run postgres on another host than the |cubicweb| repository, you should
install the `postgresql-client` package on the |cubicweb| host, and others on the
database host.

For extra details concerning installation, please refer to the `PostgreSQL
project online documentation`_.

.. _`PostgreSQL project online documentation`: http://www.postgresql.org/docs


Database cluster
++++++++++++++++

If you already have an existing cluster and PostgreSQL server running, you do
not need to execute the initilization step of your PostgreSQL database unless
you want a specific cluster for |cubicweb| databases or if your existing
cluster doesn't use the UTF8 encoding (see note below).

To initialize a PostgreSQL cluster, use the command ``initdb``::

    $ initdb -E UTF8 -D /path/to/pgsql

Notice the encoding specification. This is necessary since |cubicweb| usually
want UTF8 encoded database. If you use a cluster with the wrong encoding, you'll
get error like::

  new encoding (UTF8) is incompatible with the encoding of the template database (SQL_ASCII)
  HINT:  Use the same encoding as in the template database, or use template0 as template.

Once initialized, start the database server PostgreSQL with the command::

  $ postgres -D /path/to/psql

If you cannot execute this command due to permission issues, please make sure
that your username has write access on the database.  ::

  $ chown username /path/to/pgsql

Database authentication
+++++++++++++++++++++++

The database authentication is configured in `pg_hba.conf`. It can be either set
to `ident sameuser` or `md5`.  If set to `md5`, make sure to use an existing
user of your database.  If set to `ident sameuser`, make sure that your client's
operating system user name has a matching user in the database. If not, please
do as follow to create a user::

  $ su
  $ su - postgres
  $ createuser -s -P username

The option `-P` (for password prompt), will encrypt the password with the
method set in the configuration file :file:`pg_hba.conf`.  If you do not use this
option `-P`, then the default value will be null and you will need to set it
with::

  $ su postgres -c "echo ALTER USER username WITH PASSWORD 'userpasswd' | psql"

The above login/password will be requested when you will create an instance with
`cubicweb-ctl create` to initialize the database of your instance.

Notice that the `cubicweb-ctl db-create` does database initialization that
may requires a postgres superuser. That's why a login/password is explicitly asked
at this step, so you can use there a superuser without using this user when running
the instance. Things that require special privileges at this step:

* database creation, require the 'create database' permission
* install the plpython extension language (require superuser)
* install the tsearch extension for postgres version prior to 8.3 (require superuser)

To avoid using a super user each time you create an install, a nice trick is to
install plpython (and tsearch when needed) on the special `template1` database,
so they will be installed automatically when cubicweb databases are created
without even with needs for special access rights. To do so, run ::

  # Installation of plpythonu language by default ::
  $ createlang -U pgadmin plpythonu template1
  $ psql -U pgadmin template1
  template1=# update pg_language set lanpltrusted=TRUE where lanname='plpythonu';

Where `pgadmin` is a postgres superuser. The last command is necessary since by
default plpython is an 'untrusted' language and as such can't be used by non
superuser. This update fix that problem by making it trusted.

To install the tsearch plain-text index extension on postgres prior to 8.3, run::

    cat /usr/share/postgresql/8.X/contrib/tsearch2.sql | psql -U username template1


.. _MySqlConfiguration:

MySql
~~~~~

You must add the following lines in ``/etc/mysql/my.cnf`` file::

    transaction-isolation=READ-COMMITTED
    default-storage-engine=INNODB
    default-character-set=utf8
    max_allowed_packet = 128M

.. Note::
    It is unclear whether mysql supports indexed string of arbitrary length or
    not.


.. _SQLServerConfiguration:

SQLServer
~~~~~~~~~

As of this writing, support for SQLServer 2005 is functional but incomplete. You
should be able to connect, create a database and go quite far, but some of the
SQL generated from RQL queries is still currently not accepted by the
backend. Porting to SQLServer 2008 is also an item on the backlog.

The `source` configuration file may look like this (specific parts only are
shown)::

  [system]
  db-driver=sqlserver2005
  db-user=someuser
  # database password not needed
  #db-password=toto123
  #db-create/init may ask for a pwd: just say anything
  db-extra-arguments=Trusted_Connection
  db-encoding=utf8


You need to change the default settings on the database by running::

 ALTER DATABASE <databasename> SET READ_COMMITTED_SNAPSHOT ON;

The ALTER DATABASE command above requires some permissions that your
user may not have. In that case you will have to ask your local DBA to
run the query for you.

You can check that the setting is correct by running the following
query which must return '1'::

   SELECT is_read_committed_snapshot_on
     FROM sys.databases WHERE name='<databasename>';



.. _SQLiteConfiguration:

SQLite
~~~~~~

SQLite has the great advantage of requiring almost no configuration. Simply
use 'sqlite' as db-driver, and set path to the dabase as db-name. Don't specify
anything for db-user and db-password, they will be ignore anyway.

.. Note::
  SQLite is great for testing and to play with cubicweb but is not suited for
  production environments.


.. _PyroConfiguration:

Pyro configuration
------------------

Pyro name server
~~~~~~~~~~~~~~~~

If you want to use Pyro to access your instance remotely, or to have multi-source
or distributed configuration, it is required to have a Pyro name server running
on your network. By default it is detected by a broadcast request, but you can
specify a location in the instance's configuration file.

To do so, you need to :

* be sure to have installed it (see :ref:`InstallDependencies`)

* launch the pyro name server with `pyro-nsd start` before starting cubicweb

* under debian, edit the file :file:`/etc/default/pyro-nsd` so that the name
  server pyro will be launched automatically when the machine fire up

Note that you can use the pyro server without a running pyro nameserver.
Refer to `pyro-ns-host` server configuration option for details.

