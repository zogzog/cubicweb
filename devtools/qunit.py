# copyright 2010-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import os, os.path as osp
from tempfile import mkdtemp, NamedTemporaryFile, TemporaryFile
import tempfile
from Queue import Queue, Empty
from subprocess import Popen, check_call, CalledProcessError
from shutil import rmtree, copy as copyfile
from uuid import uuid4

# imported by default to simplify further import statements
from logilab.common.testlib import unittest_main, with_tempdir, InnerTest, Tags
from logilab.common.shellutils import getlogin

import cubicweb
from cubicweb.view import View
from cubicweb.web.controller import Controller
from cubicweb.web.views.staticcontrollers import StaticFileController, STATIC_CONTROLLERS
from cubicweb.devtools.httptest import CubicWebServerTC


class VerboseCalledProcessError(CalledProcessError):

    def __init__(self, returncode, command, stdout, stderr):
        super(VerboseCalledProcessError, self).__init__(returncode, command)
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        str = [ super(VerboseCalledProcessError, self).__str__()]
        if self.stdout.strip():
            str.append('******************')
            str.append('* process stdout *')
            str.append('******************')
            str.append(self.stdout)
        if self.stderr.strip():
            str.append('******************')
            str.append('* process stderr *')
            str.append('******************')
            str.append(self.stderr)
        return '\n'.join(str)



class FirefoxHelper(object):

    profile_name_mask = 'PYTEST_PROFILE_%(uid)s'

    def __init__(self, url=None):
        self._process = None
        self._profile_dir = mkdtemp(prefix='cwtest-ffxprof-')
        self.firefox_cmd = ['firefox', '-no-remote']
        if os.name == 'posix':
            self.firefox_cmd = [osp.join(osp.dirname(__file__), 'data', 'xvfb-run.sh'),
                                '-a', '-s', '-noreset -screen 0 800x600x24'] + self.firefox_cmd

    def start(self, url):
        self.stop()
        cmd = self.firefox_cmd + ['-silent', '--profile', self._profile_dir,
                                  '-url', url]
        with open(os.devnull, 'w') as fnull:
            self._process = Popen(cmd, stdout=fnull, stderr=fnull)

    def stop(self):
        if self._process is not None:
            assert self._process.returncode is None,  self._process.returncode
            self._process.terminate()
            self._process.wait()
            self._process = None

    def __del__(self):
        self.stop()


class QUnitTestCase(CubicWebServerTC):

    tags = CubicWebServerTC.tags | Tags(('qunit',))

    # testfile, (dep_a, dep_b)
    all_js_tests = ()

    def setUp(self):
        self.config.global_set_option('access-control-allow-origin', '*')
        super(QUnitTestCase, self).setUp()
        self.test_queue = Queue()
        class MyQUnitResultController(QUnitResultController):
            tc = self
            test_queue = self.test_queue
        self._qunit_controller = MyQUnitResultController
        self.vreg.register(MyQUnitResultController)
        self.vreg.register(QUnitView)
        self.vreg.register(CWSoftwareRootStaticController)

    def tearDown(self):
        super(QUnitTestCase, self).tearDown()
        self.vreg.unregister(self._qunit_controller)
        self.vreg.unregister(QUnitView)
        self.vreg.unregister(CWSoftwareRootStaticController)

    def abspath(self, path):
        """use self.__module__ to build absolute path if necessary"""
        if not osp.isabs(path):
           dirname = osp.dirname(__import__(self.__module__).__file__)
           return osp.abspath(osp.join(dirname,path))
        return path

    def test_javascripts(self):
        for args in self.all_js_tests:
            test_file = self.abspath(args[0])
            if len(args) > 1:
                depends   = [self.abspath(dep) for dep in args[1]]
            else:
                depends = ()
            if len(args) > 2:
                data   = [self.abspath(data) for data in args[2]]
            else:
                data = ()
            for js_test in self._test_qunit(test_file, depends, data):
                yield js_test

    @with_tempdir
    def _test_qunit(self, test_file, depends=(), data_files=(), timeout=10):
        assert osp.exists(test_file), test_file
        for dep in depends:
            assert osp.exists(dep), dep
        for data in data_files:
            assert osp.exists(data), data

        QUnitView.test_file = test_file
        QUnitView.depends = depends

        while not self.test_queue.empty():
            self.test_queue.get(False)

        browser = FirefoxHelper()
        browser.start(self.config['base-url'] + "?vid=qunit")
        test_count = 0
        error = False
        def raise_exception(cls, *data):
            raise cls(*data)
        while not error:
            try:
                result, test_name, msg = self.test_queue.get(timeout=timeout)
                test_name = '%s (%s)' % (test_name, test_file)
                self.set_description(test_name)
                if result is None:
                    break
                test_count += 1
                if result:
                    yield InnerTest(test_name, lambda : 1)
                else:
                    yield InnerTest(test_name, self.fail, msg)
            except Empty:
                error = True
                msg = '%s inactivity timeout (%is). %i test results received'
                yield InnerTest(test_file, raise_exception, RuntimeError,
                                 msg % (test_file, timeout, test_count))
        browser.stop()
        if test_count <= 0 and not error:
            yield InnerTest(test_name, raise_exception, RuntimeError,
                            'No test yielded by qunit for %s' % test_file)

