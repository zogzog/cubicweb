from cubicweb.devtools import qunit


def js(name):
    return '/static/js_examples/' + name

class QUnitTestCaseTC(qunit.QUnitTestCase):

    all_js_tests = (
                    (js('test_simple_success.js'),),
                    (js('test_with_dep.js'), (js('dep_1.js'),)),
                    (js('test_with_ordered_deps.js'), (js('dep_1.js'), js('deps_2.js'),)),
                   )


    def test_simple_failure(self):
        js_tests = list(self._test_qunit(js('test_simple_failure.js')))
        self.assertEqual(len(js_tests), 3)
        test_1, test_2, test_3 = js_tests
        self.assertRaises(self.failureException, test_1[1], *test_1[2:])
        self.assertRaises(self.failureException, test_2[1], *test_2[2:])
        test_3[1](*test_3[2:])


if __name__ == '__main__':
    from unittest import main
    main()
