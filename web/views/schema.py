"""Specific views for schema related entities

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from itertools import cycle

from logilab.mtconverter import html_escape
from yams import schema2dot as s2d

from cubicweb.selectors import implements, yes
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.view import EntityView, StartupView
from cubicweb.common.uilib import ureport_as_html
from cubicweb.web import uicfg, action
from cubicweb.web.views import TmpFileViewMixin, baseviews


uicfg.rcategories.set_rtag('primary', 'require_group', 'subject', 'CWPermission')
uicfg.rcategories.set_rtag('generated', 'final', 'subject', 'EEtype')
uicfg.rcategories.set_rtag('generated', 'final', 'subject', 'ERtype')
uicfg.rinlined.set_rtag(True, 'relation_type', 'subject', 'CWRelation')
uicfg.rinlined.set_rtag(True, 'from_entity', 'subject', 'CWRelation')
uicfg.rinlined.set_rtag(True, 'to_entity', 'subject', 'CWRelation')
uicfg.rwidgets.set_rtag('StringWidget', 'expression', 'subject', 'RQLExpression')

uicfg.rmode.set_rtag('create', 'state_of', 'object', otype='CWEType')
uicfg.rmode.set_rtag('create', 'transition_of', 'object', otype='CWEType')
uicfg.rmode.set_rtag('create', 'relation_type', 'object', otype='CWRType')
uicfg.rmode.set_rtag('link', 'from_entity', 'object', otype='CWEType')
uicfg.rmode.set_rtag('link', 'to_entity', 'object', otype='CWEType')


class ViewSchemaAction(action.Action):
    id = 'schema'
    __select__ = yes()

    title = _("site schema")
    category = 'siteactions'
    order = 30

    def url(self):
        return self.build_url(self.id)


# schema entity types views ###################################################

class _SchemaEntityPrimaryView(baseviews.PrimaryView):
    show_attr_label = False
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default

    def content_title(self, entity):
        return html_escape(entity.dc_long_title())

class CWETypePrimaryView(_SchemaEntityPrimaryView):
    __select__ = implements('CWEType')
    skip_attrs = _SchemaEntityPrimaryView.skip_attrs + ('name', 'meta', 'final')

class CWRTypePrimaryView(_SchemaEntityPrimaryView):
    __select__ = implements('CWRType')
    skip_attrs = _SchemaEntityPrimaryView.skip_attrs + ('name', 'meta', 'final',
                                                        'symetric', 'inlined')

class ErdefPrimaryView(_SchemaEntityPrimaryView):
    __select__ = implements('CWAttribute', 'CWRelation')
    show_attr_label = True

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


# in memory schema views (yams class instances) ###############################

class CWETypeSchemaView(CWETypePrimaryView):
    id = 'eschema'
    title = _('in memory entity schema')
    main_related_section = False
    skip_rels = ('is', 'is_instance_of', 'identity', 'created_by', 'owned_by',
                 'has_text',)

    def render_entity_attributes(self, entity, siderelations):
        super(CWETypeSchemaView, self).render_entity_attributes(entity, siderelations)
        eschema = self.vreg.schema.eschema(entity.name)
        viewer = SchemaViewer(self.req)
        layout = viewer.visit_entityschema(eschema, skiprels=self.skip_rels)
        self.w(ureport_as_html(layout))
        if not eschema.is_final():
            self.w(u'<img src="%s" alt="%s"/>' % (
                html_escape(entity.absolute_url(vid='eschemagraph')),
                html_escape(self.req._('graphical schema for %s') % entity.name)))


class CWRTypeSchemaView(CWRTypePrimaryView):
    id = 'eschema'
    title = _('in memory relation schema')
    main_related_section = False

    def render_entity_attributes(self, entity, siderelations):
        super(CWRTypeSchemaView, self).render_entity_attributes(entity, siderelations)
        rschema = self.vreg.schema.rschema(entity.name)
        viewer = SchemaViewer(self.req)
        layout = viewer.visit_relationschema(rschema)
        self.w(ureport_as_html(layout))
        if not rschema.is_final():
            self.w(u'<img src="%s" alt="%s"/>' % (
                html_escape(entity.absolute_url(vid='eschemagraph')),
                html_escape(self.req._('graphical schema for %s') % entity.name)))


# schema images ###############################################################

class ImageView(EntityView):
    __select__ = implements('CWEType')
    id = 'image'
    title = _('image')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        url = entity.absolute_url(vid='eschemagraph')
        self.w(u'<img src="%s" alt="%s"/>' % (
            html_escape(url),
            html_escape(self.req._('graphical schema for %s') % entity.name)))


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
    skip_rels = ('owned_by', 'created_by', 'identity', 'is', 'is_instance_of')
    def _generate(self, tmpfile):
        """display global schema information"""
        skipmeta = not int(self.req.form.get('withmeta', 0))
        visitor = FullSchemaVisitor(self.req, self.schema, skiprels=self.skip_rels, skipmeta=skipmeta)
        s2d.schema2dot(outputfile=tmpfile, visitor=visitor,
                       prophdlr=RestrictedSchemaDotPropsHandler(self.req))

class CWETypeSchemaImageView(TmpFileViewMixin, EntityView):
    id = 'eschemagraph'
    content_type = 'image/png'
    __select__ = implements('CWEType')
    skip_rels = ('owned_by', 'created_by', 'identity', 'is', 'is_instance_of')

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
