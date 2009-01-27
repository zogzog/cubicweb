"""base classes to handle tabbed views

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb import NoSelectableObject, role
from cubicweb.common.view import EntityView

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
        self.req.add_js( ('ui.core.js', 'ui.tabs.js', 'cubicweb.tabs.js') )
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
        for tab in tabs:
            try:
                tabview = self.vreg.select_view(tab, self.req, self.rset)
            except NoSelectableObject:
                self.info('no selectable view for id %s', tab)
            w(u'<li>')
            w(u'<a href="#as-%s">' % tab)
            w(u'<span onclick="set_tab(\'%s\')">' % tab)
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


