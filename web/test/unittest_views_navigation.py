"""cubicweb.web.views.navigation unit tests"""

from logilab.common.testlib import unittest_main, mock_object
from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb.web.views.navigation import PageNavigation, SortedNavigation
from cubicweb.web.views.ibreadcrumbs import BreadCrumbEntityVComponent

BreadCrumbEntityVComponent.visible = True

class NavigationTC(EnvBasedTC):
    
    def test_navigation_selection(self):
        rset = self.execute('Any X,N WHERE X name N')
        req = self.request()
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertIsInstance(navcomp, PageNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertIsInstance(navcomp, PageNavigation)
        req.set_search_state('normal')
        rset = self.execute('Any X,N ORDERBY N WHERE X name N')
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('normal')
        rset = self.execute('Any X,N LIMIT 10 WHERE X name N')
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertEquals(navcomp, None)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertEquals(navcomp, None)
        req.set_search_state('normal')
        rset = self.execute('Any N, COUNT(RDEF) GROUPBY N ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg.select_component('navigation', req, rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        
        
    def test_sorted_navigation(self):
        rset = self.execute('Any X,N ORDERBY N WHERE X name N')
        req = self.request()
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg.select_component('navigation', rset.req, rset)
        html = navcomp.dispatch()
        rset = self.execute('Any RDEF ORDERBY RT WHERE RDEF relation_type RT')
        navcomp = self.vreg.select_component('navigation', req, rset)
        html = navcomp.dispatch()
        rset = self.execute('Any RDEF ORDERBY RDEF WHERE RDEF relation_type RT')
        navcomp = self.vreg.select_component('navigation', req, rset)
        html = navcomp.dispatch()
        rset = self.execute('EFRDef RDEF ORDERBY RDEF')
        navcomp = self.vreg.select_component('navigation', req, rset)
        html = navcomp.dispatch()
        rset = self.execute('Any RDEF ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg.select_component('navigation', req, rset)
        html = navcomp.dispatch()
        rset = self.execute('Any N, COUNT(RDEF) GROUPBY N ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg.select_component('navigation', rset.req, rset)
        html = navcomp.dispatch()



class ContentNavigationTC(EnvBasedTC):

    def test_component_context(self):
        view = mock_object(is_primary=lambda x: True)
        rset = self.execute('EUser X LIMIT 1')
        req = self.request()
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset,
                                           view=view, context='navtop')
        # breadcrumbs should be in headers by default
        clsids = set(obj.id for obj in objs)
        self.failUnless('breadcrumbs' in clsids)
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset,
                                          view=view, context='navbottom')
        # breadcrumbs should _NOT_ be in footers by default
        clsids = set(obj.id for obj in objs)
        self.failIf('breadcrumbs' in clsids)
        self.execute('INSERT EProperty P: P pkey "contentnavigation.breadcrumbs.context", '
                     'P value "navbottom"')
        # breadcrumbs should now be in footers
        req.cnx.commit()
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset,
                                          view=view, context='navbottom')
        
        clsids = [obj.id for obj in objs]
        self.failUnless('breadcrumbs' in clsids)
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset,
                                          view=view, context='navtop')
        
        clsids = [obj.id for obj in objs]
        self.failIf('breadcrumbs' in clsids)
        

if __name__ == '__main__':
    unittest_main()
