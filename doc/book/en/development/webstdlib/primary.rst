The default 'primary' view (:mod:`cubicweb.web.views.primary`)
---------------------------------------------------------------

The primary view of an entity is the view called by default when a single
entity is in the result set and needs to be displayed.

This view is supposed to render a maximum of informations about the entity.

Rendering methods and attributes for ``PrimaryView``
----------------------------------------------------

By default, *CubicWeb* provides a primary view for each new entity type
you create. The first view you might be interested in modifying.

Let's have a quick look at the EntityView ``PrimaryView`` as well as
its rendering method

.. sourcecode:: python

    class PrimaryView(EntityView):
        """the full view of an non final entity"""
        id = 'primary'
        title = _('primary')
        show_attr_label = True
        show_rel_label = True
        skip_none = True
        skip_attrs = ('eid', 'creation_date', 'modification_date')
        skip_rels = ()
        main_related_section = True

        ...

    def cell_call(self, row, col):
        self.row = row
        self.render_entity(self.complete_entity(row, col))

    def render_entity(self, entity):
        """return html to display the given entity"""
        siderelations = []
        self.render_entity_title(entity)
        self.render_entity_metadata(entity)
        # entity's attributes and relations, excluding meta data
        # if the entity isn't meta itself
        self.w(u'<div>')
        self.w(u'<div class="mainInfo">')
        self.render_entity_attributes(entity, siderelations)
        self.w(u'</div>')
        self.content_navigation_components('navcontenttop')
        if self.main_related_section:
            self.render_entity_relations(entity, siderelations)
        self.w(u'</div>')
        # side boxes
        self.w(u'<div class="primaryRight">')
        self.render_side_related(entity, siderelations)
        self.w(u'</div>')
        self.w(u'<div class="clear"></div>')
        self.content_navigation_components('navcontentbottom')

    ...

``cell_call`` is executed for each entity of a result set and apply ``render_entity``.

The methods you want to modify while customizing a ``PrimaryView`` are:

*render_entity_title(self, entity)*
    Renders the entity title based on the assumption that the method
    ``def content_title(self)`` is implemented for the given entity type.

*render_entity_metadata(self, entity)*
    Renders the entity metadata based on the assumption that the method
    ``def summary(self)`` is implemented for the given entity type.

*render_entity_attributes(self, entity, siderelations)*
    Renders all the attribute of an entity with the exception of attribute
    of type `Password` and `Bytes`.

*content_navigation_components(self, context)*
    This method is applicable only for entity type implementing the interface
    `IPrevNext`. This interface is for entities which can be linked to a previous
    and/or next entity. This methods will render the navigation links between
    entities of this type, either at the top or at the bottom of the page
    given the context (navcontent{top|bottom}).

*render_entity_relations(self, entity, siderelations)*
    Renders all the relations of the entity in the main section of the page.

*render_side_related(self, entity, siderelations)*
    Renders all the relations of the entity in a side box. This is equivalent
    to *render_entity_relations* in addition to render the relations
    in a box.

Also, please note that by setting the following attributes in you class,
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
