"""The default primary view

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.mtconverter import html_escape

from cubicweb import Unauthorized
from cubicweb.view import EntityView
from cubicweb.web.uicfg import rdisplay

_ = unicode


class PrimaryView(EntityView):
    """the full view of an non final entity"""
    id = 'primary'
    title = _('primary')
    show_attr_label = True
    show_rel_label = True
    skip_none = True
    rdisplay = rdisplay
    main_related_section = True

    @classmethod
    def vreg_initialization_completed(cls):
        """set default category tags for relations where it's not yet defined in
        the category relation tags
        """
        for eschema in cls.schema.entities():
            for rschema, tschemas, role in eschema.relation_definitions(True):
                for tschema in tschemas:
                    if role == 'subject':
                        X, Y = eschema, tschema
                        card = rschema.rproperty(X, Y, 'cardinality')[0]
                        composed = rschema.rproperty(X, Y, 'composite') == 'object'
                    else:
                        X, Y = tschema, eschema
                        card = rschema.rproperty(X, Y, 'cardinality')[1]
                        composed = rschema.rproperty(X, Y, 'composite') == 'subject'
                    displayinfo = cls.rdisplay.get(rschema, role, X, Y)
                    if displayinfo is None:
                        if rschema.is_final():
                            if rschema.meta or tschema.type in ('Password', 'Bytes'):
                                where = None
                            else:
                                where = 'attributes'
                        elif card in '1+':
                            where = 'attributes'
                        elif composed:
                            where = 'relations'
                        else:
                            where = 'sideboxes'
                        displayinfo = {'where': where,
                                       'order': cls.rdisplay.get_timestamp()}
                        cls.rdisplay.tag_relation(displayinfo, (X, rschema, Y),
                                                  role)
                    displayinfo.setdefault('label', '%s_%s' % (rschema, role))

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
        self.maxrelated = self.req.property_value('navigation.related-limit')

    def render_entity(self, entity):
        """return html to display the given entity"""
        self.render_entity_title(entity)
        self.render_entity_metadata(entity)
        # entity's attributes and relations, excluding meta data
        # if the entity isn't meta itself
        boxes = self._prepare_side_boxes(entity)
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'<table width="100%"><tr><td style="width: 75%">')
        self.w(u'<div>')
        self.w(u'<div class="mainInfo">')
        try:
            self.render_entity_attributes(entity)
        except TypeError: # XXX bw compat
            warn('siderelations argument of render_entity_attributes is '
                 'deprecated (%s)' % self.__class__)
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
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'</td><td>')
            # side boxes
            self.w(u'<div class="primaryRight">')
            if hasattr(self, 'render_side_related'):
                warn('render_side_related is deprecated')
                self.render_side_related(entity, [])
            self.render_side_boxes(boxes)
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

    def render_entity_title(self, entity):
        title = self.content_title(entity) # deprecate content_title?
        if title:
            self.w(u'<h1><span class="etype">%s</span> %s</h1>'
                   % (entity.dc_type().capitalize(), title))


    def content_title(self, entity):
        """default implementation return dc_title"""
        return html_escape(entity.dc_title())

    def render_entity_metadata(self, entity):
        entity.view('metadata', w=self.w)
        summary = self.summary(entity) # deprecate summary?
        if summary:
            self.w(u'<div class="summary">%s</div>' % summary)

    def summary(self, entity):
        """default implementation return an empty string"""
        return u''

    def render_entity_attributes(self, entity, siderelations=None):
        for rschema, tschemas, role, displayinfo in self._iter_display(entity, 'attributes'):
            vid =  displayinfo.get('vid', 'reledit')
            if rschema.is_final() or vid == 'reledit':
                value = entity.view(vid, rtype=rschema.type, role=role)
            else:
                rset = self._relation_rset(entity, rschema, role, displayinfo)
                if rset:
                    value = self.view(vid, rset)
                else:
                    value = None
            if self.skip_none and (value is None or value == ''):
                continue
            self._render_attribute(rschema, value)

    def render_entity_relations(self, entity, siderelations=None):
        for rschema, tschemas, role, displayinfo in self._iter_display(entity, 'relations'):
            rset = self._relation_rset(entity, rschema, role, displayinfo)
            if rset:
                self._render_relation(rset, displayinfo, 'autolimited',
                                      self.show_rel_label)

    def render_side_boxes(self, boxes):
        """display side related relations:
        non-meta in a first step, meta in a second step
        """
        for box in boxes:
            if isinstance(box, tuple):
                label, rset, vid, _  = box
                self.w(u'<div class="sideRelated">')
                self.wview(vid, rset, title=label)
                self.w(u'</div>')
            else:
                try:
                    box.dispatch(w=self.w, row=self.row)
                except NotImplementedError:
                    # much probably a context insensitive box, which only implements
                    # .call() and not cell_call()
                    box.dispatch(w=self.w)

    def _prepare_side_boxes(self, entity):
        sideboxes = []
        for rschema, tschemas, role, displayinfo in self._iter_display(entity, 'sideboxes'):
            rset = self._relation_rset(entity, rschema, role, displayinfo)
            if not rset:
                continue
            label = display_name(self.req, rschema.type, role)
            vid = displayinfo.get('vid', 'autolimited')
            sideboxes.append((label, rset, vid, displayinfo.get('order')))
        sideboxes = sorted(sideboxes, key=lambda x: x[-1])
        sideboxes += list(self.vreg.possible_vobjects('boxes', self.req, self.rset,
                                                      row=self.row, view=self,
                                                      context='incontext'))
        return sideboxes

    def _iter_display(self, entity, where):
        eschema = entity.e_schema
        for rschema, tschemas, role in eschema.relation_definitions(True):
            matchtschemas = []
            for tschema in tschemas:
                displayinfo = self.rdisplay.etype_get(eschema, rschema, role,
                                                      tschema)
                assert displayinfo is not None, (str(rschema), role,
                                                 str(eschema), str(tschema))
                if displayinfo.get('where') == where:
                    matchtschemas.append(tschema)
            if matchtschemas:
                # XXX pick the latest displayinfo
                yield rschema, matchtschemas, role, displayinfo

    def _relation_rset(self, entity, rschema, role, displayinfo):
        try:
            if displayinfo.get('limit'):
                rset = entity.related(rschema.type, role,
                                      limit=self.maxrelated+1)
            else:
                rset = entity.related(rschema.type, role)
        except Unauthorized:
            return
        if 'filter' in displayinfo:
            rset = displayinfo['filter'](rset)
        return rset

    def _render_relation(self, rset, displayinfo, defaultvid, showlabel):
        self.w('<div class="section">')
        if showlabel:
            label = self.req._(displayinfo['label'])
            self.w('<h4>%s</h4>' % label)
        self.wview(displayinfo.get('vid', defaultvid), rset)
        self.w('</div>')

    def _render_attribute(self, rschema, value, role='subject'):
        if rschema.is_final():
            show_label = self.show_attr_label
        else:
            show_label = self.show_rel_label
        label = display_name(self.req, rschema.type, role)
        self.field(label, value, show_label=show_label, tr=False)


class RelatedView(EntityView):
    id = 'autolimited'
    def call(self, title=None, **kwargs):
        # if not too many entities, show them all in a list
        maxrelated = self.req.property_value('navigation.related-limit')
        if title:
            self.w(u'<div class="title"><span>%s</span></div>' % title)
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
            self.rset.limit(maxrelated)
            self.w(u'<div>')
            self.wview('simplelist', self.rset)
            self.w(u'[<a href="%s">%s</a>]' % (self.build_url(rql=rql),
                                               self.req._('see them all')))
            self.w(u'</div>')
