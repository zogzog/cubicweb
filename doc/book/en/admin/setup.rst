.. -*- coding: utf-8 -*-

.. _SetUpEnv:

Installation and set-up of a *CubicWeb* environment
===================================================

Installation of `Cubicweb` and its dependencies
-----------------------------------------------

*CubicWeb* is packaged for Debian and Ubuntu, but can be installed from source
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
new instances.

`cubicweb-dev` installs the development environment allowing you to
develop new cubes.

There is also a wide variety of cubes listed on http://www.cubicweb.org/Project available as debian packages and tarball.

The repositories are signed with `Logilab's gnupg key`_. To avoid warning on "apt-get update":
1. become root using sudo
2. download http://ftp.logilab.org/dists/logilab-dists-key.asc using e.g. wget
3. run "apt-key add logilab-dists-key.asc"
4. re-run apt-get update (manually or through the package manager, whichever you prefer)

.. _`Logilab's gnupg key`: http://ftp.logilab.org/dists/logilab-dists-key.asc

.. _SourceInstallation:

Install from source
```````````````````

You can download the archive containing the sources from our `ftp site`_ at::

  http://ftp.logilab.org/pub/cubicweb/

.. _`ftp site`: http://ftp.logilab.org/pub/cubicweb/

Make sure you have installed the dependencies (see appendixes for the list).

Install from version control system
```````````````````````````````````

You can keep up to date with on-going development by using Mercurial and its
forest extension::

  hg fclone http://www.logilab.org/hg/forests/cubicweb

See :ref:`MercurialPresentation` for more details about Mercurial.

When cloning a repository, you might be set in a development branch
(the 'default' branch). You should check that the branches of the
repositories are set to 'stable' (using `hg up stable` for each one)
if you do not intend to develop the framework itself.

Do not forget to update the forest itself (using `cd path/to/forest ; hg up`).

Make sure you have installed the dependencies (see appendixes for the list).

.. _WindowsInstallation:

Windows installation
````````````````````

Base elements
_____________

Setting up a windows development environment is not too complicated
but requires a series of small steps. What is proposed there is only
an example of what can be done. We assume everything goes into C:\ in
this document. Adjusting the installation drive should be
straightforward.

You should start by downloading and installing the Python(x,y)
distribution. It contains python 2.5 plus numerous useful third-party
modules and applications::

  http://www.pythonxy.com/download_fr.php

At the time of this writting, one gets version 2.1.15. Among the many
things provided, one finds Eclipse + pydev (an arguably good IDE for
python under windows).

Then you must grab Twisted. There is a windows installer directly
available from this page::

  http://twistedmatrix.com/trac/

A windows installer for lxml will be found there::

  http://pypi.python.org/pypi/lxml/2.2.1

Check out the lxml-2.2.1-win32-py2.5.exe file. More recent bugfix
releases should probably work, too.

You should find postgresql 8.4 there::

  http://www.enterprisedb.com/products/pgdownload.do#windows

The python drivers for posgtresql are to be found there::

  http://www.stickpeople.com/projects/python/win-psycopg/#Version2

Please be careful to select the right python (2.5) and postgres (8.4)
versions.

Pyro enable remote access to cubicweb repository instances. Get it
there::

  http://sourceforge.net/projects/pyro/files/

To access LDAP/Active directory directories, we need the python-ldap
package. Windows binaries are available from::

  http://www.osuch.org/python-ldap

Check out the latest release.

Having graphviz will allow schema drawings, which is quite recommended
(albeit not mandatory). You should get an msi installer there::

  http://www.graphviz.org/Download_windows.php

Simplejson will be provided within the forest, but a win32 compiled
version will run much faster::

  http://www.osuch.org/python-simplejson%3Awin32

Tools
_____

Get mercurial + its standard windows GUI (TortoiseHG) there (the
latest is the greatest)::

  http://bitbucket.org/tortoisehg/stable/wiki/download

If you need to peruse mercurial over ssh, it can be helpful to get an
ssh client like Putty::

  http://www.putty.org/

Integration of mercurial and Eclipse is convenient enough that we want
it. Instructions are set there, in the `Download & Install` section::

  http://www.vectrace.com/mercurialeclipse/

Setting up the sources
______________________

You need to enable the mercurial forest extension. To do this, edit
the file::

  C:\Program Files\TortoiseHg\Mercurial.ini

In the [extensions] section, add the following line::

  forest=C:\Program Files\TortoiseHg\ext\forest\forest.py

Now, you need to clone the cubicweb repository. We assume that you use
Eclipse. From the IDE, choose File -> Import. In the box, select
`Mercurial/Clone repository using MercurialEclipse`.

In the import main panel you just have to:

* fill the URL field with http://www.logilab.org/hg/forests/cubicwin32

