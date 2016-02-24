# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""this module contains base classes and utilities for integration with running
http server
"""
from __future__ import print_function

__docformat__ = "restructuredtext en"

import random
import threading
import socket

from six import PY3
from six.moves import range, http_client
from six.moves.urllib.parse import urlparse


from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools import ApptestConfiguration


def get_available_port(ports_scan):
    """return the first available port from the given ports range

    Try to connect port by looking for refused connection (111) or transport
    endpoint already connected (106) errors

    Raise a RuntimeError if no port can be found

    :type ports_range: list
    :param ports_range: range of ports to test
    :rtype: int

    .. see:: :func:`test.test_support.bind_port`
    """
    ports_scan = list(ports_scan)
    random.shuffle(ports_scan)  # lower the chance of race condition
    for port in ports_scan:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = s.connect(("localhost", port))
        except socket.error as err:
            if err.args[0] in (111, 106):
                return port
        finally:
            s.close()
    raise RuntimeError('get_available_port([ports_range]) cannot find an available port')


class _CubicWebServerTC(CubicWebTC):
    """Class for running a Twisted-based test web server.
    """
    ports_range = range(7000, 8000)

    def start_server(self):
        raise NotImplementedError

    def stop_server(self, timeout=15):
        """Stop the webserver, waiting for the thread to return"""
        raise NotImplementedError

    def web_login(self, user=None, passwd=None):
        """Log the current http session for the provided credential

        If no user is provided, admin connection are used.
        """
        if user is None:
            user  = self.admlogin
            passwd = self.admpassword
        if passwd is None:
            passwd = user
        response = self.web_get("login?__login=%s&__password=%s" %
                                (user, passwd))
        assert response.status == http_client.SEE_OTHER, response.status
        self._ident_cookie = response.getheader('Set-Cookie')
        assert self._ident_cookie
        return True

    def web_logout(self, user='admin', pwd=None):
        """Log out current http user"""
        if self._ident_cookie is not None:
            response = self.web_get('logout')
        self._ident_cookie = None

    def web_request(self, path='', method='GET', body=None, headers=None):
        """Return an http_client.HTTPResponse object for the specified path

        Use available credential if available.
        """
        if headers is None:
            headers = {}
        if self._ident_cookie is not None:
            assert 'Cookie' not in headers
            headers['Cookie'] = self._ident_cookie
        self._web_test_cnx.request(method, '/' + path, headers=headers, body=body)
        response = self._web_test_cnx.getresponse()
        response.body = response.read() # to chain request
        response.read = lambda : response.body
        return response

    def web_get(self, path='', body=None, headers=None):
        return self.web_request(path=path, body=body, headers=headers)

    def setUp(self):
        super(_CubicWebServerTC, self).setUp()
        port = self.config['port'] or get_available_port(self.ports_range)
        self.config.global_set_option('port', port) # force rewrite here
        self.config.global_set_option('base-url', 'http://127.0.0.1:%d/' % port)
        # call load_configuration again to let the config reset its datadir_url
        self.config.load_configuration()
        self.start_server()

    def tearDown(self):
        self.stop_server()
        super(_CubicWebServerTC, self).tearDown()


class CubicWebServerTC(_CubicWebServerTC):
    def start_server(self):
        if PY3:
            self.skipTest('not using twisted on python3')
        from twisted.internet import reactor
        from cubicweb.etwist.server import run
        # use a semaphore to avoid starting test while the http server isn't
        # fully initilialized
        semaphore = threading.Semaphore(0)
        def safe_run(*args, **kwargs):
            try:
                run(*args, **kwargs)
            finally:
                semaphore.release()

        reactor.addSystemEventTrigger('after', 'startup', semaphore.release)
        t = threading.Thread(target=safe_run, name='cubicweb_test_web_server',
                args=(self.config, True), kwargs={'repo': self.repo})
        self.web_thread = t
        t.start()
        semaphore.acquire()
        if not self.web_thread.isAlive():
            # XXX race condition with actual thread death
            raise RuntimeError('Could not start the web server')
        #pre init utils connection
        parseurl = urlparse(self.config['base-url'])
        assert parseurl.port == self.config['port'], (self.config['base-url'], self.config['port'])
        self._web_test_cnx = http_client.HTTPConnection(parseurl.hostname,
                                                        parseurl.port)
        self._ident_cookie = None

    def stop_server(self, timeout=15):
        """Stop the webserver, waiting for the thread to return"""
        from twisted.internet import reactor
        if self._web_test_cnx is None:
            self.web_logout()
            self._web_test_cnx.close()
        try:
            reactor.stop()
            self.web_thread.join(timeout)
            assert not self.web_thread.isAlive()

        finally:
            reactor.__init__()


class CubicWebWsgiTC(CubicWebServerTC):
    def start_server(self):
        from cubicweb.wsgi.handler import CubicWebWSGIApplication
        from wsgiref import simple_server
        from six.moves import queue

        config = self.config
        port = config['port'] or 8080
        interface = config['interface']
        handler_cls = simple_server.WSGIRequestHandler
        app = CubicWebWSGIApplication(config)
        start_flag = queue.Queue()

        def run(config, *args, **kwargs):
            try:
                self.httpd = simple_server.WSGIServer((interface, port), handler_cls)
                self.httpd.set_app(app)
            except Exception as exc:
                start_flag.put(False)
                start_flag.put(exc)
                raise
            else:
                start_flag.put(True)
            try:
                self.httpd.serve_forever()
            finally:
                self.httpd.server_close()
        t = threading.Thread(target=run, name='cubicweb_test_web_server',
                             args=(self.config, True), kwargs={'repo': self.repo})
        self.web_thread = t
        t.start()
        flag = start_flag.get()
        if not flag:
            t.join()
            self.fail(start_flag.get())
        parseurl = urlparse(self.config['base-url'])
        assert parseurl.port == self.config['port'], (self.config['base-url'], self.config['port'])
        self._web_test_cnx = http_client.HTTPConnection(parseurl.hostname,
                                                        parseurl.port)
        self._ident_cookie = None

    def stop_server(self, timeout=15):
        if self._web_test_cnx is None:
            self.web_logout()
            self._web_test_cnx.close()
        self.httpd.shutdown()
        self.web_thread.join(timeout)
