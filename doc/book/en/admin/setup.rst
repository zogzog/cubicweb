.. -*- coding: utf-8 -*-

.. _SetUpEnv:

Installation of a *CubicWeb* environment
========================================

There are different simple ways to install |cubicweb| and its
dependencies depending on your requirements:

* `Distribution-specific installation`. This option shows you how to
  easily install |cubicweb| and its requirements on your system:

  - `Installation on Debian/Ubuntu`_ 
  - `Installation on Windows`_
  - `Install in a virtualenv`_

* `Official release installation`. This options is the best approach
  for those who want a flexible and up-to-date stable
  version. |cubicweb| is published on `PyPI`_:

  - `Installation with pip`_
  - `Installation with easy_install`_

* `Lastest development version installation`. This option is
  dedicated for power-users who want the very lastest
  features (|cubicweb| is an `Agile software <http://en.wikipedia.org/wiki/Agile_software_development>`_).

  - `Installation from tarball`_
  - `Installation from version control`_

Once installed, you can have a look to :ref:`ConfigEnv` for better control
and advanced features of |cubicweb|.

.. _`Installation on Debian/Ubuntu`: DebianInstallation_
.. _`Installation on Windows`: WindowsInstallation_
.. _`Install in a virtualenv`: VirtualenvInstallation_
.. _`Installation with pip`: PipInstallation_
.. _`Installation with easy_install`: EasyInstallInstallation_
.. _`Installation from tarball`: TarballInstallation_
.. _`Installation from version control`: MercurialInstallation_


.. _DebianInstallation:

Debian/Ubuntu install
---------------------

|cubicweb| is packaged for Debian/Ubuntu (and derived
distributions). Their integrated package-management systems make
installation and upgrading much easier for users since
dependencies/recommends (like databases) are automatically installed.

Depending on the distribution you are using, add the appropriate line to your
`list of sources` (for example by editing ``/etc/apt/sources.list``).

For Debian Squeeze (stable)::

  deb http://download.logilab.org/production/ squeeze/

For Debian Sid (unstable)::

  deb http://download.logilab.org/production/ sid/

For Ubuntu Lucid (Long Term Support) and newer::

  deb http://download.logilab.org/production/ lucid/

  Note that for Ubuntu Maverick and newer, you shall use the `lucid`
  repository and install the ``libgecode19`` package from `lucid
  universe <http://packages.ubuntu.com/lucid/libgecode19>`_.

The repositories are signed with the `Logilab's gnupg key`_. You can download
and register the key to avoid warnings::

  wget -q http://download.logilab.org/logilab-dists-key.asc -O- | sudo apt-key add -

Update your list of packages and perform the installation::

  apt-get update
  apt-get install cubicweb cubicweb-dev

``cubicweb`` installs the framework itself, allowing you to create new
instances. ``cubicweb-dev`` installs the development environment
allowing you to develop new cubes.

There is also a wide variety of :ref:`cubes <AvailableCubes>`. You can acces a
list of availble cubes using ``apt-cache search cubicweb`` or at the
`CubicWeb.org Forge`_.

.. note::

  `cubicweb-dev` will install basic sqlite support. You can easily setup
  :ref:`cubicweb with other database <DatabaseInstallation>` using the following virtual packages :

  * `cubicweb-postgresql-support` contains necessary dependency for
    using :ref:`cubicweb with postgresql datatabase <PostgresqlConfiguration>`

  * `cubicweb-mysql-support` contains necessary dependency for using
    :ref:`cubicweb with mysql database <MySqlConfiguration>`.

.. _`list of sources`: http://wiki.debian.org/SourcesList
.. _`Logilab's gnupg key`: http://download.logilab.org/logilab-dists-key.asc
.. _`CubicWeb.org Forge`: http://www.cubicweb.org/project/

.. _WindowsInstallation:

Windows Install
---------------

You need to have `python`_ version >= 2.5 and < 3 installed.

Then your best option is probably the :ref:`EasyInstallInstallation`.
In fact it is a pure python packages manager which lacks in Windows.
It helps users to install python packages along with dependencies,
searching for suitable pre-compiled binaries on the
`The Python Package Index`_.

Moreover, if you want better control over the process as well as
a suitable development environment or if you are having problems with
`easy_install`, move right away to :ref:`SetUpWindowsEnv`.

.. _python:  http://www.python.org/
.. _`The Python Package Index`: http://pypi.python.org

