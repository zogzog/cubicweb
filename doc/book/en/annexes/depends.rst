.. -*- coding: utf-8 -*-

.. _dependencies:

Dependencies
============

When you run CubicWeb from source, either by downloading the tarball or
cloning the mercurial forest, here is the list of tools and libraries you need
to have installed in order for CubicWeb to work:

* yapps - http://theory.stanford.edu/~amitp/yapps/ -
  http://pypi.python.org/pypi/Yapps2

* pygraphviz - http://networkx.lanl.gov/pygraphviz/ -
  http://pypi.python.org/pypi/pygraphviz

* simplejson - http://code.google.com/p/simplejson/ -
  http://pypi.python.org/pypi/simplejson

* docsutils - http://docutils.sourceforge.net/ - http://pypi.python.org/pypi/docutils

* lxml - http://codespeak.net/lxml - http://pypi.python.org/pypi/lxml

* twisted - http://twistedmatrix.com/ - http://pypi.python.org/pypi/Twisted

* logilab-common - http://www.logilab.org/project/logilab-common -
  http://pypi.python.org/pypi/logilab-common/ - included in the forest

* logilab-constraint - http://www.logilab.org/project/logilab-constraint -
  http://pypi.python.org/pypi/constraint/ - included in the forest

* logilab-mtconverter - http://www.logilab.org/project/logilab-mtconverter -
  http://pypi.python.org/pypi/logilab-mtconverter - included in the forest

* rql - http://www.logilab.org/project/rql - http://pypi.python.org/pypi/rql -
  included in the forest

* yams - http://www.logilab.org/project/yams - http://pypi.python.org/pypi/yams
  - included in the forest

* indexer - http://www.logilab.org/project/indexer -
  http://pypi.python.org/pypi/indexer - included in the forest

To activate Sparql querying:

* fyzz - http://www.logilab.org/project/fyzz - http://pypi.python.org/pypi/fyzz
  - included in the forest

To use network communication between cubicweb instances / clients:

* Pyro - http://pyro.sourceforge.net/ - http://pypi.python.org/pypi/Pyro

If you're using a Postgres database (recommended):
* psycopg2 - http://initd.org/projects/psycopg2 - http://pypi.python.org/pypi/psycopg2

For the google-appengine extension to be available, you also need:

* dateutil - http://labix.org/python-dateutil -
  http://pypi.python.org/pypi/python-dateutil/

* vobject - http://vobject.skyhouseconsulting.com/ -
  http://pypi.python.org/pypi/vobject

  
Any help with the packaging of CubicWeb for more than Debian/Ubuntu (including
eggs, buildouts, etc) will be greatly appreciated.
