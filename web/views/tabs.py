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
"""base classes to handle tabbed views"""

__docformat__ = "restructuredtext en"

from logilab.common.deprecation import class_renamed
from logilab.mtconverter import xml_escape

from cubicweb import NoSelectableObject, role
from cubicweb.selectors import partial_has_related_entities
from cubicweb.view import EntityView
from cubicweb import tags, uilib
from cubicweb.utils import make_uid
from cubicweb.web.views import primary

class LazyViewMixin(object):
    """provides two convenience methods for the tab machinery
    can also be used to lazy-load arbitrary views
    """

    def _prepare_bindings(self, vid, reloadable):
        self._cw.add_onload(u"""
  jQuery('#lazy-%(vid)s').bind('%(event)s', function(event) {
     load_now('#lazy-%(vid)s', '#%(vid)s-hole', %(reloadable)s);
  });""" % {'event': 'load_%s' % vid, 'vid': vid,
            'reloadable' : str(reloadable).lower()})

    def lazyview(self, vid, rql=None, eid=None, rset=None, tabid=None,
                 reloadable=False, show_spinbox=True, w=None):
        """ a lazy version of wview """
        w = w or self.w
        self._cw.add_js('cubicweb.lazy.js')
        urlparams = {'vid' : vid, 'fname' : 'view'}
        if rql:
            urlparams['rql'] = rql
        elif eid:
            urlparams['rql'] = uilib.rql_for_eid(eid)
        elif rset:
            urlparams['rql'] = rset.printable_rql()
        if tabid is None:
            tabid = uilib.domid(vid)
        w(u'<div id="lazy-%s" cubicweb:loadurl="%s">' % (
            tabid, xml_escape(self._cw.build_url('json', **urlparams))))
        if show_spinbox:
            w(u'<img src="data/loading.gif" id="%s-hole" alt="%s"/>'
              % (tabid, self._cw._('(loading ...)')))
        else:
            w(u'<div id="%s-hole"></div>' % tabid)
        w(u'<noscript><p><a class="style: hidden" id="seo-%s" href="%s">%s</a></p></noscript>'
          % (tabid, xml_escape(self._cw.build_url(**urlparams)), xml_escape('%s (%s)') %
             (tabid, self._cw._('follow this link if javascript is deactivated'))))
        w(u'</div>')
        self._prepare_bindings(tabid, reloadable)

    def forceview(self, vid):
        """trigger an event that will force immediate loading of the view
        on dom readyness
        """
        self._cw.add_js('cubicweb.lazy.js')
        self._cw.add_onload("trigger_load('%s');" % vid)


