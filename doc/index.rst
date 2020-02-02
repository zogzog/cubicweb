=====================================================
|cubicweb| - The Semantic Web is a construction game!
=====================================================

|cubicweb| is a semantic web application framework, licensed under the LGPL,
that empowers developers to efficiently build web applications by reusing
components (called `cubes`) and following the well known object-oriented design
principles.

Main Features
~~~~~~~~~~~~~

* an engine driven by the explicit :ref:`data model
  <TutosBaseCustomizingTheApplicationDataModel>` of the application,

* a query language named :ref:`RQL <RQL>` similar to W3C's SPARQL,

* a :ref:`selection+view <TutosBaseCustomizingTheApplicationCustomViews>`
  mechanism for semi-automatic XHTML/XML/JSON/text generation,

* a library of reusable :ref:`components <Cube>` (data model and views) that
  fulfill common needs,

* the power and flexibility of the Python_ programming language,

* the reliability of SQL databases, LDAP directories and Mercurial
  for storage backends.

Built since 2000 from an R&D effort still continued, supporting 100,000s of
daily visits at some production sites, |cubicweb| is a proven end to end solution
for semantic web application development that promotes quality, reusability and
efficiency.

QuickStart
~~~~~~~~~~

The impatient developer will move right away to :ref:`SetUpEnv` then to :ref:`ConfigEnv`.

Social
~~~~~~

*   Chat on the `jabber forum`_
*   Discuss on the `mailing-list`_
*   Discover on the `blog`_
*   Contribute on the forge_
*   Find published python modules on `pypi <https://pypi.org/search/?q=cubicweb>`_
*   Find published npm modules on `npm <https://www.npmjs.com/search?q=keywords:cubicweb>`_


.. _Logilab: http://www.logilab.fr/
.. _forge: http://www.cubicweb.org/project/
.. _Python: http://www.python.org/
.. _`jabber forum`: http://www.logilab.org/blogentry/6718
.. _`mailing-list`: http://lists.cubicweb.org/mailman/listinfo/cubicweb
.. _blog: http://www.cubicweb.org/blog/1238


Narrative Documentation
~~~~~~~~~~~~~~~~~~~~~~~

A.k.a. "The Book"

.. toctree::
   :maxdepth: 2

   book/intro/index

.. toctree::
   :maxdepth: 2

   tutorials/index

.. toctree::
   :maxdepth: 3

   book/devrepo/index
   book/devweb/index
   book/pyramid/index

.. toctree::
   :maxdepth: 2

   book/admin/index
   book/additionnal_services/index
   book/annexes/index



Changes
~~~~~~~

.. toctree::
   :maxdepth: 2

   changes/changelog


Reference documentation
~~~~~~~~~~~~~~~~~~~~~~~

API
'''

.. toctree::
    :maxdepth: 1
    :glob:

    api/*

.. toctree::
    :maxdepth: 1
    :glob:

    js_api/*

Developpers
~~~~~~~~~~~

.. toctree::
    :maxdepth: 1
    :glob:

    How to contribute to the code base <https://hg.logilab.org/master/cubicweb/file/tip/README#l56>
    General contribution guide for cubes <https://www.logilab.org/Card/contributing>
    Priorities are discussed over on the development dashboard <https://www.cubicweb.org/card/cw-dev-board>
    dev/*

Indexes
~~~~~~~

* the :ref:`genindex`,
* the :ref:`modindex`,
