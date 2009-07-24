.. -*- coding: utf-8 -*-

Base views (:mod:`cubicweb.web.views.baseviews`)
------------------------------------------------

*CubicWeb* provides a lot of standard views. You can find them in
``cubicweb/web/views/``.

A certain number of views are used to build the web interface, which apply
to one or more entities. Their identifier is what distinguish them from
each others and the main ones are:

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

*null*
    This view is the default view used when nothing needs to be rendered.
    It is always applicable and it does not return anything

Entity views
````````````
*incontext, outofcontext*
    Those are used to display a link to an entity, depending if the entity is
    considered as displayed in or out of context (of another entity).  By default
    it respectively returns the result of `textincontext` and `textoutofcontext`
    wrapped in a link leading to the primary view of the entity.

*oneline*
    This view is used when we can't tell if the entity should be considered as
    displayed in or out of context.  By default it returns the result of `text`
    in a link leading to the primary view of the entity.

List
`````
*list*
    This view displays a list of entities by creating a HTML list (`<ul>`)
    and call the view `listitem` for each entity of the result set.

*listitem*
    This view redirects by default to the `outofcontext` view.

*adaptedlist*
    This view displays a list of entities of the same type, in HTML section (`<div>`)
    and call the view `adaptedlistitem` for each entity of the result set.

*adaptedlistitem*
    This view redirects by default to the `outofcontext` view.

Text entity views
~~~~~~~~~~~~~~~~~
*text*
    This is the simplest text view for an entity. By default it returns the
    result of the `.dc_title` method, which is cut to fit the
    `navigation.short-line-size` property if necessary.

*textincontext, textoutofcontext*
    Similar to the `text` view, but called when an entity is considered out or
    in context. By default it returns respectively the result of the
    methods `.dc_title` and `.dc_long_title` of the entity.
