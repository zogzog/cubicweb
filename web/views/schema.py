"""Specific views for schema related entities

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from itertools import cycle

from logilab.mtconverter import html_escape
from yams import schema2dot as s2d

from cubicweb.selectors import implements, yes
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.view import EntityView, StartupView
from cubicweb.common import tags, uilib
from cubicweb.web import action
from cubicweb.web.views import TmpFileViewMixin, primary, baseviews, tabs
from cubicweb.web.facet import AttributeFacet


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

SKIPPED_RELS = ('is', 'is_instance_of', 'identity', 'created_by', 'owned_by',
                'has_text',)

class CWETypePrimaryView(tabs.TabsMixin, primary.PrimaryView):
    __select__ = implements('CWEType')
    title = _('in memory entity schema')
    main_related_section = False
    skip_rels = SKIPPED_RELS
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

class RestrictedSchemaDotPropsHandler(s2d.SchemaDotPropsHandler):
    def __init__(self, req):
        # FIXME: colors are arbitrary
        self.nextcolor = cycle( ('#aa0000', '#00aa00', '#0000aa',
                                 '#000000', '#888888') ).next
        self.req = req

    def display_attr(self, rschema):
        return not rschema.meta and (rschema.has_local_role('read')
                                     or rschema.has_perm(self.req, 'read'))

    # XXX remove this method once yams > 0.20 is out
    def node_properties(self, eschema):
        """return default DOT drawing options for an entity schema"""
        label = ['{', eschema.type, '|']
        label.append(r'\l'.join(rel.type for rel in eschema.subject_relations()
                                if rel.final and self.display_attr(rel)))
        label.append(r'\l}') # trailing \l ensure alignement of the last one
        return {'label' : ''.join(label), 'shape' : "record",
                'fontname' : "Courier", 'style' : "filled"}

    def edge_properties(self, rschema, subjnode, objnode):
        kwargs = super(RestrictedSchemaDotPropsHandler, self).edge_properties(rschema, subjnode, objnode)
        # symetric rels are handled differently, let yams decide what's best
        if not rschema.symetric:
            kwargs['color'] = self.nextcolor()
        kwargs['fontcolor'] = kwargs['color']
        # dot label decoration is just awful (1 line underlining the label
        # + 1 line going to the closest edge spline point)
        kwargs['decorate'] = 'false'
        return kwargs


class RestrictedSchemaVisitorMiIn:
    def __init__(self, req, *args, **kwargs):
        # hack hack hack
        assert len(self.__class__.__bases__) == 2
        self.__parent = self.__class__.__bases__[1]
        self.__parent.__init__(self, *args, **kwargs)
        self.req = req

    def nodes(self):
        for etype, eschema in self.__parent.nodes(self):
            if eschema.has_local_role('read') or eschema.has_perm(self.req, 'read'):
                yield eschema.type, eschema

    def edges(self):
        for setype, oetype, rschema in self.__parent.edges(self):
            if rschema.has_local_role('read') or rschema.has_perm(self.req, 'read'):
                yield setype, oetype, rschema


class FullSchemaVisitor(RestrictedSchemaVisitorMiIn, s2d.FullSchemaVisitor):
    pass

class OneHopESchemaVisitor(RestrictedSchemaVisitorMiIn, s2d.OneHopESchemaVisitor):
    pass

class OneHopRSchemaVisitor(RestrictedSchemaVisitorMiIn, s2d.OneHopRSchemaVisitor):
    pass


class SchemaImageView(TmpFileViewMixin, StartupView):
    id = 'schemagraph'

    content_type = 'image/png'
    skip_rels = SKIPPED_RELS
    def _generate(self, tmpfile):
        """display global schema information"""
        skipmeta = not int(self.req.form.get('withmeta', 0))
        visitor = FullSchemaVisitor(self.req, self.schema, skiprels=self.skip_rels, skipmeta=skipmeta)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor,
                       prophdlr=RestrictedSchemaDotPropsHandler(self.req))

class CWETypeSchemaImageView(TmpFileViewMixin, EntityView):
    id = 'schemagraph'
    __select__ = implements('CWEType')

    content_type = 'image/png'
    skip_rels = SKIPPED_RELS

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        eschema = self.vreg.schema.eschema(entity.name)
        visitor = OneHopESchemaVisitor(self.req, eschema, skiprels=self.skip_rels)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor,
                       prophdlr=RestrictedSchemaDotPropsHandler(self.req))

class CWRTypeSchemaImageView(CWETypeSchemaImageView):
    __select__ = implements('CWRType')

    def _generate(self, tmpfile):
        """display schema information for an entity"""
        entity = self.entity(self.row, self.col)
        rschema = self.vreg.schema.rschema(entity.name)
        visitor = OneHopRSchemaVisitor(self.req, rschema)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor,
                       prophdlr=RestrictedSchemaDotPropsHandler(self.req))

### facets

class CWMetaFacet(AttributeFacet):
    id = 'cwmeta-facet'
    __select__ = AttributeFacet.__select__ & implements('CWEType')
    rtype = 'meta'

class CWFinalFacet(AttributeFacet):
    id = 'cwfinal-facet'
    __select__ = AttributeFacet.__select__ & implements('CWEType')
    rtype = 'final'
