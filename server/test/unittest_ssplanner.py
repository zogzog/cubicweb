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
                                        {'X': 'ECache', 'XN': 'String'},
                                        {'X': 'EConstraintType', 'XN': 'String'},
                                        {'X': 'EEType', 'XN': 'String'},
                                        {'X': 'EGroup', 'XN': 'String'},
                                        {'X': 'EPermission', 'XN': 'String'},
                                        {'X': 'ERType', 'XN': 'String'},
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
                                        {'X': 'ECache', 'XN': 'String'},
                                        {'X': 'EConstraintType', 'XN': 'String'},
                                        {'X': 'EEType', 'XN': 'String'},
                                        {'X': 'EGroup', 'XN': 'String'},
                                        {'X': 'EPermission', 'XN': 'String'},
                                        {'X': 'ERType', 'XN': 'String'},
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
