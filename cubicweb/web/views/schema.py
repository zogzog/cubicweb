# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Specific views for schema related entities"""


from cubicweb import _

from itertools import cycle

import tempfile
import os, os.path as osp
import codecs

from logilab.common.graph import GraphGenerator, DotBackend
from logilab.common.ureports import Section, Table
from logilab.common.registry import yes
from logilab.mtconverter import xml_escape
from yams import BASE_TYPES, schema2dot as s2d
from yams.buildobjs import DEFAULT_ATTRPERMS

from cubicweb.predicates import (is_instance, match_user_groups, match_kwargs,
                                has_related_entities, authenticated_user)
from cubicweb.schema import (META_RTYPES, SCHEMA_TYPES, SYSTEM_RTYPES,
                             WORKFLOW_TYPES, INTERNAL_TYPES)
from cubicweb.utils import make_uid
from cubicweb.view import EntityView, StartupView
from cubicweb import tags, uilib
from cubicweb.web import action, facet, schemaviewer
from cubicweb.web.views import uicfg, primary, baseviews, tabs, tableview, ibreadcrumbs

ALWAYS_SKIP_TYPES = BASE_TYPES | SCHEMA_TYPES
SKIP_TYPES  = (ALWAYS_SKIP_TYPES | META_RTYPES | SYSTEM_RTYPES | WORKFLOW_TYPES
               | INTERNAL_TYPES)
SKIP_TYPES.update(set(('CWUser', 'CWGroup', 'EmailAddress', 'Bookmark')))

def skip_types(req):
    if int(req.form.get('skipmeta', True)):
        return SKIP_TYPES
    return ALWAYS_SKIP_TYPES

_pvs = uicfg.primaryview_section
_pvdc = uicfg.primaryview_display_ctrl

for _action in ('read', 'add', 'update', 'delete'):
    _pvs.tag_subject_of(('*', '%s_permission' % _action, '*'), 'hidden')
    _pvs.tag_object_of(('*', '%s_permission' % _action, '*'), 'hidden')

for _etype in ('CWEType', 'CWRType', 'CWAttribute', 'CWRelation'):
    _pvdc.tag_attribute((_etype, 'description'), {'showlabel': False})

_pvs.tag_attribute(('CWEType', 'name'), 'hidden')
_pvs.tag_attribute(('CWEType', 'final'), 'hidden')
_pvs.tag_object_of(('*', 'workflow_of', 'CWEType'), 'hidden')
_pvs.tag_subject_of(('CWEType', 'default_workflow', '*'), 'hidden')
_pvs.tag_object_of(('*', 'specializes', 'CWEType'), 'hidden')
_pvs.tag_subject_of(('CWEType', 'specializes', '*'), 'hidden')
_pvs.tag_object_of(('*', 'from_entity', 'CWEType'), 'hidden')
_pvs.tag_object_of(('*', 'to_entity', 'CWEType'), 'hidden')

_pvs.tag_attribute(('CWRType', 'name'), 'hidden')
_pvs.tag_attribute(('CWRType', 'final'), 'hidden')
_pvs.tag_object_of(('*', 'relation_type', 'CWRType'), 'hidden')

_pvs.tag_subject_of(('CWAttribute', 'constrained_by', '*'), 'hidden')
_pvs.tag_subject_of(('CWRelation', 'constrained_by', '*'), 'hidden')


