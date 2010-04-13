"""Specific views for schema related entities

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from itertools import cycle

from logilab.common.ureports import Section, Table
from logilab.mtconverter import xml_escape
from yams import BASE_TYPES, schema2dot as s2d
from yams.buildobjs import DEFAULT_ATTRPERMS

from cubicweb.selectors import (implements, yes, match_user_groups,
                                has_related_entities, authenticated_user)
from cubicweb.schema import (META_RTYPES, SCHEMA_TYPES, SYSTEM_RTYPES,
                             WORKFLOW_TYPES, INTERNAL_TYPES)
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.view import EntityView, StartupView
from cubicweb import tags, uilib
from cubicweb.web import action, facet, uicfg
from cubicweb.web.views import TmpFileViewMixin
from cubicweb.web.views import primary, baseviews, tabs, tableview, iprogress

ALWAYS_SKIP_TYPES = BASE_TYPES | SCHEMA_TYPES
SKIP_TYPES  = (ALWAYS_SKIP_TYPES | META_RTYPES | SYSTEM_RTYPES | WORKFLOW_TYPES
               | INTERNAL_TYPES)
SKIP_TYPES.update(set(('CWUser', 'CWGroup')))

def skip_types(req):
    if int(req.form.get('skipmeta', True)):
        return SKIP_TYPES
    return ALWAYS_SKIP_TYPES

_pvs = uicfg.primaryview_section
for _action in ('read', 'add', 'update', 'delete'):
    _pvs.tag_subject_of(('*', '%s_permission' % _action, '*'), 'hidden')
    _pvs.tag_object_of(('*', '%s_permission' % _action, '*'), 'hidden')

_pvs.tag_object_of(('Workflow', 'workflow_of', 'CWEType'), 'hidden')
_pvs.tag_subject_of(('CWEType', 'default_workflow', 'Workflow'), 'hidden')

_pvs.tag_object_of(('*', 'relation_type', 'CWRType'), 'hidden')

class SecurityViewMixIn(object):
    """mixin providing methods to display security information for a entity,
    relation or relation definition schema
    """

    def permissions_table(self, erschema, permissions=None):
        self._cw.add_css('cubicweb.acl.css')
        w = self.w
        _ = self._cw._
        w(u'<table class="schemaInfo">')
        w(u'<tr><th>%s</th><th>%s</th><th>%s</th></tr>' % (
            _("permission"), _('granted to groups'), _('rql expressions')))
        for action in erschema.ACTIONS:
            w(u'<tr><td>%s</td><td>' % _(action))
            if permissions is None:
                groups = erschema.get_groups(action)
            else:
                groups = permissions[action][0]
            # XXX get group entity and call it's incontext view
            groups = [u'<a class="%s" href="%s">%s</a>' % (
                group, self._cw.build_url('cwgroup/%s' % group), label)
                      for group, label in sorted((_(g), g) for g in groups)]
            w(u'<br/>'.join(groups))
            w(u'</td><td>')
            if permissions is None:
                rqlexprs = sorted(e.expression for e in erschema.get_rqlexprs(action))
            else:
                rqlexprs = permissions[action][1]
            w(u'<br/>'.join(rqlexprs))
            w(u'</td></tr>\n')
        w(u'</table>')

    def grouped_permissions_table(self, rschema):
        # group relation definitions with identical permissions
        perms = {}
        for rdef in rschema.rdefs.itervalues():
            rdef_perms = []
            for action in ('read', 'add', 'delete'):
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
        w(u'<div style="margin: 0px 1.5em">')
        tmpl = u'<strong>%s</strong> %s <strong>%s</strong>'
        for perm, rdefs in perms.iteritems():
            w(u'<div>%s</div>' % u', '.join(
                tmpl % (_(s.type), _(rschema.type), _(o.type)) for s, o in rdefs))
            # accessing rdef from previous loop by design: only used to get
            # ACTIONS
            self.permissions_table(rdef, dict(perm))
        w(u'</div>')


# global schema view ###########################################################

class SchemaView(tabs.TabsMixin, StartupView):
    __regid__ = 'schema'
    title = _('instance schema')
    tabs = [_('schema-description'), _('schema-image'), _('schema-security')]
    default_tab = 'schema-description'

    def call(self):
        """display schema information"""
        self.w(u'<h1>%s</h1>' % _('Schema of the data model'))
        self.render_tabs(self.tabs, self.default_tab)


class SchemaImageTab(StartupView):
    __regid__ = 'schema-image'

    def call(self):
        self.w(_(u'<div>This schema of the data model <em>excludes</em> the '
                 u'meta-data, but you can also display a <a href="%s">complete '
                 u'schema with meta-data</a>.</div>')
               % xml_escape(self._cw.build_url('view', vid='schemagraph', skipmeta=0)))
        self.w(u'<img src="%s" alt="%s"/>\n' % (
            xml_escape(self._cw.build_url('view', vid='schemagraph', skipmeta=1)),
            self._cw._("graphical representation of the instance'schema")))


class SchemaDescriptionTab(StartupView):
    __regid__ = 'schema-description'

    def call(self):
        rset = self._cw.execute('Any X ORDERBY N WHERE X is CWEType, X name N, '
                                'X final FALSE')
        self.wview('table', rset, displayfilter=True)
        rset = self._cw.execute('Any X ORDERBY N WHERE X is CWRType, X name N, '
                                'X final FALSE')
        self.wview('table', rset, displayfilter=True)
        owl_downloadurl = self._cw.build_url('view', vid='owl')
        self.w(u'<div><a href="%s">%s</a></div>' %
               (owl_downloadurl, self._cw._(u'Download schema as OWL')))


class SchemaPermissionsTab(SecurityViewMixIn, StartupView):
    __regid__ = 'schema-security'
    __select__ = StartupView.__select__ & match_user_groups('managers')

    def call(self, display_relations=True):
        self._cw.add_css('cubicweb.acl.css')
        skiptypes = skip_types(self._cw)
        schema = self._cw.vreg.schema
        # compute entities
        entities = sorted(eschema for eschema in schema.entities()
                          if not (eschema.final or eschema in skiptypes))
        # compute relations
        if display_relations:
            relations = sorted(rschema for rschema in schema.relations()
                               if not (rschema.final
                                       or rschema in skiptypes
                                       or rschema in META_RTYPES))
        else:
            relations = []
        # index
        _ = self._cw._
        url = xml_escape(self._cw.build_url('schema'))
        self.w(u'<div id="schema_security">')
        self.w(u'<h2 class="schema">%s</h2>' % _('Index'))
        self.w(u'<h4 id="entities">%s</h4>' % _('Entity types'))
        ents = []
        for eschema in sorted(entities):
            ents.append(u'<a class="grey" href="%s#%s">%s</a>' % (
                url,  eschema.type, eschema.type))
        self.w(u', '.join(ents))
        self.w(u'<h4 id="relations">%s</h4>' % _('Relation types'))
        rels = []
        for rschema in sorted(relations):
            rels.append(u'<a class="grey" href="%s#%s">%s</a>' %  (
                url , rschema.type, rschema.type))
        self.w(u', '.join(rels))
        # permissions tables
        self.display_entities(entities)
        if relations:
            self.display_relations(relations)
        self.w(u'</div>')

    def has_non_default_perms(self, rdef):
        """return true if the given *attribute* relation definition has custom
        permission
        """
        for action in rdef.ACTIONS:
            def_rqlexprs = []
            def_groups = []
            for perm in DEFAULT_ATTRPERMS[action]:
                if not isinstance(perm, basestring):
                    def_rqlexprs.append(perm.expression)
                else:
                    def_groups.append(perm)
            rqlexprs = [rql.expression for rql in rdef.get_rqlexprs(action)]
            groups = rdef.get_groups(action)
            if groups != frozenset(def_groups) or \
                frozenset(rqlexprs) != frozenset(def_rqlexprs):
                return True
        return False

    def display_entities(self, entities):
        _ = self._cw._
        url = xml_escape(self._cw.build_url('schema'))
        self.w(u'<h2 id="entities" class="schema">%s</h2>' % _('Permissions for entity types'))
        for eschema in entities:
            self.w(u'<h3 id="%s" class="schema"><a href="%s">%s (%s)</a> ' % (
                eschema.type, self._cw.build_url('cwetype/%s' % eschema.type),
                eschema.type, _(eschema.type)))
            self.w(u'<a href="%s#schema_security"><img src="%s" alt="%s"/></a>' % (
                url,  self._cw.external_resource('UP_ICON'), _('up')))
            self.w(u'</h3>')
            self.w(u'<div style="margin: 0px 1.5em">')
            self.permissions_table(eschema)
            # display entity attributes only if they have some permissions modified
            modified_attrs = []
            for attr, etype in  eschema.attribute_definitions():
                rdef = eschema.rdef(attr)
                if attr not in META_RTYPES and self.has_non_default_perms(rdef):
                    modified_attrs.append(rdef)
            if modified_attrs:
                self.w(u'<h4>%s</h4>' % _('Attributes with non default permissions:'))
                self.w(u'</div>')
                self.w(u'<div style="margin: 0px 6em">')
                for rdef in modified_attrs:
                    attrtype = str(rdef.rtype)
                    self.w(u'<h4 class="schema">%s (%s)</h4> ' % (attrtype, _(attrtype)))
                    self.permissions_table(rdef)
            self.w(u'</div>')

    def display_relations(self, relations):
        _ = self._cw._
        url = xml_escape(self._cw.build_url('schema'))
        self.w(u'<h2 id="relations" class="schema">%s</h2>' % _('Permissions for relations'))
        for rschema in relations:
            self.w(u'<h3 id="%s" class="schema"><a href="%s">%s (%s)</a> ' % (
                rschema.type, self._cw.build_url('cwrtype/%s' % rschema.type),
                rschema.type, _(rschema.type)))
            self.w(u'<a href="%s#schema_security"><img src="%s" alt="%s"/></a>' % (
                url,  self._cw.external_resource('UP_ICON'), _('up')))
            self.w(u'</h3>')
            self.grouped_permissions_table(rschema)


# CWEType ######################################################################

# register msgid generated in entity relations tables
_('i18ncard_1'), _('i18ncard_?'), _('i18ncard_+'), _('i18ncard_*')

class CWETypePrimaryView(tabs.TabbedPrimaryView):
    __select__ = implements('CWEType')
    tabs = [_('cwetype-description'), _('cwetype-box'), _('cwetype-workflow'),
            _('cwetype-views'), _('cwetype-permissions')]
    default_tab = 'cwetype-description'


class CWETypeDescriptionTab(tabs.PrimaryTab):
    __regid__ = 'cwetype-description'
    __select__ = tabs.PrimaryTab.__select__ & implements('CWEType')

    def render_entity_attributes(self, entity, siderelations=None):
        _ = self._cw._
        self.w(u'<div>%s</div>' % xml_escape(entity.description or u''))
        # entity schema image
        url = entity.absolute_url(vid='schemagraph')
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(url),
            xml_escape(_('graphical schema for %s') % entity.name)))
        # entity schema attributes
        self.w(u'<h2>%s</h2>' % _('Attributes'))
        rset = self._cw.execute(
            'Any A,F,D,C,I,J,A,DE ORDERBY AA WHERE A is CWAttribute, '
            'A ordernum AA, A defaultval D, A description DE, A cardinality C, '
            'A fulltextindexed I, A internationalizable J, '
            'A relation_type R, R name N, A to_entity O, O name F, '
            'A from_entity S, S eid %(x)s',
            {'x': entity.eid})
        self.wview('table', rset, 'null',
                   cellvids={0: 'rdef-name-cell',
                             3: 'etype-attr-cardinality-cell',
                             6: 'rdef-constraints-cell'},
                   headers=(_(u'name'), _(u'type'),
                            _(u'default value'), _(u'required'),
                            _(u'fulltext indexed'), _(u'internationalizable'),
                            _(u'constraints'), _(u'description')),
                   mainindex=0)
        # entity schema relations
        self.w(u'<h2>%s</h2>' % _('Relations'))
        rset = self._cw.execute(
            'Any A,TT,"i18ncard_"+SUBSTRING(C, 1, 1),K,A,TTN ORDERBY RN '
            'WHERE A is CWRelation, A composite K, A cardinality C, '
            'A relation_type R, R name RN, '
            'A to_entity TT, TT name TTN, A from_entity S, S eid %(x)s',
            {'x': entity.eid})
        if rset:
            self.w(u'<h5>%s %s</h5>' % (entity.name, _('is subject of:')))
        self.wview('table', rset, 'null',
                   cellvids={0: 'rdef-name-cell',
                             2: 'etype-rel-cardinality-cell',
                             4: 'rdef-constraints-cell'},
                   headers=(_(u'name'), _(u'object type'), _(u'cardinality'),
                            _(u'composite'), _(u'constraints')),
                   displaycols=range(5))
        self.w(u'<br/>')
        rset = self._cw.execute(
            'Any A,TT,"i18ncard_"+SUBSTRING(C, 2, 1),K,A,TTN ORDERBY RN '
            'WHERE A is CWRelation, A composite K, A cardinality C, '
            'A relation_type R, R name RN, '
            'A from_entity TT, TT name TTN, A to_entity O, O eid %(x)s',
            {'x': entity.eid})
        if rset:
            self.w(u'<h5>%s %s</h5>' % (entity.name, _('is object of:')))
        self.wview('table', rset, 'null',
                   cellvids={0: 'rdef-object-name-cell',
                             2: 'etype-rel-cardinality-cell',
                             4: 'rdef-constraints-cell'},
                   headers=(_(u'name'), _(u'subject type'), _(u'cardinality'),
                            _(u'composite'), _(u'constraints')),
                   displaycols=range(5))


class CWETypeAttributeCardinalityCell(baseviews.FinalView):
    __regid__ = 'etype-attr-cardinality-cell'

    def cell_call(self, row, col):
        if self.cw_rset.rows[row][col][0] == '1':
            self.w(self._cw._(u'yes'))
        else:
            self.w(self._cw._(u'no'))


class CWETypeRelationCardinalityCell(baseviews.FinalView):
    __regid__ = 'etype-rel-cardinality-cell'

    def cell_call(self, row, col):
        self.w(self._cw._(self.cw_rset.rows[row][col]))


class CWETypeBoxTab(EntityView):
    __regid__ = 'cwetype-box'
    __select__ = implements('CWEType')

    def cell_call(self, row, col):
        viewer = SchemaViewer(self._cw)
        entity = self.cw_rset.get_entity(row, col)
        eschema = self._cw.vreg.schema.eschema(entity.name)
        layout = viewer.visit_entityschema(eschema)
        self.w(uilib.ureport_as_html(layout))
        self.w(u'<br class="clear"/>')


class CWETypePermTab(SecurityViewMixIn, EntityView):
    __regid__ = 'cwetype-permissions'
    __select__ = implements('CWEType') & authenticated_user()

    def cell_call(self, row, col):
        self._cw.add_css('cubicweb.acl.css')
        entity = self.cw_rset.get_entity(row, col)
        eschema = self._cw.vreg.schema.eschema(entity.name)
        self.w(u'<div style="margin: 0px 1.5em">')
        self.permissions_table(eschema)
        self.w(u'<h4>%s</h4>' % _('attributes permissions:').capitalize())
        for attr, etype in  eschema.attribute_definitions():
            if attr not in META_RTYPES:
                rdef = eschema.rdef(attr)
                attrtype = str(rdef.rtype)
                self.w(u'<h4 class="schema">%s (%s)</h4> ' % (attrtype, _(attrtype)))
                self.permissions_table(rdef)
        self.w(u'</div>')


class CWETypeWorkflowTab(EntityView):
    __regid__ = 'cwetype-workflow'
    __select__ = (implements('CWEType')
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
    __regid__ = 'cwetype-views'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        etype = entity.name
        _ = self._cw._
        # possible views for this entity type
        views = [(_(view.title),) for view in self.possible_views(etype)]
        self.wview('pyvaltable', pyvalue=sorted(views), headers=(_(u'views'),))

    def possible_views(self, etype):
        rset = self._cw.etype_rset(etype)
        return [v for v in self._cw.vreg['views'].possible_views(self._cw, rset)
                if v.category != 'startupview']


class CWETypeOneLineView(baseviews.OneLineView):
    __select__ = implements('CWEType')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        if entity.final:
            self.w(u'<em class="finalentity">')
        super(CWETypeOneLineView, self).cell_call(row, col, **kwargs)
        if entity.final:
            self.w(u'</em>')


# CWRType ######################################################################

class CWRTypePrimaryView(tabs.TabbedPrimaryView):
    __select__ = implements('CWRType')
    tabs = [_('cwrtype-description'), _('cwrtype-permissions')]
    default_tab = 'cwrtype-description'


class CWRTypeDescriptionTab(tabs.PrimaryTab):
    __regid__ = 'cwrtype-description'
    __select__ = implements('CWRType')

    def render_entity_attributes(self, entity, siderelations=None):
        _ = self._cw._
        self.w(u'<div>%s</div>' % xml_escape(entity.description or u''))
        rschema = self._cw.vreg.schema.rschema(entity.name)
        if not rschema.final:
            msg = _('graphical schema for %s') % entity.name
            self.w(tags.img(src=entity.absolute_url(vid='schemagraph'),
                            alt=msg))
        rset = self._cw.execute('Any R,C,CC,R WHERE R is CWRelation, '
                                'R relation_type RT, RT eid %(x)s, '
                                'R cardinality C, R composite CC',
                                {'x': entity.eid})
        self.wview('table', rset, 'null',
                   headers=(_(u'relation'),  _(u'cardinality'), _(u'composite'),
                            _(u'constraints')),
                   cellvids={3: 'rdef-constraints-cell'})


class CWRTypePermTab(SecurityViewMixIn, EntityView):
    __regid__ = 'cwrtype-permissions'
    __select__ = implements('CWRType') & authenticated_user()

    def cell_call(self, row, col):
        self._cw.add_css('cubicweb.acl.css')
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema.rschema(entity.name)
        self.grouped_permissions_table(rschema)


# CWAttribute / CWRelation #####################################################

class CWRDEFPrimaryView(tabs.TabbedPrimaryView):
    __select__ = implements('CWRelation', 'CWAttribute')
    tabs = [_('cwrdef-description'), _('cwrdef-permissions')]
    default_tab = 'cwrdef-description'

class CWRDEFDescriptionTab(tabs.PrimaryTab):
    __regid__ = 'cwrdef-description'
    __select__ = implements('CWRelation', 'CWAttribute')

class CWRDEFPermTab(SecurityViewMixIn, EntityView):
    __regid__ = 'cwrdef-permissions'
    __select__ = implements('CWRelation', 'CWAttribute') & authenticated_user()

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema.rschema(entity.rtype.name)
        rdef = rschema.rdefs[(entity.stype.name, entity.otype.name)]
        self.permissions_table(rdef)


class CWRDEFNameView(tableview.CellView):
    """display relation name and its translation only in a cell view, link to
    relation definition's primary view (for use in entity type relations table
    for instance)
    """
    __regid__ = 'rdef-name-cell'
    __select__ = implements('CWRelation', 'CWAttribute')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rtype = entity.relation_type[0].name
        # XXX use contect entity + pgettext
        self.w(u'<a href="%s">%s</a> (%s)' % (
            entity.absolute_url(), rtype, self._cw._(rtype)))

class CWRDEFObjectNameView(tableview.CellView):
    """same as CWRDEFNameView but when the context is the object entity
    """
    __regid__ = 'rdef-object-name-cell'
    __select__ = implements('CWRelation', 'CWAttribute')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rtype = entity.relation_type[0].name
        # XXX use contect entity + pgettext
        self.w(u'<a href="%s">%s</a> (%s)' % (
            entity.absolute_url(), rtype, self._cw.__(rtype + '_object')))

class CWRDEFConstraintsCell(EntityView):
    __regid__ = 'rdef-constraints-cell'
    __select__ = implements('CWAttribute', 'CWRelation')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema.rschema(entity.rtype.name)
        rdef = rschema.rdefs[(entity.stype.name, entity.otype.name)]
        constraints = [xml_escape(str(c)) for c in getattr(rdef, 'constraints')]
        self.w(u'<br/>'.join(constraints))


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


class SchemaImageView(TmpFileViewMixin, StartupView):
    __regid__ = 'schemagraph'
    content_type = 'image/png'

    def _generate(self, tmpfile):
        """display global schema information"""
        visitor = FullSchemaVisitor(self._cw, self._cw.vreg.schema,
                                    skiptypes=skip_types(self._cw))
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor)


class CWETypeSchemaImageView(TmpFileViewMixin, EntityView):
    __regid__ = 'schemagraph'
    __select__ = implements('CWEType')
    content_type = 'image/png'

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.cw_rset.get_entity(self.cw_row, self.cw_col)
        eschema = self._cw.vreg.schema.eschema(entity.name)
        visitor = OneHopESchemaVisitor(self._cw, eschema,
                                       skiptypes=skip_types(self._cw))
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor)


class CWRTypeSchemaImageView(CWETypeSchemaImageView):
    __select__ = implements('CWRType')

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.cw_rset.get_entity(self.cw_row, self.cw_col)
        rschema = self._cw.vreg.schema.rschema(entity.name)
        visitor = OneHopRSchemaVisitor(self._cw, rschema)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor)


# misc: facets, actions ########################################################

class CWFinalFacet(facet.AttributeFacet):
    __regid__ = 'cwfinal-facet'
    __select__ = facet.AttributeFacet.__select__ & implements('CWEType', 'CWRType')
    rtype = 'final'

class ViewSchemaAction(action.Action):
    __regid__ = 'schema'
    __select__ = yes()

    title = _("site schema")
    category = 'siteactions'
    order = 30

    def url(self):
        return self._cw.build_url(self.__regid__)
