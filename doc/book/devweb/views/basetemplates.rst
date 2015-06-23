.. -*- coding: utf-8 -*-

.. _templates:

Templates
=========

Templates are the entry point for the |cubicweb| view system. As seen
in :ref:`views_base_class`, there are two kinds of views: the
templatable and non-templatable.


Non-templatable views
---------------------

Non-templatable views are standalone. They are responsible for all the details
such as setting a proper content type (or mime type), the proper document
headers, namespaces, etc. Examples are pure xml views such as RSS or Semantic Web
views (`SIOC`_, `DOAP`_, `FOAF`_, `Linked Data`_, etc.), and views which generate
binary files (pdf, excel files, etc.)

.. _`SIOC`: http://sioc-project.org/
.. _`DOAP`: http://trac.usefulinc.com/doap
.. _`FOAF`: http://www.foaf-project.org/
.. _`Linked Data`: http://linkeddata.org/


To notice that a view is not templatable, you just have to set the
view's class attribute `templatable` to `False`. In this case, it
should set the `content_type` class attribute to the correct MIME
type. By default, it is text/xhtml. Additionally, if your view
generate a binary file, you have to set the view's class attribute
`binary` to `True` too.


Templatable views
-----------------

Templatable views are not concerned with such pesky details. They
leave it to the template. Conversely, the template's main job is to:

* set up the proper document header and content type
* define the general layout of a document
* invoke adequate views in the various sections of the document


Look at :mod:`cubicweb.web.views.basetemplates` and you will find the base
templates used to generate (X)HTML for your application. The most important
template there is :class:`~cubicweb.web.views.basetemplates.TheMainTemplate`.

.. _the_main_template_layout:

TheMainTemplate
~~~~~~~~~~~~~~~

.. _the_main_template_sections:

Layout and sections
```````````````````

A page is composed as indicated on the schema below :

.. image:: ../../../images/main_template.png

The sections dispatches specific views:

* `header`: the rendering of the header is delegated to the
  `htmlheader` view, whose default implementation can be found in
  ``basetemplates.py`` and which does the following things:

    * inject the favicon if there is one
    * inject the global style sheets and javascript resources
    * call and display a link to an rss component if there is one available

  it also sets up the page title, and fills the actual
  `header` section with top-level components, using the `header` view, which:

    * tries to display a logo, the name of the application and the `breadcrumbs`
    * provides a login status area
    * provides a login box (hiden by default)

* `left column`: this is filled with all selectable boxes matching the
  `left` context (there is also a right column but nowadays it is
  seldom used due to bad usability)

* `contentcol`: this is the central column; it is filled with:

    * the `rqlinput` view (hidden by default)
    * the `applmessages` component
    * the `contentheader` view which in turns dispatches all available
      content navigation components having the `navtop` context (this
      is used to navigate through entities implementing the IPrevNext
      interface)
    * the view that was given as input to the template's `call`
      method, also dealing with pagination concerns
    * the `contentfooter`

* `footer`: adds all footer actions

.. note::

  How and why a view object is given to the main template is explained
  in the :ref:`publisher` chapter.

Configure the main template
```````````````````````````

You can overload some methods of the
:class:`~cubicweb.web.views.basetemplates.TheMainTemplate`, in order to fulfil
your needs. There are also some attributes and methods which can be defined on a
view to modify the base template behaviour:

* `paginable`: if the result set is bigger than a configurable size, your result
  page will be paginated by default. You can set this attribute to `False` to
  avoid this.

* `binary`: boolean flag telling if the view generates some text or a binary
  stream.  Default to False. When view generates text argument given to `self.w`
  **must be a unicode string**, encoded string otherwise.

* `content_type`, view's content type, default to 'text/xhtml'

* `templatable`, boolean flag telling if the view's content should be returned
  directly (when `False`) or included in the main template layout (including
  header, boxes and so on).

* `page_title()`, method that should return a title that will be set as page
  title in the html headers.

* `html_headers()`, method that should return a list of HTML headers to be
  included the html headers.


You can also modify certain aspects of the main template of a page
when building a url or setting these parameters in the req.form:

* `__notemplate`, if present (whatever the value assigned), only the content view
  is returned

* `__force_display`, if present and its value is not null, no pagination whatever
  the number of entities to display (e.g. similar effect as view's `paginable`
  attribute described above.

* `__method`, if the result set to render contains only one entity and this
  parameter is set, it refers to a method to call on the entity by passing it the
  dictionary of the forms parameters, before going the classic way (through step
  1 and 2 described juste above)

* `vtitle`, a title to be set as <h1> of the content

Other templates
~~~~~~~~~~~~~~~

There are also the following other standard templates:

* :class:`cubicweb.web.views.basetemplates.LogInTemplate`
* :class:`cubicweb.web.views.basetemplates.LogOutTemplate`
* :class:`cubicweb.web.views.basetemplates.ErrorTemplate` specializes
  :class:`~cubicweb.web.views.basetemplates.TheMainTemplate` to do
  proper end-user output if an error occurs during the computation of
  TheMainTemplate (it is a fallback view).
