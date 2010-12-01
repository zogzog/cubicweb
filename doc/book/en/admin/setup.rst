.. -*- coding: utf-8 -*-

.. _SetUpEnv:

Installation and set-up of a *CubicWeb* environment
===================================================

Installation of `Cubicweb` and its dependencies
-----------------------------------------------

|cubicweb| is packaged for `Debian and Ubuntu`_, is `pip installable`_ and
`easy_install installable`_. It can be installed from source using a tarball_
or the `Mercurial version control system`_ . Windows user may want to check the
`Windows Installation`_ section.

Also, since version 3.9, can be safely installed, used and contained inside a
`virtualenv`_.


.. _`Debian and Ubuntu` : DebianInstallation_
.. _`pip installable`: PipInstallation_
.. _`easy_install installable`: EasyInstallInstallation_
.. _tarball: TarballInstallation_
.. _`Mercurial version control system`: MercurialInstallation_
.. _`Windows Installation`: WindowsInstallation_
.. _`virtualenv`: http://pypi.python.org/pypi/virtualenv


.. file:///home/pyves/tmp/cwdoc/html/admin/setup.html#pipinstallation

.. _DebianInstallation:

Debian and Ubuntu packages
```````````````````````````

Depending on the distribution you are using, add the appropriate line to your
list of sources (for example by editing ``/etc/apt/sources.list``).

For Debian Lenny::

  deb http://ftp.logilab.org/dists/ lenny/

For Debian Sid::

  deb http://ftp.logilab.org/dists/ sid/

For Ubuntu Hardy::

  deb http://ftp.logilab.org/dists/ hardy/


You can now install the required packages with the following command::

  apt-get update
  apt-get install cubicweb cubicweb-dev


`cubicweb` installs the framework itself, allowing you to create new instances.

`cubicweb-dev` installs the development environment allowing you to develop new
cubes.

.. note::

   `cubicweb-dev` will install basic sqlite support. You can easily setup
   `cubicweb with other database`_ using the following virtual packages :
   `cubicweb-postgresql-support` contains necessary dependency for using
   `cubicweb with postgresql datatabase`_ and `cubicweb-mysql-support` contains
   necessary dependency for using `cubicweb with mysql database`_ .

There is also a wide variety of :ref:`cubes <Cubes>` listed on the `CubicWeb.org Forge`_
available as debian packages and tarball.

The repositories are signed with `Logilab's gnupg key`_. To avoid warning on
"apt-get update":

1. become root using sudo
2. download http://ftp.logilab.org/dists/logilab-dists-key.asc using e.g. wget
3. run "apt-key add logilab-dists-key.asc"
4. re-run apt-get update (manually or through the package manager, whichever you prefer)

.. _`Logilab's gnupg key`: http://ftp.logilab.org/dists/logilab-dists-key.asc
.. _`CubicWeb.org Forge`: http://www.cubicweb.org/project/
.. _`cubicweb with other database`: DatabaseInstallation_
.. _`cubicweb with postgresql datatabase` : PostgresqlConfiguration_
.. _`cubicweb with mysql database` : MySqlConfiguration_


.. _PipInstallation:

Installation with pip
`````````````````````

pip_ is a smart python utility that lets you automatically download, build,
install, and manage python packages and their dependencies.

|cubicweb| and its cubes have been pip_ installable since version 3.9. Search
for them on pypi_::

  pip install cubicweb
  pip install cubicweb-blog

.. note::

    Pip is the recommended way to install |cubicweb| if there is no binary
    package available on your system or you want to install it inside a
    `virtualenv`_. However pip doesn't install binary package and may require
    several compilation steps while installing |cubicweb| dependencies. If you
    don't have a compilation environment you should use  `easy_install
    installation`_ to install |cubicweb|.

    Once, |cubicweb| is installed, this limitation doesn't apply when installing
    cubes.


.. _pip: http://pypi.python.org/pypi/pip
.. _pypi: http://pypi.python.org/pypi?%3Aaction=search&term=cubicweb
.. _`easy_install installation`: EasyInstallInstallation_


.. warning::

  |cubicweb| depends upon the `lxml` python module. This module contains ``C``
  code that must be compiled.  To successfully install |cubicweb| with pip, you
  must either have an environment ables to compile Python ``C`` extensions or
  preinstall lxml from a binary package.

.. note::

  For better performance the setup processor will compile a ``C`` extension for
  the :ref:`RQL <RQL>` language if you have an environment ables to compile
  Python ``C`` extensions and the `gecode library`_.  Otherwise, a pure python
  alternative will be used for degraded performance.

.. _`gecode library`: http://www.gecode.org/
.. _`easy_install`:   http://packages.python.org/distribute/easy_install.html


.. _EasyInstallInstallation:

Installation with EasyInstall
``````````````````````````````

.. note::

    We don't recommend the use of `easy_install` and setuptools in the generic
    case. However as easy_install is currently the sole pure python package
    system that support binary installation. Using `easy_install` is currently
    the easiest way to install |cubicweb| when you don't have a compilation
    environment set-up or Debian based distribution.


|cubicweb| is easy_install_ installable for version 3.9::

  easy_install cubicweb

.. warning::

    Cubes are **not** is easy_install_ installable. But they are
    `pip installable`_




.. _SourceInstallation:

Install from source
```````````````````

