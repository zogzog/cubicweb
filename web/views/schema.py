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
                                has_related_entities, anonymous_user)
from cubicweb.schema import (META_RTYPES, SCHEMA_TYPES, SYSTEM_RTYPES,
                             WORKFLOW_TYPES, INTERNAL_TYPES)
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.view import EntityView, StartupView
from cubicweb import tags, uilib
from cubicweb.web import action, facet, uicfg
from cubicweb.web.views import TmpFileViewMixin
from cubicweb.web.views import primary, baseviews, tabs, management, tableview

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

# global schema view ###########################################################

class SchemaView(tabs.TabsMixin, StartupView):
    __regid__ = 'schema'
    title = _('instance schema')
    tabs = [_('schema-text'), _('schema-image'), _('schema-security')]
    default_tab = 'schema-text'

    def call(self):
        """display schema information"""
        self._cw.add_js('cubicweb.ajax.js')
        self._cw.add_css(('cubicweb.schema.css','cubicweb.acl.css'))
        self.w(u'<h1>%s</h1>' % _('Schema of the data model'))
        self.render_tabs(self.tabs, self.default_tab)


class SchemaTabImageView(StartupView):
    __regid__ = 'schema-image'

    def call(self):
        self.w(_(u'<div>This schema of the data model <em>excludes</em> the '
                 u'meta-data, but you can also display a <a href="%s">complete '
                 u'schema with meta-data</a>.</div>')
               % xml_escape(self._cw.build_url('view', vid='schemagraph', skipmeta=0)))
        self.w(u'<img src="%s" alt="%s"/>\n' % (
            xml_escape(self._cw.build_url('view', vid='schemagraph', skipmeta=1)),
            self._cw._("graphical representation of the instance'schema")))


class SchemaTabTextView(StartupView):
    __regid__ = 'schema-text'

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


class SchemaPermissionsView(StartupView, management.SecurityViewMixIn):
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
        for access_type in rdef.ACTIONS:
            def_rqlexprs = []
            def_groups = []
            for perm in DEFAULT_ATTRPERMS[access_type]:
                if not isinstance(perm, basestring):
                    def_rqlexprs.append(perm.expression)
                else:
                    def_groups.append(perm)
            rqlexprs = [rql.expression for rql in rdef.get_rqlexprs(access_type)]
            groups = rdef.get_groups(access_type)
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
            self.schema_definition(eschema)
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
                    self.schema_definition(rdef)
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
            self.w(u'<div style="margin: 0px 1.5em">')
            for rdef in rschema.rdefs.itervalues():
                self.w(u'<h4 class="schema">%s %s %s</h4>' % (
                        rdef.subject, rschema, rdef.object))
                self.schema_definition(rdef)
            self.w(u'</div>')


# CWAttribute / CWRelation #####################################################

class CWRDEFPrimaryView(primary.PrimaryView):
    __select__ = implements('CWAttribute', 'CWRelation')
    cache_max_age = 60*60*2 # stawy in http cache for 2 hours by default

    def render_entity_title(self, entity):
        self.w(u'<h1><span class="etype">%s</span> %s</h1>'
               % (entity.dc_type().capitalize(),
                  xml_escape(entity.dc_long_title())))


class CWAttributeConstraints(EntityView):
    __regid__ = 'attr_constraints'
    __select__ = implements('CWAttribute')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        rschema = self._cw.vreg.schema.rschema(entity.rtype.name)
        rdef = rschema.rdefs[(entity.stype.name, entity.otype.name)]
        constraints = [xml_escape(str(c)) for c in getattr(rdef, 'constraints')]
        self.w(u', '.join(constraints))


class CWAttributeCellView(tableview.CellView):
    """display attribute name only in a cell view, link to
       cwattribute primary view"""
    __select__ = tableview.CellView.__select__ & implements('CWAttribute')

    def cell_call(self, row, col, cellvid=None):
        """display attribute name only in a cell view, link to
           cwattribute primary view"""
        etype, val = self.cw_rset.description[row][col], self.cw_rset[row][col]
        if val is not None and not self._cw.vreg.schema.eschema(etype).final:
            e = self.cw_rset.get_entity(row, col)
            if cellvid is not None and cellvid != 'incontext':
                self.wview(cellvid, e.as_rset(), 'null')
            else:
                desc = uilib.cut(e.dc_description(), 50)
                self.w(u'<a href="%s" title="%s">%s' % 
                       (xml_escape(e.absolute_url()) ,xml_escape(desc),
                        self.cell_content(e)))
                self.w(u'</a>')
        elif val is None:
            # This is usually caused by a left outer join and in that case,
            # regular views will most certainly fail if they don't have
            # a real eid
            self.wview('final', self.cw_rset, row=row, col=col)
        else:
            self.wview(cellvid or 'final', self.cw_rset, 'null', row=row, col=col)

    def cell_content(self, entity):
        return entity.relation_type[0].name


