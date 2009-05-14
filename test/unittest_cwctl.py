import sys
import os
from cStringIO import StringIO
from logilab.common.testlib import TestCase, unittest_main

if os.environ.get('APYCOT_ROOT'):
    root = os.environ['APYCOT_ROOT']
    CUBES_DIR = '%s/local/share/cubicweb/cubes/' % root
    os.environ['CW_CUBES'] = CUBES_DIR
    REGISTRY_DIR = '%s/etc/cubicweb.d/' % root
    os.environ['CW_REGISTRY_DIR'] = REGISTRY_DIR

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
