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
"""this module contains base classes for windmill integration

:todo:

    * import CubicWeb session object into windmill scope to be able to run RQL
    * manage command line option from pytest to run specific use tests only
"""


import os, os.path as osp
import sys
import unittest

# imported by default to simplify further import statements
from logilab.common.testlib import unittest_main

from windmill.dep import functest

from cubicweb.devtools.httptest import CubicWebServerTC


# Excerpt from :ref:`windmill.authoring.unit`
class UnitTestReporter(functest.reports.FunctestReportInterface):
    def summary(self, test_list, totals_dict, stdout_capture):
        self.test_list = test_list

unittestreporter = UnitTestReporter()
functest.reports.register_reporter(unittestreporter)

class WindmillUnitTestCase(unittest.TestCase):
    def setUp(self):
        import windmill
        windmill.stdout, windmill.stdin = sys.stdout, sys.stdin
        from windmill.bin.admin_lib import configure_global_settings, setup
        configure_global_settings()
        windmill.settings['TEST_URL'] = self.test_url
        if hasattr(self,"windmill_settings"):
            for (setting,value) in self.windmill_settings.iteritems():
                windmill.settings[setting] = value
        self.windmill_shell_objects = setup()

    def tearDown(self):
        from windmill.bin.admin_lib import teardown
        teardown(self.windmill_shell_objects)


class CubicWebWindmillUseCase(CubicWebServerTC, WindmillUnitTestCase):
    """basic class for Windmill use case tests

    :param browser: browser identification string (firefox|ie|safari|chrome) (firefox by default)
    :param test_dir: testing file path or directory (./windmill by default)
    :param edit_test: load and edit test for debugging (False by default)
    """
    browser = 'firefox'
    test_dir = osp.join(os.getcwd(), 'windmill')
    edit_test = "-i" in sys.argv # detection for pytest invocation

    def setUp(self):
        # reduce log output
        from logging import getLogger, ERROR
        getLogger('cubicweb').setLevel(ERROR)
        getLogger('logilab').setLevel(ERROR)
        getLogger('windmill').setLevel(ERROR)
        # Start CubicWeb session before running the server to populate self.vreg
        CubicWebServerTC.setUp(self)
        assert os.path.exists(self.test_dir), "provide 'test_dir' as the given test file/dir"
        WindmillUnitTestCase.setUp(self)

    def tearDown(self):
        WindmillUnitTestCase.tearDown(self)
        CubicWebServerTC.tearDown(self)

    def testWindmill(self):
        if self.edit_test:
            # see windmill.bin.admin_options.Firebug
            import windmill
            windmill.settings['INSTALL_FIREBUG'] = 'firebug'
            windmill.settings['MOZILLA_PLUGINS'].append('/usr/share/mozilla-extensions/')
            windmill.settings['MOZILLA_PLUGINS'].append('/usr/share/xul-ext/')

        self.windmill_shell_objects['start_' + self.browser]()
        self.windmill_shell_objects['do_test'](self.test_dir,
                                               load=self.edit_test,
                                               threaded=False)
        # set a breakpoint to be able to debug windmill test
        if self.edit_test:
            import pdb; pdb.set_trace()
            return

        for test in unittestreporter.test_list:
            msg = ""
            self._testMethodDoc = getattr(test, "__doc__", None)
            self._testMethodName = test.__name__
            # try to display a better message in case of failure
            if hasattr(test, "tb"):
                msg = '\n'.join(test.tb)
            self.assertEquals(test.result, True, msg=msg)

