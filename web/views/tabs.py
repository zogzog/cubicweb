"""base classes to handle tabbed views

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from logilab.common.decorators import monkeypatch
from logilab.mtconverter import html_escape

from cubicweb import NoSelectableObject, role
from cubicweb.selectors import partial_has_related_entities
from cubicweb.common.view import EntityView
from cubicweb.common.utils import HTMLHead
from cubicweb.common.uilib import rql_for_eid

from cubicweb.web.views.basecontrollers import JSonController


class LazyViewMixin(object):
    """provides two convenience methods for the tab machinery
    can also be used to lazy-load arbitrary views
    caveat : lazyview is not recursive, i.e : you can't (successfully)
    lazyload a view that in turns does the same
    """

    def _prepare_bindings(self, vid, reloadable):
        self.req.html_headers.add_onload(u"""
  jQuery('#lazy-%(vid)s').bind('%(event)s', function(event) {
     load_now('#lazy-%(vid)s', '#%(vid)s-hole', %(reloadable)s);
  });""" % {'event': 'load_%s' % vid, 'vid': vid,
            'reloadable' : str(reloadable).lower()})

    def lazyview(self, vid, eid=None, reloadable=False, show_spinbox=True, w=None):
        """a lazy version of wview
        first version only support lazy viewing for an entity at a time
        """
        w = w or self.w
        self.req.add_js('cubicweb.lazy.js')
        urlparams = {'vid' : vid, 'mode' : 'html'}
        if eid:
            urlparams['rql'] = rql_for_eid(eid)
        w(u'<div id="lazy-%s" cubicweb:loadurl="%s">' % (
            vid, html_escape(self.build_url('json', **urlparams))))
        if show_spinbox:
            w(u'<img src="data/loading.gif" id="%s-hole" alt="%s"/>'
              % (vid, self.req._('loading')))
        w(u'</div>')
        self._prepare_bindings(vid, reloadable)

    def forceview(self, vid):
        """trigger an event that will force immediate loading of the view
        on dom readyness
        """
        self.req.add_js('cubicweb.lazy.js')
        self.req.html_headers.add_onload("trigger_load('%s');" % vid)


class TabsMixin(LazyViewMixin):

    @property
    def cookie_name(self):
        return str('%s_active_tab' % self.config.appid)

    def active_tab(self, tabs, default):
        cookie = self.req.get_cookie()
        cookiename = self.cookie_name
        activetab = cookie.get(cookiename)
        if activetab is None:
            cookie[cookiename] = default
            self.req.set_cookie(cookie, cookiename)
            tab = default
        else:
            tab = activetab.value
        return tab in tabs and tab or default

    def prune_tabs(self, tabs):
        selected_tabs = []
        for tab in tabs:
            try:
                self.vreg.select_view(tab, self.req, self.rset)
                selected_tabs.append(tab)
            except NoSelectableObject:
                continue
        return selected_tabs

    def render_tabs(self, tabs, default, entity):
        self.req.add_css('ui.tabs.css')
        self.req.add_js(('ui.core.js', 'ui.tabs.js',
                         'cubicweb.ajax.js', 'cubicweb.tabs.js', 'cubicweb.lazy.js'))
        # prune tabs : not all are to be shown
        tabs = self.prune_tabs(tabs)
        # select a tab
        active_tab = self.active_tab(tabs, default)
        # build the html structure
        w = self.w
        w(u'<div id="entity-tabs">')
        w(u'<ul>')
        for tab in tabs:
            w(u'<li>')
            w(u'<a href="#as-%s">' % tab)
            w(u'<span onclick="set_tab(\'%s\', \'%s\')">' % (tab, self.cookie_name))
            w(self.req._(tab))
            w(u'</span>')
            w(u'</a>')
            w(u'</li>')
        w(u'</ul>')
        w(u'</div>')
        for tab in tabs:
            w(u'<div id="as-%s">' % tab)
            self.lazyview(tab, entity.eid)
            w(u'</div>')
        # call the set_tab() JS function *after* each tab is generated
        # because the callback binding needs to be done before
        self.req.html_headers.add_onload(u"""
   jQuery('#entity-tabs > ul').tabs( { selected: %(tabindex)s });
   set_tab('%(vid)s', '%(cookiename)s');
 """ % {'tabindex'   : tabs.index(active_tab),
        'vid'        : active_tab,
        'cookiename' : self.cookie_name})



class EntityRelationView(EntityView):
    """view displaying entity related stuff. Such a view _must_ provide rtype
    and target attributes

    Example :

    class ProjectScreenshotsView(EntityRelationView):
        '''display project's screenshots'''
        id = title = _('projectscreenshots')
        __select__ = implements('Project')
        rtype = 'screenshot'
        target = 'object'
    """
    __select__ = EntityView.__select__ & partial_has_related_entities()
    vid = 'list'
    
    def cell_call(self, row, col):
        rset = self.rset.get_entity(row, col).related(self.rtype, role(self))
        self.w(u'<h1>%s</h1>' % self.req._(self.title).capitalize())
        self.w(u'<div class="mainInfo">')
        self.wview(self.vid, rset, 'noresult')
        self.w(u'</div>')

from logilab.common.deprecation import class_moved
EntityRelatedTab = class_moved(EntityRelationView)
