# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""The default primary view"""

__docformat__ = "restructuredtext en"
_ = unicode

from warnings import warn

from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized
from cubicweb.selectors import match_kwargs
from cubicweb.view import EntityView
from cubicweb.schema import VIRTUAL_RTYPES, display_name
from cubicweb.web import uicfg


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

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default primary views are indexed
        """
        return []

    def cell_call(self, row, col):
        self.cw_row = row
        self.cw_col = col
        self.maxrelated = self._cw.property_value('navigation.related-limit')
        entity = self.cw_rset.complete_entity(row, col)
        self.render_entity(entity)

    def render_entity(self, entity):
        self.render_entity_toolbox(entity)
        self.render_entity_title(entity)
        # entity's attributes and relations, excluding meta data
        # if the entity isn't meta itself
        if self.is_primary():
            boxes = self._prepare_side_boxes(entity)
        else:
            boxes = None
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'<table width="100%"><tr><td style="width: 75%">')
        self.render_entity_summary(entity)
        self.w(u'<div class="mainInfo">')
        self.content_navigation_components('navcontenttop')
        self.render_entity_attributes(entity)
        if self.main_related_section:
            self.render_entity_relations(entity)
        self.content_navigation_components('navcontentbottom')
        self.w(u'</div>')
        # side boxes
        if boxes or hasattr(self, 'render_side_related'):
            self.w(u'</td><td>')
            self.w(u'<div class="primaryRight">')
            if hasattr(self, 'render_side_related'):
                warn('[3.2] render_side_related is deprecated')
                self.render_side_related(entity, [])
            self.render_side_boxes(boxes)
            self.w(u'</div>')
            self.w(u'</td></tr></table>')

    def content_navigation_components(self, context):
        self.w(u'<div class="%s">' % context)
        for comp in self._cw.vreg['contentnavigation'].poss_visible_objects(
            self._cw, rset=self.cw_rset, row=self.cw_row, view=self, context=context):
            try:
                comp.render(w=self.w, row=self.cw_row, view=self)
            except NotImplementedError:
                warn('[3.2] component %s doesnt implement cell_call, please update'
                     % comp.__class__, DeprecationWarning)
                comp.render(w=self.w, view=self)
        self.w(u'</div>')

    def render_entity_title(self, entity):
        """default implementation return dc_title"""
        title = xml_escape(entity.dc_title())
        if title:
            if self.is_primary():
                self.w(u'<h1>%s</h1>' % title)
            else:
                atitle = self._cw._('follow this link for more information on this %s') % entity.dc_type()
                self.w(u'<h4><a href="%s" title="%s">%s</a></h4>'
                       % (entity.absolute_url(), atitle, title))

    def render_entity_toolbox(self, entity):
        self.content_navigation_components('ctxtoolbar')

    def render_entity_metadata(self, entity):
        entity.view('metadata', w=self.w)

    def render_entity_summary(self, entity):
        summary = self.summary(entity) # deprecate summary?
        if summary:
            self.w(u'<div class="summary">%s</div>' % summary)

    def summary(self, entity):
        """default implementation return an empty string"""
        return u''

    def render_entity_attributes(self, entity):
        display_attributes = []
        for rschema, _, role, dispctrl in self._section_def(entity, 'attributes'):
            vid = dispctrl.get('vid', 'reledit')
            if rschema.final or vid == 'reledit' or dispctrl.get('rtypevid'):
                value = entity.view(vid, rtype=rschema.type, role=role,
                                    initargs={'dispctrl': dispctrl})
            else:
                rset = self._relation_rset(entity, rschema, role, dispctrl)
                if rset:
                    value = self._cw.view(vid, rset)
                else:
                    value = None
            if not self.skip_none or (value is not None and value != ''):
                display_attributes.append( (rschema, role, dispctrl, value) )
        if display_attributes:
            self.w(u'<table>')
            for rschema, role, dispctrl, value in display_attributes:
                try:
                    self._render_attribute(dispctrl, rschema, value,
                                           role=role, table=True)
                except TypeError:
                    warn('[3.6] _render_attribute prototype has changed, please'
                         ' update %s' % self.__class___, DeprecationWarning)
                    self._render_attribute(rschema, value, role=role, table=True)
            self.w(u'</table>')

    def render_entity_relations(self, entity):
        for rschema, tschemas, role, dispctrl in self._section_def(entity, 'relations'):
            if rschema.final or dispctrl.get('rtypevid'):
                self.w(u'<div class="section">')
                label = self._rel_label(entity, rschema, role, dispctrl)
                if label:
                    self.w(u'<h4>%s</h4>' % label)
                vid = dispctrl.get('vid', 'reledit')
                entity.view(vid, rtype=rschema.type, role=role, w=self.w,
                            initargs={'dispctrl': dispctrl})
                self.w(u'</div>')
                continue
            rset = self._relation_rset(entity, rschema, role, dispctrl)
            if rset:
                try:
                    self._render_relation(dispctrl, rset, 'autolimited')
                except TypeError:
                    warn('[3.6] _render_relation prototype has changed, '
                         'please update %s' % self.__class__, DeprecationWarning)
                    self._render_relation(rset, dispctrl, 'autolimited',
                                          self.show_rel_label)

    def render_side_boxes(self, boxes):
        """display side related relations:
        non-meta in a first step, meta in a second step
        """
        for box in boxes:
            if isinstance(box, tuple):
                try:
                    label, rset, vid, dispctrl  = box
                except ValueError:
                    warn('[3.5] box views should now be defined as a 4-uple (label, rset, vid, dispctrl), '
                         'please update %s' % self.__class__.__name__,
                         DeprecationWarning)
                    label, rset, vid = box
                    dispctrl = {}
                self.w(u'<div class="sideBox">')
                self.wview(vid, rset, title=label, initargs={'dispctrl': dispctrl})
                self.w(u'</div>')
            else:
                try:
                    box.render(w=self.w, row=self.cw_row)
                except NotImplementedError:
                    # much probably a context insensitive box, which only implements
                    # .call() and not cell_call()
                    box.render(w=self.w)

    def _prepare_side_boxes(self, entity):
        sideboxes = []
        for rschema, tschemas, role, dispctrl in self._section_def(entity, 'sideboxes'):
            rset = self._relation_rset(entity, rschema, role, dispctrl)
            if not rset:
                continue
            label = display_name(self._cw, rschema.type, role)
            vid = dispctrl.get('vid', 'sidebox')
            sideboxes.append( (label, rset, vid, dispctrl) )
        sideboxes += self._cw.vreg['boxes'].poss_visible_objects(
            self._cw, rset=self.cw_rset, row=self.cw_row, view=self,
            context='incontext')
        # XXX since we've two sorted list, it may be worth using bisect
        def get_order(x):
            if isinstance(x, tuple):
                # x is a view box (label, rset, vid, dispctrl)
                # default to 1000 so view boxes occurs after component boxes
                return x[-1].get('order', 1000)
            # x is a component box
            return x.cw_propval('order')
        return sorted(sideboxes, key=get_order)

    def _section_def(self, entity, where):
        rdefs = []
        eschema = entity.e_schema
        for rschema, tschemas, role in eschema.relation_definitions(True):
            if rschema in VIRTUAL_RTYPES:
                continue
            matchtschemas = []
            for tschema in tschemas:
                section = self.rsection.etype_get(eschema, rschema, role,
                                                  tschema)
                if section == where:
                    matchtschemas.append(tschema)
            if matchtschemas:
                # XXX pick the latest dispctrl
                dispctrl = self.display_ctrl.etype_get(eschema, rschema, role,
                                                       matchtschemas[-1])

                rdefs.append( (rschema, matchtschemas, role, dispctrl) )
        return sorted(rdefs, key=lambda x: x[-1]['order'])

    def _relation_rset(self, entity, rschema, role, dispctrl):
        try:
            dispctrl.setdefault('limit', self.maxrelated)
            rset = entity.related(rschema.type, role, limit=dispctrl['limit']+1)
        except Unauthorized:
            return
        if 'filter' in dispctrl:
            rset = dispctrl['filter'](rset)
        return rset

    def _render_relation(self, dispctrl, rset, defaultvid):
        self.w(u'<div class="section">')
        if dispctrl.get('showlabel', self.show_rel_label):
            self.w(u'<h4>%s</h4>' % self._cw._(dispctrl['label']))
        self.wview(dispctrl.get('vid', defaultvid), rset,
                   initargs={'dispctrl': dispctrl})
        self.w(u'</div>')

    def _render_attribute(self, dispctrl, rschema, value,
                          role='subject', table=False):
        if rschema.final:
            showlabel = dispctrl.get('showlabel', self.show_attr_label)
        else:
            showlabel = dispctrl.get('showlabel', self.show_rel_label)
        if dispctrl.get('label'):
            label = self._cw._(dispctrl.get('label'))
        else:
            label = display_name(self._cw, rschema.type, role)
        self.field(label, value, show_label=showlabel, tr=False, table=table)

    def _rel_label(self, entity, rschema, role, dispctrl):
        if rschema.final:
            showlabel = dispctrl.get('showlabel', self.show_attr_label)
        else:
            showlabel = dispctrl.get('showlabel', self.show_rel_label)
        if showlabel:
            if dispctrl.get('label'):
                label = self._cw._(dispctrl['label'])
            else:
                label = display_name(self._cw, rschema.type, role,
                                     context=entity.__regid__)
            return label
        return u''


class RelatedView(EntityView):
    __regid__ = 'autolimited'

    def call(self, **kwargs):
        # nb: rset is retreived using entity.related with limit + 1 if any.
        # Because of that, we know that rset.printable_rql() will return rql
        # with no limit set anyway (since it's handled manually)
        if 'dispctrl' in self.cw_extra_kwargs:
            limit = self.cw_extra_kwargs['dispctrl'].get('limit')
            subvid = self.cw_extra_kwargs['dispctrl'].get('subvid', 'incontext')
        else:
            limit = None
            subvid = 'incontext'
        if limit is None or self.cw_rset.rowcount <= limit:
            if self.cw_rset.rowcount == 1:
                self.wview(subvid, self.cw_rset, row=0)
            elif 1 < self.cw_rset.rowcount <= 5:
                self.wview('csv', self.cw_rset, subvid=subvid)
            else:
                self.w(u'<div>')
                self.wview('simplelist', self.cw_rset, subvid=subvid)
                self.w(u'</div>')
        # else show links to display related entities
        else:
            rql = self.cw_rset.printable_rql()
            self.cw_rset.limit(limit) # remove extra entity
            self.w(u'<div>')
            self.wview('simplelist', self.cw_rset, subvid=subvid)
            self.w(u'[<a href="%s">%s</a>]' % (
                xml_escape(self._cw.build_url(rql=rql, vid=subvid)),
                self._cw._('see them all')))
            self.w(u'</div>')


class URLAttributeView(EntityView):
    """use this view for attributes whose value is an url and that you want
    to display as clickable link
    """
    __regid__ = 'urlattr'
    __select__ = EntityView.__select__ & match_kwargs('rtype')

    def cell_call(self, row, col, rtype, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        url = entity.printable_value(rtype)
        if url:
            self.w(u'<a href="%s">%s</a>' % (url, url))


## default primary ui configuration ###########################################

_pvs = uicfg.primaryview_section
for rtype in ('eid', 'creation_date', 'modification_date', 'cwuri',
              'is', 'is_instance_of', 'identity', 'owned_by', 'created_by',
              'require_permission', 'see_also'):
    _pvs.tag_subject_of(('*', rtype, '*'), 'hidden')
    _pvs.tag_object_of(('*', rtype, '*'), 'hidden')
