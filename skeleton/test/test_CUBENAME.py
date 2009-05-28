"""template automatic tests

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main

class DefaultTC(TestCase):
    def test_something(self):
        self.skip('this cube has no test')

## uncomment the import if you want to activate automatic test for your
## template

# from cubicweb.devtools.testlib import AutomaticWebTest


if __name__ == '__main__':
    unittest_main()
