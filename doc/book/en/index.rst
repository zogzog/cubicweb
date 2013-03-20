.. -*- coding: utf-8 -*-

.. _contents:

=====================================================
|cubicweb| - The Semantic Web is a construction game!
=====================================================

|cubicweb| is a semantic web application framework, licensed under the LGPL,
that empowers developers to efficiently build web applications by reusing
components (called `cubes`) and following the well known object-oriented design
principles.

Its main features are:

* an engine driven by the explicit :ref:`data model
  <TutosBaseCustomizingTheApplicationDataModel>` of the application,

* a query language named :ref:`RQL <RQL>` similar to W3C's SPARQL,

* a :ref:`selection+view <TutosBaseCustomizingTheApplicationCustomViews>`
  mechanism for semi-automatic XHTML/XML/JSON/text generation,

* a library of reusable :ref:`components <Cube>` (data model and views) that
  fulfill common needs,

* the power and flexibility of the Python_ programming language,

* the reliability of SQL databases, LDAP directories, Subversion and Mercurial
  for storage backends.

Built since 2000 from an R&D effort still continued, supporting 100,000s of
daily visits at some production sites, |cubicweb| is a proven end to end solution
for semantic web application development that promotes quality, reusability and
efficiency.

The unbeliever will read the :ref:`Tutorials`.

The hacker will join development at the forge_.

The impatient developer will move right away to :ref:`SetUpEnv` then to :ref:`ConfigEnv`.

The chatter lover will join the `jabber forum`_, the `mailing-list`_ and the blog_.

.. _Logilab: http://www.logilab.fr/
.. _forge: http://www.cubicweb.org/project/
.. _Python: http://www.python.org/
.. _`jabber forum`: http://www.logilab.org/blogentry/6718
.. _`mailing-list`: http://lists.cubicweb.org/mailman/listinfo/cubicweb
.. _blog: http://www.cubicweb.org/blog/1238

.. toctree::
   :maxdepth: 2

   intro/index
   tutorials/index

.. toctree::
   :maxdepth: 3

   devrepo/index
   devweb/index

.. toctree::
   :maxdepth: 2

   admin/index
   additionnal_services/index
   annexes/index

See also:

* the :ref:`genindex`,
* the :ref:`modindex`,
