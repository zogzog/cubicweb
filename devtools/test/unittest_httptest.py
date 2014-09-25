# copyright 2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unittest for cubicweb.devtools.httptest module"""

import httplib

from logilab.common.testlib import Tags
from cubicweb.devtools.httptest import CubicWebServerTC


class TwistedCWAnonTC(CubicWebServerTC):

    def test_response(self):
        try:
            response = self.web_get()
        except httplib.NotConnected as ex:
            self.fail("Can't connection to test server: %s" % ex)

    def test_response_anon(self):
        response = self.web_get()
        self.assertEqual(response.status, httplib.OK)

    def test_base_url(self):
        if self.config['base-url'] not in self.web_get().read():
            self.fail('no mention of base url in retrieved page')


class TwistedCWIdentTC(CubicWebServerTC):
    test_db_id = 'httptest-cwident'
    anonymous_allowed = False
    tags = CubicWebServerTC.tags | Tags(('auth',))

    def test_response_denied(self):
        response = self.web_get()
        self.assertEqual(response.status, httplib.FORBIDDEN)

    def test_login(self):
        response = self.web_get()
        if response.status != httplib.FORBIDDEN:
            self.skipTest('Already authenticated, "test_response_denied" must have failed')
        # login
        self.web_login(self.admlogin, self.admpassword)
        response = self.web_get()
        self.assertEqual(response.status, httplib.OK, response.body)
        # logout
        self.web_logout()
        response = self.web_get()
        self.assertEqual(response.status, httplib.FORBIDDEN, response.body)




if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
