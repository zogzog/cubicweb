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
"""this module contains base classes and utilities for integration with running
http server
"""
from __future__ import with_statement

__docformat__ = "restructuredtext en"

import threading
import socket
import httplib

from twisted.internet import reactor, error

from cubicweb.etwist.server import run
from cubicweb.devtools.testlib import CubicWebTC


def get_available_port(ports_scan):
    """return the first available port from the given ports range

    Try to connect port by looking for refused connection (111) or transport
    endpoint already connected (106) errors

    Raise a RuntimeError if no port can be found

    :type ports_range: list
    :param ports_range: range of ports to test
    :rtype: int
    """
    for port in ports_scan:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock = s.connect(("localhost", port))
        except socket.error, err:
            if err.args[0] in (111, 106):
                return port
        finally:
            s.close()
    raise RuntimeError('get_available_port([ports_range]) cannot find an available port')


class CubicWebServerTC(CubicWebTC):
    """basic class for running test server

    :param ports_range: range of http ports to test (range(7000, 8000) by default)
    :type ports_range: iterable
    :param anonymous_logged: is anonymous user logged by default ? (True by default)
    :type anonymous_logged: bool
    :param test_url: base url used by server
    :param test_host: server host
    :param test_port: server port

    The first port found as available in `ports_range` will be used to launch
    the test server
    """
    ports_range = range(7000, 8000)
    # anonymous is logged by default in cubicweb test cases
    anonymous_logged = True
    test_host='127.0.0.1'



    @property
    def test_url(self):
        return 'http://%s:%d/' % (self.test_host, self.test_port)

    def init_server(self):
        self.test_port = get_available_port(self.ports_range)
        self.config['port'] = self.test_port
        self.config['base-url'] = self.test_url
        self.config['force-html-content-type'] = True
        self.config['pyro-server'] = False

    def start_server(self):
        self.config.pyro_enabled = lambda : False
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
                             args=(self.config, self.vreg, True))
        self.web_thread = t
        if not self.anonymous_logged:
                self.config.global_set_option('anonymous-user', None)
        t.start()
        semaphore.acquire()
        if not self.web_thread.isAlive():
            # XXX race condition with actual thread death
            raise RuntimeError('Could not start the web server')
        #pre init utils connection
        self._web_test_cnx = httplib.HTTPConnection(self.test_host, self.test_port)
        self._ident_cookie = None

    def stop_server(self, timeout=15):
        """Stop the webserver, waiting for the thread to return"""
        if self._web_test_cnx is None:
            self.web_logout()
            self._web_test_cnx.close()
        try:
            reactor.stop()
            self.web_thread.join(timeout)
            assert not self.web_thread.isAlive()

        finally:
            reactor.__init__()

    def web_login(self, user=None, passwd=None):
        """Log the current http session for the provided credential

        If no user is provided, admin connection are used.
        """
        if user is None:
            user  = self.admlogin
            passwd = self.admpassword
        if passwd is None:
            passwd = user
        self.login(user)
        response = self.web_get("?__login=%s&__password=%s" %
                                (user, passwd))
        assert response.status == httplib.SEE_OTHER, response.status
        self._ident_cookie = response.getheader('Set-Cookie')
        assert self._ident_cookie
        return True

    def web_logout(self, user='admin', pwd=None):
        """Log out current http user"""
        if self._ident_cookie is not None:
            response = self.web_get('logout')
        self._ident_cookie = None

    def web_get(self, path='', headers=None):
        """Return an httplib.HTTPResponse object for the specified path

        Use available credential if available.
        """
        if headers is None:
            headers = {}
        if self._ident_cookie is not None:
            assert 'Cookie' not in headers
            headers['Cookie'] = self._ident_cookie
        self._web_test_cnx.request("GET", '/' + path, headers=headers)
        response = self._web_test_cnx.getresponse()
        response.body = response.read() # to chain request
        response.read = lambda : response.body
        return response

    def setUp(self):
        CubicWebTC.setUp(self)
        self.init_server()
        self.start_server()

    def tearDown(self):
        try:
            self.stop_server()
        except error.ReactorNotRunning, err:
            # Server could be launched manually
            print err
        CubicWebTC.tearDown(self)

