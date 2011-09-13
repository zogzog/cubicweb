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

from logilab.common.deprecation import deprecated
from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized, NoSelectableObject
from cubicweb.utils import support_args
from cubicweb.selectors import match_kwargs, match_context
from cubicweb.view import EntityView
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, display_name
from cubicweb.web import uicfg, component


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

    def entity_call(self, entity):
        entity.complete()
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
        if hasattr(self, 'render_entity_summary'):
            warn('[3.10] render_entity_summary method is deprecated (%s)' % self,
                 DeprecationWarning)
            self.render_entity_summary(entity)
        summary = self.summary(entity)
        if summary:
            warn('[3.10] summary method is deprecated (%s)' % self,
                 DeprecationWarning)
            self.w(u'<div class="summary">%s</div>' % summary)
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
        for comp in self._cw.vreg['ctxcomponents'].poss_visible_objects(
            self._cw, rset=self.cw_rset, view=self, context=context):
            # XXX bw compat code
            try:
                comp.render(w=self.w, row=self.cw_row, view=self)
            except TypeError:
                comp.render(w=self.w)
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

    @deprecated('[3.8] render_entity_metadata method is deprecated')
    def render_entity_metadata(self, entity):
        entity.view('metadata', w=self.w)

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
                if not hasattr(self, '_render_attribute'):
                    label = self._rel_label(entity, rschema, role, dispctrl)
                    self.render_attribute(label, value, table=True)
                elif support_args(self._render_attribute, 'dispctrl'):
                    warn('[3.9] _render_attribute prototype has changed and '
                         'renamed to render_attribute, please update %s'
                         % self.__class___, DeprecationWarning)
                    self._render_attribute(dispctrl, rschema, value, role=role,
                                           table=True)
                else:
                    self._render_attribute(rschema, value, role=role, table=True)
                    warn('[3.6] _render_attribute prototype has changed and '
                         'renamed to render_attribute, please update %s'
                         % self.__class___, DeprecationWarning)
            self.w(u'</table>')

    def render_attribute(self, label, value, table=False):
        self.field(label, value, tr=False, table=table)

    def render_entity_relations(self, entity):
        for rschema, tschemas, role, dispctrl in self._section_def(entity, 'relations'):
            if rschema.final or dispctrl.get('rtypevid'):
                vid = dispctrl.get('vid', 'reledit')
                try:
                    rview = self._cw.vreg['views'].select(
                        vid, self._cw, rset=entity.cw_rset, row=entity.cw_row,
                        col=entity.cw_col, dispctrl=dispctrl,
                        rtype=rschema, role=role)
                except NoSelectableObject:
                    continue
                value = rview.render(row=entity.cw_row, col=entity.cw_col,
                                     rtype=rschema.type, role=role)
            else:
                rset = self._relation_rset(entity, rschema, role, dispctrl)
                if not rset:
                    continue
                if hasattr(self, '_render_relation'):
                    if not support_args(self._render_relation, 'showlabel'):
                        self._render_relation(dispctrl, rset, 'autolimited')
                        warn('[3.9] _render_relation prototype has changed and has '
                             'been renamed to render_relation, please update %s'
                             % self.__class__, DeprecationWarning)
                    else:
                        self._render_relation(rset, dispctrl, 'autolimited',
                                              self.show_rel_label)
                        warn('[3.6] _render_relation prototype has changed and has '
                             'been renamed to render_relation, please update %s'
                             % self.__class__, DeprecationWarning)
                    continue
                vid = dispctrl.get('vid', 'autolimited')
                try:
                    rview = self._cw.vreg['views'].select(
                        vid, self._cw, rset=rset, dispctrl=dispctrl)
                except NoSelectableObject:
                    continue
                value = rview.render()
            label = self._rel_label(entity, rschema, role, dispctrl)
            self.render_relation(label, value)

    def render_relation(self, label, value):
        self.w(u'<div class="section">')
        if label:
            self.w(u'<h4>%s</h4>' % label)
        self.w(value)
        self.w(u'</div>')

    def render_side_boxes(self, boxes):
        """display side related relations:
        non-meta in a first step, meta in a second step
        """
        for box in boxes:
            if isinstance(box, tuple):
                try:
                    label, rset, vid, dispctrl  = box
                except ValueError:
                    label, rset, vid = box
                    dispctrl = {}
                warn('[3.10] box views should now be a RsetBox instance, '
                     'please update %s' % self.__class__.__name__,
                     DeprecationWarning)
                self.w(u'<div class="sideBox">')
                self.wview(vid, rset, title=label, initargs={'dispctrl': dispctrl})
                self.w(u'</div>')
            else:
                 try:
                     box.render(w=self.w, row=self.cw_row)
                 except TypeError:
                     box.render(w=self.w)

    def _prepare_side_boxes(self, entity):
        sideboxes = []
        boxesreg = self._cw.vreg['ctxcomponents']
        for rschema, tschemas, role, dispctrl in self._section_def(entity, 'sideboxes'):
            rset = self._relation_rset(entity, rschema, role, dispctrl)
            if not rset:
                continue
            label = self._rel_label(entity, rschema, role, dispctrl)
            vid = dispctrl.get('vid', 'autolimited')
            box = boxesreg.select('rsetbox', self._cw, rset=rset,
                                  vid=vid, title=label, dispctrl=dispctrl,
                                  context='incontext')
            sideboxes.append(box)
        sideboxes += boxesreg.poss_visible_objects(
             self._cw, rset=self.cw_rset, view=self,
             context='incontext')
        # XXX since we've two sorted list, it may be worth using bisect
        def get_order(x):
            if 'order' in x.cw_property_defs:
                return x.cw_propval('order')
            # default to 9999 so view boxes occurs after component boxes
            return x.cw_extra_kwargs.get('dispctrl', {}).get('order', 9999)
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
                dispctrl = self.display_ctrl.etype_get(eschema, rschema, role, '*')
                rdefs.append( (rschema, matchtschemas, role, dispctrl) )
        return sorted(rdefs, key=lambda x: x[-1]['order'])

    def _relation_rset(self, entity, rschema, role, dispctrl):
        try:
            rset = entity.related(rschema.type, role)
        except Unauthorized:
            return
        if 'filter' in dispctrl:
            rset = dispctrl['filter'](rset)
        return rset

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
    """Display a rset, usually containing entities linked to another entity
    being displayed.

    It will try to display nicely according to the number of items in the result
    set.
    """
    __regid__ = 'autolimited'

    def call(self, **kwargs):
        if 'dispctrl' in self.cw_extra_kwargs:
            if 'limit' in self.cw_extra_kwargs['dispctrl']:
                limit = self.cw_extra_kwargs['dispctrl']['limit']
            else:
                limit = self._cw.property_value('navigation.related-limit')
            list_limit = self.cw_extra_kwargs['dispctrl'].get('use_list_limit', 5)
            subvid = self.cw_extra_kwargs['dispctrl'].get('subvid', 'incontext')
        else:
            limit = list_limit = None
            subvid = 'incontext'
        if limit is None or self.cw_rset.rowcount <= limit:
            if self.cw_rset.rowcount == 1:
                self.wview(subvid, self.cw_rset, row=0)
            elif list_limit is None or 1 < self.cw_rset.rowcount <= list_limit:
                self.wview('csv', self.cw_rset, subvid=subvid)
            else:
                self.w(u'<div>')
                self.wview('simplelist', self.cw_rset, subvid=subvid)
                self.w(u'</div>')
        # else show links to display related entities
        else:
            rql = self.cw_rset.printable_rql()
            rset = self.cw_rset.limit(limit) # remove extra entity
            if list_limit is None:
                self.wview('csv', rset, subvid=subvid)
                self.w(u'[<a href="%s">%s</a>]' % (
                    xml_escape(self._cw.build_url(rql=rql, vid=subvid)),
                    self._cw._('see them all')))
            else:
                self.w(u'<div>')
                self.wview('simplelist', rset, subvid=subvid)
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