class QUnitResultController(Controller):

    __regid__ = 'qunit_result'


    # Class variables to circumvent the instantiation of a new Controller for each request.
    _log_stack = [] # store QUnit log messages
    _current_module_name = '' # store the current QUnit module name

    def publish(self, rset=None):
        event = self._cw.form['event']
        getattr(self, 'handle_%s' % event)()

    def handle_module_start(self):
        self.__class__._current_module_name = self._cw.form.get('name', '')

    def handle_test_done(self):
        name = '%s // %s' %  (self._current_module_name, self._cw.form.get('name', ''))
        failures = int(self._cw.form.get('failures', 0))
        total = int(self._cw.form.get('total', 0))

        self._log_stack.append('%i/%i assertions failed' % (failures, total))
        msg = '\n'.join(self._log_stack)

        if failures:
            self.tc.test_queue.put((False, name, msg))
        else:
            self.tc.test_queue.put((True, name, msg))
        self._log_stack[:] = []

    def handle_done(self):
        self.tc.test_queue.put((None, None, None))

    def handle_log(self):
        result = self._cw.form['result']
        message = self._cw.form.get('message', '<no message>')
        actual = self._cw.form.get('actual')
        expected = self._cw.form.get('expected')
        source = self._cw.form.get('source')
        log = '%s: %s' % (result, message)
        if result == 'false' and actual is not None and expected is not None:
            log += ' (got: %s, expected: %s)' % (actual, expected)
            if source is not None:
                log += '\n' + source
        self._log_stack.append(log)


class QUnitView(View):
    __regid__ = 'qunit'

    templatable = False

    depends = None
    test_file = None

    def call(self, **kwargs):
        w = self.w
        req = self._cw
        data = {
            'jquery': req.data_url('jquery.js'),
            'web_test': req.build_url('cwsoftwareroot/devtools/data'),
        }
        w(u'''<!DOCTYPE html>
        <html>
        <head>
        <meta http-equiv="content-type" content="application/html; charset=UTF-8"/>
        <!-- JS lib used as testing framework -->
        <link rel="stylesheet" type="text/css" media="all" href="%(web_test)s/qunit.css" />
        <script src="%(jquery)s" type="text/javascript"></script>
        <script src="%(web_test)s/cwmock.js" type="text/javascript"></script>
        <script src="%(web_test)s/qunit.js" type="text/javascript"></script>'''
        % data)
        w(u'<!-- result report tools -->')
        w(u'<script type="text/javascript">')
        w(u"var BASE_URL = '%s';" % req.base_url())
        w(u'''
            QUnit.moduleStart(function (details) {
              jQuery.ajax({
                          url: BASE_URL + 'qunit_result',
                         data: {"event": "module_start",
                                "name": details.name},
                         async: false});
            });

            QUnit.testDone(function (details) {
              jQuery.ajax({
                          url: BASE_URL + 'qunit_result',
                         data: {"event": "test_done",
                                "name": details.name,
                                "failures": details.failed,
                                "total": details.total},
                         async: false});
            });

            QUnit.done(function (details) {
              jQuery.ajax({
                           url: BASE_URL + 'qunit_result',
                           data: {"event": "done",
                                  "failures": details.failed,
                                  "total": details.total},
                           async: false});
            });

            QUnit.log(function (details) {
              jQuery.ajax({
                           url: BASE_URL + 'qunit_result',
                           data: {"event": "log",
                                  "result": details.result,
                                  "actual": details.actual,
                                  "expected": details.expected,
                                  "source": details.source,
                                  "message": details.message},
                           async: false});
            });''')
        w(u'</script>')
        w(u'<!-- Test script dependencies (tested code for example) -->')

        prefix = len(cubicweb.CW_SOFTWARE_ROOT) + 1
        for dep in self.depends:
            dep = req.build_url('cwsoftwareroot/') + dep[prefix:]
            w(u'    <script src="%s" type="text/javascript"></script>' % dep)

        w(u'    <!-- Test script itself -->')
        test_url = req.build_url('cwsoftwareroot/') + self.test_file[prefix:]
        w(u'    <script src="%s" type="text/javascript"></script>' % test_url)
        w(u'''  </head>
        <body>
        <div id="qunit-fixture"></div>
        <div id="qunit"></div>
        </body>
        </html>''')


class CWSoftwareRootStaticController(StaticFileController):
    __regid__ = 'cwsoftwareroot'

    def publish(self, rset=None):
        staticdir = cubicweb.CW_SOFTWARE_ROOT
        relpath = self.relpath[len(self.__regid__) + 1:]
        return self.static_file(osp.join(staticdir, relpath))


STATIC_CONTROLLERS.append(CWSoftwareRootStaticController)


if __name__ == '__main__':
    unittest_main()
