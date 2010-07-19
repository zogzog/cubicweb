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
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""this module contains base classes for windmill integration"""

import os, os.path as osp

# imported by default to simplify further import statements
from logilab.common.testlib import unittest_main

from windmill.authoring import unit
from windmill.dep import functest

from cubicweb.devtools.httptest import CubicWebServerTC


class UnitTestReporter(functest.reports.FunctestReportInterface):
    def summary(self, test_list, totals_dict, stdout_capture):
        self.test_list = test_list

unittestreporter = UnitTestReporter()
functest.reports.register_reporter(unittestreporter)

class CubicWebWindmillUseCase(CubicWebServerTC, unit.WindmillUnitTestCase):
    """basic class for Windmill use case tests

    :param browser: browser identification string (firefox|ie|safari|chrome) (firefox by default)
    :param test_dir: testing file path or directory (./windmill by default)
    """
    browser = 'firefox'
    test_dir = osp.join(os.getcwd(), 'windmill')

    def setUp(self):
        # reduce log output
        from logging import getLogger, ERROR
        getLogger('cubicweb').setLevel(ERROR)
        getLogger('logilab').setLevel(ERROR)
        getLogger('windmill').setLevel(ERROR)
        # Start CubicWeb session before running the server to populate self.vreg
        CubicWebServerTC.setUp(self)
        assert os.path.exists(self.test_dir), "provide 'test_dir' as the given test file/dir"
        unit.WindmillUnitTestCase.setUp(self)

    def tearDown(self):
        unit.WindmillUnitTestCase.tearDown(self)
        CubicWebServerTC.tearDown(self)

    def testWindmill(self):
        self.windmill_shell_objects['start_' + self.browser]()
        self.windmill_shell_objects['do_test'](self.test_dir, threaded=False)
        for test in unittestreporter.test_list:
            self._testMethodDoc = getattr(test, "__doc__", None)
            self._testMethodName = test.__name__
            self.assertEquals(test.result, True)