.. _VirtualenvInstallation:

`Virtualenv` install
--------------------

Since version 3.9, |cubicweb| can be safely installed, used and contained inside
a `virtualenv`_. You can use either 
:ref:`pip <PipInstallation>` or
:ref:`easy_install <EasyInstallInstallation>` to install |cubicweb| inside an
activated virtual environment.

.. _PipInstallation:

`pip` install
-------------

Using pip_ is the recommended way to install |cubicweb|. pip_ is a
smart python utility that lets you automatically download, build,
install, and manage python packages and their dependencies. It is full
compatible with `virtualenv`_.

pip_ install the packages from sources published on the
*The Python Package Index* (PyPI_).
You need a compilation environment because some dependencies have C
extensions. If you definitively wont, installing 
`Lxml <http://codespeak.net/lxml/>`_,
`Twisted <http://twistedmatrix.com/trac/>`_ and 
`libgecode <http://www.gecode.org/>`_ will help.

To install |cubicweb| and all dependencies just use the following command
line::

  pip install cubicweb

There is also a wide variety of :ref:`cubes <AvailableCubes>`. You can acces a
list of availble cubes on
`PyPI <http://pypi.python.org/pypi?%3Aaction=search&term=cubicweb&submit=search>`_ 
or at the `CubicWeb.org Forge`_.

For example, installing the *blog cube* is achieved by::

  pip install cubicweb-blog

.. _`gecode library`: http://www.gecode.org/


.. _EasyInstallInstallation:

`easy_install` install
----------------------

If you are not a Windows user and you have a compilation environment,
we recommend you to use the PipInstallation_.

Install |cubicweb| version >= 3.9 with::

  easy_install cubicweb

There is also a wide variety of :ref:`cubes <AvailableCubes>`. You can acces a
list of availble cubes on `PyPI
<http://pypi.python.org/pypi?%3Aaction=search&term=cubicweb&submit=search>`_
or at the `CubicWeb.org Forge`_. 

For example, installing the *blog cube* is achieved by::

  easy_install cubicweb-blog

.. note::

  If you encounter problem with :ref:`cubes <AvailableCubes>` installation,
  considere using :ref:`PipInstallation` which is more stable
  but do not offer binaries installation.

.. _`easy_install`:   http://packages.python.org/distribute/easy_install.html


.. _SourceInstallation:

Install from source
-------------------

.. _TarballInstallation:

You can download the archive containing the sources from our download site at
`http://download.logilab.org/pub/cubicweb/ <http://download.logilab.org/pub/cubicweb/>`_.

Make sure you also have all the :ref:`InstallDependencies`.

Once uncompressed, you can install the framework from inside the uncompressed
folder with::

  python setup.py install

Or you can run |cubicweb| directly from the source directory by
setting the :ref:`resource mode <RessourcesConfiguration>` to `user`. This will
ease the development with the framework.

There is also a wide variety of :ref:`cubes <AvailableCubes>`. You can acces a
list of availble cubes at the `CubicWeb.org Forge`_.


.. _MercurialInstallation:

Install from version control system
-----------------------------------

To install the lastest stable development version from our Mercurial
repository, you can use `pip` (you need a compilation devlopment to perform
such install)::

  pip install -e "hg+http://www.logilab.org/hg/cubicweb/@stable#egg=cubicweb"

Or, to develop with the framework you can keep up to date with on-going
development by cloning our :ref:`Mercurial <MercurialPresentation>`
repository::

  hg clone -u stable http://hg.logilab.org/cubicweb # stable branch
  hg clone http://hg.logilab.org/cubicweb # very lastest (development branch)

Then a practical way to get many of CubicWeb's dependencies and a nice set
of base cubes is to run the `clone_deps.py` script located in
`cubicweb/bin/`::

  python cubicweb/bin/clone_deps.py

(Windows users should replace slashes with antislashes).

This script will clone a set of mercurial repositories into the
directory containing the ``cubicweb`` repository, and update them to the
latest published version tag (if any).

.. note::

  In every cloned repositories, a `hg tags` will display a list of
  tags in reverse chronological order. One reasonnable option is to go to a
  taged version: the latest published version or example, as done by
  the `clone_deps` script)::

   hg update cubicweb-debian-version-3.10.7-1

Make sure you also have all the :ref:`InstallDependencies`.

.. _`pip`: http://pip.openplans.org/
.. _`virtualenv`: http://virtualenv.openplans.org/
