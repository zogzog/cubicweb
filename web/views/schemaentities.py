"""Specific views for schema related entities

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb.selectors import implements
from cubicweb.schemaviewer import SchemaViewer
from cubicweb.common.uilib import ureport_as_html
from cubicweb.common.view import EntityView
from cubicweb.web.views import baseviews


class ImageView(EntityView):
    accepts = ('EEType',)
    id = 'image'
    title = _('image')

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        url = entity.absolute_url(vid='eschemagraph')
        self.w(u'<img src="%s" alt="%s"/>' % (
            html_escape(url),
            html_escape(self.req._('graphical schema for %s') % entity.name)))


class _SchemaEntityPrimaryView(baseviews.PrimaryView):
    show_attr_label = False
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default 
    
    def content_title(self, entity):
        return html_escape(entity.dc_long_title())
    
class EETypePrimaryView(_SchemaEntityPrimaryView):
    accepts = ('EEType',)
    skip_attrs = _SchemaEntityPrimaryView.skip_attrs + ('name', 'meta', 'final')

class ERTypePrimaryView(_SchemaEntityPrimaryView):
    accepts = ('ERType',)
    skip_attrs = _SchemaEntityPrimaryView.skip_attrs + ('name', 'meta', 'final',
                                                        'symetric', 'inlined')

class ErdefPrimaryView(_SchemaEntityPrimaryView):
    accepts = ('EFRDef', 'ENFRDef')
    show_attr_label = True

class EETypeSchemaView(EETypePrimaryView):
    id = 'eschema'
    title = _('in memory entity schema')
    main_related_section = False
    skip_rels = ('is', 'is_instance_of', 'identity', 'created_by', 'owned_by',
                 'has_text',)
    
    def render_entity_attributes(self, entity, siderelations):
        super(EETypeSchemaView, self).render_entity_attributes(entity, siderelations)
        eschema = self.vreg.schema.eschema(entity.name)
        viewer = SchemaViewer(self.req)
        layout = viewer.visit_entityschema(eschema, skiprels=self.skip_rels)
        self.w(ureport_as_html(layout))
        if not eschema.is_final():
            self.w(u'<img src="%s" alt="%s"/>' % (
                html_escape(entity.absolute_url(vid='eschemagraph')),
                html_escape(self.req._('graphical schema for %s') % entity.name)))

class ERTypeSchemaView(ERTypePrimaryView):
    id = 'eschema'
    title = _('in memory relation schema')
    main_related_section = False

    def render_entity_attributes(self, entity, siderelations):
        super(ERTypeSchemaView, self).render_entity_attributes(entity, siderelations)
        rschema = self.vreg.schema.rschema(entity.name)
        viewer = SchemaViewer(self.req)
        layout = viewer.visit_relationschema(rschema)
        self.w(ureport_as_html(layout))
        if not rschema.is_final():
            self.w(u'<img src="%s" alt="%s"/>' % (
                html_escape(entity.absolute_url(vid='eschemagraph')),
                html_escape(self.req._('graphical schema for %s') % entity.name)))

        
class EETypeWorkflowView(EntityView):
    id = 'workflow'
    accepts = ('EEType',)
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default 
    
    def cell_call(self, row, col, **kwargs):
        entity = self.entity(row, col)
        self.w(u'<h1>%s</h1>' % (self.req._('workflow for %s')
                                 % display_name(self.req, entity.name)))
        self.w(u'<img src="%s" alt="%s"/>' % (
            html_escape(entity.absolute_url(vid='ewfgraph')),
            html_escape(self.req._('graphical workflow for %s') % entity.name)))


class EETypeOneLineView(baseviews.OneLineView):
    accepts = ('EEType',)
    
    def cell_call(self, row, col, **kwargs):
        entity = self.entity(row, col)
        final = entity.final
        if final:
            self.w(u'<em class="finalentity">')
        super(EETypeOneLineView, self).cell_call(row, col, **kwargs)
        if final:
            self.w(u'</em>')
        

from cubicweb.web.action import Action

class ViewWorkflowAction(Action):
    id = 'workflow'
    __selectors__ = (implements('EEType'), )
    
    category = 'mainactions'
    title = _('view workflow')
    accepts = ('EEType',)
    condition = 'S state_of X' # must have at least one state associated
    def url(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        return entity.absolute_url(vid='workflow')
        
