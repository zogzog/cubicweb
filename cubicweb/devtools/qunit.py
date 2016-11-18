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
from __future__ import absolute_import, print_function

import os, os.path as osp
import errno
import shutil
from tempfile import mkdtemp
from subprocess import Popen, PIPE, STDOUT

from six.moves.queue import Queue, Empty

# imported by default to simplify further import statements
from logilab.common.testlib import Tags
import webtest.http

import cubicweb
from cubicweb.view import View
from cubicweb.web.controller import Controller
from cubicweb.web.views.staticcontrollers import StaticFileController, STATIC_CONTROLLERS
from cubicweb.devtools import webtest as cwwebtest
from cubicweb.devtools.testlib import TemporaryDirectory


class FirefoxHelper(object):

    def __init__(self, url):
        self._url = url
        self._process = None
        self._profile_dir = None
        self.firefox_cmd = ['firefox', '-no-remote']
        if os.name == 'posix':
            self.firefox_cmd = [osp.join(osp.dirname(__file__), 'data', 'xvfb-run.sh'),
                                '-a', '-s', '-noreset -screen 0 800x600x24'] + self.firefox_cmd

    def __enter__(self):
        self._profile_dir = mkdtemp(prefix='cwtest-ffxprof-')
        isavailable, reason = self.test()
        if not isavailable:
            raise RuntimeError(
                'firefox not available or not working properly (%s)' % reason)
        self.start()
        return self

    def __exit__(self, *exc_info):
        self.stop()
        shutil.rmtree(self._profile_dir, ignore_errors=True)

    def test(self):
        try:
            proc = Popen(['firefox', '--help'], stdout=PIPE, stderr=STDOUT)
            stdout, _ = proc.communicate()
            return proc.returncode == 0, stdout
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                msg = '[%s] %s' % (errno.errorcode[exc.errno], exc.strerror)
                return False, msg
            raise

    @property
    def log_file(self):
        return osp.join(self._profile_dir, 'cwtest.log')

    def start(self):
        self.stop()
        cmd = self.firefox_cmd + ['-silent', '--profile', self._profile_dir,
                                  '-url', self._url]
        with open(self.log_file, 'wb') as fout:
            self._process = Popen(cmd, stdout=fout, stderr=STDOUT)

    def stop(self):
        if self._process is not None:
            assert self._process.returncode is None,  self._process.returncode
            self._process.terminate()
            self._process.wait()
            self._process = None

    def __del__(self):
        self.stop()


class QUnitTestCase(cwwebtest.CubicWebTestTC):

    tags = cwwebtest.CubicWebTestTC.tags | Tags(('qunit',))

    # testfile, (dep_a, dep_b)
    all_js_tests = ()
    timeout_error = RuntimeError

    def setUp(self):
        super(QUnitTestCase, self).setUp()
        self.test_queue = Queue()
        class MyQUnitResultController(QUnitResultController):
            tc = self
            test_queue = self.test_queue
        self._qunit_controller = MyQUnitResultController
        self.webapp.app.appli.vreg.register(MyQUnitResultController)
        self.webapp.app.appli.vreg.register(QUnitView)
        self.webapp.app.appli.vreg.register(CWDevtoolsStaticController)
        self.server = webtest.http.StopableWSGIServer.create(self.webapp.app)
        self.config.global_set_option('base-url', self.server.application_url)

    def tearDown(self):
        self.server.shutdown()
        self.webapp.app.appli.vreg.unregister(self._qunit_controller)
        self.webapp.app.appli.vreg.unregister(QUnitView)
        self.webapp.app.appli.vreg.unregister(CWDevtoolsStaticController)
        super(QUnitTestCase, self).tearDown()

    def test_javascripts(self):
        for args in self.all_js_tests:
            self.assertIn(len(args), (1, 2))
            test_file = args[0]
            if len(args) > 1:
                depends = args[1]
            else:
                depends = ()
            with TemporaryDirectory():
                for name, func, args in self._test_qunit(test_file, depends):
                    with self.subTest(name=name):
                        func(*args)

    def _test_qunit(self, test_file, depends=(), timeout=10):
        QUnitView.test_file = test_file
        QUnitView.depends = depends

        while not self.test_queue.empty():
            self.test_queue.get(False)

        with FirefoxHelper(self.config['base-url'] + '?vid=qunit') as browser:
            test_count = 0
            error = False

            def runtime_error(*data):
                with open(browser.log_file) as logf:
                    print(logf.read())
                raise RuntimeError(*data)

            def timeout_failure(test_file, timeout, test_count):
                with open(browser.log_file) as logf:
                    print(logf.read())
                msg = '%s inactivity timeout (%is). %i test results received' % (
                    test_file, timeout, test_count)
                raise self.timeout_error(msg)

            while not error:
                try:
                    result, test_name, msg = self.test_queue.get(timeout=timeout)
                    test_name = '%s (%s)' % (test_name, test_file)
                    if result is None:
                        break
                    test_count += 1
                    if result:
                        yield test_name, lambda *args: 1, ()
                    else:
                        yield test_name, self.fail, (msg, )
                except Empty:
                    error = True
                    yield test_file, timeout_failure, (test_file, timeout, test_count)

        if test_count <= 0 and not error:
            yield test_name, runtime_error, ('No test yielded by qunit for %s' % test_file, )


class QUnitResultController(Controller):

    __regid__ = 'qunit_result'


    # Class variables to circumvent the instantiation of a new Controller for each request.
    _log_stack = [] # store QUnit log messages
    _current_module_name = '' # store the current QUnit module name

    def publish(self, rset=None):
        event = self._cw.form['event']
        getattr(self, 'handle_%s' % event)()
        return b''

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
        w(u'''<!DOCTYPE html>
        <html>
        <head>
        <meta http-equiv="content-type" content="application/html; charset=UTF-8"/>
        <!-- JS lib used as testing framework -->
        <link rel="stylesheet" type="text/css" media="all" href="/devtools/qunit.css" />
        <script src="/data/jquery.js" type="text/javascript"></script>
        <script src="/devtools/cwmock.js" type="text/javascript"></script>
        <script src="/devtools/qunit.js" type="text/javascript"></script>''')
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

        for dep in self.depends:
            w(u'    <script src="%s" type="text/javascript"></script>\n' % dep)

        w(u'    <!-- Test script itself -->')
        w(u'    <script src="%s" type="text/javascript"></script>' % self.test_file)
        w(u'''  </head>
        <body>
        <div id="qunit-fixture"></div>
        <div id="qunit"></div>
        </body>
        </html>''')


class CWDevtoolsStaticController(StaticFileController):
    __regid__ = 'devtools'

    def publish(self, rset=None):
        staticdir = osp.join(osp.dirname(__file__), 'data')
        relpath = self.relpath[len(self.__regid__) + 1:]
        return self.static_file(osp.join(staticdir, relpath))


STATIC_CONTROLLERS.append(CWDevtoolsStaticController)


if __name__ == '__main__':
    import unittest
    unittest.main()
