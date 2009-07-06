"""Set of HTML startup views. A startup view is global, e.g. doesn't
apply to a result set.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.textutils import unormalize
from logilab.mtconverter import html_escape

from cubicweb.view import StartupView
from cubicweb.selectors import match_user_groups, implements
from cubicweb.schema import display_name
from cubicweb.common.uilib import ureport_as_html
from cubicweb.web import ajax_replace_url, uicfg, httpcache
from cubicweb.web.views import tabs
from cubicweb.web.views.management import SecurityViewMixIn

class ManageView(StartupView):
    id = 'manage'
    title = _('manage')
    http_cache_manager = httpcache.EtagHTTPCacheManager

    @classmethod
    def vreg_initialization_completed(cls):
        for eschema in cls.schema.entities():
            if eschema.schema_entity():
                uicfg.indexview_etype_section.setdefault(eschema, 'schema')
            elif eschema.is_subobject(strict=True):
                uicfg.indexview_etype_section.setdefault(eschema, 'subobject')
            elif eschema.meta:
                uicfg.indexview_etype_section.setdefault(eschema, 'system')
            else:
                uicfg.indexview_etype_section.setdefault(eschema, 'application')

    def display_folders(self):
        return False

    def call(self, **kwargs):
        """The default view representing the application's management"""
        self.req.add_css('cubicweb.manageview.css')
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
        self.vreg.select_view('tree', self.req, None).render(w=self.w)

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
                                if uicfg.indexview_etype_section.get(eschema) == 'application')
        if manager:
            self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self.req._('system entities'))
            self.entity_types_table(eschema for eschema in schema.entities()
                                if uicfg.indexview_etype_section.get(eschema) == 'system')
            if 'CWAttribute' in schema: # check schema support
                self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self.req._('schema entities'))
                self.entity_types_table(eschema for eschema in schema.entities()
                                        if uicfg.indexview_etype_section.get(eschema) == 'schema')
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

class SchemaView(tabs.TabsMixin, StartupView):
    id = 'schema'
    title = _('application schema')
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
               % html_escape(self.build_url('view', vid='schemagraph', withmeta=1)))
        self.w(u'<img src="%s" alt="%s"/>\n' % (
            html_escape(self.req.build_url('view', vid='schemagraph', withmeta=0)),
            self.req._("graphical representation of the application'schema")))


class SchemaTabTextView(StartupView):
    id = 'schema-text'

    def call(self):
        rset = self.req.execute('Any X ORDERBY N WHERE X is CWEType, X name N, '
                                'X final FALSE')
        self.wview('table', rset, displayfilter=True)


class ManagerSchemaPermissionsView(StartupView, SecurityViewMixIn):
    id = 'schema-security'
    __select__ = StartupView.__select__ & match_user_groups('managers')

    def call(self, display_relations=True,
             skiprels=('is', 'is_instance_of', 'identity', 'owned_by', 'created_by')):
        self.req.add_css('cubicweb.acl.css')
        _ = self.req._
        formparams = {}
        formparams['sec'] = self.id
        formparams['withmeta'] = int(self.req.form.get('withmeta', True))
        schema = self.schema
        # compute entities
        entities = [eschema for eschema in schema.entities()
                   if not eschema.is_final()]
        if not formparams['withmeta']:
            entities = [eschema for eschema in entities
                        if not eschema.meta]
        # compute relations
        if display_relations:
            relations = [rschema for rschema in schema.relations()
                         if not (rschema.is_final() or rschema.type in skiprels)]
            if not formparams['withmeta']:
                relations = [rschema for rschema in relations
                             if not rschema.meta]
        else:
            relations = []
        # index
        self.w(u'<div id="schema_security"><a id="index" href="index"/>')
        self.w(u'<h2 class="schema">%s</h2>' % _('index').capitalize())
        self.w(u'<h4>%s</h4>' %   _('Entities').capitalize())
        ents = []
        for eschema in sorted(entities):
            url = html_escape(self.build_url('schema', **formparams))
            ents.append(u'<a class="grey" href="%s#%s">%s</a> (%s)' % (
                url,  eschema.type, eschema.type, _(eschema.type)))
        self.w(u', '.join(ents))
        self.w(u'<h4>%s</h4>' % (_('relations').capitalize()))
        rels = []
        for rschema in sorted(relations):
            url = html_escape(self.build_url('schema', **formparams))
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
        for eschema in sorted(entities):
            self.w(u'<a id="%s" href="%s"/>' %  (eschema.type, eschema.type))
            self.w(u'<h3 class="schema">%s (%s) ' % (eschema.type, _(eschema.type)))
            url = html_escape(self.build_url('schema', **formparams) + '#index')
            self.w(u'<a href="%s"><img src="%s" alt="%s"/></a>' % (url,  self.req.external_resource('UP_ICON'), _('up')))
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
            else:
                self.w(u'</div>')


    def display_relations(self, relations, formparams):
        _ = self.req._
        self.w(u'<a id="relations" href="relations"/>')
        self.w(u'<h2 class="schema">%s </h2>' % _('permissions for relations').capitalize())
        for rschema in sorted(relations):
            self.w(u'<a id="%s" href="%s"/>' %  (rschema.type, rschema.type))
            self.w(u'<h3 class="schema">%s (%s) ' % (rschema.type, _(rschema.type)))
            url = html_escape(self.build_url('schema', **formparams) + '#index')
            self.w(u'<a href="%s"><img src="%s" alt="%s"/></a>' % (url,  self.req.external_resource('UP_ICON'), _('up')))
            self.w(u'</h3>')
            self.w(u'<div style="margin: 0px 1.5em">')
            subjects = [str(subj) for subj in rschema.subjects()]
            self.w(u'<div><strong>%s</strong> %s (%s)</div>' % (_('subject_plural:'),
                                                ', '.join( [str(subj) for subj in rschema.subjects()]),
                                                ', '.join( [_(str(subj)) for subj in rschema.subjects()])))
            self.w(u'<div><strong>%s</strong> %s (%s)</div>' % (_('object_plural:'),
                                                ', '.join( [str(obj) for obj in rschema.objects()]),
                                                ', '.join( [_(str(obj)) for obj in rschema.objects()])))
            self.schema_definition(rschema, link=False)
            self.w(u'</div>')


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


