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
"""

"""
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.facet import insert_attr_select_relation, prepare_facets_rqlst


class InsertAttrRelationTC(CubicWebTC):

    def parse(self, query):
        rqlst = self.vreg.parse(self.session, query)
        select = rqlst.children[0]
        # XXX done in real life?
        select.remove_groups()
        return rqlst

    def _generate(self, rqlst, rel, role, attr):
        mainvar = prepare_facets_rqlst(rqlst)[0]
        insert_attr_select_relation(rqlst.children[0], mainvar, rel, role, attr)
        return rqlst.as_string()

    @property
    def select(self):
        return self.parse('Any B,(NOW - CD),S,V,U,GROUP_CONCAT(TN),VN,P,CD,BMD '
                          'GROUPBY B,CD,S,V,U,VN,P,BMD '
                          'WHERE B in_state S, B creation_date CD, '
                          'B modification_date BMD, T? tags B, T name TN, '
                          'V? bookmarked_by B, V title VN, B created_by U?, '
                          'B in_group P, P name "managers"')

    def test_1(self):
        self.assertEquals(self._generate(self.select, 'in_state', 'subject', 'name'),
                          "DISTINCT Any A,C ORDERBY C WHERE B in_group P, P name 'managers', "
                          "B in_state A, A name C, B is CWUser")

    def test_2(self):
        self.assertEquals(self._generate(self.select, 'tags', 'object', 'name'),
                          "DISTINCT Any A,C ORDERBY C WHERE B in_group P, P name 'managers', "
                          "A tags B, A name C, B is CWUser")

    def test_3(self):
        self.assertEquals(self._generate(self.select, 'created_by', 'subject', 'login'),
                          "DISTINCT Any A,C ORDERBY C WHERE B in_group P, P name 'managers', "
                          "B created_by A, A login C, B is CWUser")

    def test_4(self):
        self.assertEquals(self._generate(self.parse('Any X WHERE X is CWUser'), 'created_by', 'subject', 'login'),
                          "DISTINCT Any A,B ORDERBY B WHERE X is CWUser, X created_by A, A login B")

    def test_5(self):
        self.assertEquals(self._generate(self.parse('Any X,L WHERE X is CWUser, X login L'), 'created_by', 'subject', 'login'),
                          "DISTINCT Any A,B ORDERBY B WHERE X is CWUser, X created_by A, A login B")

    def test_nonregr1(self):
        select = self.parse('Any T,V WHERE T bookmarked_by V?, '
                            'V in_state VS, VS name "published", T created_by U')
        self.assertEquals(self._generate(select, 'created_by', 'subject', 'login'),
                          "DISTINCT Any A,B ORDERBY B WHERE T created_by U, "
                          "T created_by A, A login B, T is Bookmark")

    def test_nonregr2(self):
        #'DISTINCT Any X,TMP,N WHERE P name TMP, X version_of P, P is Project, X is Version, not X in_state S,S name "published", X num N ORDERBY TMP,N'
        select = self.parse('DISTINCT Any V,TN,L ORDERBY TN,L WHERE T nom TN, V connait T, T is Personne, V is CWUser,'
                            'NOT V in_state VS, VS name "published", V login L')
        rschema = self.schema['connait']
        for rdefs in rschema.rdefs.values():
            rdefs.cardinality =  '++'
        try:
            self.assertEquals(self._generate(select, 'in_state', 'subject', 'name'),
                              "DISTINCT Any A,B ORDERBY B WHERE V is CWUser, "
                              "NOT V in_state VS, VS name 'published', "
                              "V in_state A, A name B")
        finally:
            for rdefs in rschema.rdefs.values():
                rdefs.cardinality =  '**'

    def test_nonregr3(self):
        #'DISTINCT Any X,TMP,N WHERE P name TMP, X version_of P, P is Project, X is Version, not X in_state S,S name "published", X num N ORDERBY TMP,N'
        select = self.parse('DISTINCT Any X, MAX(Y) GROUPBY X WHERE X is CWUser, Y is Bookmark, X in_group A')
        self.assertEquals(self._generate(select, 'in_group', 'subject', 'name'),
                          "DISTINCT Any B,C ORDERBY C WHERE X is CWUser, X in_group B, B name C")


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
