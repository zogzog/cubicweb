.. -*- coding: utf-8 -*-

URL publishing
--------------

(:mod:`cubicweb.web.views.urlpublishing`)

.. automodule:: cubicweb.web.views.urlpublishing

.. autoclass:: cubicweb.web.views.urlpublishing.URLPublisherComponent
   :members:

URL rewriting
-------------

(:mod:`cubicweb.web.views.urlrewrite`)

.. autoclass:: cubicweb.web.views.urlrewrite.URLRewriter
   :members:

.. autoclass:: cubicweb.web.views.urlrewrite.SimpleReqRewriter
   :members:

.. autoclass:: cubicweb.web.views.urlrewrite.SchemaBasedRewriter
   :members:


``SimpleReqRewriter`` is enough for a certain number of simple cases. If it is not sufficient, ``SchemaBasedRewriter`` allows to do more elaborate things.

Here is an example of ``SimpleReqRewriter`` usage with plain string:

.. sourcecode:: python

   from cubicweb.web.views.urlrewrite import SimpleReqRewriter
   class TrackerSimpleReqRewriter(SimpleReqRewriter):
       rules = [
        ('/versions', dict(vid='versionsinfo')),
        ]

When the url is `<base_url>/versions`, the view with the __regid__ `versionsinfo` is displayed.

Here is an example of ``SimpleReqRewriter`` usage with regular expressions:

.. sourcecode:: python

    from cubicweb.web.views.urlrewrite import (
        SimpleReqRewriter, rgx)

    class BlogReqRewriter(SimpleReqRewriter):
        rules = [
            (rgx('/blogentry/([a-z_]+)\.rss'),
             dict(rql=('Any X ORDERBY CD DESC LIMIT 20 WHERE X is BlogEntry,'
                       'X creation_date CD, X created_by U, '
                       'U login "%(user)s"'
                       % {'user': r'\1'}, vid='rss'))),
            ]

When a url matches the regular expression, the view with the __regid__
`rss` which match the result set is displayed.

Here is an example of ``SchemaBasedRewriter`` usage:

.. sourcecode:: python

    from cubicweb.web.views.urlrewrite import (
        SchemaBasedRewriter, rgx, build_rset)

    class TrackerURLRewriter(SchemaBasedRewriter):
        rules = [
            (rgx('/project/([^/]+)/([^/]+)/tests'),
             build_rset(rql='Version X WHERE X version_of P, P name %(project)s, X num %(num)s',
                        rgxgroups=[('project', 1), ('num', 2)], vid='versiontests')),
            ]