.. _TarballInstallation:

You can download the archive containing the sources from our `ftp site`_ at::

  http://ftp.logilab.org/pub/cubicweb/

.. _`ftp site`: http://ftp.logilab.org/pub/cubicweb/

Make sure you also have all the :ref:`InstallDependencies`.

.. _MercurialInstallation:

Install from version control system
```````````````````````````````````

You can keep up to date with on-going development by using Mercurial::

  hg clone http://hg.logilab.org/cubicweb

See :ref:`MercurialPresentation` for more details about Mercurial.

A practical way to get many of CubicWeb's dependencies and a nice set
of base cubes is to run the `clone_deps.py` script located in
`cubicweb/bin/`::

  python cubicweb/bin/clone_deps.py

(Windows users should replace slashes with antislashes).

This script will clone a set of mercurial repositories into in the
directory containing the CubicWeb repository, and update them to the
latest published version tag (if any).

When cloning a repository, you might be set in a development branch
(the 'default' branch). You should check that the branches of the
repositories are set to 'stable' (using `hg up stable` for each one)
if you do not intend to develop the framework itself.

Even better, `hg tags` will display a list of tags in reverse
chronological order. One reasonnable way to get to a working version
is to pick the latest published version (as done by the `clone_deps`
script). These look like `cubicweb-debian-version-3.9.7-1`. Typing::

 hg update cubicweb-debian-version-3.9.7-1

will update the repository files to this version.

Make sure you also have all the :ref:`InstallDependencies`.


.. _WindowsInstallation:

Windows installation
````````````````````

Your best option is probably the :ref:`PipInstallation`. If it does not work or
if you want more control over the process, continue with the following
instructions.

Base elements
~~~~~~~~~~~~~

Setting up a windows development environment is not too complicated but requires
a series of small steps. What is proposed there is only an example of what can be
done. We assume everything goes into `C:\\` in this document. Adjusting the
installation drive should be straightforward.

You should start by downloading and installing Python version >= 2.5 and < 3.

An alternative option would be installing the Python(x,y)
distribution. Python(x,y) is not a requirement, but it makes things easier for
Windows user by wrapping in a single installer python 2.5 plus numerous useful
third-party modules and applications (including Eclipse + pydev, which is an
arguably good IDE for Python under Windows). Download it from this page::

  http://code.google.com/p/pythonxy/wiki/Downloads

Then you must grab Twisted. There is a windows installer directly available from
this page::

  http://twistedmatrix.com/trac/

A windows installer for lxml will be found there::

  http://pypi.python.org/pypi/lxml/2.2.1

Check out the lxml-2.2.1-win32-py2.5.exe file. More recent bugfix
releases should probably work, too.

You should find postgresql 8.4 there::

  http://www.enterprisedb.com/products/pgdownload.do#windows

The python drivers for posgtresql are to be found there::

  http://www.stickpeople.com/projects/python/win-psycopg/#Version2

Please be careful to select the right python (2.5) and postgres (8.4) versions.

A windows compiled recent version of gettext::

  http://ftp.logilab.org/pub/gettext/gettext-0.17-win32-setup.exe

A pre-compiled version of rql for windows (take care of retrieving the
most recent version available there)::

  http://ftp.logilab.org/pub/rql/rql-0.23.0.win32-py2.5.exe

Pyro enables remote access to cubicweb repository instances. Get it there::

  http://sourceforge.net/projects/pyro/files/

To access LDAP/Active directory directories, we need the python-ldap
package. Windows binaries are available from::

  http://www.osuch.org/python-ldap

Check out the latest release.

Having graphviz will allow schema drawings, which is quite recommended (albeit
not mandatory). You should get an msi installer there::

  http://www.graphviz.org/Download_windows.php

Simplejson is needed when installing with Python 2.5, but included in the
standard library for Python >= 2.6. Get it from there::

  http://www.osuch.org/python-simplejson%3Awin32

Make sure you also have all the :ref:`InstallDependencies` that are not specific
to Windows.

Tools
~~~~~

Get mercurial + its standard windows GUI (TortoiseHG) there (the latest is the
greatest)::

  http://bitbucket.org/tortoisehg/stable/wiki/download

If you need to peruse mercurial over ssh, it can be helpful to get an ssh client
like Putty::

  http://www.putty.org/

Integration of mercurial and Eclipse is convenient enough that we want
it. Instructions are set there, in the `Download & Install` section::

  http://www.vectrace.com/mercurialeclipse/

Getting the sources
~~~~~~~~~~~~~~~~~~~

You can either download the latest release (see
:ref:`SourceInstallation`) or get the development version using
Mercurial (see :ref:`MercurialInstallation` and below), which is more
convenient.

Environment variables
~~~~~~~~~~~~~~~~~~~~~

You will need some convenience environment variables once all is set up. These
variables are settable through the GUI by getting at the 'System properties'
window (by righ-clicking on 'My Computer' -> properties).

In the 'advanced' tab, there is an 'Environment variables' button. Click on
it. That opens a small window allowing edition of user-related and system-wide
variables.

We will consider only user variables. First, the PATH variable. You should ensure
it contains, separated by semi-colons, and assuming you are logged in as user
Jane::

  C:\Documents and Settings\Jane\My Documents\Python\cubicweb\cubicweb\bin
  C:\Program Files\Graphviz2.24\bin

The PYTHONPATH variable should also contain::

  C:\Documents and Settings\Jane\My Documents\Python\cubicweb\

From now, on a fresh `cmd` shell, you should be able to type::

  cubicweb-ctl list

... and get a meaningful output.

Running an instance as a service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This currently assumes that the instances configurations is located at
C:\\etc\\cubicweb.d.

For a cube 'my_instance', you will then find
C:\\etc\\cubicweb.d\\my_instance\\win32svc.py that has to be used as follows::

  win32svc install

This should just register your instance as a windows service. A simple::

  net start cubicweb-my_instance

should start the service.


Other dependencies
``````````````````

You can also install:

* `pyro` if you wish the repository to be accessible through Pyro
  or if the client and the server are not running on the same machine
  (in which case the packages will have to be installed on both
  machines)

* `python-ldap` if you plan to use a LDAP source on the server


.. _DatabaseInstallation:

Databases configuration
-----------------------

Each instance can be configured with its own database connection information,
that will be stored in the instance's :file:`sources` file. The database to use
will be chosen when creating the instance. Currently cubicweb has been tested
using Postgresql (recommended), MySQL, SQLServer and SQLite.

Other possible sources of data include CubicWeb, Subversion, LDAP and Mercurial,
but at least one relational database is required for CubicWeb to work. You do
not need to install a backend that you do not intend to use for one of your
instances. SQLite is not fit for production use, but it works well for testing
and ships with Python, which saves installation time when you want to get
started quickly.

.. _PostgresqlConfiguration:

PostgreSQL configuration
````````````````````````

For installation, please refer to the `PostgreSQL project online documentation`_.

.. _`PostgreSQL project online documentation`: http://www.postgresql.org/

You need to install the three following packages: `postgresql-8.X`,
`postgresql-client-8.X`, and `postgresql-plpython-8.X`. If you run postgres
version prior to 8.3, you'll also need the `postgresql-contrib-8.X` package for
full-text search extension.

If you run postgres on another host than the |cubicweb| repository, you should
install the `postgresql-client` package on the |cubicweb| host, and others on the
database host.

.. Note::

    If you already have an existing cluster and PostgreSQL server running, you do
    not need to execute the initilization step of your PostgreSQL database unless
    you want a specific cluster for |cubicweb| databases or if your existing
    cluster doesn't use the UTF8 encoding (see note below).

* First, initialize a PostgreSQL cluster with the command ``initdb``.
  ::

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

* The database authentication can be either set to `ident sameuser` or `md5`.  If
  set to `md5`, make sure to use an existing user of your database.  If set to
  `ident sameuser`, make sure that your client's operating system user name has a
  matching user in the database. If not, please do as follow to create a user::

    $ su
    $ su - postgres
    $ createuser -s -P username

  The option `-P` (for password prompt), will encrypt the password with the
  method set in the configuration file :file:`pg_hba.conf`.  If you do not use this
  option `-P`, then the default value will be null and you will need to set it
  with::

    $ su postgres -c "echo ALTER USER username WITH PASSWORD 'userpasswd' | psql"

.. Note::
    The authentication method can be configured in file:`pg_hba.conf`.


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

MySql configuration
```````````````````
You must add the following lines in ``/etc/mysql/my.cnf`` file::

    transaction-isolation=READ-COMMITTED
    default-storage-engine=INNODB
    default-character-set=utf8
    max_allowed_packet = 128M

.. Note::
    It is unclear whether mysql supports indexed string of arbitrary length or
    not.


.. _SQLServerConfiguration:

SQLServer configuration
```````````````````````

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



.. _SQLiteConfiguration:

SQLite configuration
````````````````````
SQLite has the great advantage of requiring almost no configuration. Simply
use 'sqlite' as db-driver, and set path to the dabase as db-name. Don't specify
anything for db-user and db-password, they will be ignore anyway.

.. Note::
  SQLite is great for testing and to play with cubicweb but is not suited for
  production environments.


.. _PyroConfiguration:

Pyro configuration
------------------

If you want to use Pyro to access your instance remotely, or to have multi-source
or distributed configuration, it is required to have a Pyro name server running
on your network. By default it is detected by a broadcast request, but you can
specify a location in the instance's configuration file.

To do so, you need to :

* launch the pyro name server with `pyro-nsd start` before starting cubicweb

* under debian, edit the file :file:`/etc/default/pyro-nsd` so that the name
  server pyro will be launched automatically when the machine fire up


Cubicweb resources configuration
--------------------------------

.. autodocstring:: cubicweb.cwconfig