class SecurityViewMixIn(object):
    """mixin providing methods to display security information for a entity,
    relation or relation definition schema
    """
    cssclass = "listing schemaInfo"

    def permissions_table(self, erschema, permissions=None):
        self._cw.add_css('cubicweb.acl.css')
        w = self.w
        _ = self._cw._
        w(u'<table class="%s">' % self.cssclass)
        w(u'<tr><th>%s</th><th>%s</th><th>%s</th></tr>' % (
            _("permission"), _('granted to groups'), _('rql expressions')))
        for action in erschema.ACTIONS:
            w(u'<tr><td>%s</td><td>' % _(action))
            if permissions is None:
                groups = erschema.get_groups(action)
                rqlexprs = sorted(e.expression for e in erschema.get_rqlexprs(action))
            else:
                groups = permissions[action][0]
                rqlexprs = permissions[action][1]
            # XXX get group entity and call it's incontext view
            groups = [u'<a class="%s" href="%s">%s</a>' % (
                group, self._cw.build_url('cwgroup/%s' % group), label)
                      for label, group in sorted((_(g), g) for g in groups)]
            w(u'<br/>'.join(groups))
            w(u'</td><td>')
            w(u'<br/>'.join(rqlexprs))
            w(u'</td></tr>\n')
        w(u'</table>')

    def grouped_permissions_table(self, rschema):
        # group relation definitions with identical permissions
        perms = {}
        for rdef in rschema.rdefs.values():
            rdef_perms = []
            for action in rdef.ACTIONS:
                groups = sorted(rdef.get_groups(action))
                exprs = sorted(e.expression for e in rdef.get_rqlexprs(action))
                rdef_perms.append( (action, (tuple(groups), tuple(exprs))) )
            rdef_perms = tuple(rdef_perms)
            if rdef_perms in perms:
                perms[rdef_perms].append( (rdef.subject, rdef.object) )
            else:
                perms[rdef_perms] = [(rdef.subject, rdef.object)]
        # set layout permissions in a table for each group of relation
        # definition
        w = self.w
        _ = self._cw._
        w(u'<div style="margin: 0px 1.5em">')
        tmpl = u'<strong>%s</strong> %s <strong>%s</strong>'
        for perm, rdefs in perms.items():
            w(u'<div>%s</div>' % u', '.join(
                tmpl % (_(s.type), _(rschema.type), _(o.type)) for s, o in rdefs))
            # accessing rdef from previous loop by design: only used to get
            # ACTIONS
            self.permissions_table(rdef, dict(perm))
        w(u'</div>')


# global schema view ###########################################################

class SchemaView(tabs.TabsMixin, StartupView):
    """display schema information (graphically, listing tables...) in tabs"""
    __regid__ = 'schema'
    title = _('data model schema')
    tabs = [_('schema-diagram'), _('schema-entity-types'),
            _('schema-relation-types')]
    default_tab = 'schema-diagram'

    def call(self):
        self.w(u'<h1>%s</h1>' % self._cw._(self.title))
        self.render_tabs(self.tabs, self.default_tab)


class SchemaImageTab(StartupView):
    __regid__ = 'schema-diagram'

    def call(self):
        _ = self._cw._
        self.w(self._cw._(
            u'<div>This schema of the data model <em>excludes</em> the '
            'meta-data, but you can also display a <a href="%s">complete '
            'schema with meta-data</a>.</div>')
               % xml_escape(self._cw.build_url('view', vid='schemagraph', skipmeta=0)))
        self.w(u'<div><a href="%s">%s</a></div>' %
               (self._cw.build_url('view', vid='owl'),
                self._cw._(u'Download schema as OWL')))
        self.wview('schemagraph')

class SchemaETypeTab(StartupView):
    __regid__ = 'schema-entity-types'

    def call(self):
        self.wview('table', self._cw.execute(
            'Any X ORDERBY N WHERE X is CWEType, X name N, X final FALSE'))


class SchemaRTypeTab(StartupView):
    __regid__ = 'schema-relation-types'

    def call(self):
        self.wview('table', self._cw.execute(
            'Any X ORDERBY N WHERE X is CWRType, X name N, X final FALSE'))

# CWEType ######################################################################

# register msgid generated in entity relations tables
_('i18ncard_1'), _('i18ncard_?'), _('i18ncard_+'), _('i18ncard_*')

class CWETypePrimaryView(tabs.TabbedPrimaryView):
    __select__ = is_instance('CWEType')
    tabs = [_('cwetype-description'), _('cwetype-box'), _('cwetype-workflow'),
            _('cwetype-views'), _('cwetype-permissions')]
    default_tab = 'cwetype-description'


