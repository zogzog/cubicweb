"""Set of HTML startup views. A startup view is global, e.g. doesn't
apply to a result set.

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb.common.uilib import ureport_as_html, unormalize, ajax_replace_url
from cubicweb.common.view import StartupView
from cubicweb.web.httpcache import EtagHTTPCacheManager

_ = unicode


class ManageView(StartupView):
    id = 'manage'
    title = _('manage')    
    http_cache_manager = EtagHTTPCacheManager

    def display_folders(self):
        return False
    
    def call(self, **kwargs):
        """The default view representing the application's management"""
        self.w(u'<div>\n')
        if not self.display_folders():
            self._main_index()
        else:
            self.w(u'<table><tr>\n')
            self.w(u'<td style="width:40%">')
            self._main_index()
            self.w(u'</td><td style="width:60%">')            
            self.folders()
            self.w(u'</td>')
            self.w(u'</tr></table>\n')
        self.w(u'</div>\n')

    def _main_index(self):
        req = self.req
        manager = req.user.matching_groups('managers')
        if not manager and 'Card' in self.schema:
            rset = self.req.execute('Card X WHERE X wikiid "index"')
        else:
            rset = None
        if rset:
            self.wview('inlined', rset, row=0)
        else:
            self.entities()
            self.w(u'<div class="hr">&nbsp;</div>')
            self.startup_views()
        if manager and 'Card' in self.schema:
            self.w(u'<div class="hr">&nbsp;</div>')
            if rset:
                href = rset.get_entity(0, 0).absolute_url(vid='edition')
                label = self.req._('edit the index page')
            else:
                href = req.build_url('view', vid='creation', etype='Card', wikiid='index')
                label = self.req._('create an index page')
            self.w(u'<br/><a href="%s">%s</a>\n' % (html_escape(href), label))
        
    def folders(self):
        self.w(u'<h4>%s</h4>\n' % self.req._('Browse by category'))
        self.vreg.select_view('tree', self.req, None).dispatch(w=self.w)
        
    def startup_views(self):
        self.w(u'<h4>%s</h4>\n' % self.req._('Startup views'))
        self.startupviews_table()
        
    def startupviews_table(self):
        for v in self.vreg.possible_views(self.req, None):
            if v.category != 'startupview' or v.id in ('index', 'tree', 'manage'):
                continue
            self.w('<p><a href="%s">%s</a></p>' % (
                html_escape(v.url()), html_escape(self.req._(v.title).capitalize())))
        
    def entities(self):
        schema = self.schema
        self.w(u'<h4>%s</h4>\n' % self.req._('The repository holds the following entities'))
        manager = self.req.user.matching_groups('managers')
        self.w(u'<table class="startup">')
        if manager:
            self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self.req._('application entities'))
        self.entity_types_table(eschema for eschema in schema.entities()
                                if not eschema.meta and not eschema.is_subobject(strict=True))
        if manager: 
            self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self.req._('system entities'))
            self.entity_types_table(eschema for eschema in schema.entities()
                                    if eschema.meta and not eschema.schema_entity())
            if 'EFRDef' in schema: # check schema support
                self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self.req._('schema entities'))
                self.entity_types_table(schema.eschema(etype)
                                        for etype in schema.schema_entity_types())
        self.w(u'</table>')
        
    def entity_types_table(self, eschemas):
        newline = 0
        infos = sorted(self.entity_types(eschemas),
                       key=lambda (l,a,e):unormalize(l))
        q, r = divmod(len(infos), 2)
        if r:
            infos.append( (None, '&nbsp;', '&nbsp;') )
        infos = zip(infos[:q+r], infos[q+r:])
        for (_, etypelink, addlink), (_, etypelink2, addlink2) in infos:
            self.w(u'<tr>\n')
            self.w(u'<td class="addcol">%s</td><td>%s</td>\n' % (addlink,  etypelink))
            self.w(u'<td class="addcol">%s</td><td>%s</td>\n' % (addlink2, etypelink2))
            self.w(u'</tr>\n')
        
        
    def entity_types(self, eschemas):
        """return a list of formatted links to get a list of entities of
        a each entity's types
        """
        req = self.req
        for eschema in eschemas:
            if eschema.is_final() or (not eschema.has_perm(req, 'read') and
                                      not eschema.has_local_role('read')):
                continue
            etype = eschema.type
            label = display_name(req, etype, 'plural')
            nb = req.execute('Any COUNT(X) WHERE X is %s' % etype)[0][0]
            if nb > 1:
                view = self.vreg.select_view('list', req, req.etype_rset(etype))
                url = view.url()
            else:
                url = self.build_url('view', rql='%s X' % etype)
            etypelink = u'&nbsp;<a href="%s">%s</a> (%d)' % (
                html_escape(url), label, nb)
            yield (label, etypelink, self.add_entity_link(eschema, req))
    
    def add_entity_link(self, eschema, req):
        """creates a [+] link for adding an entity if user has permission to do so"""
        if not eschema.has_perm(req, 'add'):
            return u''
        return u'[<a href="%s" title="%s">+</a>]' % (
            html_escape(self.create_url(eschema.type)),
            self.req.__('add a %s' % eschema))

    
class IndexView(ManageView):
    id = 'index'
    title = _('index')
    
    def display_folders(self):
        return 'Folder' in self.schema and self.req.execute('Any COUNT(X) WHERE X is Folder')[0][0]
    


class SchemaView(StartupView):
    id = 'schema'
    title = _('application schema')

    def call(self):
        """display schema information"""
        self.req.add_js('cubicweb.ajax.js')
        self.req.add_css('cubicweb.schema.css')
        withmeta = int(self.req.form.get('withmeta', 0))
        self.w(u'<img src="%s" alt="%s"/>\n' % (
            html_escape(self.req.build_url('view', vid='schemagraph', withmeta=withmeta)),
            self.req._("graphical representation of the application'schema")))
        if withmeta:
            self.w(u'<div><a href="%s">%s</a></div>' % (
                self.build_url('schema', withmeta=0),
                self.req._('hide meta-data')))
        else:
            self.w(u'<div><a href="%s">%s</a></div>' % (
                self.build_url('schema', withmeta=1),
                self.req._('show meta-data')))
        self.w(u'<div id="detailed_schema"><a href="%s">%s</a></div>' %
               (html_escape(ajax_replace_url('detailed_schema', '', 'schematext',
                                             skipmeta=int(not withmeta))),
                self.req._('detailed schema view')))


class SchemaUreportsView(StartupView):
    id = 'schematext'

    def call(self):
        from cubicweb.schemaviewer import SchemaViewer
        skipmeta = int(self.req.form.get('skipmeta', True))
        schema = self.schema
        viewer = SchemaViewer(self.req)
        layout = viewer.visit_schema(schema, display_relations=True,
                                     skiprels=('is', 'is_instance_of', 'identity',
                                               'owned_by', 'created_by'),
                                     skipmeta=skipmeta)
        self.w(ureport_as_html(layout))

