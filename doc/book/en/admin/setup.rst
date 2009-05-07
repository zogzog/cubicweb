.. -*- coding: utf-8 -*-

.. _SetUpEnv:

===================================================
Installation and set-up of a `CubicWeb` environment
===================================================

Installation of `Cubicweb` and its dependencies
-----------------------------------------------

`CubicWeb` is packaged for Debian and Ubuntu, but can be installed from source
using a tarball or the Mercurial version control system.

.. _DebianInstallation:

Debian and Ubuntu packages
```````````````````````````

Depending on the distribution you are using, add the appropriate line to your list
of sources (for example by editing ``/etc/apt/sources.list``).

For Debian Lenny::

  deb http://ftp.logilab.org/dists/ lenny/

For Debian Sid::

  deb http://ftp.logilab.org/dists/ sid/

For Ubuntu Hardy::

  deb http://ftp.logilab.org/dists/ hardy/


You can now install the required packages with the following command::

  apt-get update 
  apt-get install cubicweb cubicweb-dev

`cubicweb` installs the framework itself, allowing you to create
new applications.

`cubicweb-dev` installs the development environment allowing you to
develop new cubes.

There is also a wide variety of cubes listed on http://www.cubicweb.org/Project available as debian packages and tarball.


Install from source
```````````````````

You can download the archive containing the sources from our `ftp site`_ at::

  http://ftp.logilab.org/pub/cubicweb/

.. _`ftp site`: http://ftp.logilab.org/pub/cubicweb/

or keep up to date with on-going development by using Mercurial and its forest
extension::

  hg fclone http://www.logilab.org/hg/forests/cubicweb

See :ref:`MercurialPresentation` for more details about Mercurial.

Postgres installation
`````````````````````

Please refer to the `Postgresql project online documentation`_.

.. _`Postgresql project online documentation`: http://www.postgresql.org/

You need to install the three following packages: `postgres-8.3`,
`postgres-contrib-8.3` and `postgresql-plpython-8.3`.


Then you can install:

* `pyro` if you wish the repository to be accessible through Pyro
  or if the client and the server are not running on the same machine
  (in which case the packages will have to be installed on both
  machines)

* `python-ldap` if you plan to use a LDAP source on the server

.. _ConfigurationEnv:

Environment configuration
-------------------------

If you installed `CubicWeb` by cloning the Mercurial forest, then you
will need to update the environment variable PYTHONPATH by adding  
the path to the forest ``cubicweb``:

Add the following lines to either `.bashrc` or `.bash_profile` to configure
your development environment ::
  
  export PYTHONPATH=/full/path/to/cubicweb-forest

If you installed the debian packages, no configuration is required.
Your new cubes will be placed in `/usr/share/cubicweb/cubes` and
your applications will be placed in `/etc/cubicweb.d`.

To use others directories then you will have to configure the
following environment variables as follows::

    export CW_CUBES_PATH=~/lib/cubes
    export CW_REGISTRY=~/etc/cubicweb.d/
    export CW_INSTANCE_DATA=$CW_REGISTRY
    export CW_RUNTIME=/tmp

.. note::
    The values given above are our suggestions but of course
    can be different.


Databases configuration
-----------------------



.. _ConfigurationPostgres:

Postgres configuration
``````````````````````

.. note::
    If you already have an existing cluster and postgres server
    running, you do not need to execute the initilization step
    of your Postgres database.

* First, initialize the database Postgres with the command ``initdb``.
  ::

    $ initdb -D /path/to/pgsql

  Once initialized, start the database server Postgres 
  with the command::
  
    $ postgres -D /path/to/psql

  If you cannot execute this command due to permission issues, please
  make sure that your username has write access on the database.
  ::
 
    $ chown username /path/to/pgsql

* The database authentication can be either set to `ident sameuser`
  or `md5`. 
  If set to `md5`, make sure to use an existing user
  of your database.
  If set to `ident sameuser`, make sure that your
  client's operating system user name has a matching user in
  the database. If not, please do as follow to create a user::
    
    $ su
    $ su - postgres
    $ createuser -s -P username

  The option `-P` (for password prompt), will encrypt the password with
  the method set in the configuration file ``pg_hba.conf``. 
  If you do not use this option `-P`, then the default value will be null
  and you will need to set it with::
    
    $ su postgres -c "echo ALTER USER username WITH PASSWORD 'userpasswd' | psql"

  This login/password will be requested when you will create an
  instance with `cubicweb-ctl create` to initialize the database of
  your application.

.. note::
    The authentication method can be configured in ``pg_hba.conf``.


.. FIXME Are these steps really necessary? It seemed to work without.

* Installation of plain-text index extension ::

    cat /usr/share/postgresql/8.3/contrib/tsearch2.sql | psql -U username template1

* Installation of plpythonu language by default ::

    createlang -U pgadmin plpythonu template1

MySql configuration
```````````````````
Yout must add the following lines in /etc/mysql/my.cnf file::

    transaction-isolation = READ-COMMITTED
    default-storage-engine=INNODB
    default-character-set=utf8
    max_allowed_packet = 128M

Pyro configuration
------------------

If you use Pyro, it is required to have a name server Pyro running on your
network (by default it is detected by a broadcast request).

To do so, you need to :

* launch the server manually before starting cubicweb as a server with
  `pyro-nsd start`

* edit the file ``/etc/default/pyro-nsd`` so that the name server pyro
  will be launched automatically when the machine fire up

