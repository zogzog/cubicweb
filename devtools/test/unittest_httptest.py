import httplib

from cubicweb.devtools.httptest import CubicWebServerTC
from cubicweb.devtools.httptest import CubicWebServerConfig


class TwistedCWAnonTC(CubicWebServerTC):

    def test_response(self):
        try:
            response = self.web_get()
        except httplib.NotConnected, ex:
            self.fail("Can't connection to test server: %s" % ex)

    def test_response_anon(self):
        response = self.web_get()
        self.assertEqual(response.status, httplib.OK)

    def test_base_url(self):
        if self.config['base-url'] not in self.web_get().read():
            self.fail('no mention of base url in retrieved page')


class TwistedCWIdentTC(CubicWebServerTC):

    def setUp(self):
        CubicWebServerConfig.anonymous_logged = False
        CubicWebServerTC.setUp(self)

    def test_response_denied(self):
        response = self.web_get()
        self.assertEqual(response.status, httplib.FORBIDDEN)

    def test_login(self):
        response = self.web_get()
        if response.status != httplib.FORBIDDEN:
             self.skipTest('Already authenticated')
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
