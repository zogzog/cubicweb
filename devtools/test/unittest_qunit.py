from logilab.common.testlib import unittest_main
from cubicweb.devtools.qunit import QUnitTestCase

from os import path as osp

JSTESTDIR = osp.abspath(osp.join(osp.dirname(__file__), 'data', 'js_examples'))


def js(name):
    return osp.join(JSTESTDIR, name)

class QUnitTestCaseTC(QUnitTestCase):

    all_js_tests = (
                    (js('test_simple_success.js'),),
                    (js('test_with_dep.js'), (js('dep_1.js'),)),
                    (js('test_with_ordered_deps.js'), (js('dep_1.js'), js('deps_2.js'),)),
                   )


    def test_simple_failure(self):
        js_tests = list(self._test_qunit(js('test_simple_failure.js')))
        self.assertEqual(len(js_tests), 3)
        test_1, test_2, test_3 = js_tests
        self.assertRaises(self.failureException, test_1[0], *test_1[1:])
        self.assertRaises(self.failureException, test_2[0], *test_2[1:])
        test_3[0](*test_3[1:])


if __name__ == '__main__':
    unittest_main()
