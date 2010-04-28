# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# logilab-common is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""

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
