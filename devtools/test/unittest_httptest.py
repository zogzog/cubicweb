from logilab.common.testlib import TestCase, unittest_main, tag
from cubicweb.devtools.httptest import CubicWebServerTC

import httplib
from os import path as osp


class TwistedCWAnonTC(CubicWebServerTC):

    def test_response(self):
        try:
            response = self.web_get()
        except httplib.NotConnected, ex:
            self.fail("Can't connection to test server: %s" % ex)

    def test_response_anon(self):
        response = self.web_get()
        self.assertEquals(response.status, httplib.OK)


    def test_base_url(self):
        if self.test_url not in self.web_get().read():
            self.fail('no mention of base url in retrieved page')


class TwistedCWIdentTC(CubicWebServerTC):

    anonymous_logged = False

    def test_response_denied(self):
        response = self.web_get()
        self.assertEquals(response.status, httplib.FORBIDDEN)

    def test_login(self):
        response = self.web_get()
        if response.status != httplib.FORBIDDEN:
             self.skip('Already authenticated')
        # login
        self.web_login(self.admlogin, self.admpassword)
        response = self.web_get()
        self.assertEquals(response.status, httplib.OK)
        # logout
        self.web_logout()
        response = self.web_get()
        self.assertEquals(response.status, httplib.FORBIDDEN)




if __name__ == '__main__':
    unittest_main()
