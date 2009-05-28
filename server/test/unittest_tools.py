"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import TestCase, unittest_main

class ImportTC(TestCase):
    def test(self):
        # the minimal test: module is importable...
        import cubicweb.server.server
        import cubicweb.server.checkintegrity
        import cubicweb.server.serverctl

if __name__ == '__main__':
    unittest_main()
