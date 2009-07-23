"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import sys
import os
from cStringIO import StringIO
from logilab.common.testlib import TestCase, unittest_main

if os.environ.get('APYCOT_ROOT'):
    root = os.environ['APYCOT_ROOT']
    CUBES_DIR = '%s/local/share/cubicweb/cubes/' % root
    os.environ['CW_CUBES_PATH'] = CUBES_DIR
    REGISTRY_DIR = '%s/etc/cubicweb.d/' % root
    os.environ['CW_INSTANCES_DIR'] = REGISTRY_DIR

from cubicweb.cwconfig import CubicWebConfiguration
CubicWebConfiguration.load_cwctl_plugins()

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