class CWETypeDescriptionTab(tabs.PrimaryTab):
    __regid__ = 'cwetype-description'
    __select__ = tabs.PrimaryTab.__select__ & is_instance('CWEType')

    def render_entity_attributes(self, entity):
        super(CWETypeDescriptionTab, self).render_entity_attributes(entity)
        _ = self._cw._
        # inheritance
        if entity.specializes:
            self.w(u'<div><strong>%s</strong>' % _('Parent class:'))
            self.wview('csv', entity.related('specializes', 'subject'))
            self.w(u'</div>')
        if entity.reverse_specializes:
            self.w(u'<div><strong>%s</strong>' % _('Sub-classes:'))
            self.wview('csv', entity.related('specializes', 'object'))
            self.w(u'</div>')
        # entity schema image
        self.wview('schemagraph', etype=entity.name)
        # entity schema attributes
        self.w(u'<h2>%s</h2>' % _('CWAttribute_plural'))
        rset = self._cw.execute(
            'Any A,ON,D,C,A,DE,A, IDX,FTI,I18N,R,O,RN,S ORDERBY AA '
            'WHERE A is CWAttribute, A from_entity S, S eid %(x)s, '
            'A ordernum AA, A defaultval D, A description DE, A cardinality C, '
            'A fulltextindexed FTI, A internationalizable I18N, A indexed IDX, '
            'A relation_type R, R name RN, A to_entity O, O name ON',
            {'x': entity.eid})
        self.wview('table', rset, 'null',
                   cellvids={0: 'rdef-name-cell',
                             2: 'etype-attr-defaultval-cell',
                             3: 'etype-attr-cardinality-cell',
                             4: 'rdef-constraints-cell',
                             6: 'rdef-options-cell'},
                   headers=(_(u'name'), _(u'type'),
                            _(u'default value'), _(u'required'),
                            _(u'constraints'), _(u'description'), _('options')))
        # entity schema relations
        self.w(u'<h2>%s</h2>' % _('CWRelation_plural'))
        cellvids = {0: 'rdef-name-cell',
                    2: 'etype-rel-cardinality-cell',
                    3: 'rdef-constraints-cell',
                    4: 'rdef-options-cell'}
        headers= [_(u'name'), _(u'object type'), _(u'cardinality'),
                  _(u'constraints'), _(u'options')]
        rset = self._cw.execute(
            'Any A,TT,"i18ncard_"+SUBSTRING(C,1,1),A,A, K,TTN,R,RN ORDERBY RN '
            'WHERE A is CWRelation, A from_entity S, S eid %(x)s, '
            'A composite K, A cardinality C, '
            'A relation_type R, R name RN, A to_entity TT, TT name TTN',
            {'x': entity.eid})
        if rset:
            self.w(u'<h5>%s %s</h5>' % (entity.name, _('is subject of:')))
            self.wview('table', rset, cellvids=cellvids, headers=headers)
        rset = self._cw.execute(
            'Any A,TT,"i18ncard_"+SUBSTRING(C,1,1),A,A, K,TTN,R,RN ORDERBY RN '
            'WHERE A is CWRelation, A to_entity O, O eid %(x)s, '
            'A composite K, A cardinality C, '
            'A relation_type R, R name RN, A from_entity TT, TT name TTN',
            {'x': entity.eid})
        if rset:
            cellvids[0] = 'rdef-object-name-cell'
            headers[1] = _(u'subject type')
            self.w(u'<h5>%s %s</h5>' % (entity.name, _('is object of:')))
            self.wview('table', rset, cellvids=cellvids, headers=headers)


class CWETypeAttributeCardinalityCell(baseviews.FinalView):
    __regid__ = 'etype-attr-cardinality-cell'

    def cell_call(self, row, col):
        if self.cw_rset.rows[row][col][0] == '1':
            self.w(self._cw._(u'yes'))
        else:
            self.w(self._cw._(u'no'))


class CWETypeAttributeDefaultValCell(baseviews.FinalView):
    __regid__ = 'etype-attr-defaultval-cell'

    def cell_call(self, row, col):
        defaultval = self.cw_rset.rows[row][col]
        if defaultval is not None:
            self.w(str(self.cw_rset.rows[row][col].unzpickle()))

