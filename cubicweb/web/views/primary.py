# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""
Public API of the PrimaryView class
````````````````````````````````````
.. autoclass:: cubicweb.web.views.primary.PrimaryView

Views that may be used to display an entity's attribute or relation
```````````````````````````````````````````````````````````````````

Yoy may easily the display of an attribute or relation by simply configuring the
view using one of `primaryview_display_ctrl` or `reledit_ctrl` to use one of the
views describled below. For instance:

.. sourcecode:: python

    primaryview_display_ctrl.tag_attribute(('Foo', 'bar'), {'vid': 'attribute'})


.. autoclass:: AttributeView
.. autoclass:: URLAttributeView
.. autoclass:: VerbatimAttributeView
"""


from cubicweb import _

from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized, NoSelectableObject
from cubicweb.utils import support_args
from cubicweb.predicates import match_kwargs, match_context
from cubicweb.view import EntityView
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, display_name
from cubicweb.web import component
from cubicweb.web.views import uicfg


class PrimaryView(EntityView):
    """
    The basic layout of a primary view is as in the :ref:`primary_view_layout`
    section. This layout is actually drawn by the `render_entity` method.

    The methods you may want to modify while customizing a ``PrimaryView``
    are:

    .. automethod:: cubicweb.web.views.primary.PrimaryView.render_entity_title
    .. automethod:: cubicweb.web.views.primary.PrimaryView.render_entity_attributes
    .. automethod:: cubicweb.web.views.primary.PrimaryView.render_entity_relations
    .. automethod:: cubicweb.web.views.primary.PrimaryView.render_side_boxes

    The placement of relations in the relations section or in side boxes
    can be controlled through the :ref:`primary_view_configuration` mechanism.

    .. automethod:: cubicweb.web.views.primary.PrimaryView.content_navigation_components

    Also, please note that by setting the following attributes in your
    subclass, you can already customize some of the rendering:

    :attr:`show_attr_label`
        Renders the attribute label next to the attribute value if set to `True`.
        Otherwise, does only display the attribute value.

    :attr:`show_rel_label`
        Renders the relation label next to the relation value if set to `True`.
        Otherwise, does only display the relation value.

    :attr:`main_related_section`
        Renders the relations of the entity if set to `True`.

    A good practice is for you to identify the content of your entity type for
    which the default rendering does not answer your need so that you can focus
    on the specific method (from the list above) that needs to be modified. We
    do not advise you to overwrite ``render_entity`` unless you want a
    completely different layout.
    """

    __regid__ = 'primary'
    title = _('primary')
    show_attr_label = True
    show_rel_label = True
    rsection = None
    display_ctrl = None
    main_related_section = True

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default primary views are indexed
        """
        return []

    def entity_call(self, entity, **kwargs):
        entity.complete()
        uicfg_reg = self._cw.vreg['uicfg']
        if self.rsection is None:
            self.rsection = uicfg_reg.select('primaryview_section',
                                             self._cw, entity=entity)
        if self.display_ctrl is None:
            self.display_ctrl = uicfg_reg.select('primaryview_display_ctrl',
                                                 self._cw, entity=entity)
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
            self.render_side_boxes(boxes)
            self.w(u'</div>')
            self.w(u'</td></tr></table>')

    def content_navigation_components(self, context):
        """This method is applicable only for entity type implementing the
        interface `IPrevNext`. This interface is for entities which can be
        linked to a previous and/or next entity. This method will render the
        navigation links between entities of this type, either at the top or at
        the bottom of the page given the context (navcontent{top|bottom}).
        """
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
        """Renders the entity title, by default using entity's
        :meth:`dc_title()` method.
        """
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

    def render_entity_attributes(self, entity):
        """Renders all attributes and relations in the 'attributes' section. 
        """
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
            if value is not None and value != '':
                display_attributes.append( (rschema, role, dispctrl, value) )
        if display_attributes:
            self.w(u'<table>')
            for rschema, role, dispctrl, value in display_attributes:
                label = self._rel_label(entity, rschema, role, dispctrl)
                self.render_attribute(label, value, table=True)
            self.w(u'</table>')

    def render_attribute(self, label, value, table=False):
        self.field(label, value, tr=False, table=table)

    def render_entity_relations(self, entity):
        """Renders all relations in the 'relations' section."""
        defaultlimit = self._cw.property_value('navigation.related-limit')
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
                vid = dispctrl.get('vid', 'autolimited')
                limit = dispctrl.get('limit', defaultlimit) if vid == 'autolimited' else None
                if limit is not None:
                    limit += 1 # need one more so the view can check if there is more than the limit
                rset = self._relation_rset(entity, rschema, role, dispctrl, limit=limit)
                if not rset:
                    continue
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
        """Renders side boxes on the right side of the content. This will
        generate a box for each relation in the 'sidebox' section, as well as
        explicit box appobjects selectable in this context.
        """
        for box in boxes:
            try:
                box.render(w=self.w, row=self.cw_row)
            except TypeError:
                box.render(w=self.w)

    def _prepare_side_boxes(self, entity):
        sideboxes = []
        boxesreg = self._cw.vreg['ctxcomponents']
        defaultlimit = self._cw.property_value('navigation.related-limit')
        for rschema, tschemas, role, dispctrl in self._section_def(entity, 'sideboxes'):
            vid = dispctrl.get('vid', 'autolimited')
            limit = defaultlimit if vid == 'autolimited' else None
            rset = self._relation_rset(entity, rschema, role, dispctrl, limit=limit)
            if not rset:
                continue
            label = self._rel_label(entity, rschema, role, dispctrl)
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

    def _relation_rset(self, entity, rschema, role, dispctrl, limit=None):
        try:
            rset = entity.related(rschema.type, role, limit=limit)
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
                                     context=entity.cw_etype)
            return label
        return u''


class RelatedView(EntityView):
    """Display a rset, usually containing entities linked to another entity
    being displayed.

    It will try to display nicely according to the number of items in the result
    set.

    XXX include me in the doc
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


class AttributeView(EntityView):
    """:__regid__: *attribute*

    This view is generally used to disable the *reledit* feature. It works on
    both relations and attributes.
    """
    __regid__ = 'attribute'
    __select__ = EntityView.__select__ & match_kwargs('rtype')

    def entity_call(self, entity, rtype, role='subject', **kwargs):
        if self._cw.vreg.schema.rschema(rtype).final:
            self.w(entity.printable_value(rtype))
        else:
            dispctrl = uicfg.primaryview_display_ctrl.etype_get(
                entity.e_schema, rtype, role, '*')
            rset = entity.related(rtype, role)
            if rset:
                self.wview('autolimited', rset, initargs={'dispctrl': dispctrl})


class URLAttributeView(EntityView):
    """:__regid__: *urlattr*

    This view will wrap an attribute value (hence expect a string) into an '<a>'
    HTML tag to display a clickable link.
    """
    __regid__ = 'urlattr'
    __select__ = EntityView.__select__ & match_kwargs('rtype')

    def entity_call(self, entity, rtype, **kwargs):
        url = entity.printable_value(rtype)
        if url:
            self.w(u'<a href="%s">%s</a>' % (url, url))


class VerbatimAttributeView(EntityView):
    """:__regid__: *verbatimattr*

    This view will wrap an attribute value into an '<pre>' HTML tag to display
    arbitrary text where EOL will be respected. It usually make sense for
    attributes whose value is a multi-lines string where new lines matters.
    """
    __regid__ = 'verbatimattr'
    __select__ = EntityView.__select__ & match_kwargs('rtype')

    def entity_call(self, entity, rtype, **kwargs):
        value = entity.printable_value(rtype)
        if value:
            self.w(u'<pre>%s</pre>' % value)





class ToolbarLayout(component.Layout):
    # XXX include me in the doc
    __select__ = match_context('ctxtoolbar')

    def render(self, w):
        if self.init_rendering():
            self.cw_extra_kwargs['view'].render_body(w)


## default primary ui configuration ###########################################

_pvs = uicfg.primaryview_section
for rtype in META_RTYPES:
    _pvs.tag_subject_of(('*', rtype, '*'), 'hidden')
    _pvs.tag_object_of(('*', rtype, '*'), 'hidden')
