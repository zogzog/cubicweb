
.. _foundationsCube:

.. _cubelayout:

Standard structure for a cube
-----------------------------

A cube is structured as follows:

::

  mycube/
  |
  |-- data/
  |   |-- cubes.mycube.css
  |   |-- cubes.mycube.js
  |   `-- external_resources
  |
  |-- debian/
  |   |-- changelog
  |   |-- compat
  |   |-- control
  |   |-- copyright
  |   |-- cubicweb-mycube.prerm
  |   `-- rules
  |
  |-- entities.py
  |
  |-- i18n/
  |   |-- en.po
  |   |-- es.po
  |   `-- fr.po
  |
  |-- __init__.py
  |
  |-- MANIFEST.in
  |
  |-- migration/
  |   |-- postcreate.py
  |   `-- precreate.py
  |
  |-- __pkginfo__.py
  |
  |-- schema.py
  |
  |-- setup.py
  |
  |-- site_cubicweb.py
  |
  |-- hooks.py
  |
  |-- test/
  |   |-- data/
  |   |   `-- bootstrap_cubes
  |   |-- pytestconf.py
  |   |-- realdb_test_mycube.py
  |   `-- test_mycube.py
  |
  `-- views.py


We can use subpackages instead of python modules for ``views.py``, ``entities.py``,
``schema.py`` or ``hooks.py``. For example, we could have:

::

  mycube/
  |
  |-- entities.py
  |-- hooks.py
  `-- views/
      |-- forms.py
      |-- primary.py
      `-- widgets.py


where :

* ``schema`` contains the schema definition (server side only)
* ``entities`` contains the entities definition (server side and web interface)
* ``hooks`` contains hooks and/or views notifications (server side only)
* ``views`` contains the web interface components (web interface only)
* ``test`` contains tests related to the cube (not installed)
* ``i18n`` contains message catalogs for supported languages (server side and
  web interface)
* ``data`` contains data files for static content (images, css, javascripts)
  ...(web interface only)
* ``migration`` contains initialization files for new instances (``postcreate.py``)
  and a file containing dependencies of the component depending on the version
  (``depends.map``)
* ``debian`` contains all the files managing debian packaging (you will find
  the usual files ``control``, ``rules``, ``changelog``... not installed)
* file ``__pkginfo__.py`` provides component meta-data, especially the distribution
  and the current version (server side and web interface) or sub-cubes used by
  the cube.


At least you should have:

* the file ``__pkginfo__.py``
* the schema definition
  XXX false, we may want to have cubes which are only adding a service,
  no persistent data (eg embedding for instance)



The :file:`__init__.py` and :file:`site_cubicweb.py` files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :file:`__pkginfo__.py` file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
XXX contains metadata describing your cubes
    distname / modname
    version / numversion
    __use__
    __recommend__


:file:`migration/precreate.py` and :file:`migration/postcreate.py`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
XXX detail steps of instance creation


External resources such as image, javascript and css files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
XXX naming convention external_resources file


Out-of the box testing
~~~~~~~~~~~~~~~~~~~~~~
XXX MANIFEST.in, __pkginfo__.include_dirs, debian



Packaging and distribution
~~~~~~~~~~~~~~~~~~~~~~~~~~
XXX MANIFEST.in, __pkginfo__.include_dirs, debian