class CWETypeRelationCardinalityCell(baseviews.FinalView):
    __regid__ = 'etype-rel-cardinality-cell'

    def cell_call(self, row, col):
        self.w(self._cw._(self.cw_rset.rows[row][col]))


class CWETypeBoxTab(EntityView):
    __regid__ = 'cwetype-box'
    __select__ = is_instance('CWEType')

    def cell_call(self, row, col):
        viewer = schemaviewer.SchemaViewer(self._cw)
        entity = self.cw_rset.get_entity(row, col)
        eschema = self._cw.vreg.schema.eschema(entity.name)
        layout = viewer.visit_entityschema(eschema)
        self.w(uilib.ureport_as_html(layout))
        self.w(u'<br class="clear"/>')


class CWETypePermTab(SecurityViewMixIn, EntityView):
    __regid__ = 'cwetype-permissions'
    __select__ = is_instance('CWEType') & authenticated_user()

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        eschema = self._cw.vreg.schema.eschema(entity.name)
        self.w(u'<h4>%s</h4>' % self._cw._('This entity type permissions:'))
        self.permissions_table(eschema)
        self.w(u'<div style="margin: 0px 1.5em">')
        self.w(u'<h4>%s</h4>' % self._cw._('Attributes permissions:'))
        for attr, etype in  eschema.attribute_definitions():
            if attr not in META_RTYPES:
                rdef = eschema.rdef(attr)
                attrtype = str(rdef.rtype)
                self.w(u'<h4 class="schema">%s (%s)</h4> '
                       % (attrtype, self._cw._(attrtype)))
                self.permissions_table(rdef)
        self.w(u'</div>')


class CWETypeWorkflowTab(EntityView):
    __regid__ = 'cwetype-workflow'
    __select__ = (is_instance('CWEType')
                  & has_related_entities('workflow_of', 'object'))

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        if entity.default_workflow:
            wf = entity.default_workflow[0]
            if len(entity.reverse_workflow_of) > 1:
                self.w(u'<h1>%s (%s)</h1>'
                       % (wf.name, self._cw._('default_workflow')))
            self.display_workflow(wf)
            defaultwfeid = wf.eid
        else:
            self.w(u'<div class="error">%s</div>'
                   % self._cw._('There is no default workflow'))
            defaultwfeid = None
        for altwf in entity.reverse_workflow_of:
            if altwf.eid == defaultwfeid:
                continue
            self.w(u'<h1>%s</h1>' % altwf.name)
            self.display_workflow(altwf)

    def display_workflow(self, wf):
        self.w(wf.view('wfgraph'))
        self.w('<a href="%s">%s</a>' % (
            wf.absolute_url(), self._cw._('more info about this workflow')))


class CWETypeViewsTab(EntityView):
    """possible views for this entity type"""
    __regid__ = 'cwetype-views'
    __select__ = EntityView.__select__ & is_instance('CWEType')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        _ = self._cw._
        self.w('<div>%s</div>' % _('Non exhaustive list of views that may '
                                   'apply to entities of this type'))
        views = [(view.content_type, view.__regid__, _(view.title))
                 for view in self.possible_views(entity.name)]
        self.wview('pyvaltable', pyvalue=sorted(views),
                   headers=(_(u'content type'), _(u'view identifier'),
                            _(u'view title')))

    def possible_views(self, etype):
        rset = self._cw.etype_rset(etype)
        return [v for v in self._cw.vreg['views'].possible_views(self._cw, rset)
                if v.category != 'startupview']


class CWETypeOneLineView(baseviews.OneLineView):
    __select__ = is_instance('CWEType')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        if entity.final:
            self.w(u'<em class="finalentity">')
        super(CWETypeOneLineView, self).cell_call(row, col, **kwargs)
        if entity.final:
            self.w(u'</em>')


# CWRType ######################################################################

