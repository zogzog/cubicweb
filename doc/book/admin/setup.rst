.. -*- coding: utf-8 -*-

.. _SetUpEnv:

Installation of a *CubicWeb* environment
========================================

Official releases are available from the `CubicWeb.org forge`_ and from
`PyPI`_. Since CubicWeb is developed using `Agile software development
<http://en.wikipedia.org/wiki/Agile_software_development>`_ techniques, releases
happen frequently. In a version numbered X.Y.Z, X changes after a few years when
the API breaks, Y changes after a few weeks when features are added and Z
changes after a few days when bugs are fixed.

Depending on your needs, you will chose a different way to install CubicWeb on
your system:

- `Installation using docker`_
- `Installation on Debian/Ubuntu`_
- `Installation in a virtualenv`_
- `Installation with pip`_
- `Installation from tarball`_

If you are a power-user and need the very latest features, you will

- `Install from version control`_

Once the software is installed, move on to :ref:`ConfigEnv` for better control
and advanced features of |cubicweb|.

.. _`Installation on Debian/Ubuntu`: DebianInstallation_
.. _`Installation in a virtualenv`: VirtualenvInstallation_
.. _`Installation with pip`: PipInstallation_
.. _`Installation from tarball`: TarballInstallation_
.. _`Install from version control`: MercurialInstallation_


.. _DockerInstallation:

Docker install
--------------

Detailed instructions on how to deploy CubicWeb using docker can be found
on the `docker hub <https://hub.docker.com/r/logilab/cubicweb>`_.

The images there are built using the following source code :
`docker-cubicweb <https://hg.logilab.org/master/docker-cubicweb/>`_,
see it's `README <https://hg.logilab.org/master/docker-cubicweb/file/tip/README.rst>`_

.. _DebianInstallation:

Debian/Ubuntu install
---------------------

|cubicweb| is packaged for Debian/Ubuntu (and derived
distributions). Their integrated package-management system make
installation and upgrade much easier for users since
dependencies (like databases) are automatically installed.

Depending on the distribution you are using, add the appropriate line to your
`list of sources` (for example by editing ``/etc/apt/sources.list``), replacing
``<release>`` with e.g. ``buster`` or ``bionic``::

  deb http://apt.logilab.fr <release> main  # all cubicweb & cubes
  deb http://apt.logilab.fr <release> cubicweb-3.26  # latest cubicweb 3.26 & cubes

The repositories are signed with `Logilab's gnupg key`_. You can download
and register the key to avoid warnings::

  wget -O/etc/apt/trusted.gpg.d/logilab.gpg https://www.logilab.fr/logilab-debian-keyring.gpg

Update your list of packages and perform the installation::

  apt-get update
  apt-get install python3-cubicweb --install-recommends

``python3-cubicweb`` installs the framework itself, allowing you to create new
instances. Installing recommended packages will install the development
environment allowing you to develop new cubes.

There is also a wide variety of :ref:`cubes <AvailableCubes>`. You can access a
list of available cubes using ``apt-cache search cubicweb`` or at the
`CubicWeb.org forge`_.

.. note::

  `python3-cubicweb` will install basic sqlite support. You can easily setup
  :ref:`cubicweb with other database <DatabaseInstallation>` using the following
  virtual packages :

  * `python3-cubicweb-postgresql-support` contains the necessary dependencies for
    using :ref:`cubicweb with postgresql datatabase <PostgresqlConfiguration>`

.. _`list of sources`: http://wiki.debian.org/SourcesList
.. _`Logilab's gnupg key`: https://www.logilab.fr/logilab-debian-keyring.gpg
.. _`CubicWeb.org Forge`: http://www.cubicweb.org/project/

.. _VirtualenvInstallation:

`Virtualenv` install
--------------------

|cubicweb| can be safely installed, used and contained inside a
`virtualenv`_. You can use either :ref:`pip <PipInstallation>` or
:ref:`easy_install <EasyInstallInstallation>` to install |cubicweb|
inside an activated virtual environment.

.. _PipInstallation:

`pip` install
-------------

`pip <https://pip.pypa.io/>`_ is a python tool that helps downloading,
building, installing, and managing Python packages and their dependencies. It
is fully compatible with `virtualenv`_ and installs the packages from sources
published on the `The Python Package Index`_.

.. _`virtualenv`: https://virtualenv.pypa.io

A working compilation chain is needed to build the modules that include C
extensions. If you really do not want to compile anything, installing `lxml <http://lxml.de/>`_,
and `libgecode <http://www.gecode.org/>`_ will help.

For Debian, these minimal dependencies can be obtained by doing::

  apt-get install gcc python3-pip python3-dev python3-lxml

or, if you prefer to get as much as possible from pip::

  apt-get install gcc python3-pip python3-dev libxslt1-dev libxml2-dev

For Windows, you can install pre-built packages (possible `source
<http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_). For a minimal setup, install:

- pip http://www.lfd.uci.edu/~gohlke/pythonlibs/#pip
- setuptools http://www.lfd.uci.edu/~gohlke/pythonlibs/#setuptools
- libxml-python http://www.lfd.uci.edu/~gohlke/pythonlibs/#libxml-python>
- lxml http://www.lfd.uci.edu/~gohlke/pythonlibs/#lxml and

Make sure to choose the correct architecture and version of Python.

Finally, install |cubicweb| and its dependencies, by running::

  pip install cubicweb[pyramid]

Many other :ref:`cubes <AvailableCubes>` are available. A list is available at
`PyPI <http://pypi.python.org/pypi?%3Aaction=search&term=cubicweb&submit=search>`_
or at the `CubicWeb.org forge`_.

For example, installing the *blog cube* is achieved by::

  pip install cubicweb-blog

.. _SourceInstallation:

Install from source
-------------------

.. _TarballInstallation:

You can download the archive containing the sources from
`http://download.logilab.org/pub/cubicweb/ <http://download.logilab.org/pub/cubicweb/>`_.

Make sure you also have all the :ref:`InstallDependencies`.

Once uncompressed, you can install the framework from inside the uncompressed
folder with::

  python3 setup.py install

Or you can run |cubicweb| directly from the source directory by
setting the :ref:`resource mode <RessourcesConfiguration>` to `user`. This will
ease the development with the framework.

There is also a wide variety of :ref:`cubes <AvailableCubes>`. You can access a
list of availble cubes at the `CubicWeb.org Forge`_.


.. _MercurialInstallation:

Install from version control system
-----------------------------------

To keep-up with on-going development, clone the :ref:`Mercurial
<MercurialPresentation>` repository::

  hg clone -u 'last(tag())' http://hg.logilab.org/cubicweb # stable version
  hg clone http://hg.logilab.org/cubicweb # development branch

Make sure you also have all the :ref:`InstallDependencies`.
