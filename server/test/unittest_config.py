"""tests for server config

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from os.path import join, dirname

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools import TestServerConfiguration

class ConfigTC(TestCase):

    def test_load_hooks_twice(self):
        class vreg:
            @staticmethod
            def registry_objects(registry):
                return []

        cfg1 = TestServerConfiguration('data/config1')
        cfg1.bootstrap_cubes()
        cfg2 = TestServerConfiguration('data/config2')
        cfg2.bootstrap_cubes()
        self.failIf(cfg1.load_hooks(vreg) is cfg2.load_hooks(vreg))
        self.failUnless('after_add_relation' in cfg1.load_hooks(vreg))
        self.failUnless('after_delete_relation' in cfg2.load_hooks(vreg))


if __name__ == '__main__':
    unittest_main()