class CWRelationCellView(CWAttributeCellView):
    """display relation name and its translation only in a cell view, link to
       cwrelation primary view"""
    __select__ = tableview.CellView.__select__ & implements('CWRelation')

    def cell_content(self, entity):
        return u'%s (%s)' % (entity.relation_type[0].name,
                             self._cw._(entity.relation_type[0].name))

# CWEType ######################################################################

class CWETypeOneLineView(baseviews.OneLineView):
    __select__ = implements('CWEType')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        final = entity.final
        if final:
            self.w(u'<em class="finalentity">')
        super(CWETypeOneLineView, self).cell_call(row, col, **kwargs)
        if final:
            self.w(u'</em>')


class CWETypePrimaryView(tabs.TabbedPrimaryView):
    __select__ = implements('CWEType')
    tabs = [_('cwetype-text-tab'), _('cwetype-box-tab'), _('cwetype-workflow-tab'),
            _('cwetype-views-tab'), _('cwetype-perm-tab')]
    default_tab = 'cwetype-text-tab'


# register generated msgid
_('i18ncard_1'), _('i18ncard_?'), _('i18ncard_+'), _('i18ncard_*')

class CWETypeTextTab(tabs.PrimaryTab):
    __regid__ = 'cwetype-text-tab'
    __select__ = tabs.PrimaryTab.__select__ & implements('CWEType')

    def render_entity_attributes(self, entity, siderelations=None):
        self.w(u'<div>%s</div>' % xml_escape(entity.description or u''))
        # entity schema image
        url = entity.absolute_url(vid='schemagraph')
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(url),
            xml_escape(self._cw._('graphical schema for %s') % entity.name)))
        # entity schema attributes
        self.w(u'<h2>%s</h2>' % _('Attributes'))
        rset = self._cw.execute('Any A,F,DE,D,C, I,J,A '
                                'ORDERBY AA WHERE A is CWAttribute, '
                                'A ordernum AA, A defaultval D, '
                                'A description DE, A cardinality C, '
                                'A fulltextindexed I, A internationalizable J, '
                                'A relation_type R, R name N, '
                                'A to_entity O, O name F, '
                                'A from_entity S, S eid %(x)s',
                                {'x': entity.eid})
        self.wview('table', rset, 'null',
                   cellvids={4: 'attr_cardinality', 7: 'attr_constraints'},
                   headers=(_(u'name'), _(u'type'), _(u'description'),
                            _(u'default value'), _(u'required'),
                            _(u'fulltext indexed'), _(u'internationalizable'),
                            _(u'constraints')),
                   mainindex=0)
        # entity schema relations
        self.w(u'<h2>%s</h2>' % _('Relations'))
        rset = self._cw.execute(
            'Any A, TT, "i18ncard_"+SUBSTRING(C, 1, 1),K,D,A,RN,TTN ORDERBY RN '
            'WHERE A is CWRelation, A description D, A composite K, '
            'A relation_type R, R name RN, A to_entity TT, TT name TTN, '
            'A cardinality C, A from_entity S, S eid %(x)s',
            {'x': entity.eid})
        if rset:
            self.w(u'<h5>%s %s</h5>' % (entity.name, _('is subject of:')))
        self.wview('table', rset, 'null',
                   cellvids={2: 'entity_relation_cardinality',},
                   headers=(_(u'name'), _(u'object type'), _(u'cardinality'),
                            _(u'composite'), _(u'description'),
                            _(u'relation direction')),
                   displaycols=range(5), mainindex=0)
        self.w(u'<br/>')
        rset = self._cw.execute(
            'Any A, TT, "i18ncard_"+SUBSTRING(C, 2, 1),K,D,A,RN,TTN ORDERBY RN '
            'WHERE A is CWRelation, A description D, A composite K, '
            'A relation_type R, R name RN, A from_entity TT, TT name TTN, '
            'A cardinality C, A to_entity O, O eid %(x)s',
            {'x': entity.eid})
        if rset:
            self.w(u'<h5>%s %s</h5>' % (entity.name, _('is object of:')))
        self.wview('table', rset, 'null',
                   cellvids={2: 'entity_relation_cardinality',},
                   headers=(_(u'name'), _(u'subject type'), _(u'cardinality'),
                            _(u'composite'), _(u'description'),
                            _(u'relation direction')),
                   displaycols=range(5), mainindex=0)


