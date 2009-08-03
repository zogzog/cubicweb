"""cubicweb.web.views.navigation unit tests

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import unittest_main, mock_object
from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb.web.views.navigation import PageNavigation, SortedNavigation
from cubicweb.web.views.ibreadcrumbs import BreadCrumbEntityVComponent

BreadCrumbEntityVComponent.visible = True

class NavigationTC(EnvBasedTC):

    def test_navigation_selection(self):
        rset = self.execute('Any X,N WHERE X name N')
        req = self.request()
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, PageNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, PageNavigation)
        req.set_search_state('normal')
        rset = self.execute('Any X,N ORDERBY N WHERE X name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('normal')
        rset = self.execute('Any X,N LIMIT 10 WHERE X name N')
        navcomp = self.vreg['components'].select_object('navigation', req, rset=rset)
        self.assertEquals(navcomp, None)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select_object('navigation', req, rset=rset)
        self.assertEquals(navcomp, None)
        req.set_search_state('normal')
        rset = self.execute('Any N, COUNT(RDEF) GROUPBY N ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, SortedNavigation)


    def test_sorted_navigation(self):
        rset = self.execute('Any X,N ORDERBY N WHERE X name N')
        req = self.request()
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select('navigation', rset.req, rset=rset)
        html = navcomp.render()
        rset = self.execute('Any RDEF ORDERBY RT WHERE RDEF relation_type RT')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()
        rset = self.execute('Any RDEF ORDERBY RDEF WHERE RDEF relation_type RT')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()
        rset = self.execute('CWAttribute RDEF ORDERBY RDEF')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()
        rset = self.execute('Any RDEF ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()
        rset = self.execute('Any N, COUNT(RDEF) GROUPBY N ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg['components'].select('navigation', rset.req, rset=rset)
        html = navcomp.render()



class ContentNavigationTC(EnvBasedTC):

    def test_component_context(self):
        view = mock_object(is_primary=lambda x: True)
        rset = self.execute('CWUser X LIMIT 1')
        req = self.request()
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset=rset,
                                           view=view, context='navtop')
        # breadcrumbs should be in headers by default
        clsids = set(obj.id for obj in objs)
        self.failUnless('breadcrumbs' in clsids)
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset=rset,
                                          view=view, context='navbottom')
        # breadcrumbs should _NOT_ be in footers by default
        clsids = set(obj.id for obj in objs)
        self.failIf('breadcrumbs' in clsids)
        self.execute('INSERT CWProperty P: P pkey "contentnavigation.breadcrumbs.context", '
                     'P value "navbottom"')
        # breadcrumbs should now be in footers
        req.cnx.commit()
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset=rset,
                                          view=view, context='navbottom')

        clsids = [obj.id for obj in objs]
        self.failUnless('breadcrumbs' in clsids)
        objs = self.vreg.possible_vobjects('contentnavigation', req, rset=rset,
                                          view=view, context='navtop')

        clsids = [obj.id for obj in objs]
        self.failIf('breadcrumbs' in clsids)


if __name__ == '__main__':
    unittest_main()