* check the 'Repository is a forest' box.

Then, click on 'Finish'. It might take some time to get it all. Note
that the `cubicwin32` forest contains additional python packages such
as yapps, vobject, simplejson and twisted-web2 which are not provided
with Python(x,y). This is provided for convenience, as we do not
ensure the up-to-dateness of these packages, especially with respect
to security fixes.

Environment variables
_____________________

You will need some convenience environment variables once all is set
up. These variables are settable through the GUI by getting at the
'System properties' window (by righ-clicking on 'My Computer' ->
properties).

In the 'advanced' tab, there is an 'Environment variables'
button. Click on it. That opens a small window allowing edition of
user-related and system-wide variables.

We will consider only user variables. First, the PATH variable. You
should ensure it contains, separated by semi-colons, and assuming you
are logged in as user Jane::

  C:\Documents and Settings\Jane\My Documents\Python\cubicweb\cubicweb\bin
  C:\Program Files\Graphviz2.24\bin

The PYTHONPATH variable should also contain::

  C:\Documents and Settings\Jane\My Documents\Python\cubicweb\

From now, on a fresh `cmd` shell, you should be able to type::

  cubicweb-ctl list

... and get a meaningful output.

Running an instance as a service
--------------------------------

This currently assumes that the instances configurations is located
at C:\etc\cubicweb.d.

For a cube 'my_cube', you will then find C:\etc\cubicweb.d\my_cube\win32svc.py
that has to be used thusly::

  win32svc install

This should just register your instance as a windows service. A simple::

  net start cubicweb-my_cube

should start the service.


PostgreSQL installation
```````````````````````

Please refer to the `PostgreSQL project online documentation`_.

.. _`PostgreSQL project online documentation`: http://www.postgresql.org/

You need to install the three following packages: `postgresql-8.3`,
`postgresql-contrib-8.3` and `postgresql-plpython-8.3`.


Other dependencies
``````````````````

You can also install:

* `pyro` if you wish the repository to be accessible through Pyro
  or if the client and the server are not running on the same machine
  (in which case the packages will have to be installed on both
  machines)

* `python-ldap` if you plan to use a LDAP source on the server

.. _ConfigurationEnv:

Environment configuration
-------------------------

If you installed *CubicWeb* by cloning the Mercurial forest, then you
will need to update the environment variable PYTHONPATH by adding
the path to the forest ``cubicweb``:

Add the following lines to either `.bashrc` or `.bash_profile` to configure
your development environment ::

    export PYTHONPATH=/full/path/to/cubicweb-forest

If you installed *CubicWeb* with packages, no configuration is required and your
new cubes will be placed in `/usr/share/cubicweb/cubes` and your instances
will be placed in `/etc/cubicweb.d`.

You may run a system-wide install of *CubicWeb* in "user mode" and use it for
development by setting the following environment variable::

    export CW_MODE=user
    export CW_CUBES_PATH=~/lib/cubes
    export CW_INSTANCES_DIR=~/etc/cubicweb.d/
    export CW_INSTANCES_DATA_DIR=$CW_INSTANCES_DIR
    export CW_RUNTIME_DIR=/tmp

.. note::
    The values given above are our suggestions but of course
    can be different.


Databases configuration
-----------------------

.. _ConfigurationPostgresql:

PostgreSQL configuration
````````````````````````

.. note::
    If you already have an existing cluster and PostgreSQL server
    running, you do not need to execute the initilization step
    of your PostgreSQL database.

* First, initialize the database PostgreSQL with the command ``initdb``.
  ::

    $ initdb -D /path/to/pgsql

  Once initialized, start the database server PostgreSQL
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
  your instance.

.. note::
    The authentication method can be configured in ``pg_hba.conf``.


.. FIXME Are these steps really necessary? It seemed to work without.

* Installation of plain-text index extension ::

    cat /usr/share/postgresql/8.3/contrib/tsearch2.sql | psql -U username template1

* Installation of plpythonu language by default ::

    createlang -U pgadmin plpythonu template1

MySql configuration
```````````````````
Yout must add the following lines in ``/etc/mysql/my.cnf`` file::

    transaction-isolation = READ-COMMITTED
    default-storage-engine=INNODB
    default-character-set=utf8
    max_allowed_packet = 128M

.. note::
    It is unclear whether mysql supports indexed string of arbitrary lenght or
    not.

Pyro configuration
------------------

If you use Pyro, it is required to have a name server Pyro running on your
network (by default it is detected by a broadcast request).

To do so, you need to :

* launch the server manually before starting cubicweb as a server with
  `pyro-nsd start`

* edit the file ``/etc/default/pyro-nsd`` so that the name server pyro
  will be launched automatically when the machine fire up

