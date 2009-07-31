"""Specific views for schema related entities

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from itertools import cycle

from logilab.mtconverter import xml_escape
from yams import BASE_TYPES, schema2dot as s2d

from cubicweb.selectors import implements, yes, match_user_groups
from cubicweb.schema import META_RTYPES, SCHEMA_TYPES
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.view import EntityView, StartupView
from cubicweb.common import tags, uilib
from cubicweb.web import action, facet
from cubicweb.web.views import TmpFileViewMixin
from cubicweb.web.views import primary, baseviews, tabs, management

ALWAYS_SKIP_TYPES = BASE_TYPES | SCHEMA_TYPES
SKIP_TYPES = ALWAYS_SKIP_TYPES | META_RTYPES
SKIP_TYPES.update(set(('Transition', 'State', 'TrInfo',
                       'CWUser', 'CWGroup',
                       'CWCache', 'CWProperty', 'CWPermission',
                       'ExternalUri')))

def skip_types(req):
    if int(req.form.get('skipmeta', True)):
        return SKIP_TYPES
    return ALWAYS_SKIP_TYPES

# global schema view ###########################################################

class SchemaView(tabs.TabsMixin, StartupView):
    id = 'schema'
    title = _('instance schema')
    tabs = [_('schema-text'), _('schema-image')]
    default_tab = 'schema-text'

    def call(self):
        """display schema information"""
        self.req.add_js('cubicweb.ajax.js')
        self.req.add_css(('cubicweb.schema.css','cubicweb.acl.css'))
        self.w(u'<h1>%s</h1>' % _('Schema of the data model'))
        self.render_tabs(self.tabs, self.default_tab)


class SchemaTabImageView(StartupView):
    id = 'schema-image'

    def call(self):
        self.w(_(u'<div>This schema of the data model <em>excludes</em> the '
                 u'meta-data, but you can also display a <a href="%s">complete '
                 u'schema with meta-data</a>.</div>')
               % xml_escape(self.build_url('view', vid='schemagraph', skipmeta=0)))
        self.w(u'<img src="%s" alt="%s"/>\n' % (
            xml_escape(self.req.build_url('view', vid='schemagraph', skipmeta=1)),
            self.req._("graphical representation of the instance'schema")))


class SchemaTabTextView(StartupView):
    id = 'schema-text'

    def call(self):
        rset = self.req.execute('Any X ORDERBY N WHERE X is CWEType, X name N, '
                                'X final FALSE')
        self.wview('table', rset, displayfilter=True)


class ManagerSchemaPermissionsView(StartupView, management.SecurityViewMixIn):
    id = 'schema-security'
    __select__ = StartupView.__select__ & match_user_groups('managers')

    def call(self, display_relations=True):
        self.req.add_css('cubicweb.acl.css')
        skiptypes = skip_types(self.req)
        formparams = {}
        formparams['sec'] = self.id
        if not skiptypes:
            formparams['skipmeta'] = u'0'
        schema = self.schema
        # compute entities
        entities = sorted(eschema for eschema in schema.entities()
                          if not (eschema.is_final() or eschema in skiptypes))
        # compute relations
        if display_relations:
            relations = sorted(rschema for rschema in schema.relations()
                               if not (rschema.is_final()
                                       or rschema in skiptypes
                                       or rschema in META_RTYPES))
        else:
            relations = []
        # index
        _ = self.req._
        self.w(u'<div id="schema_security"><a id="index" href="index"/>')
        self.w(u'<h2 class="schema">%s</h2>' % _('index').capitalize())
        self.w(u'<h4>%s</h4>' %   _('Entities').capitalize())
        ents = []
        for eschema in sorted(entities):
            url = xml_escape(self.build_url('schema', **formparams))
            ents.append(u'<a class="grey" href="%s#%s">%s</a> (%s)' % (
                url,  eschema.type, eschema.type, _(eschema.type)))
        self.w(u', '.join(ents))
        self.w(u'<h4>%s</h4>' % (_('relations').capitalize()))
        rels = []
        for rschema in sorted(relations):
            url = xml_escape(self.build_url('schema', **formparams))
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
        _ = self.req._
        self.w(u'<a id="entities" href="entities"/>')
        self.w(u'<h2 class="schema">%s</h2>' % _('permissions for entities').capitalize())
        for eschema in entities:
            self.w(u'<a id="%s" href="%s"/>' %  (eschema.type, eschema.type))
            self.w(u'<h3 class="schema">%s (%s) ' % (eschema.type, _(eschema.type)))
            url = xml_escape(self.build_url('schema', **formparams) + '#index')
            self.w(u'<a href="%s"><img src="%s" alt="%s"/></a>' % (
                url,  self.req.external_resource('UP_ICON'), _('up')))
            self.w(u'</h3>')
            self.w(u'<div style="margin: 0px 1.5em">')
            self.schema_definition(eschema, link=False)
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
                    self.schema_definition(attr, link=False)
            self.w(u'</div>')

    def display_relations(self, relations, formparams):
        _ = self.req._
        self.w(u'<a id="relations" href="relations"/>')
        self.w(u'<h2 class="schema">%s </h2>' % _('permissions for relations').capitalize())
        for rschema in relations:
            self.w(u'<a id="%s" href="%s"/>' %  (rschema.type, rschema.type))
            self.w(u'<h3 class="schema">%s (%s) ' % (rschema.type, _(rschema.type)))
            url = xml_escape(self.build_url('schema', **formparams) + '#index')
            self.w(u'<a href="%s"><img src="%s" alt="%s"/></a>' % (
                url,  self.req.external_resource('UP_ICON'), _('up')))
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
            self.schema_definition(rschema, link=False)
            self.w(u'</div>')


class SchemaUreportsView(StartupView):
    id = 'schema-block'

    def call(self):
        viewer = SchemaViewer(self.req)
        layout = viewer.visit_schema(self.schema, display_relations=True,
                                     skiptypes=skip_types(self.req))
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
        entity = self.entity(row, col)
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
    id = 'cwetype-schema-text'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(u'<h2>%s</h2>' % _('Attributes'))
        rset = self.req.execute('Any N,F,D,I,J,DE,A '
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
        rset = self.req.execute(
            'Any R,C,TT,K,D,A,RN,TTN ORDERBY RN '
            'WHERE A is CWRelation, A description D, A composite K?, '
            'A relation_type R, R name RN, A to_entity TT, TT name TTN, '
            'A cardinality C, A from_entity S, S eid %(x)s',
            {'x': entity.eid})
        self.wview('editable-table', rset, 'null', displayfilter=True,
                   displaycols=range(6), mainindex=5)
        rset = self.req.execute(
            'Any R,C,TT,K,D,A,RN,TTN ORDERBY RN '
            'WHERE A is CWRelation, A description D, A composite K?, '
            'A relation_type R, R name RN, A from_entity TT, TT name TTN, '
            'A cardinality C, A to_entity O, O eid %(x)s',
            {'x': entity.eid})
        self.wview('editable-table', rset, 'null', displayfilter=True,
                   displaycols=range(6), mainindex=5)


class CWETypeSImageView(EntityView):
    id = 'cwetype-schema-image'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        url = entity.absolute_url(vid='schemagraph')
        self.w(u'<img src="%s" alt="%s"/>' % (
            xml_escape(url),
            xml_escape(self.req._('graphical schema for %s') % entity.name)))

class CWETypeSPermView(EntityView):
    id = 'cwetype-schema-permissions'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(u'<h2>%s</h2>' % _('Add permissions'))
        rset = self.req.execute('Any P WHERE X add_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')
        self.w(u'<h2>%s</h2>' % _('Read permissions'))
        rset = self.req.execute('Any P WHERE X read_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')
        self.w(u'<h2>%s</h2>' % _('Update permissions'))
        rset = self.req.execute('Any P WHERE X update_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')
        self.w(u'<h2>%s</h2>' % _('Delete permissions'))
        rset = self.req.execute('Any P WHERE X delete_permission P, '
                                'X eid %(x)s',
                                {'x': entity.eid})
        self.wview('outofcontext', rset, 'null')

class CWETypeSWorkflowView(EntityView):
    id = 'cwetype-workflow'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        if entity.reverse_state_of:
            self.w(u'<img src="%s" alt="%s"/>' % (
                    xml_escape(entity.absolute_url(vid='ewfgraph')),
                    xml_escape(self.req._('graphical workflow for %s') % entity.name)))
        else:
            self.w(u'<p>%s</p>' % _('There is no workflow defined for this entity.'))

# CWRType ######################################################################

class CWRTypeSchemaView(primary.PrimaryView):
    __select__ = implements('CWRType')
    title = _('in memory relation schema')
    main_related_section = False

    def render_entity_attributes(self, entity):
        super(CWRTypeSchemaView, self).render_entity_attributes(entity)
        rschema = self.vreg.schema.rschema(entity.name)
        viewer = SchemaViewer(self.req)
        layout = viewer.visit_relationschema(rschema)
        self.w(uilib.ureport_as_html(layout))
        if not rschema.is_final():
            msg = self.req._('graphical schema for %s') % entity.name
            self.w(tags.img(src=entity.absolute_url(vid='schemagraph'),
                            alt=msg))


# schema images ###############################################################

class RestrictedSchemaVisitorMixIn(object):
    def __init__(self, req, *args, **kwargs):
        self.req = req
        super(RestrictedSchemaVisitorMixIn, self).__init__(*args, **kwargs)

    def should_display_schema(self, rschema):
        return (super(RestrictedSchemaVisitorMixIn, self).should_display_schema(rschema)
                and (rschema.has_local_role('read')
                     or rschema.has_perm(self.req, 'read')))

    def should_display_attr(self, rschema):
        return (super(RestrictedSchemaVisitorMixIn, self).should_display_attr(rschema)
                and (rschema.has_local_role('read')
                     or rschema.has_perm(self.req, 'read')))


class FullSchemaVisitor(RestrictedSchemaVisitorMixIn, s2d.FullSchemaVisitor):
    pass

class OneHopESchemaVisitor(RestrictedSchemaVisitorMixIn,
                           s2d.OneHopESchemaVisitor):
    pass

class OneHopRSchemaVisitor(RestrictedSchemaVisitorMixIn,
                           s2d.OneHopRSchemaVisitor):
    pass


class SchemaImageView(TmpFileViewMixin, StartupView):
    id = 'schemagraph'
    content_type = 'image/png'

    def _generate(self, tmpfile):
        """display global schema information"""
        print 'skipedtypes', skip_types(self.req)
        visitor = FullSchemaVisitor(self.req, self.schema,
                                    skiptypes=skip_types(self.req))
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor)


class CWETypeSchemaImageView(TmpFileViewMixin, EntityView):
    id = 'schemagraph'
    __select__ = implements('CWEType')
    content_type = 'image/png'

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        eschema = self.vreg.schema.eschema(entity.name)
        visitor = OneHopESchemaVisitor(self.req, eschema,
                                       skiptypes=skip_types(self.req))
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor)


class CWRTypeSchemaImageView(CWETypeSchemaImageView):
    __select__ = implements('CWRType')

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        rschema = self.vreg.schema.rschema(entity.name)
        visitor = OneHopRSchemaVisitor(self.req, rschema)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor)


# misc: facets, actions ########################################################

class CWFinalFacet(facet.AttributeFacet):
    id = 'cwfinal-facet'
    __select__ = facet.AttributeFacet.__select__ & implements('CWEType', 'CWRType')
    rtype = 'final'

class ViewSchemaAction(action.Action):
    id = 'schema'
    __select__ = yes()

    title = _("site schema")
    category = 'siteactions'
    order = 30

    def url(self):
        return self.build_url(self.id)
