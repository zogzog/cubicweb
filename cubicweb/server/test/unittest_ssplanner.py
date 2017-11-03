# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb import devtools
from cubicweb.devtools.repotest import BasePlannerTC, check_plan
from cubicweb.server.ssplanner import SSPlanner


def setUpModule(*args):
    # keep cnx so it's not garbage collected and the associated session closed
    global repo, cnx
    handler = devtools.get_test_db_handler(devtools.TestServerConfiguration('data', __file__))
    handler.build_db_cache()
    global repo, cnx
    repo, cnx = handler.get_repo_and_cnx()


def tearDownModule(*args):
    global repo, cnx
    del repo, cnx


class SSPlannerTC(BasePlannerTC):
    _test = check_plan

    def setUp(self):
        self.__class__.repo = repo
        BasePlannerTC.setUp(self)
        self.planner = SSPlanner(self.o.schema, self.repo.vreg.rqlhelper)
        self.system = self.o._repo.system_source

    def test_ordered_ambigous_sol(self):
        self._test(
            'Any XN ORDERBY XN WHERE X name XN, X is IN (Basket, State, Folder)',
            [('OneFetchStep', [('Any XN ORDERBY XN WHERE X name XN, '
                                'X is IN(Basket, State, Folder)',
                                [{'X': 'Basket', 'XN': 'String'},
                                 {'X': 'State', 'XN': 'String'},
                                 {'X': 'Folder', 'XN': 'String'}])],
              [])])

    def test_groupeded_ambigous_sol(self):
        self._test(
            'Any XN,COUNT(X) GROUPBY XN WHERE X name XN, X is IN (Basket, State, Folder)',
            [('OneFetchStep', [('Any XN,COUNT(X) GROUPBY XN WHERE X name XN, '
                                'X is IN(Basket, State, Folder)',
                                [{'X': 'Basket', 'XN': 'String'},
                                 {'X': 'State', 'XN': 'String'},
                                 {'X': 'Folder', 'XN': 'String'}])],
              [])])


if __name__ == '__main__':
    import unittest
    unittest.main()
