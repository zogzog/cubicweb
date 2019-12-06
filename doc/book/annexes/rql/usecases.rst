.. _rql_usecases:

RQL usecases
------------

Search bar
~~~~~~~~~~

The search bar is available on a CubicWeb instance to use RQL and it's use and
configuration is described in `:doc:_searchbar`

Use of RQL in Card documents - ReST
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With a CubicWeb instance supporting object types with ReST content (for example
`Card <https://www.cubicweb.org/project/cubicweb-card>`_), one can build content
based on RQL queries as dynamic documents.

For this, use the `rql` and `rql-table` ReST directive, for more information
about custom ReST directives `head over to the sphinx documentation
<https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html>`_
which uses them extensivelly.

rql directive
~~~~~~~~~~~~~

The `rql` directive takes as input an RQL expression and a view to apply to the
result.

For example, create a Card content by opening
http://cubicweb_example.org/add/Card and add the following content, as an
example : a table of blog entries (10 most recent blog entries table with user
and date information) ::

   Recent blog entries
   -------------------

   :rql:`Any B,U,D ORDERBY D DESC LIMIT 10 WHERE B is BlogEntry, B title T, B creation_date D, B created_by U:table`

.. image:: ../../images/example-card-with-rql-directive.png

rql-table directive
~~~~~~~~~~~~~~~~~~~

`rql-table` enables more customization, enabling you to modify the column
(`header`) contents, and the view applied for a specific column (`colvids`).

For example, create a Card content by openning http://cubicweb_example.org/add/Card and add the following content ::

        Blog entries with rql-table
        -----------------------------

        .. rql-table::
           :vid: table
           :headers: Title with link, who wrote it, at what date
           :colvids: 1=sameetypelist

           Any B,U,D ORDERBY D DESC LIMIT 10 WHERE B is BlogEntry, B title T, B creation_date D, B created_by U

All fields but the RQL string are optionnal. The ``:headers:`` option can
contain empty column names.

.. image:: ../../images/example-card-with-rql-table-directive.png

Use in python projects and CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`cwclientlib <https://pypi.org/project/cwclientlib/>` enables you to use RQL
in your python projects using only web requests. This project also provides a
remote command line interface (CLI) you can use to replace a server side
`cubicweb-ctl shell`.

Use in JavaScript/React components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`cwclientelements <https://forge.extranet.logilab.fr/open-source/cwclientelements>`
is a library of reusable React components for building web application with
cubicweb and RQL.
