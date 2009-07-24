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
from logilab.mtconverter import xml_escape

from cubicweb.view import StartupView
from cubicweb.selectors import match_user_groups, implements
from cubicweb.schema import display_name
from cubicweb.web import ajax_replace_url, uicfg, httpcache

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
            else:
                uicfg.indexview_etype_section.setdefault(eschema, 'application')

    def display_folders(self):
        return False

    def call(self, **kwargs):
        """The default view representing the instance's management"""
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
            self.w(u'<br/><a href="%s">%s</a>\n' % (xml_escape(href), label))

    def folders(self):
        self.w(u'<h4>%s</h4>\n' % self.req._('Browse by category'))
        self.vreg.select('views', 'tree', self.req).render(w=self.w)

    def startup_views(self):
        self.w(u'<h4>%s</h4>\n' % self.req._('Startup views'))
        self.startupviews_table()

    def startupviews_table(self):
        for v in self.vreg.possible_views(self.req, None):
            if v.category != 'startupview' or v.id in ('index', 'tree', 'manage'):
                continue
            self.w('<p><a href="%s">%s</a></p>' % (
                xml_escape(v.url()), xml_escape(self.req._(v.title).capitalize())))

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
                view = self.vreg.select('views', 'list', req,
                                        rset=req.etype_rset(etype))
                url = view.url()
            else:
                url = self.build_url('view', rql='%s X' % etype)
            etypelink = u'&nbsp;<a href="%s">%s</a> (%d)' % (
                xml_escape(url), label, nb)
            yield (label, etypelink, self.add_entity_link(eschema, req))

    def add_entity_link(self, eschema, req):
        """creates a [+] link for adding an entity if user has permission to do so"""
        if not eschema.has_perm(req, 'add'):
            return u''
        return u'[<a href="%s" title="%s">+</a>]' % (
            xml_escape(self.create_url(eschema.type)),
            self.req.__('add a %s' % eschema))


class IndexView(ManageView):
    id = 'index'
    title = _('view_index')

    def display_folders(self):
        return 'Folder' in self.schema and self.req.execute('Any COUNT(X) WHERE X is Folder')[0][0]

