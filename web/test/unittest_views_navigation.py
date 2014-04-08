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
"""cubicweb.web.views.navigation unit tests"""

from logilab.common.testlib import unittest_main, mock_object

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.views.navigation import (PageNavigation, SortedNavigation,
                                           PageNavigationSelect)
from cubicweb.web.views.ibreadcrumbs import BreadCrumbEntityVComponent

BreadCrumbEntityVComponent.visible = True

class NavigationTC(CubicWebTC):

    def test_navigation_selection_whatever(self):
        req = self.request()
        rset = self.execute('Any X,N WHERE X name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, PageNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, PageNavigation)
        req.set_search_state('normal')

    def test_navigation_selection_ordered(self):
        req = self.request()
        rset = self.execute('Any X,N ORDERBY N LIMIT 40 WHERE X name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset, page_size=20)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset, page_size=20)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('normal')
        html = navcomp.render()

    def test_navigation_selection_large_rset(self):
        req = self.request()
        rset = self.execute('Any X,N LIMIT 120 WHERE X name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset, page_size=20)
        self.assertIsInstance(navcomp, PageNavigationSelect)
        rset = self.execute('Any X,N ORDERBY N LIMIT 120 WHERE X name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset, page_size=20)
        self.assertIsInstance(navcomp, PageNavigationSelect)

    def test_navigation_selection_not_enough_1(self):
        req = self.request()
        rset = self.execute('Any X,N LIMIT 10 WHERE X name N')
        navcomp = self.vreg['components'].select_or_none('navigation', req, rset=rset)
        self.assertEqual(navcomp, None)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select_or_none('navigation', req, rset=rset)
        self.assertEqual(navcomp, None)
        req.set_search_state('normal')

    def test_navigation_selection_not_enough_2(self):
        req = self.request()
        rset = self.execute('Any N, COUNT(RDEF) GROUPBY N ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, SortedNavigation)
        req.set_search_state('W:X:Y:Z')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        self.assertIsInstance(navcomp, SortedNavigation)

    def test_navigation_selection_wrong_boundary(self):
        req = self.request()
        rset = self.execute('Any X,N WHERE X name N')
        req = self.request()
        req.form['__start'] = 1000000
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()

    def test_sorted_navigation_1(self):
        req = self.request()
        rset = self.execute('Any RDEF ORDERBY RT WHERE RDEF relation_type RT')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()

    def test_sorted_navigation_2(self):
        req = self.request()
        rset = self.execute('Any RDEF ORDERBY RDEF WHERE RDEF relation_type RT')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()

    def test_sorted_navigation_3(self):
        req = self.request()
        rset = self.execute('CWAttribute RDEF ORDERBY RDEF')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()

    def test_sorted_navigation_4(self):
        req = self.request()
        rset = self.execute('Any RDEF ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg['components'].select('navigation', req, rset=rset)
        html = navcomp.render()

    def test_sorted_navigation_5(self):
        req = self.request()
        rset = self.execute('Any N, COUNT(RDEF) GROUPBY N ORDERBY N WHERE RDEF relation_type RT, RT name N')
        navcomp = self.vreg['components'].select('navigation', rset.req, rset=rset)
        html = navcomp.render()


# XXX deactivate, contextual component has been removed
# class ContentNavigationTC(CubicWebTC):
    # def test_component_context(self):
    #     view = mock_object(is_primary=lambda x: True)
    #     rset = self.execute('CWUser X LIMIT 1')
    #     req = self.request()
    #     objs = self.vreg['ctxcomponents'].poss_visible_objects(
    #         req, rset=rset, view=view, context='navtop')
    #     # breadcrumbs should be in headers by default
    #     clsids = set(obj.id for obj in objs)
    #     self.assertIn('breadcrumbs', clsids)
    #     objs = self.vreg['ctxcomponents'].poss_visible_objects(
    #         req, rset=rset, view=view, context='navbottom')
    #     # breadcrumbs should _NOT_ be in footers by default
    #     clsids = set(obj.id for obj in objs)
    #     self.assertNotIn('breadcrumbs', clsids)
    #     self.execute('INSERT CWProperty P: P pkey "ctxcomponents.breadcrumbs.context", '
    #                  'P value "navbottom"')
    #     # breadcrumbs should now be in footers
    #     req.cnx.commit()
    #     objs = self.vreg['ctxcomponents'].poss_visible_objects(
    #         req, rset=rset, view=view, context='navbottom')

    #     clsids = [obj.id for obj in objs]
    #     self.assertIn('breadcrumbs', clsids)
    #     objs = self.vreg['ctxcomponents'].poss_visible_objects(
    #         req, rset=rset, view=view, context='navtop')

    #     clsids = [obj.id for obj in objs]
    #     self.assertNotIn('breadcrumbs', clsids)


if __name__ == '__main__':
    unittest_main()
