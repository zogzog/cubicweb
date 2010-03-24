"""Specific views for schema related entities

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from itertools import cycle

from logilab.mtconverter import xml_escape
from yams import BASE_TYPES, schema2dot as s2d

from cubicweb.selectors import (implements, yes, match_user_groups,
                                has_related_entities)
from cubicweb.schema import (META_RTYPES, SCHEMA_TYPES, SYSTEM_RTYPES,
                             WORKFLOW_TYPES, INTERNAL_TYPES)
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.view import EntityView, StartupView
from cubicweb import tags, uilib
from cubicweb.web import action, facet, uicfg
from cubicweb.web.views import TmpFileViewMixin
from cubicweb.web.views import primary, baseviews, tabs, management

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
    tabs = [_('schema-text'), _('schema-image')]
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


class ManagerSchemaPermissionsView(StartupView, management.SecurityViewMixIn):
    __regid__ = 'schema-security'
    __select__ = StartupView.__select__ & match_user_groups('managers')

    def call(self, display_relations=True):
        self._cw.add_css('cubicweb.acl.css')
        skiptypes = skip_types(self._cw)
        formparams = {}
        formparams['sec'] = self.__regid__
        if not skiptypes:
            formparams['skipmeta'] = u'0'
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
        self.w(u'<div id="schema_security"><a id="index" href="index"/>')
        self.w(u'<h2 class="schema">%s</h2>' % _('index').capitalize())
        self.w(u'<h4>%s</h4>' %   _('Entities').capitalize())
        ents = []
        for eschema in sorted(entities):
            url = xml_escape(self._cw.build_url('schema', **formparams))
            ents.append(u'<a class="grey" href="%s#%s">%s</a> (%s)' % (
                url,  eschema.type, eschema.type, _(eschema.type)))
        self.w(u', '.join(ents))
        self.w(u'<h4>%s</h4>' % (_('relations').capitalize()))
        rels = []
        for rschema in sorted(relations):
            url = xml_escape(self._cw.build_url('schema', **formparams))
            rels.append(u'<a class="grey" href="%s#%s">%s</a> (%s), ' %  (
                url , rschema.type, rschema.type, _(rschema.type)))
        self.w(u', '.join(ents))
        # entities
        self.display_entities(entities, formparams)
        # relations
        if relations:
            self.display_relations(relations, formparams)
        self.w(u'</div>')

    def display_entities(self, entities, formparams):
        _ = self._cw._
        self.w(u'<a id="entities" href="entities"/>')
        self.w(u'<h2 class="schema">%s</h2>' % _('permissions for entities').capitalize())
        for eschema in entities:
            self.w(u'<a id="%s" href="%s"/>' %  (eschema.type, eschema.type))
            self.w(u'<h3 class="schema">%s (%s) ' % (eschema.type, _(eschema.type)))
            url = xml_escape(self._cw.build_url('schema', **formparams) + '#index')
            self.w(u'<a href="%s"><img src="%s" alt="%s"/></a>' % (
                url,  self._cw.external_resource('UP_ICON'), _('up')))
            self.w(u'</h3>')
            self.w(u'<div style="margin: 0px 1.5em">')
            self._cw.vreg.schema_definition(eschema, link=False)
            # display entity attributes only if they have some permissions modified
            modified_attrs = []
            for attr, etype in  eschema.attribute_definitions():
                if self.has_schema_modified_permissions(attr, attr.ACTIONS):
                    modified_attrs.append(attr)
            if  modified_attrs:
                self.w(u'<h4>%s</h4>' % _('attributes with modified permissions:').capitalize())
                self.w(u'</div>')
                self.w(u'<div style="margin: 0px 6em">')
                for attr in  modified_attrs:
                    self.w(u'<h4 class="schema">%s (%s)</h4> ' % (attr.type, _(attr.type)))
                    self._cw.vreg.schema_definition(attr, link=False)
            self.w(u'</div>')

    def display_relations(self, relations, formparams):
        _ = self._cw._
        self.w(u'<a id="relations" href="relations"/>')
        self.w(u'<h2 class="schema">%s </h2>' % _('permissions for relations').capitalize())
        for rschema in relations:
            self.w(u'<a id="%s" href="%s"/>' %  (rschema.type, rschema.type))
            self.w(u'<h3 class="schema">%s (%s) ' % (rschema.type, _(rschema.type)))
            url = xml_escape(self._cw.build_url('schema', **formparams) + '#index')
            self.w(u'<a href="%s"><img src="%s" alt="%s"/></a>' % (
                url,  self._cw.external_resource('UP_ICON'), _('up')))
            self.w(u'</h3>')
            self.w(u'<div style="margin: 0px 1.5em">')
            subjects = [str(subj) for subj in rschema.subjects()]
            self.w(u'<div><strong>%s</strong> %s (%s)</div>' % (
                _('subject_plural:'),
                ', '.join(str(subj) for subj in rschema.subjects()),
                ', '.join(_(str(subj)) for subj in rschema.subjects())))
            self.w(u'<div><strong>%s</strong> %s (%s)</div>' % (
                _('object_plural:'),
                ', '.join(str(obj) for obj in rschema.objects()),
                ', '.join(_(str(obj)) for obj in rschema.objects())))
            self._cw.vreg.schema_definition(rschema, link=False)
            self.w(u'</div>')


class SchemaUreportsView(StartupView):
    __regid__ = 'schema-block'

    def call(self):
        viewer = SchemaViewer(self._cw)
        layout = viewer.visit_schema(self._cw.vreg.schema, display_relations=True,
                                     skiptypes=skip_types(self._cw))
        self.w(uilib.ureport_as_html(layout))


# CWAttribute / CWRelation #####################################################

class CWRDEFPrimaryView(primary.PrimaryView):
    __select__ = implements('CWAttribute', 'CWRelation')
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default

    def render_entity_title(self, entity):
        self.w(u'<h1><span class="etype">%s</span> %s</h1>'
               % (entity.dc_type().capitalize(),
                  xml_escape(entity.dc_long_title())))


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


class CWETypePrimaryView(tabs.TabsMixin, primary.PrimaryView):
    __select__ = implements('CWEType')
    title = _('in memory entity schema')
    main_related_section = False
    tabs = [_('cwetype-schema-text'), _('cwetype-schema-image'),
            _('cwetype-schema-permissions'), _('cwetype-workflow')]
    default_tab = 'cwetype-schema-text'

    def render_entity(self, entity):
        self.render_entity_title(entity)
        self.w(u'<div>%s</div>' % entity.description)
        self.render_tabs(self.tabs, self.default_tab, entity)


class CWETypeSTextView(EntityView):
    __regid__ = 'cwetype-schema-text'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        self.w(u'<h2>%s</h2>' % _('Attributes'))
        rset = self._cw.execute('Any N,F,D,I,J,DE,A '
                                'ORDERBY AA WHERE A is CWAttribute, '
                                'A ordernum AA, A defaultval D, '
                                'A description DE, '
                                'A fulltextindexed I, A internationalizable J, '
                                'A relation_type R, R name N, '
                                'A to_entity O, O name F, '
                                'A from_entity S, S eid %(x)s',
                                {'x': entity.eid})
        self.wview('editable-table', rset, 'null', displayfilter=True)
        self.w(u'<h2>%s</h2>' % _('Relations'))
        rset = self._cw.execute(
            'Any R,C,TT,K,D,A,RN,TTN ORDERBY RN '
            'WHERE A is CWRelation, A description D, A composite K, '
            'A relation_type R, R name RN, A to_entity TT, TT name TTN, '
            'A cardinality C, A from_entity S, S eid %(x)s',
            {'x': entity.eid})
        self.wview('editable-table', rset, 'null', displayfilter=True,
                   displaycols=range(6), mainindex=5)
        rset = self._cw.execute(
            'Any R,C,TT,K,D,A,RN,TTN ORDERBY RN '
            'WHERE A is CWRelation, A description D, A composite K, '
            'A relation_type R, R name RN, A from_entity TT, TT name TTN, '
            'A cardinality C, A to_entity O, O eid %(x)s',
            {'x': entity.eid})
        self.wview('editable-table', rset, 'null', displayfilter=True,
                   displaycols=range(6), mainindex=5)


class CWETypeSImageView(EntityView):
    __regid__ = 'cwetype-schema-image'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        url = entity.absolute_url(vid='schemagraph')
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(url),
            xml_escape(self._cw._('graphical schema for %s') % entity.name)))


class CWETypeSPermView(EntityView):
    __regid__ = 'cwetype-schema-permissions'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        _ = self._cw._
        self.w(u'<h2>%s</h2>' % _('Add permissions'))
        rset = self._cw.execute('Any P WHERE X add_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')
        self.w(u'<h2>%s</h2>' % _('Read permissions'))
        rset = self._cw.execute('Any P WHERE X read_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')
        self.w(u'<h2>%s</h2>' % _('Update permissions'))
        rset = self._cw.execute('Any P WHERE X update_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')
        self.w(u'<h2>%s</h2>' % _('Delete permissions'))
        rset = self._cw.execute('Any P WHERE X delete_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')


class CWETypeSWorkflowView(EntityView):
    __regid__ = 'cwetype-workflow'
    __select__ = (EntityView.__select__ & implements('CWEType') &
                  has_related_entities('workflow_of', 'object'))

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        if entity.default_workflow:
            wf = entity.default_workflow[0]
            self.w(u'<h1>%s (%s)</h1>' % (wf.name, self._cw._('default')))
            self.wf_image(wf)
        for altwf in entity.reverse_workflow_of:
            if altwf.eid == wf.eid:
                continue
            self.w(u'<h1>%s</h1>' % altwf.name)
            self.wf_image(altwf)

    def wf_image(self, wf):
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(wf.absolute_url(vid='wfgraph')),
            xml_escape(self._cw._('graphical representation of %s') % wf.name)))


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
