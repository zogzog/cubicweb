from logilab.mtconverter import html_escape

from cubicweb.common.view import EntityView

# XXX
# This is premature & tied to JPL
# It should go away & be replaced by something like
# a TabbedPrimaryView (that would really a primary view)

class TabView(EntityView):
    id = 'tabview'
    accepts = ('Project',)

    def active_tab(self):
        cookie = self.req.get_cookie()
        cookietab = cookie.get('active_tab')
        if cookietab is None:
            cookie['active_tab'] = 'project_main'
            self.req.set_cookie(cookie, 'active_tab')
        return cookietab and cookietab.value or 'project_main'

    def cell_call(self, row, col, tabs):
        self.req.add_css('ui.tabs.css')
        self.req.add_js( ('ui.core.js', 'ui.tabs.js', 'cubes.jpl.primary.js') )
        active_tab = self.active_tab()
        self.req.html_headers.add_post_inline_script(u"""
 jQuery(document).ready(function() {
   jQuery('#entity-tabs > ul').tabs( { selected: %(tabindex)s });
   set_tab('%(vid)s');
 });
 """ % {'tabindex' : tabs.index(active_tab),
        'vid'      : active_tab})
        # build the html structure
        self.w(u'<div id="entity-tabs">')
        self.w(u'<ul>')
        for tab in tabs:
            self.w(u'<li>')
            self.w(u'<a href="#as-%s">' % tab)
            cookie_setter = "set_tab('%s')" % tab
            self.w(u'<span onclick="%s">' % cookie_setter)
            self.w('%s' % self.req._(tab))
            self.w(u'</span>')
            self.w(u'</a>')
            self.w(u'</li>')
        self.w(u'</ul>')
        self.w(u'</div>')
        for tab in tabs:
            self.w(u'<div id="as-%s">' % tab)
            self.wview(tab, self.rset)
            self.w(u'</div>')    
  