class CWRTypePrimaryView(tabs.TabbedPrimaryView):
    __select__ = is_instance('CWRType')
    tabs = [_('cwrtype-description'), _('cwrtype-permissions')]
    default_tab = 'cwrtype-description'


class CWRTypeDescriptionTab(tabs.PrimaryTab):
    __regid__ = 'cwrtype-description'
    __select__ = is_instance('CWRType')

    def render_entity_attributes(self, entity):
        super(CWRTypeDescriptionTab, self).render_entity_attributes(entity)
        _ = self._cw._
        if not entity.final:
            self.wview('schemagraph', rtype=entity.name)
        rset = self._cw.execute('Any R,C,R,R, RT WHERE '
                                'R relation_type RT, RT eid %(x)s, '
                                'R cardinality C', {'x': entity.eid})
        self.wview('table', rset, 'null',
                   headers=(_(u'relation'),  _(u'cardinality'), _(u'constraints'),
                            _(u'options')),
                   cellvids={2: 'rdef-constraints-cell',
                             3: 'rdef-options-cell'})


class CWRTypePermTab(SecurityViewMixIn, EntityView):
    __regid__ = 'cwrtype-permissions'
    __select__ = is_instance('CWRType') & authenticated_user()

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema.rschema(entity.name)
        self.grouped_permissions_table(rschema)


# CWAttribute / CWRelation #####################################################

class RDEFPrimaryView(tabs.TabbedPrimaryView):
    __select__ = is_instance('CWRelation', 'CWAttribute')
    tabs = [_('rdef-description'), _('rdef-permissions')]
    default_tab = 'rdef-description'


class RDEFDescriptionTab(tabs.PrimaryTab):
    __regid__ = 'rdef-description'
    __select__ = is_instance('CWRelation', 'CWAttribute')

    def render_entity_attributes(self, entity):
        super(RDEFDescriptionTab, self).render_entity_attributes(entity)
        rdef = entity.yams_schema()
        if rdef.constraints:
            self.w(u'<h4>%s</h4>' % self._cw._('constrained_by'))
            self.w(entity.view('rdef-constraints-cell'))


class RDEFPermTab(SecurityViewMixIn, EntityView):
    __regid__ = 'rdef-permissions'
    __select__ = is_instance('CWRelation', 'CWAttribute') & authenticated_user()

    def cell_call(self, row, col):
        self.permissions_table(self.cw_rset.get_entity(row, col).yams_schema())


class RDEFNameView(tableview.CellView):
    """display relation name and its translation only in a cell view, link to
    relation definition's primary view (for use in entity type relations table
    for instance)
    """
    __regid__ = 'rdef-name-cell'
    __select__ = is_instance('CWRelation', 'CWAttribute')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rtype = entity.relation_type[0].name
        # XXX use context entity + pgettext
        self.w(u'<a href="%s">%s</a> (%s)' % (
            entity.absolute_url(), rtype, self._cw._(rtype)))

class RDEFObjectNameView(tableview.CellView):
    """same as RDEFNameView but when the context is the object entity
    """
    __regid__ = 'rdef-object-name-cell'
    __select__ = is_instance('CWRelation', 'CWAttribute')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rtype = entity.relation_type[0].name
        # XXX use context entity + pgettext
        self.w(u'<a href="%s">%s</a> (%s)' % (
            entity.absolute_url(), rtype, self._cw.__(rtype + '_object')))

class RDEFConstraintsCell(EntityView):
    __regid__ = 'rdef-constraints-cell'
    __select__ = is_instance('CWAttribute', 'CWRelation')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema.rschema(entity.rtype.name)
        rdef = rschema.rdefs[(entity.stype.name, entity.otype.name)]
        constraints = [xml_escape(str(c)) for c in getattr(rdef, 'constraints')]
        self.w(u'<br/>'.join(constraints))

class CWAttributeOptionsCell(EntityView):
    __regid__ = 'rdef-options-cell'
    __select__ = is_instance('CWAttribute')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        options = []
        if entity.indexed:
            options.append(self._cw._('indexed'))
        if entity.fulltextindexed:
            options.append(self._cw._('fulltextindexed'))
        if entity.internationalizable:
            options.append(self._cw._('internationalizable'))
        self.w(u','.join(options))

