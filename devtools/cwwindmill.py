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
from logging import getLogger, ERROR
import sys

# imported by default to simplify further import statements
from logilab.common.testlib import TestCase, unittest_main, Tags

try:
    import windmill
    from windmill.dep import functest
    from windmill.bin.admin_lib import configure_global_settings, setup, teardown
except ImportError, ex:
    windmill = None

from cubicweb.devtools.httptest import CubicWebServerTC, CubicWebServerConfig

if windmill is None:
    class CubicWebWindmillUseCase(CubicWebServerTC):
        tags = CubicWebServerTC.tags & Tags(('windmill',))

        def testWindmill(self):
            self.skipTest("can't import windmill %s" % ex)
else:
    # Excerpt from :ref:`windmill.authoring.unit`
    class UnitTestReporter(functest.reports.FunctestReportInterface):
        def summary(self, test_list, totals_dict, stdout_capture):
            self.test_list = test_list

    unittestreporter = UnitTestReporter()
    functest.reports.register_reporter(unittestreporter)

    class CubicWebWindmillUseCase(CubicWebServerTC):
        """basic class for Windmill use case tests

        If you want to change cubicweb test server parameters, define a new
        :class:`CubicWebServerConfig` and override the :var:`configcls`
        attribute:

            configcls = CubicWebServerConfig

        From Windmill configuration:

        .. attribute:: browser
            identification string (firefox|ie|safari|chrome) (firefox by default)
        .. attribute :: edit_test
            load and edit test for debugging (False by default)
        .. attribute:: test_dir (optional)
            testing file path or directory (windmill directory under your unit case
            file by default)

        Examples:

            browser = 'firefox'
            test_dir = osp.join(__file__, 'windmill')
            edit_test = False

        If you prefer, you can put here the use cases recorded by windmill GUI
        (services transformer) instead of the windmill sub-directory
        You can change `test_dir` as following:

            test_dir = __file__

        Instead of toggle `edit_test` value, try `python <test script> -f`
        """
        browser = 'firefox'

        edit_test = "-i" in sys.argv # detection for pytest invocation
        # Windmill use case are written with no anonymous user
        anonymous_allowed = False

        tags = CubicWebServerTC.tags & Tags(('windmill',))

        def _test_dir(self):
            """access to class attribute if possible or make assumption
            of expected directory"""
            try:
                return getattr(self, 'test_dir')
            except AttributeError:
                if os.path.basename(sys.argv[0]) == "pytest":
                    test_dir = os.getcwd()
                else:
                    import inspect
                    test_dir = os.path.dirname(inspect.stack()[-1][1])
                return osp.join(test_dir, 'windmill')

        def setUp(self):
            # Start CubicWeb session before running the server to populate self.vreg
            CubicWebServerTC.setUp(self)
            # XXX reduce log output (should be done in a cleaner way)
            # windmill fu** up our logging configuration
            for logkey in ('windmill', 'logilab', 'cubicweb'):
                getLogger(logkey).setLevel(ERROR)
            self.test_dir = self._test_dir()
            msg = "provide a valid 'test_dir' as the given test file/dir (current: %s)"
            assert os.path.exists(self.test_dir), (msg % self.test_dir)
            # windmill setup
            windmill.stdout, windmill.stdin = sys.stdout, sys.stdin
            configure_global_settings()
            windmill.settings['TEST_URL'] = self.config['base-url']
            if hasattr(self,"windmill_settings"):
                for (setting,value) in self.windmill_settings.iteritems():
                    windmill.settings[setting] = value
            self.windmill_shell_objects = setup()

        def tearDown(self):
            teardown(self.windmill_shell_objects)
            CubicWebServerTC.tearDown(self)

        def testWindmill(self):
            if self.edit_test:
                # see windmill.bin.admin_options.Firebug
                windmill.settings['INSTALL_FIREBUG'] = 'firebug'
                windmill.settings.setdefault('MOZILLA_PLUGINS', []).extend(
                    ['/usr/share/mozilla-extensions/',
                     '/usr/share/xul-ext/'])
            controller = self.windmill_shell_objects['start_' + self.browser]()
            self.windmill_shell_objects['do_test'](self.test_dir,
                                                   load=self.edit_test,
                                                   threaded=False)
            # set a breakpoint to be able to debug windmill test
            if self.edit_test:
                import pdb; pdb.set_trace()
                return

            # reporter
            for test in unittestreporter.test_list:
                msg = ""
                self._testMethodDoc = getattr(test, "__doc__", None)
                self._testMethodName = test.__name__
                # try to display a better message in case of failure
                if hasattr(test, "tb"):
                    msg = '\n'.join(test.tb)
                self.assertEqual(test.result, True, msg=msg)