class CWETypePermTab(EntityView, management.SecurityViewMixIn):
    __regid__ = 'cwetype-perm-tab'
    __select__ = EntityView.__select__ & implements('CWEType') & ~anonymous_user()

    def cell_call(self, row, col):
        self._cw.add_css('cubicweb.acl.css')
        entity = self.cw_rset.get_entity(row, col)
        eschema = self._cw.vreg.schema.eschema(entity.name)
        self.w(u'<a id="%s" href="cwetype/%s">' %  (eschema.type, eschema.type))
        self.w(u'<h3 class="schema">%s (%s) ' % (eschema.type, _(eschema.type)))
        self.w(u'</h3></a>')
        self.w(u'<div style="margin: 0px 1.5em">')
        self.schema_definition(eschema)
        # display entity attributes only if they have some permissions modified
        modified_attrs = []
        self.w(u'<h4>%s</h4>' % _('attributes permissions:').capitalize())
        for attr, etype in  eschema.attribute_definitions():
            if attr not in META_RTYPES:
                rdef = eschema.rdef(attr)
                attrtype = str(rdef.rtype)
                self.w(u'<h4 class="schema">%s (%s)</h4> ' % (attrtype, _(attrtype)))
                self.schema_definition(rdef, link=False)
        self.w(u'</div>')


class CWETypeWorkflowTab(EntityView):
    __regid__ = 'cwetype-workflow-tab'
    __select__ = (EntityView.__select__ & implements('CWEType') &
                  has_related_entities('workflow_of', 'object'))

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


class CWETypeBoxTab(EntityView):
    __regid__ = 'cwetype-box-tab'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        viewer = SchemaViewer(self._cw)
        entity = self.cw_rset.get_entity(row, col)
        eschema = self._cw.vreg.schema.eschema(entity.name)
        layout = viewer.visit_entityschema(eschema)
        self.w(uilib.ureport_as_html(layout))
        self.w(u'<br class="clear"/>')


class CWETypeViewsTab(EntityView):
    __regid__ = 'cwetype-views-tab'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        etype = entity.name
        _ = self._cw._
        # possible views for this entity type
        views = [(_(view.title),) for view in self.possible_views(etype)]
        self.wview('pyvaltable', pyvalue=views, headers=(_(u'views'),))

    def possible_views(self, etype):
        rset = self._cw.etype_rset(etype)
        return [v for v in self._cw.vreg['views'].possible_views(self._cw, rset)
                if v.category != 'startupview']


# CWRType ######################################################################

class CWRTypeSchemaView(primary.PrimaryView):
    __select__ = implements('CWRType')
    title = _('in memory relation schema')
    main_related_section = False

    def render_entity_attributes(self, entity):
        super(CWRTypeSchemaView, self).render_entity_attributes(entity)
        rschema = self._cw.vreg.schema.rschema(entity.name)
        viewer = SchemaViewer(self._cw)
        layout = viewer.visit_relationschema(rschema, title=False)
        self.w(uilib.ureport_as_html(layout))
        if not rschema.final:
            msg = self._cw._('graphical schema for %s') % entity.name
            self.w(tags.img(src=entity.absolute_url(vid='schemagraph'),
                            alt=msg))

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


# final views #################################################################

class CardinalityRequiredCellView(baseviews.FinalView):
    __regid__ = 'attr_cardinality'

    def cell_call(self, row, col):
        value = self.cw_rset.rows[row][col]
        if value is not None and value[0] == '1':
            self.w(self._cw._(u'required'))

class I18NCardinalityCellView(baseviews.FinalView):
    __regid__ = 'entity_relation_cardinality'

    def cell_call(self, row, col):
        value = self.cw_rset.rows[row][col]
        if value is not None:
            self.w(self._cw._(value))


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
