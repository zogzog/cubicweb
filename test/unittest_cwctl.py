"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import sys
import os
from cStringIO import StringIO
from logilab.common.testlib import TestCase, unittest_main

from cubicweb.cwconfig import CubicWebConfiguration
CubicWebConfiguration.load_cwctl_plugins() # XXX necessary?

class CubicWebCtlTC(TestCase):
    def setUp(self):
        self.stream = StringIO()
        sys.stdout = self.stream
    def tearDown(self):
        sys.stdout = sys.__stdout__

    def test_list(self):
        from cubicweb.cwctl import ListCommand
        ListCommand().run([])

if __name__ == '__main__':
    unittest_main()
