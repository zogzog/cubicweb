.. -*- coding: utf-8 -*-

.. _InstallDependencies:

Installation dependencies
=========================

When you run CubicWeb from source, either by downloading the tarball or
cloning the mercurial tree, here is the list of tools and libraries you need
to have installed in order for CubicWeb to work:

* yapps - http://theory.stanford.edu/~amitp/yapps/ -
  http://pypi.python.org/pypi/Yapps2

* pygraphviz - http://networkx.lanl.gov/pygraphviz/ -
  http://pypi.python.org/pypi/pygraphviz

* docutils - http://docutils.sourceforge.net/ - http://pypi.python.org/pypi/docutils

* lxml - http://codespeak.net/lxml - http://pypi.python.org/pypi/lxml

* twisted - http://twistedmatrix.com/ - http://pypi.python.org/pypi/Twisted

* logilab-common - http://www.logilab.org/project/logilab-common -
  http://pypi.python.org/pypi/logilab-common/

* logilab-database - http://www.logilab.org/project/logilab-database -
  http://pypi.python.org/pypi/logilab-database/

* logilab-constraint - http://www.logilab.org/project/logilab-constraint -
  http://pypi.python.org/pypi/constraint/

* logilab-mtconverter - http://www.logilab.org/project/logilab-mtconverter -
  http://pypi.python.org/pypi/logilab-mtconverter

* rql - http://www.logilab.org/project/rql - http://pypi.python.org/pypi/rql

* yams - http://www.logilab.org/project/yams - http://pypi.python.org/pypi/yams

* indexer - http://www.logilab.org/project/indexer -
  http://pypi.python.org/pypi/indexer

* passlib - https://code.google.com/p/passlib/ -
  http://pypi.python.org/pypi/passlib

If you're using a Postgresql database (recommended):

* psycopg2 - http://initd.org/projects/psycopg2 - http://pypi.python.org/pypi/psycopg2
* plpythonu extension

Other optional packages:

* fyzz - http://www.logilab.org/project/fyzz -
  http://pypi.python.org/pypi/fyzz *to activate Sparql querying*


Any help with the packaging of CubicWeb for more than Debian/Ubuntu (including
eggs, buildouts, etc) will be greatly appreciated.
