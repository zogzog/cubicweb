.. -*- coding: utf-8 -*-

Base views (:mod:`cubicweb.web.views.baseviews`)
------------------------------------------------

`CubicWeb` provides a lot of standard views. You can find them in
``cubicweb/web/views/``.

A certain number of views are used to build the web interface, which apply
to one or more entities. Their identifier is what distinguish them from
each others and the main ones are:

HTML views
~~~~~~~~~~
*oneline*
    This is a hyper linked *text* view. Similar to the `secondary` view,
    but called when we want the view to stand on a single line, or just
    get a brief view. By default this view uses the
    parameter `MAX_LINE_CHAR` to control the result size.

*secondary*
    This is a combinaison of an icon and a *oneline* view.
    By default it renders the two first attributes of the entity as a
    clickable link redirecting to the primary view.

*incontext, outofcontext*
    Similar to the `secondary` view, but called when an entity is considered
    as in or out of context. By default it respectively returns the result of
    `textincontext` and `textoutofcontext` wrapped in a link leading to
    the primary view of the entity.

List
`````
*list*
    This view displays a list of entities by creating a HTML list (`<ul>`)
    and call the view `listitem` for each entity of the result set.

*listitem*
    This view redirects by default to the `outofcontext` view.


Special views
`````````````

*noresult*
    This view is the default view used when no result has been found
    (e.g. empty result set).

*final*
    Display the value of a cell without trasnformation (in case of a non final
    entity, we see the eid). Applicable on any result set.

*null*
    This view is the default view used when nothing needs to be rendered.
    It is always applicable and it does not return anything

Text views
~~~~~~~~~~
*text*
    This is the simplest text view for an entity. It displays the
    title of an entity. It should not contain HTML.

*textincontext, textoutofcontext*
    Similar to the `text` view, but called when an entity is considered out or
    in context. By default it returns respectively the result of the
    methods `.dc_title` and `.dc_long_title` of the entity.
