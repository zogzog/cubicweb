# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Set of HTML startup views. A startup view is global, e.g. doesn't
apply to a result set.
"""

__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.textutils import unormalize
from logilab.mtconverter import xml_escape

from cubicweb.view import StartupView
from cubicweb.selectors import match_user_groups, is_instance
from cubicweb.schema import display_name
from cubicweb.web import ajax_replace_url, uicfg, httpcache

class ManageView(StartupView):
    __regid__ = 'manage'
    title = _('manage')
    http_cache_manager = httpcache.EtagHTTPCacheManager
    add_etype_links = ()

    def display_folders(self):
        return False

    def call(self, **kwargs):
        """The default view representing the instance's management"""
        self._cw.add_css('cubicweb.manageview.css')
        self.w(u'<h1>%s</h1>' % self._cw.property_value('ui.site-title'))
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

    def _main_index(self):
        req = self._cw
        manager = req.user.matching_groups('managers')
        if not manager and 'Card' in self._cw.vreg.schema:
            rset = self._cw.execute('Card X WHERE X wikiid "index"')
        else:
            rset = None
        if rset:
            self.wview('inlined', rset, row=0)
        else:
            self.entities()
            self.w(u'<div class="hr">&#160;</div>')
            self.startup_views()
        if manager and 'Card' in self._cw.vreg.schema:
            self.w(u'<div class="hr">&#160;</div>')
            if rset:
                href = rset.get_entity(0, 0).absolute_url(vid='edition')
                label = self._cw._('edit the index page')
            else:
                href = req.build_url('view', vid='creation', etype='Card', wikiid='index')
                label = self._cw._('create an index page')
            self.w(u'<br/><a href="%s">%s</a>\n' % (xml_escape(href), label))

    def folders(self):
        self.w(u'<h2>%s</h2>\n' % self._cw._('Browse by category'))
        self._cw.vreg['views'].select('tree', self._cw).render(w=self.w, maxlevel=1)

    def create_links(self):
        self.w(u'<ul class="createLink">')
        for etype in self.add_etype_links:
            eschema = self.schema.eschema(etype)
            if eschema.has_perm(self._cw, 'add'):
                self.w(u'<li><a href="%s">%s</a></li>' % (
                        self._cw.build_url('add/%s' % eschema),
                        self._cw.__('add a %s' % eschema).capitalize()))
        self.w(u'</ul>')

    def startup_views(self):
        self.w(u'<h2>%s</h2>\n' % self._cw._('Startup views'))
        self.startupviews_table()

    def startupviews_table(self):
        views = self._cw.vreg['views'].possible_views(self._cw, None)
        if not views:
            return
        self.w(u'<ul class="startup">')
        for v in sorted(views, key=lambda x: self._cw._(x.title)):
            if v.category != 'startupview' or v.__regid__ in ('index', 'tree', 'manage'):
                continue
            self.w('<li><a href="%s">%s</a></li>' % (
                xml_escape(v.url()), xml_escape(self._cw._(v.title).capitalize())))
        self.w(u'</ul>')

    def entities(self):
        schema = self._cw.vreg.schema
        self.w(u'<h2>%s</h2>\n' % self._cw._('Browse by entity type'))
        manager = self._cw.user.matching_groups('managers')
        self.w(u'<table class="startup">')
        if manager:
            self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self._cw._('application entities'))
        self.entity_types_table(eschema for eschema in schema.entities()
                                if uicfg.indexview_etype_section.get(eschema) == 'application')
        if manager:
            self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self._cw._('system entities'))
            self.entity_types_table(eschema for eschema in schema.entities()
                                if uicfg.indexview_etype_section.get(eschema) == 'system')
            if 'CWAttribute' in schema: # check schema support
                self.w(u'<tr><th colspan="4">%s</th></tr>\n' % self._cw._('schema entities'))
                self.entity_types_table(eschema for eschema in schema.entities()
                                        if uicfg.indexview_etype_section.get(eschema) == 'schema')
        self.w(u'</table>')

    def entity_types_table(self, eschemas):
        newline = 0
        infos = sorted(self.entity_types(eschemas),
                       key=lambda (l,a,e):unormalize(l))
        q, r = divmod(len(infos), 2)
        if r:
            infos.append( (None, '&#160;', '&#160;') )
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
        req = self._cw
        for eschema in eschemas:
            if eschema.final or not eschema.may_have_permission('read', req):
                continue
            etype = eschema.type
            nb = req.execute('Any COUNT(X) WHERE X is %s' % etype)[0][0]
            if nb > 1:
                label = display_name(req, etype, 'plural')
            else:
                label = display_name(req, etype)
            nb = req.execute('Any COUNT(X) WHERE X is %s' % etype)[0][0]
            url = self._cw.build_url(etype)
            etypelink = u'&#160;<a href="%s">%s</a> (%d)' % (
                xml_escape(url), label, nb)
            yield (label, etypelink, self.add_entity_link(eschema, req))

    def add_entity_link(self, eschema, req):
        """creates a [+] link for adding an entity if user has permission to do so"""
        if not eschema.has_perm(req, 'add'):
            return u''
        return u'[<a href="%s" title="%s">+</a>]' % (
            xml_escape(self.create_url(eschema.type)),
            self._cw.__('add a %s' % eschema))


class IndexView(ManageView):
    __regid__ = 'index'
    title = _('view_index')

    def display_folders(self):
        return 'Folder' in self._cw.vreg.schema and self._cw.execute('Any COUNT(X) WHERE X is Folder')[0][0]

