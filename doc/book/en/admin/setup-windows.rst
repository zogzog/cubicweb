.. -*- coding: utf-8 -*-

.. _SetUpWindowsEnv:

Installing a development environement on Windows
================================================

Setting up a Windows development environment is not too complicated
but it requires a series of small steps.

We propose an example of a typical |cubicweb| installation on Windows
from sources. We assume everything goes into ``C:\\`` and for any
package, without version specification, "the latest is
the greatest".

Mind that adjusting the installation drive should be straightforward.



Install the required elements
-----------------------------

|cubicweb| requires some base elements that must be installed to run
correctly. So, first of all, you must install them :

* python >= 2.6 and < 3
  (`Download Python <http://www.python.org/download/>`_).
  You can also consider the Python(x,y) distribution
  (`Download Python(x,y) <http://code.google.com/p/pythonxy/wiki/Downloads>`_)
  as it makes things easier for Windows user by wrapping in a single installer
  python 2.7 plus numerous useful third-party modules and
  applications (including Eclipse + pydev, which is an arguably good
  IDE for Python under Windows).

* `Twisted <http://twistedmatrix.com/trac/>`_ is an event-driven
  networking engine
  (`Download Twisted <http://twistedmatrix.com/trac/>`_)

* `lxml <http://codespeak.net/lxml/>`_ library
  (version >=2.2.1) allows working with XML and HTML
  (`Download lxml <http://pypi.python.org/pypi/lxml/2.2.1>`_)

* `Postgresql <http://www.postgresql.org/>`_,
  an object-relational database system
  (`Download Postgresql <http://www.enterprisedb.com/products/pgdownload.do#windows>`_)
  and its python drivers
  (`Download psycopg <http://www.stickpeople.com/projects/python/win-psycopg/#Version2>`_)

* A recent version of `gettext`
  (`Download gettext <http://download.logilab.org/pub/gettext/gettext-0.17-win32-setup.exe>`_).

* `rql <http://www.logilab.org/project/rql>`_,
  the recent version of the Relationship Query Language parser.

Install optional elements
-------------------------

We recommend you to install the following elements. They are not
mandatory but they activate very interesting features in |cubicweb|:

* `python-ldap <http://pypi.python.org/pypi/python-ldap>`_
  provides access to LDAP/Active directory directories
  (`Download python-ldap <http://www.osuch.org/python-ldap>`_).

* `graphviz <http://www.graphviz.org/>`_
  which allow schema drawings.
  (`Download graphviz <http://www.graphviz.org/Download_windows.php>`_).
  It is quite recommended (albeit not mandatory).

Other elements will activate more features once installed. Take a look
at :ref:`InstallDependencies`.

Useful tools
------------

Some additional tools could be useful to develop :ref:`cubes <AvailableCubes>`
with the framework.

* `mercurial <http://mercurial.selenic.com/>`_ and its standard windows GUI
  (`TortoiseHG <http://tortoisehg.bitbucket.org/>`_) allow you to get the source
  code of |cubicweb| from control version repositories. So you will be able to
  get the latest development version and pre-release bugfixes in an easy way
  (`Download mercurial <http://bitbucket.org/tortoisehg/stable/wiki/download>`_).

* You can also consider the ssh client `Putty` in order to peruse
  mercurial over ssh (`Download <http://www.putty.org/>`_).

* If you are an Eclipse user, mercurial can be integrated using the
  `MercurialEclipse` plugin
  (`Home page <http://www.vectrace.com/mercurialeclipse/>`_).

Getting the sources
-------------------

There are two ways to get the sources of |cubicweb| and its
:ref:`cubes <AvailableCubes>`:

* download the latest release (:ref:`SourceInstallation`)
* get the development version using Mercurial
  (:ref:`MercurialInstallation`)

Environment variables
---------------------

You will need some convenience environment variables once all is set up. These
variables are settable through the GUI by getting at the `System properties`
window (by righ-clicking on `My Computer` -> `properties`).

In the `advanced` tab, there is an `Environment variables` button. Click on
it. That opens a small window allowing edition of user-related and system-wide
variables.

We will consider only user variables. First, the ``PATH`` variable. Assuming
you are logged as user *Jane*, add the following paths, separated by
semi-colons::

  C:\Documents and Settings\Jane\My Documents\Python\cubicweb\cubicweb\bin
  C:\Program Files\Graphviz2.24\bin

The ``PYTHONPATH`` variable should also contain::

  C:\Documents and Settings\Jane\My Documents\Python\cubicweb\

From now, on a fresh `cmd` shell, you should be able to type::

  cubicweb-ctl list

... and get a meaningful output.

Running an instance as a service
--------------------------------

This currently assumes that the instances configurations is located at
``C:\\etc\\cubicweb.d``. For a cube 'my_instance', you will find
``C:\\etc\\cubicweb.d\\my_instance\\win32svc.py``.

Now, register your instance as a windows service with::

  win32svc install

Then start the service with::

  net start cubicweb-my_instance

In case this does not work, you should be able to see error reports in
the application log, using the windows event log viewer.
