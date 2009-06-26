"""Specific views for schema related entities

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape
from yams import schema2dot as s2d

from cubicweb.selectors import implements, yes
from cubicweb.schema import META_RELATIONS_TYPES, SCHEMA_TYPES
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.view import EntityView, StartupView
from cubicweb.common import tags, uilib
from cubicweb.web import action
from cubicweb.web.views import TmpFileViewMixin, primary, baseviews, tabs
from cubicweb.web.facet import AttributeFacet

SKIP_TYPES = set()
SKIP_TYPES.update(META_RELATIONS_TYPES)
SKIP_TYPES.update(SCHEMA_TYPES)

def skip_types(req):
    if int(req.form.get('skipmeta', True)):
        return schema.SKIP_TYPES
    return ()

class ViewSchemaAction(action.Action):
    id = 'schema'
    __select__ = yes()

    title = _("site schema")
    category = 'siteactions'
    order = 30

    def url(self):
        return self.build_url(self.id)


class CWRDEFPrimaryView(primary.PrimaryView):
    __select__ = implements('CWAttribute', 'CWRelation')
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default

    def render_entity_title(self, entity):
        self.w(u'<h1><span class="etype">%s</span> %s</h1>'
               % (entity.dc_type().capitalize(),
                  html_escape(entity.dc_long_title())))

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
        rset = self.req.execute('Any N,F,D,GROUP_CONCAT(C),I,J,DE,A '
                                'GROUPBY N,F,D,AA,A,I,J,DE '
                                'ORDERBY AA WHERE A is CWAttribute, '
                                'A ordernum AA, A defaultval D, '
                                'A constrained_by C?, A description DE, '
                                'A fulltextindexed I, A internationalizable J, '
                                'A relation_type R, R name N, '
                                'A to_entity O, O name F, '
                                'A from_entity S, S eid %(x)s',
                                {'x': entity.eid})
        self.wview('editable-table', rset, 'null', displayfilter=True)
        self.w(u'<h2>%s</h2>' % _('Relations'))
        rset = self.req.execute('Any N,C,F,M,K,D,A ORDERBY N '
                                'WITH N,C,F,M,D,K,A BEING ('
                                '(Any N,C,F,M,K,D,A '
                                'ORDERBY N WHERE A is CWRelation, '
                                'A description D, A composite K?, '
                                'A relation_type R, R name N, '
                                'A to_entity O, O name F, '
                                'A cardinality C, O meta M, '
                                'A from_entity S, S eid %(x)s)'
                                ' UNION '
                                '(Any N,C,F,M,K,D,A '
                                'ORDERBY N WHERE A is CWRelation, '
                                'A description D, A composite K?, '
                                'A relation_type R, R name N, '
                                'A from_entity S, S name F, '
                                'A cardinality C, S meta M, '
                                'A to_entity O, O eid %(x)s))'
                                ,{'x': entity.eid})
        self.wview('editable-table', rset, 'null', displayfilter=True)


class CWETypeSImageView(EntityView):
    id = 'cwetype-schema-image'
    __select__ = EntityView.__select__ & implements('CWEType')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        url = entity.absolute_url(vid='schemagraph')
        self.w(u'<img src="%s" alt="%s"/>' % (
            html_escape(url),
            html_escape(self.req._('graphical schema for %s') % entity.name)))

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
                    html_escape(entity.absolute_url(vid='ewfgraph')),
                    html_escape(self.req._('graphical workflow for %s') % entity.name)))
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
        super(RestrictedSchemaVisitorMixIn, self).__init__(*args, **kwargs)
        self.req = req

    def should_display_schema(self, schema):
        return (super(RestrictedSchemaVisitorMixIn, self).should_display_schema(schema)
                and rschema.has_local_role('read') or rschema.has_perm(self.req, 'read'))

    def should_display_attr(self, schema):
        return (super(RestrictedSchemaVisitorMixIn, self).should_display_attr(schema)
                and rschema.has_local_role('read') or rschema.has_perm(self.req, 'read'))


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

### facets

class CWMetaFacet(AttributeFacet):
    id = 'cwmeta-facet'
    __select__ = AttributeFacet.__select__ & implements('CWEType')
    rtype = 'meta'

class CWFinalFacet(AttributeFacet):
    id = 'cwfinal-facet'
    __select__ = AttributeFacet.__select__ & implements('CWEType')
    rtype = 'final'
