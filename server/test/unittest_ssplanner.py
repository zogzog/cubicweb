"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.devtools import init_test_database
from cubicweb.devtools.repotest import BasePlannerTC, test_plan
from cubicweb.server.ssplanner import SSPlanner

# keep cnx so it's not garbage collected and the associated session is closed
repo, cnx = init_test_database('sqlite')

class SSPlannerTC(BasePlannerTC):
    repo = repo
    _test = test_plan

    def setUp(self):
        BasePlannerTC.setUp(self)
        self.planner = SSPlanner(self.o.schema, self.o._rqlhelper)
        self.system = self.o._repo.system_source

    def tearDown(self):
        BasePlannerTC.tearDown(self)

    def test_ordered_ambigous_sol(self):
        self._test('Any XN ORDERBY XN WHERE X name XN',
                   [('OneFetchStep', [('Any XN ORDERBY XN WHERE X name XN',
                                       [{'X': 'Basket', 'XN': 'String'},
                                        {'X': 'CWCache', 'XN': 'String'},
                                        {'X': 'CWConstraintType', 'XN': 'String'},
                                        {'X': 'CWEType', 'XN': 'String'},
                                        {'X': 'CWGroup', 'XN': 'String'},
                                        {'X': 'CWPermission', 'XN': 'String'},
                                        {'X': 'CWRType', 'XN': 'String'},
                                        {'X': 'File', 'XN': 'String'},
                                        {'X': 'Folder', 'XN': 'String'},
                                        {'X': 'Image', 'XN': 'String'},
                                        {'X': 'State', 'XN': 'String'},
                                        {'X': 'Tag', u'XN': 'String'},
                                        {'X': 'Transition', 'XN': 'String'}])],
                     None, None,
                     [self.system], None, [])])

    def test_groupeded_ambigous_sol(self):
        self._test('Any XN,COUNT(X) GROUPBY XN WHERE X name XN',
                   [('OneFetchStep', [('Any XN,COUNT(X) GROUPBY XN WHERE X name XN',
                                       [{'X': 'Basket', 'XN': 'String'},
                                        {'X': 'CWCache', 'XN': 'String'},
                                        {'X': 'CWConstraintType', 'XN': 'String'},
                                        {'X': 'CWEType', 'XN': 'String'},
                                        {'X': 'CWGroup', 'XN': 'String'},
                                        {'X': 'CWPermission', 'XN': 'String'},
                                        {'X': 'CWRType', 'XN': 'String'},
                                        {'X': 'File', 'XN': 'String'},
                                        {'X': 'Folder', 'XN': 'String'},
                                        {'X': 'Image', 'XN': 'String'},
                                        {'X': 'State', 'XN': 'String'},
                                        {'X': 'Tag', u'XN': 'String'},
                                        {'X': 'Transition', 'XN': 'String'}])],
                     None, None,
                     [self.system], None, [])])

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
