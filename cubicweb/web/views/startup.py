# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""This module contains the default index page and management view.

.. autoclass:: IndexView
.. autoclass:: ManageView
"""


from cubicweb import _

from logilab.common.textutils import unormalize
from logilab.mtconverter import xml_escape

from cubicweb.view import StartupView
from cubicweb.predicates import match_user_groups, is_instance
from cubicweb.schema import display_name
from cubicweb.web import httpcache
from cubicweb.web.views import uicfg

class ManageView(StartupView):
    """:__regid__: *manage*

    The manage view, display some information about what's contained by your
    site and provides access to administration stuff such as user and groups
    management.

    Regarding the section displaying link to entity type, notice by default it
    won't display entity types which are related to another one using a
    mandatory (cardinality == 1) composite relation.

    You can still configure that behaviour manually using the
    `indexview_etype_section` as explained in :mod:`cubicweb.web.uicfg`.
    """
    __regid__ = 'manage'
    title = _('manage')
    http_cache_manager = httpcache.EtagHTTPCacheManager
    add_etype_links = ()
    skip_startup_views = set( ('index', 'manage', 'schema', 'owl', 
                               'systempropertiesform', 'propertiesform',
                               'loggedout', 'login',
                               'cw.users-and-groups-management', 'cw.groups-management', 
                               'cw.users-management', 'cw.sources-management',
                               'siteinfo', 'info', 'registry', 'gc',
                               'tree') )

    def call(self, **kwargs):
        """The default view representing the instance's management"""
        self._cw.add_css('cubicweb.manageview.css')
        self.w(u'<h1>%s</h1>' % self._cw.property_value('ui.site-title'))
        self.entities()
        self.manage_actions()
        self.startup_views()

    def manage_actions(self):
        allactions = self._cw.vreg['actions'].possible_actions(self._cw)
        if allactions.get('manage'):
            self.w(u'<div class="hr">&#160;</div>')
            self.w(u'<h2>%s</h2>\n' % self._cw._('Manage'))
            self.w(u'<ul class="manageActions">')
            for action in allactions['manage']:
                self.w(u'<li><a href="%s">%s</a></li>' % (
                    action.url(), self._cw._(action.title)))
            self.w(u'</ul>')

    def startup_views(self):
        views = [v for v in self._cw.vreg['views'].possible_views(self._cw, None)
                 if v.category == 'startupview'
                 and v.__regid__ not in self.skip_startup_views]
        if not views:
            return
        self.w(u'<div class="hr">&#160;</div>')
        self.w(u'<h2>%s</h2>\n' % self._cw._('Startup views'))
        self.w(u'<ul class="startup">')
        for v in sorted(views, key=lambda x: self._cw._(x.title)):
            self.w('<li><a href="%s">%s</a></li>' % (
                xml_escape(v.url()), xml_escape(self._cw._(v.title).capitalize())))
        self.w(u'</ul>')

    def entities(self):
        schema = self._cw.vreg.schema
        eschemas = [eschema for eschema in schema.entities()
                    if uicfg.indexview_etype_section.get(eschema) == 'application']
        if eschemas:
            self.w(u'<div class="hr">&#160;</div>')
            self.w(u'<h2>%s</h2>\n' % self._cw._('Browse by entity type'))
            self.w(u'<table class="startup">')
            self.entity_types_table(eschemas)
            self.w(u'</table>')

    def entity_types_table(self, eschemas):
        infos = sorted(self.entity_types(eschemas),
                       key=lambda t: unormalize(t[0]))
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
        """return an iterator on formatted links to get a list of entities of
        each entity types
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
            url = self._cw.build_url(etype)
            etypelink = u'&#160;<a href="%s">%s</a> (%d)' % (
                xml_escape(url), label, nb)
            if eschema.has_perm(req, 'add'):
                yield (label, etypelink, self.add_entity_link(etype))
            else:
                yield (label, etypelink, u'')

    def create_links(self):
        self.w(u'<ul class="createLink">')
        for etype in self.add_etype_links:
            eschema = self._cw.vreg.schema.eschema(etype)
            if eschema.has_perm(self._cw, 'add'):
                url = self._cw.vreg["etypes"].etype_class(etype).cw_create_url(self._cw)
                self.w(u'<li><a href="%s">%s</a></li>' % (
                        url, self._cw.__('New %s' % eschema).capitalize()))
        self.w(u'</ul>')

    def add_entity_link(self, etype):
        """creates a [+] link for adding an entity"""
        url = self._cw.vreg["etypes"].etype_class(etype).cw_create_url(self._cw)
        return u'[<a href="%s" title="%s">+</a>]' % (
            xml_escape(url), self._cw.__('New %s' % etype))



class IndexView(ManageView):
    """:__regid__: *index*

    The default index view, that you'll get when accessing your site's root url.
    It's by default indentical to the
    :class:`~cubicweb.web.views.startup.ManageView`, but you'll usually want to
    customize this one.
    """
    __regid__ = 'index'
    title = _('view_index')