class AttributeView(EntityView):
    """use this view on an entity as an alternative to more sophisticated
    views such as reledit.

    Ex. usage:

    uicfg.primaryview_display_ctrl.tag_attribute(('Foo', 'bar'), {'vid': 'attribute'})
    """
    __regid__ = 'attribute'
    __select__ = EntityView.__select__ & match_kwargs('rtype')

    def cell_call(self, row, col, rtype, role, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        if self._cw.vreg.schema.rschema(rtype).final:
            self.w(entity.printable_value(rtype))
        else:
            dispctrl = uicfg.primaryview_display_ctrl.etype_get(
                entity.e_schema, rtype, role, '*')
            rset = entity.related(rtype, role)
            if rset:
                self.wview('autolimited', rset, initargs={'dispctrl': dispctrl})



class ToolbarLayout(component.Layout):
    __select__ = match_context('ctxtoolbar')

    def render(self, w):
        if self.init_rendering():
            self.cw_extra_kwargs['view'].render_body(w)

## default primary ui configuration ###########################################

_pvs = uicfg.primaryview_section
for rtype in META_RTYPES:
    _pvs.tag_subject_of(('*', rtype, '*'), 'hidden')
    _pvs.tag_object_of(('*', rtype, '*'), 'hidden')
_pvs.tag_subject_of(('*', 'require_permission', '*'), 'hidden')
_pvs.tag_object_of(('*', 'require_permission', '*'), 'hidden')
