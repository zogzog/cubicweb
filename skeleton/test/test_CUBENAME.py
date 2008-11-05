"""template automatic tests"""

from logilab.common.testlib import TestCase, unittest_main

class DefaultTC(TestCase):
    def test_something(self):
        self.skip('this cube has no test')

## uncomment the import if you want to activate automatic test for your
## template

# from cubicweb.devtools.testlib import AutomaticWebTest


if __name__ == '__main__':
    unittest_main()
