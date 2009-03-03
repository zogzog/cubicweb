"""base classes to handle tabbed views

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from logilab.common.decorators import monkeypatch
from logilab.mtconverter import html_escape

from cubicweb import NoSelectableObject, role
from cubicweb.common.view import EntityView
from cubicweb.common.selectors import has_related_entities
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
        # tabbed views do no support concatenation
        # hence we delegate to the default tab
        if self.req.form.get('vid') == 'primary':
            entity.view(default)
            return
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


class EntityRelatedTab(EntityView):
    """A view you should inherit from leftmost,
    to wrap another actual view displaying entity related stuff.
    Such a view _must_ provide the rtype, target and vid attributes :

    Example :

    class ProjectScreenshotsView(EntityRelationView):
        '''display project's screenshots'''
        id = title = _('projectscreenshots')
        accepts = ('Project',)
        rtype = 'screenshot'
        target = 'object'
        vid = 'gallery'
        __selectors__ = EntityRelationView.__selectors__ + (one_line_rset,)


    This is the view we want to have in a tab, only if there is something to show.
    Then, just define as below, and declare this being the tab content :

    class ProjectScreenshotTab(DataDependantTab, ProjectScreenshotsView):
        id = 'screenshots_tab'
    """
    __selectors__ = EntityView.__selectors__ + (has_related_entities,)
    vid = 'list'

    def cell_call(self, row, col):
        rset = self.entity(row, col).related(self.rtype, role(self))
        self.w(u'<div class="mainInfo">')
        self.wview(self.vid, rset, 'noresult')
        self.w(u'</div>')