class CWRelationOptionsCell(EntityView):
    __regid__ = 'rdef-options-cell'
    __select__ = is_instance('CWRelation',)

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rtype = entity.rtype
        options = []
        if rtype.symmetric:
            options.append(self._cw._('symmetric'))
        if rtype.inlined:
            options.append(self._cw._('inlined'))
        if rtype.fulltext_container:
            options.append('%s=%s' % (self._cw._('fulltext_container'),
                                      self._cw._(rtype.fulltext_container)))
        if entity.composite:
            options.append('%s=%s' % (self._cw._('composite'),
                                      self._cw._(entity.composite)))
        self.w(u','.join(options))


# schema images ###############################################################

class RestrictedSchemaVisitorMixIn(object):
    def __init__(self, req, *args, **kwargs):
        self._cw = req
        super(RestrictedSchemaVisitorMixIn, self).__init__(*args, **kwargs)

    def should_display_schema(self, rschema):
        return (super(RestrictedSchemaVisitorMixIn, self).should_display_schema(rschema)
                and rschema.may_have_permission('read', self._cw))

    def should_display_attr(self, eschema, rschema):
        return (super(RestrictedSchemaVisitorMixIn, self).should_display_attr(eschema, rschema)
                and eschema.rdef(rschema).may_have_permission('read', self._cw))


class FullSchemaVisitor(RestrictedSchemaVisitorMixIn, s2d.FullSchemaVisitor):
    pass

class OneHopESchemaVisitor(RestrictedSchemaVisitorMixIn,
                           s2d.OneHopESchemaVisitor):
    pass

class OneHopRSchemaVisitor(RestrictedSchemaVisitorMixIn,
                           s2d.OneHopRSchemaVisitor):
    pass

class CWSchemaDotPropsHandler(s2d.SchemaDotPropsHandler):
    def __init__(self, visitor, cw):
        self.visitor = visitor
        self.cw = cw
        self._cycle = iter(cycle(('#ff7700', '#000000', '#ebbc69', '#888888')))
        self.nextcolor = lambda: next(self._cycle)

        self.colors = {}

    def node_properties(self, eschema):
        """return DOT drawing options for an entity schema include href"""
        label = ['{',eschema.type,'|']
        label.append(r'\l'.join('%s (%s)' % (rel.type, eschema.rdef(rel.type).object)
                                for rel in eschema.ordered_relations()
                                    if rel.final and self.visitor.should_display_attr(eschema, rel)))
        label.append(r'\l}') # trailing \l ensure alignement of the last one
        return {'label' : ''.join(label), 'shape' : "record",
                'fontname' : "Courier", 'style' : "filled",
                'href': self.cw.build_url('cwetype/%s' % eschema.type),
                'fontsize': '10px'
                }

    def edge_properties(self, rschema, subjnode, objnode):
        """return default DOT drawing options for a relation schema"""
        # Inheritance relation (i.e 'specializes').
        if rschema is None:
            kwargs = {'label': 'Parent class',
                      'color' : 'grey',  'style' : 'filled',
                      'arrowhead': 'empty',
                      'fontsize': '10px'}
        # symmetric rels are handled differently, let yams decide what's best
        elif rschema.symmetric:
            kwargs = {'label': rschema.type,
                      'color': '#887788', 'style': 'dashed',
                      'dir': 'both', 'arrowhead': 'normal', 'arrowtail': 'normal',
                      'fontsize': '10px',
                      'href': self.cw.build_url('cwrtype/%s' % rschema.type)}
        else:
            kwargs = {'label': rschema.type,
                      'color' : 'black',  'style' : 'filled', 'fontsize': '10px',
                      'href': self.cw.build_url('cwrtype/%s' % rschema.type)}
            rdef = rschema.rdef(subjnode, objnode)
            composite = rdef.composite
            if rdef.composite == 'subject':
                kwargs['arrowhead'] = 'none'
                kwargs['arrowtail'] = 'diamond'
            elif rdef.composite == 'object':
                kwargs['arrowhead'] = 'diamond'
                kwargs['arrowtail'] = 'none'
            else:
                kwargs['arrowhead'] = 'open'
                kwargs['arrowtail'] = 'none'
            # UML like cardinalities notation, omitting 1..1
            if rdef.cardinality[1] != '1':
                kwargs['taillabel'] = s2d.CARD_MAP[rdef.cardinality[1]]
            if rdef.cardinality[0] != '1':
                kwargs['headlabel'] = s2d.CARD_MAP[rdef.cardinality[0]]
            try:
                kwargs['color'] = self.colors[rschema]
            except KeyError:
                kwargs['color'] = self.nextcolor()
                self.colors[rschema] = kwargs['color']
        kwargs['fontcolor'] = kwargs['color']
        # dot label decoration is just awful (1 line underlining the label
        # + 1 line going to the closest edge spline point)
        kwargs['decorate'] = 'false'
        #kwargs['labelfloat'] = 'true'
        return kwargs


