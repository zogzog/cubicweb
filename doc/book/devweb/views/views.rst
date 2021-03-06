
.. _Views:

Principles
----------

We'll start with a description of the interface providing a basic
understanding of the available classes and methods, then detail the
view selection principle.

A `View` is an object responsible for the rendering of data from the
model into an end-user consummable form. They typically churn out an
XHTML stream, but there are views concerned with email other non-html
outputs.

.. _views_base_class:

Discovering possible views
~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to configure the web user interface to have a left box
showing all the views than can be applied to the current result set.

To enable this, click on your login at the top right corner. Chose
"user preferences", then "boxes", then "possible views box" and check
"visible = yes" before validating your changes.

The views listed there we either not selected because of a lower
score, or they were deliberately excluded by the main template logic.


Basic class for views
~~~~~~~~~~~~~~~~~~~~~

Class :class:`~cubicweb.view.View`
``````````````````````````````````

.. autoclass:: cubicweb.view.View

The basic interface for views is as follows (remember that the result
set has a tabular structure with rows and columns, hence cells):

* `render(**context)`, render the view by calling `call` or
  `cell_call` depending on the context

* `call(**kwargs)`, call the view for a complete result set or null
  (the default implementation calls `cell_call()` on each cell of the
  result set)

* `cell_call(row, col, **kwargs)`, call the view for a given cell of a
  result set (`row` and `col` being integers used to access the cell)

* `url()`, returns the URL enabling us to get the view with the current
  result set

* `wview(__vid, rset, __fallback_vid=None, **kwargs)`, call the view of
  identifier `__vid` on the given result set. It is possible to give a
  fallback view identifier that will be used if the requested view is
  not applicable to the result set.

* `html_headers()`, returns a list of HTML headers to be set by the
  main template

* `page_title()`, returns the title to use in the HTML header `title`

Other basic view classes
````````````````````````
Here are some of the subclasses of :class:`~cubicweb.view.View` defined in :mod:`cubicweb.view`
that are more concrete as they relate to data rendering within the application:

.. autoclass:: cubicweb.view.EntityView
.. autoclass:: cubicweb.view.StartupView
.. autoclass:: cubicweb.view.EntityStartupView
.. autoclass:: cubicweb.view.AnyRsetView

Examples of views class
```````````````````````

- Using `templatable`, `content_type` and HTTP cache configuration

.. sourcecode:: python

    class RSSView(XMLView):
        __regid__ = 'rss'
        title = _('rss')
        templatable = False
        content_type = 'text/xml'
        http_cache_manager = MaxAgeHTTPCacheManager
        cache_max_age = 60*60*2 # stay in http cache for 2 hours by default


- Using a custom selector

.. sourcecode:: python

    class SearchForAssociationView(EntityView):
        """view called by the edition view when the user asks
        to search for something to link to the edited eid
        """
        __regid__ = 'search-associate'
        title = _('search for association')
        __select__ = one_line_rset() & match_search_state('linksearch') & is_instance('Any')


XML views, binaries views...
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For views generating other formats than HTML (an image generated dynamically
for example), and which can not simply be included in the HTML page generated
by the main template (see above), you have to:

* set the attribute `templatable` of the class to `False`
* set, through the attribute `content_type` of the class, the MIME
  type generated by the view to `application/octet-stream` or any
  relevant and more specialised mime type

For views dedicated to binary content creation (like dynamically generated
images), we have to set the attribute `binary` of the class to `True` (which
implies that `templatable == False`, so that the attribute `w` of the view could be
replaced by a binary flow instead of unicode).
