"""The default primary view

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

from warnings import warn

from cubicweb import Unauthorized
from cubicweb.view import EntityView

_ = unicode

PRIMARY_SKIP_RELS = set(['is', 'is_instance_of', 'identity',
                         'owned_by', 'created_by',
                         'in_state', 'wf_info_for', 'require_permission',
                         'from_entity', 'to_entity',
                         'see_also'])

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

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default primary views are indexed
        """
        return []

    def cell_call(self, row, col):
        self.row = row
        # XXX move render_entity implementation here
        self.render_entity(self.complete_entity(row, col))

    def render_entity(self, entity):
        """return html to display the given entity"""
        self.render_entity_title(entity)
        self.render_entity_metadata(entity)
        # entity's attributes and relations, excluding meta data
        # if the entity isn't meta itself
        boxes = self._preinit_side_related(entity)
        if boxes:
            self.w(u'<table width="100%"><tr><td width="75%">')
        self.w(u'<div>')
        self.w(u'<div class="mainInfo">')
        try:
            self.render_entity_attributes(entity)
        except TypeError: # XXX bw compat
            warn('siderelations argument of render_entity_attributes is '
                 'deprecated')
            self.render_entity_attributes(entity, [])
        self.w(u'</div>')
        self.content_navigation_components('navcontenttop')
        if self.main_related_section:
            try:
                self.render_entity_relations(entity)
            except TypeError: # XXX bw compat
                warn('siderelations argument of render_entity_relations is '
                     'deprecated')
                self.render_entity_relations(entity, [])
        self.w(u'</div>')
        if boxes:
            self.w(u'</td><td>')
            # side boxes
            self.w(u'<div class="primaryRight">')
            try:
                self.render_side_related(entity)
            except TypeError: # XXX bw compat
                warn('siderelations argument of render_entity_relations is '
                     'deprecated')
                self.render_entity_relations(entity, [])
            self.w(u'</div>')
            self.w(u'</td></tr></table>')
        self.content_navigation_components('navcontentbottom')


    def content_navigation_components(self, context):
        self.w(u'<div class="%s">' % context)
        for comp in self.vreg.possible_vobjects('contentnavigation',
                                                self.req, self.rset, row=self.row,
                                                view=self, context=context):
            try:
                comp.dispatch(w=self.w, row=self.row, view=self)
            except NotImplementedError:
                warn('component %s doesnt implement cell_call, please update'
                     % comp.__class__, DeprecationWarning)
                comp.dispatch(w=self.w, view=self)
        self.w(u'</div>')

    def iter_attributes(self, entity):
        for rschema, targetschema in entity.e_schema.attribute_definitions():
            if rschema.type in self.skip_attrs:
                continue
            yield rschema, targetschema

    def iter_relations(self, entity):
        skip = set(self.skip_rels)
        skip.update(PRIMARY_SKIP_RELS)
        for rschema, targetschemas, x in entity.e_schema.relation_definitions():
            if rschema.type in skip:
                continue
            yield rschema, targetschemas, x

    def render_entity_title(self, entity):
        title = self.content_title(entity) # deprecate content_title?
        if title:
            self.w(u'<h1><span class="etype">%s</span> %s</h1>'
                   % (entity.dc_type().capitalize(), title))

    def content_title(self, entity):
        """default implementation return an empty string"""
        return u''

    def render_entity_metadata(self, entity):
        entity.view('metadata', w=self.w)
        summary = self.summary(entity) # deprecate summary?
        if summary:
            self.w(u'<div class="summary">%s</div>' % summary)

    def summary(self, entity):
        """default implementation return an empty string"""
        return u''

    def render_entity_attributes(self, entity, siderelations=None):
        for rschema, targetschema in self.iter_attributes(entity):
            attr = rschema.type
            if targetschema.type in ('Password', 'Bytes'):
                continue
            try:
                wdg = entity.get_widget(attr)
            except Exception, ex:
                value = entity.printable_value(attr, entity[attr], targetschema.type)
            else:
                value = wdg.render(entity)
            if self.skip_none and (value is None or value == ''):
                continue
            if rschema.meta:
                continue
            self._render_related_entities(entity, rschema, value)

    def _preinit_side_related(self, entity):
        self._sideboxes = []
        if hasattr(self, 'get_side_boxes_defs'):
            self._sideboxes = [(label, rset, 'sidebox') for label, rset in self.get_side_boxes_defs(entity)
                               if rset]
        else:
            eschema = entity.e_schema
            maxrelated = self.req.property_value('navigation.related-limit')
            for rschema, targetschemas, role in self.iter_relations(entity):
                if self.is_side_related(rschema, eschema):
                    try:
                        related = entity.related(rschema.type, role, limit=maxrelated+1)
                    except Unauthorized:
                        continue
                    if not related:
                        continue
                    label = display_name(self.req, rschema.type, role)
                    self._sideboxes.append((label, related, 'autolimited'))
        self._contextboxes = list(self.vreg.possible_vobjects('boxes', self.req, self.rset,
                                                                  row=self.row, view=self,
                                                                  context='incontext'))
        return self._sideboxes or self._contextboxes

    def render_entity_relations(self, entity, siderelations=None):
        eschema = entity.e_schema
        for rschema, targetschemas, x in self.iter_relations(entity):
            if not self.is_side_related(rschema, eschema):
                try:
                    related = entity.related(rschema.type, x, limit=maxrelated+1)
                except Unauthorized:
                    continue
                self._render_related_entities(entity, rschema, related, x)


    def render_side_related(self, entity, siderelations=None):
        """display side related relations:
        non-meta in a first step, meta in a second step
        """
        if self._sideboxes:
            for label, rset, vid in self._sideboxes:
                self.w(u'<div class="sideRelated">')
                self.wview(vid, rset, title=label)
                self.w(u'</div>')
        if self._contextboxes:
            for box in self._contextboxes:
                try:
                    box.dispatch(w=self.w, row=self.row)
                except NotImplementedError:
                    # much probably a context insensitive box, which only implements
                    # .call() and not cell_call()
                    box.dispatch(w=self.w)

    def is_side_related(self, rschema, eschema):
        return rschema.meta and \
               not rschema.schema_relation() == eschema.schema_entity()

    def _render_related_entities(self, entity, rschema, related,
                                 role='subject'):
        if rschema.is_final():
            value = related
            show_label = self.show_attr_label
        else:
            if not related:
                return
            value = self.view('autolimited', related)
        label = display_name(self.req, rschema.type, role)
        self.field(label, value, show_label=show_label, tr=False)


class RelatedView(EntityView):
    id = 'autolimited'
    def call(self):
        # if not too many entities, show them all in a list
        maxrelated = self.req.property_value('navigation.related-limit')
        if self.rset.rowcount <= maxrelated:
            if self.rset.rowcount == 1:
                self.wview('incontext', self.rset, row=0)
            elif 1 < self.rset.rowcount <= 5:
                self.wview('csv', self.rset)
            else:
                self.w(u'<div>')
                self.wview('simplelist', self.rset)
                self.w(u'</div>')
        # else show links to display related entities
        else:
            rql = self.rset.printable_rql()
            self.rset.limit(maxself.rset)
            self.w(u'<div>')
            self.wview('simplelist', self.rset)
            self.w(u'[<a href="%s">%s</a>]' % (self.build_url(rql=rql),
                                               self.req._('see them all')))
            self.w(u'</div>')
