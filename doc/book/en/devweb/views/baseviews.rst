.. -*- coding: utf-8 -*-

Base views
----------

*CubicWeb* provides a lot of standard views, that can be found in
:mod:`cubicweb.web.views` sub-modules.

A certain number of views are used to build the web interface, which apply to one
or more entities. As other appobject, Their identifier is what distinguish them
from each others. The most generic ones, found in
:mod:`cubicweb.web.views.baseviews`, are described below.

HTML views
~~~~~~~~~~

Special views
`````````````

*noresult*
    This view is the default view used when no result has been found
    (e.g. empty result set).

*final*
    Display the value of a cell without trasnformation (in case of a non final
    entity, we see the eid). Applicable on any result set.

.. note::

   `final` entities are merely attributes.

*null*
    This view is the default view used when nothing needs to be rendered.
    It is always applicable.


Entity views
````````````

*incontext, outofcontext*

    Those are used to display a link to an entity, whose label depends on the
    entity having to be displayed in or out of context (of another entity): some
    entities make sense in the context of another entity. For instance, the
    `Version` of a `Project` in forge. So one may expect that 'incontext' will
    be called when display a version from within the context of a project, while
    'outofcontext"' will be called in other cases. In our example, the
    'incontext' view of the version would be something like '0.1.2', while the
    'outofcontext' view would include the project name, e.g. 'baz 0.1.2' (since
    only a version number without the associated project doesn't make sense if
    you don't know yet that you're talking about the famous 'baz' project. |cubicweb|
    tries to make guess and call 'incontext'/'outofcontext' nicely. When it can't
    know, the 'oneline' view should be used.

    By default it respectively produces the result of `textincontext` and
    `textoutofcontext` wrapped in a link leading to the primary view of the
    entity.


*oneline*

    This view is used when we can't tell if the entity should be considered as
    displayed in or out of context. By default it produces the result of `text`
    in a link leading to the primary view of the entity.


List
`````

*list*

    This view displays a list of entities by creating a HTML list (`<ul>`) and
    call the view `listitem` for each entity of the result set. The 'list' view
    will generate html like:

    .. sourcecode:: html

      <ul class="section">
        <li>"result of 'subvid' view for a row</li>
        ...
      </ul>


*simplelist*

  This view is not 'ul' based, and rely on div behaviour to separate items. html
  will look like

    .. sourcecode:: html

      <div class="section">"result of 'subvid' view for a row</div>
      ...


  It relies on base :class:`~cubicweb.view.View` class implementation of the
  :meth:`call` method to insert those <div>.


*sameetypelist*

    This view displays a list of entities of the same type, in HTML section
    (`<div>`) and call the view `sameetypelistitem` for each entity of the result
    set. It's designed to get a more adapted global list when displayed entities
    are all of the same type.


*csv*

    This view displays each entity in a coma separated list. It is NOT related to
    the well-known text file format.


Those list view can be given a 'subvid' arguments, telling the view to use of
each item in the list. When not specified, the value of the 'redirect_vid'
attribute of :class:`ListItemView` (for 'listview') or of :class:`SimpleListView`
will be used. This default to 'outofcontext' for 'list' / 'incontext' for
'simplelist'


Text entity views
~~~~~~~~~~~~~~~~~

Basic html view have some variantsto be used when generating raw text, not html
(for notifications for instance).

*text*

    This is the simplest text view for an entity. By default it returns the
    result of the `.dc_title` method, which is cut to fit the
    `navigation.short-line-size` property if necessary.

*textincontext, textoutofcontext*

    Similar to the `text` view, but called when an entity is considered out or in
    context (see description of incontext/outofcontext html views for more
    information on this). By default it returns respectively the result of the
    methods `.dc_title()` and `.dc_long_title()` of the entity.
