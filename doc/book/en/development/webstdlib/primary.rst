The default 'primary' view (:mod:`cubicweb.web.views.primary`)
---------------------------------------------------------------

The primary view of an entity is the view called by default when a single
entity is in the result set and needs to be displayed.

This view is supposed to render a maximum of informations about the entity.

Beware when overriding this top level `cell_call` in a primary because
you will loose a bunch of functionnality that automatically comes with
it : `in-context` boxes, related boxes, some navigation, some
displaying of the metadata, etc. It might be interresting to
understand the implementation fo the `cell_call` to override specifics
bits of it.

Rendering methods and attributes for ``PrimaryView``
----------------------------------------------------

By default, *CubicWeb* provides a primary view for every available
entity type. This is the first view you might be interested in
modifying.

Let's have a quick look at the EntityView ``PrimaryView`` as well as
its rendering method

.. sourcecode:: python

    class PrimaryView(EntityView):
        """the full view of an non final entity"""
        __regid__ = 'primary'
        title = _('primary')
        show_attr_label = True
        show_rel_label = True
        skip_none = True
        rsection = uicfg.primaryview_section
        display_ctrl = uicfg.primaryview_display_ctrl
        main_related_section = True

        ...

    def cell_call(self, row, col):
        self.row = row
        self.maxrelated = self._cw.property_value('navigation.related-limit')
        entity = self.complete_entity(row, col)
        self.render_entity(entity)

    def render_entity(self, entity):
        self.render_entity_title(entity)
        self.render_entity_metadata(entity)
        # entity's attributes and relations, excluding meta data
        # if the entity isn't meta itself
        boxes = self._prepare_side_boxes(entity)
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'<table width="100%"><tr><td style="width: 75%">')
        self.render_entity_summary(entity)
        self.w(u'<div class="mainInfo">')
        self.content_navigation_components('navcontenttop')
        self.render_entity_attributes(entity)
        if self.main_related_section:
            self.render_entity_relations(entity)
        self.w(u'</div>')
        # side boxes
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'</td><td>')
            self.w(u'<div class="primaryRight">')
            if hasattr(self, 'render_side_related'):
                warn('render_side_related is deprecated')
                self.render_side_related(entity, [])
            self.render_side_boxes(boxes)
            self.w(u'</div>')
            self.w(u'</td></tr></table>')
        self.content_navigation_components('navcontentbottom')

    ...

``cell_call`` is executed for each entity of a result set.

The methods you want to modify while customizing a ``PrimaryView`` are:

*render_entity_title(self, entity)*
    Renders the entity title based on the assumption that the method
    ``def dc_title(self)`` is implemented for the given entity type.

*render_entity_metadata(self, entity)*
    Renders the entity metadata by calling the 'metadata' view on the
    entity. This generic view is in cubicweb.views.baseviews.

*render_entity_attributes(self, entity)*
    Renders all the attribute of an entity with the exception of
    attribute of type `Password` and `Bytes`. The skip_none class
    attribute controls the display of None valued attributes.

*content_navigation_components(self, context)*
    This method is applicable only for entity type implementing the interface
    `IPrevNext`. This interface is for entities which can be linked to a previous
    and/or next entity. This methods will render the navigation links between
    entities of this type, either at the top or at the bottom of the page
    given the context (navcontent{top|bottom}).

*render_entity_relations(self, entity)*
    Renders all the relations of the entity in the main section of the page.

*render_side_boxes(self, entity, boxes)*
    Renders all the relations of the entity in a side box. This is equivalent
    to *render_entity_relations* in addition to render the relations
    in a box.

Also, please note that by setting the following attributes in your class,
you can already customize some of the rendering:

*show_attr_label*
    Renders the attribute label next to the attribute value if set to True.
    Otherwise, does only display the attribute value.

*show_rel_label*
    Renders the relation label next to the relation value if set to True.
    Otherwise, does only display the relation value.

*skip_none*
    Does not render an attribute value that is None if set to True.

*main_related_section*
    Renders the relations of the entity if set to True.

A good practice is for you to identify the content of your entity type for which
the default rendering does not answer your need so that you can focus on the specific
method (from the list above) that needs to be modified. We do not recommand you to
overwrite ``render_entity`` as you might potentially loose the benefits of the side
boxes handling.

.. XXX talk about uicfg.rdisplay