class SchemaGraphView(StartupView):
    __regid__ = 'schemagraph'

    def call(self, etype=None, rtype=None, alt=''):
        if 'MSIE 8' in self._cw.useragent():
            return
        schema = self._cw.vreg.schema
        if etype:
            assert rtype is None
            visitor = OneHopESchemaVisitor(self._cw, schema.eschema(etype),
                                           skiptypes=skip_types(self._cw))
            alt = self._cw._('graphical representation of the %(etype)s '
                             'entity type from %(appid)s data model')
        elif rtype:
            visitor = OneHopRSchemaVisitor(self._cw, schema.rschema(rtype),
                                           skiptypes=skip_types(self._cw))
            alt = self._cw._('graphical representation of the %(rtype)s '
                             'relation type from %(appid)s data model')
        else:
            visitor = FullSchemaVisitor(self._cw, schema,
                                        skiptypes=skip_types(self._cw))
            alt = self._cw._('graphical representation of %(appid)s data model')
        alt %= {'rtype': rtype, 'etype': etype,
                'appid': self._cw.vreg.config.appid}
        prophdlr = CWSchemaDotPropsHandler(visitor, self._cw)
        generator = GraphGenerator(DotBackend('schema', 'BT',
                                              ratio='compress',size=None,
                                              renderer='dot',
                                              additionnal_param={
                                                  'overlap':'false',
                                                  'splines':'true',
                                                  'sep':'0.2',
                                              }))
        # svg image file
        fd, tmpfile = tempfile.mkstemp('.svg')
        try:
            os.close(fd)
            generator.generate(visitor, prophdlr, tmpfile)
            with codecs.open(tmpfile, 'rb', encoding='utf-8') as svgfile:
                self.w(svgfile.read())
        finally:
            os.unlink(tmpfile)

# breadcrumbs ##################################################################

class CWRelationIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('CWRelation')
    def parent_entity(self):
        return self.entity.rtype

class CWAttributeIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('CWAttribute')
    def parent_entity(self):
        return self.entity.stype

class CWConstraintIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('CWConstraint')
    def parent_entity(self):
        if self.entity.reverse_constrained_by:
            return self.entity.reverse_constrained_by[0]

class RQLExpressionIBreadCrumbsAdapter(ibreadcrumbs.IBreadCrumbsAdapter):
    __select__ = is_instance('RQLExpression')
    def parent_entity(self):
        return self.entity.expression_of


# misc: facets, actions ########################################################

class CWFinalFacet(facet.AttributeFacet):
    __regid__ = 'cwfinal-facet'
    __select__ = facet.AttributeFacet.__select__ & is_instance('CWEType', 'CWRType')
    rtype = 'final'


class ViewSchemaAction(action.Action):
    __regid__ = 'schema'
    __select__ = yes()

    title = _('data model schema')
    order = 30
    category = 'manage'

    def url(self):
        return self._cw.build_url(self.__regid__)