class TabsMixin(LazyViewMixin):
    """a tab mixin
    """

    @property
    def cookie_name(self):
        return str('%s_active_tab' % self._cw.vreg.config.appid)

    def active_tab(self, default):
        if 'tab' in self._cw.form:
            return self._cw.form['tab']
        cookies = self._cw.get_cookie()
        cookiename = self.cookie_name
        activetab = cookies.get(cookiename)
        if activetab is None:
            domid = uilib.domid(default)
            cookies[cookiename] = domid
            self._cw.set_cookie(cookies, cookiename)
            return domid
        return activetab.value

    def prune_tabs(self, tabs, default_tab):
        selected_tabs = []
        may_be_active_tab = self.active_tab(default_tab)
        active_tab = uilib.domid(default_tab)
        viewsvreg = self._cw.vreg['views']
        for tab in tabs:
            try:
                tabid, tabkwargs = tab
                tabkwargs = tabkwargs.copy()
            except ValueError:
                tabid, tabkwargs = tab, {}
            tabkwargs.setdefault('rset', self.cw_rset)
            vid = tabkwargs.get('vid', tabid)
            domid = uilib.domid(tabid)
            try:
                viewsvreg.select(vid, self._cw, **tabkwargs)
            except NoSelectableObject:
                continue
            selected_tabs.append((tabid, domid, tabkwargs))
            if domid == may_be_active_tab:
                active_tab = domid
        return selected_tabs, active_tab

    def render_tabs(self, tabs, default, entity=None):
        # delegate to the default tab if there is more than one entity
        # in the result set (tabs are pretty useless there)
        if entity and len(self.cw_rset) > 1:
            entity.view(default, w=self.w)
            return
        self._cw.add_css('ui.tabs.css')
        self._cw.add_js(('ui.core.js', 'ui.tabs.js',
                         'cubicweb.ajax.js', 'cubicweb.tabs.js', 'cubicweb.lazy.js'))
        # prune tabs : not all are to be shown
        tabs, active_tab = self.prune_tabs(tabs, default)
        # build the html structure
        w = self.w
        uid = entity and entity.eid or make_uid('tab')
        w(u'<div id="entity-tabs-%s">' % uid)
        w(u'<ul>')
        active_tab_idx = None
        for i, (tabid, domid, tabkwargs) in enumerate(tabs):
            w(u'<li>')
            w(u'<a href="#%s">' % domid)
            w(u'<span onclick="set_tab(\'%s\', \'%s\')">' % (domid, self.cookie_name))
            w(tabkwargs.pop('label', self._cw._(tabid)))
            w(u'</span>')
            w(u'</a>')
            w(u'</li>')
            if domid == active_tab:
                active_tab_idx = i
        w(u'</ul>')
        w(u'</div>')
        for tabid, domid, tabkwargs in tabs:
            w(u'<div id="%s">' % domid)
            tabkwargs.setdefault('tabid', domid)
            tabkwargs.setdefault('vid', tabid)
            tabkwargs.setdefault('rset', self.cw_rset)
            self.lazyview(**tabkwargs)
            w(u'</div>')
        # call the set_tab() JS function *after* each tab is generated
        # because the callback binding needs to be done before
        # XXX make work history: true
        self._cw.add_onload(u"""
  jQuery('#entity-tabs-%(eeid)s > ul').tabs( { selected: %(tabindex)s });
  set_tab('%(domid)s', '%(cookiename)s');
""" % {'tabindex'   : active_tab_idx,
       'domid'        : active_tab,
       'eeid'       : (entity and entity.eid or uid),
       'cookiename' : self.cookie_name})


class EntityRelationView(EntityView):
    """view displaying entity related stuff.
    Such a view _must_ provide the rtype, target and vid attributes :

    Example :

    class ProjectScreenshotsView(EntityRelationView):
        '''display project's screenshots'''
        __regid__ = title = _('projectscreenshots')
        __select__ = EntityRelationView.__select__ & is_instance('Project')
        rtype = 'screenshot'
        role = 'subject'
        vid = 'gallery'

    in this example, entities related to project entity by the 'screenshot'
    relation (where the project is subject of the relation) will be displayed
    using the 'gallery' view.
    """
    __select__ = EntityView.__select__ & partial_has_related_entities()
    vid = 'list'

    def cell_call(self, row, col):
        rset = self.cw_rset.get_entity(row, col).related(self.rtype, role(self))
        self.w(u'<div class="mainInfo">')
        if self.title:
            self.w(tags.h1(self._cw._(self.title)))
        self.wview(self.vid, rset, 'noresult')
        self.w(u'</div>')


class TabbedPrimaryView(TabsMixin, primary.PrimaryView):
    __abstract__ = True # don't register

    tabs = [_('main_tab')]
    default_tab = 'main_tab'

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
        self.render_entity_toolbox(entity)
        self.w(u'<div class="tabbedprimary"></div>')
        self.render_entity_title(entity)
        self.render_tabs(self.tabs, self.default_tab, entity)

TabedPrimaryView = class_renamed('TabedPrimaryView', TabbedPrimaryView)

class PrimaryTab(primary.PrimaryView):
    __regid__ = 'main_tab'
    title = None # should not appear in possible views

    def is_primary(self):
        return True

    def render_entity_title(self, entity):
        pass
    def render_entity_toolbox(self, entity):
        pass
