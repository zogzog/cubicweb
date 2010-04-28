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
from cubicweb.devtools import init_test_database
from cubicweb.devtools.repotest import BasePlannerTC, test_plan
from cubicweb.server.ssplanner import SSPlanner

# keep cnx so it's not garbage collected and the associated session closed
repo, cnx = init_test_database()

def teardown_module(*args):
    global repo, cnx
    del repo, cnx

class SSPlannerTC(BasePlannerTC):
    repo = repo
    _test = test_plan

    def setUp(self):
        BasePlannerTC.setUp(self)
        self.planner = SSPlanner(self.o.schema, self.repo.vreg.rqlhelper)
        self.system = self.o._repo.system_source

    def tearDown(self):
        BasePlannerTC.tearDown(self)

    def test_ordered_ambigous_sol(self):
        self._test('Any XN ORDERBY XN WHERE X name XN, X is IN (Basket, State, Folder)',
                   [('OneFetchStep', [('Any XN ORDERBY XN WHERE X name XN, X is IN(Basket, State, Folder)',
                                       [{'X': 'Basket', 'XN': 'String'},
                                        {'X': 'State', 'XN': 'String'},
                                        {'X': 'Folder', 'XN': 'String'}])],
                     None, None,
                     [self.system], None, [])])

    def test_groupeded_ambigous_sol(self):
        self._test('Any XN,COUNT(X) GROUPBY XN WHERE X name XN, X is IN (Basket, State, Folder)',
                   [('OneFetchStep', [('Any XN,COUNT(X) GROUPBY XN WHERE X name XN, X is IN(Basket, State, Folder)',
                                       [{'X': 'Basket', 'XN': 'String'},
                                        {'X': 'State', 'XN': 'String'},
                                        {'X': 'Folder', 'XN': 'String'}])],
                     None, None,
                     [self.system], None, [])])

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
