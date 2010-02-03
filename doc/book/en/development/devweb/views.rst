
.. _Views:

Views
-----

This chapter aims to describe the concept of a `view` used all along
the development of a web application and how it has been implemented
in *CubicWeb*.

We'll start with a description of the interface providing you with a basic
understanding of the classes and methods available, then detail the view
selection principle which makes *CubicWeb* web interface very flexible.

A `View` is an object applied to another object such as an entity.

Basic class for views
~~~~~~~~~~~~~~~~~~~~~

Class `View` (`cubicweb.view`)
`````````````````````````````````````

This class is an abstraction of a view class, used as a base class for every
renderable object such as views, templates, graphic components, etc.

A `View` is instantiated to render a result set or part of a result set. `View`
subclasses may be parametrized using the following class attributes:

    * `templatable` indicates if the view may be embeded in a main
      template or if it has to be rendered standalone (i.e. XML views
      must not be embeded in the main template for HTML pages)
    * if the view is not templatable, it should set the `content_type` class
      attribute to the correct MIME type (text/xhtml by default)
    * the `category` attribute may be used in the interface to regroup related
      objects together

At instantiation time, the standard `_cw` and `cw_rset` attributes are
added and the `w` attribute will be set at rendering time.

A view writes to its output stream thanks to its attribute `w` (an
`UStreamIO`, except for binary views).

The basic interface for views is as follows (remember that the result set has a
tabular structure with rows and columns, hence cells):

* `render(**context)`, render the view by calling `call` or
  `cell_call` depending on the given parameters

* `call(**kwargs)`, call the view for a complete result set or null
  (the default implementation calls `cell_call()` on each cell of the
  result set)

* `cell_call(row, col, **kwargs)`, call the view for a given cell of a
  result set

* `url()`, returns the URL enabling us to get the view with the current
  result set

* `view(__vid, rset, __fallback_vid=None, **kwargs)`, call the view of identifier
  `__vid` on the given result set. It is possible to give a view identifier
  of fallback that will be used if the view requested is not applicable to the
  result set. This is actually defined on the AppObject class.

* `wview(__vid, rset, __fallback_vid=None, **kwargs)`, similar to `view` except
  the flow is automatically passed in the parameters

* `html_headers()`, returns a list of HTML headers to set by the main template

* `page_title()`, returns the title to use in the HTML header `title`


Other basic view classes
````````````````````````
Here are some of the subclasses of `View` defined in `cubicweb.common.view`
that are more concrete as they relate to data rendering within the application:

* `EntityView`, view applying to lines or cell containing an entity (e.g. an eid)
* `StartupView`, start view that does not._cwuire a result set to apply to
* `AnyRsetView`, view applicable to any result set
* `EmptyRsetView`, view applicable to an empty result set


Examples of views class
-----------------------

- Using `templatable`, `content_type` and HTTP cache configuration

.. sourcecode:: python

    class RSSView(XMLView):
        id = 'rss'
        title = _('rss')
        templatable = False
        content_type = 'text/xml'
        http_cache_manager = MaxAgeHTTPCacheManager
        cache_max_age = 60*60*2 # stay in http cache for 2 hours by default


- Using custom selector

.. sourcecode:: python

    class SearchForAssociationView(EntityView):
        """view called by the edition view when the user asks
        to search for something to link to the edited eid
        """
        id = 'search-associate'
        title = _('search for association')
        __select__ = one_line_rset() & match_search_state('linksearch') & implements('Any')


Example of view customization and creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We'll show you now an example of a ``primary`` view and how to customize it.

If you want to change the way a ``BlogEntry`` is displayed, just override
the method ``cell_call()`` of the view ``primary`` in ``BlogDemo/views.py``:

.. sourcecode:: python

  from cubicweb.selectors import implements
  from cubicweb.web.views.primary improt Primaryview

  class BlogEntryPrimaryView(PrimaryView):
    __select__ = PrimaryView.__select__ & implements('BlogEntry')

      def render_entity_attributes(self, entity):
          self.w(u'<p>published on %s</p>' %
                 entity.publish_date.strftime('%Y-%m-%d'))
          super(BlogEntryPrimaryView, self).render_entity_attributes(entity)

The above source code defines a new primary view for
``BlogEntry``. The `id` class attribute is not repeated there since it
is inherited through the `primary.PrimaryView` class.

The selector for this view chains the selector of the inherited class
with its own specific criterion.

The view method ``self.w()`` is used to output data. Here `lines
08-09` output HTML for the publication date of the entry.

.. image:: ../../images/lax-book.09-new-view-blogentry.en.png
   :alt: blog entries now look much nicer

Let us now improve the primary view of a blog

.. sourcecode:: python

 from logilab.mtconverter import xml_escape
 from cubicweb.selectors import implements, one_line_rset
 from cubicweb.web.views.primary import Primaryview

 class BlogPrimaryView(PrimaryView):
     id = 'primary'
     __select__ = PrimaryView.__select__ & implements('Blog')
     rql = 'Any BE ORDERBY D DESC WHERE BE entry_of B, BE publish_date D, B eid %(b)s'

     def render_entity_relations(self, entity):
         rset = self._cw.execute(self.rql, {'b' : entity.eid})
         for entry in rset.entities():
             self.w(u'<p>%s</p>' % entry.view('inblogcontext'))

 class BlogEntryInBlogView(EntityView):
     id = 'inblogcontext'
     __select__ = implements('BlogEntry')

     def cell_call(self, row, col):
         entity = self.cw_rset.get_entity(row, col)
         self.w(u'<a href="%s" title="%s">%s</a>' %
                entity.absolute_url(),
                xml_escape(entity.content[:50]),
                xml_escape(entity.description))

This happens in two places. First we override the
render_entity_relations method of a Blog's primary view. Here we want
to display our blog entries in a custom way.

At `line 10`, a simple request is made to build a result set with all
the entities linked to the current ``Blog`` entity by the relationship
``entry_of``. The part of the framework handling the request knows
about the schema and infers that such entities have to be of the
``BlogEntry`` kind and retrieves them (in the prescribed publish_date
order).

The request returns a selection of data called a result set. Result
set objects have an .entities() method returning a generator on
requested entities (going transparently through the `ORM` layer).

At `line 13` the view 'inblogcontext' is applied to each blog entry to
output HTML. (Note that the 'inblogcontext' view is not defined
whatsoever in *CubicWeb*. You are absolutely free to define whole view
families.) We juste arrange to wrap each blogentry output in a 'p'
html element.

Next, we define the 'inblogcontext' view. This is NOT a primary view,
with its well-defined sections (title, metadata, attribtues,
relations/boxes). All a basic view has to define is cell_call.

Since views are applied to result sets which can be tables of data, we
have to recover the entity from its (row,col)-coordinates (`line
20`). Then we can spit some HTML.

But careful: all strings manipulated in *CubicWeb* are actually
unicode strings. While web browsers are usually tolerant to incoherent
encodings they are being served, we should not abuse it. Hence we have
to properly escape our data. The xml_escape() function has to be used
to safely fill (X)HTML elements from Python unicode strings.


**This is to be compared to interfaces and protocols in object-oriented
languages. Applying a given view called 'a_view' to all the entities
of a result set only._cwuires to have for each entity of this result set,
an available view called 'a_view' which accepts the entity.

Instead of merely using type based dispatch, we do predicate dispatch
which quite more powerful**

Assuming we added entries to the blog titled `MyLife`, displaying it
now allows to read its description and all its entries.

.. image:: ../../images/lax-book.10-blog-with-two-entries.en.png
   :alt: a blog and all its entries

**Before we move forward, remember that the selection/view principle is
at the core of *CubicWeb*. Everywhere in the engine, data is requested
using the RQL language, then HTML/XML/text/PNG is output by applying a
view to the result set returned by the query. That is where most of the
flexibility comes from.**

[WRITE ME]

* implementing interfaces, calendar for blog entries
* show that a calendar view can export data to ical

We will implement the `cubicweb.interfaces.ICalendarable` interfaces on
entities.BlogEntry and apply the OneMonthCalendar and iCalendar views
to result sets like "Any E WHERE E is BlogEntry"

* create view "blogentry table" with title, publish_date, category

We will show that by default the view that displays
"Any E,D,C WHERE E publish_date D, E category C" is the table view.
Of course, the same can be obtained by calling
self.wview('table',rset)

* in view blog, select blogentries and apply view "blogentry table"
* demo ajax by filtering blogentry table on category

we did the same with 'primary', but with tables we can turn on filters
and show that ajax comes for free.
[FILLME]


XML views, binaries views...
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For views generating other formats than HTML (an image generated dynamically
for example), and which can not simply be included in the HTML page generated
by the main template (see above), you have to:

* set the attribute `templatable` of the class to `False`
* set, through the attribute `content_type` of the class, the MIME type generated
  by the view to `application/octet-stream`

For views dedicated to binary content creation (like dynamically generated
images), we have to set the attribute `binary` of the class to `True` (which
implies that `templatable == False`, so that the attribute `w` of the view could be
replaced by a binary flow instead of unicode).
