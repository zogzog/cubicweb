.. -*- coding: utf-8 -*-

URL publishing
--------------

(:mod:`cubicweb.web.views.urlpublishing`)

.. automodule:: cubicweb.web.views.urlpublishing

.. autoclass:: cubicweb.web.views.urlpublishing.URLPublisherComponent
   :members:


You can write your own *URLPathEvaluator* class to handle custom paths.
For instance, if you want */my-card-id* to redirect to the corresponding
card's primary view, you would write:

.. sourcecode:: python

    class CardWikiidEvaluator(URLPathEvaluator):
        priority = 3 # make it be evaluated *before* RestPathEvaluator

        def evaluate_path(self, req, segments):
            if len(segments) != 1:
                raise PathDontMatch()
            rset = req.execute('Any C WHERE C wikiid %(w)s',
                               {'w': segments[0]})
            if len(rset) == 0:
                # Raise NotFound if no card is found
                raise PathDontMatch()
            return None, rset

On the other hand, you can also deactivate some of the standard
evaluators in your final application. The only thing you have to
do is to unregister them, for instance in a *registration_callback*
in your cube:

.. sourcecode:: python

    def registration_callback(vreg):
        vreg.unregister(RestPathEvaluator)

You can even replace the :class:`cubicweb.web.views.urlpublishing.URLPublisherComponent`
class if you want to customize the whole toolchain process or if you want
to plug into an early enough extension point to control your request
parameters:

.. sourcecode:: python

    class SanitizerPublisherComponent(URLPublisherComponent):
        """override default publisher component to explicitly ignore
        unauthorized request parameters in anonymous mode.
        """
        unauthorized_form_params = ('rql', 'vid', '__login', '__password')

        def process(self, req, path):
            if req.session.anonymous_session:
                self._remove_unauthorized_params(req)
            return super(SanitizerPublisherComponent, self).process(req, path)

        def _remove_unauthorized_params(self, req):
            for param in req.form.keys():
                if param in self.unauthorized_form_params:
                     req.form.pop(param)


    def registration_callback(vreg):
        vreg.register_and_replace(SanitizerPublisherComponent, URLPublisherComponent)


.. autoclass:: cubicweb.web.views.urlpublishing.RawPathEvaluator
.. autoclass:: cubicweb.web.views.urlpublishing.EidPathEvaluator
.. autoclass:: cubicweb.web.views.urlpublishing.URLRewriteEvaluator
.. autoclass:: cubicweb.web.views.urlpublishing.RestPathEvaluator
.. autoclass:: cubicweb.web.views.urlpublishing.ActionPathEvaluator

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
                       % {'user': r'\1'}), vid='rss'))
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
