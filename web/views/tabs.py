"""base classes to handle tabbed views

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb import NoSelectableObject, role
from cubicweb.common.selectors import has_related_entities
from cubicweb.common.view import EntityView

class TabsMixIn(object):
    
    def active_tab(self, default):
        cookie = self.req.get_cookie()
        activetab = cookie.get('active_tab')
        if activetab is None:
            cookie['active_tab'] = default
            self.req.set_cookie(cookie, 'active_tab')
            return default
        return activetab.value

    def render_tabs(self, tabs, default, **kwargs):
        self.req.add_css('ui.tabs.css')
        self.req.add_js( ('ui.core.js', 'ui.tabs.js', 'cubicweb.tabs.js') )
        active_tab = self.active_tab(default)
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
        tabviews = []
        for tab in tabs:
            try:
                tabview = self.vreg.select_view(tab, self.req, self.rset, **kwargs)
            except NoSelectableObject:
                continue
            tabviews.append(tabview)
            w(u'<li>')
            w(u'<a href="#as-%s">' % tab)
            w(u'<span onclick="set_tab(\'%s\')">' % tab)
            w(self.req._(tab))
            w(u'</span>')
            w(u'</a>')
            w(u'</li>')
        w(u'</ul>')
        w(u'</div>')
        # XXX ajaxify !
        for tabview in tabviews:
            w(u'<div id="as-%s">' % tabview.id)
            tabview.dispatch(w=self.w, **kwargs)
            w(u'</div>')    

  
class EntityRelationTab(EntityView):
    __selectors__ = EntityView.__selectors__ + (has_related_entities,)
    vid = 'list'

    def cell_call(self, row, col):
        rset = self.rset.get_entity(row, col).related(self.rtype, role(self))
        self.w(u'<div class="mainInfo">')
        self.wview(self.vid, rset, 'noresult')
        self.w(u'</div>')
