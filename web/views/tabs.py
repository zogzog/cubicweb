"""base classes to handle tabbed views

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb import NoSelectableObject, role
from cubicweb.common.view import EntityView
from cubicweb.common.selectors import has_related_entities

from cubicweb.common.utils import HTMLHead

# the prepend hack only work for 1-level lazy views
# a whole lot different thing must be done otherwise
def prepend_post_inline_script(self, content):
    self.post_inlined_scripts.insert(0, content)
HTMLHead.prepend_post_inline_script = prepend_post_inline_script

class LazyViewMixin(object):

    def lazyview(self, vid, eid=None, show_spinbox=True, w=None):
        """a lazy version of wview
        first version only support lazy viewing for an entity at a time
        """
        w = w or self.w
        self.req.add_js('cubicweb.lazy.js')
        eid = eid if eid else ''
        w(u'<div id="lazy-%s" cubicweb__loadurl="%s-%s">' % (vid, vid, eid))
        if show_spinbox:
            w(u'<img src="data/loading.gif" id="%s-hole"/>' % vid)
        w(u'</div>')
        self.req.html_headers.prepend_post_inline_script(u"""
jQuery(document).ready(function () {
  $('#lazy-%(vid)s').bind('%(event)s', function(event) {
     load_now('#lazy-%(vid)s', '#%(vid)s-hole');
  });});""" % {'event' : 'load_%s' % vid,
               'vid' : vid})

    def forceview(self, vid):
        """trigger an event that will force immediate loading of the view
        on dom readyness
        """
        self.req.add_js('.lazy.js')
        self.req.html_headers.add_post_inline_script(u"""
jQuery(document).ready(function() {
  trigger_load('%(vid)s');})
""" % {'vid' : vid})

class TabsMixin(LazyViewMixin):

    def active_tab(self, tabs, default):
        cookie = self.req.get_cookie()
        activetab = cookie.get('active_tab')
        if activetab is None:
            cookie['active_tab'] = default
            self.req.set_cookie(cookie, 'active_tab')
            tab = default
        else:
            tab = activetab.value
        return tab if tab in tabs else default

    def render_tabs(self, tabs, default, entity):
        self.req.add_css('ui.tabs.css')
        self.req.add_js(('ui.core.js', 'ui.tabs.js', 'cubicweb.tabs.js', 'cubicweb.lazy.js'))
        active_tab = self.active_tab(tabs, default)
        self.req.html_headers.add_post_inline_script(u"""
 jQuery(document).ready(function() {
   jQuery('#entity-tabs > ul').tabs( { selected: %(tabindex)s });
   set_tab('%(vid)s');
 });
 """ % {'tabindex' : tabs.index(active_tab),
        'vid'      : active_tab})
        # build the html structure
        w = self.w
        w(u'<div id="entity-tabs">')
        w(u'<ul>')
        selected_tabs = []
        for tab in tabs:
            try:
                tabview = self.vreg.select_view(tab, self.req, self.rset)
                selected_tabs.append(tab)
            except NoSelectableObject:
                self.info('no selectable view for id %s', tab)
                continue
            w(u'<li>')
            w(u'<a href="#as-%s">' % tab)
            w(u'<span onclick="set_tab(\'%s\')">' % tab)
            w(self.req._(tab))
            w(u'</span>')
            w(u'</a>')
            w(u'</li>')
        w(u'</ul>')
        w(u'</div>')
        for tab in selected_tabs:
            w(u'<div id="as-%s">' % tab)
            self.lazyview(tab, entity.eid)
            w(u'</div>')


from cubicweb.web.views.basecontrollers import JSonController
class TabsController(JSonController):

    def js_remember_active_tab(self, tabname):
        cookie = self.req.get_cookie()
        cookie['active_tab'] = tabname
        self.req.set_cookie(cookie, 'active_tab')

    def js_lazily(self, vid_eid):
        vid, eid = vid_eid.split('-')
        rset = self.req.eid_rset(eid) if eid else None
        view = self.vreg.select_view(vid, self.req, rset)
        return self._set_content_type(view, view.dispatch())

class DataDependantTab(EntityView):
    """A view you should inherit from leftmost,
    to wrap another actual view displaying entity related stuff.
    Such a view _must_ provide the rtype, target and vid attributes :

    Example :

    class ProjectScreenshotsView(EntityRelationView):
        "display project's screenshots"
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
        rset = self.rset.get_entity(row, col).related(self.rtype, role(self))
        self.w(u'<div class="mainInfo">')
        self.wview(self.vid, rset, 'noresult')
        self.w(u'</div>')
