from six.moves import http_client

from logilab.common.testlib import Tags
from cubicweb.devtools.webtest import CubicWebTestTC


class CWTTC(CubicWebTestTC):
    def test_response(self):
        response = self.webapp.get('/')
        self.assertEqual(200, response.status_int)

    def test_base_url(self):
        if self.config['base-url'] not in self.webapp.get('/').text:
            self.fail('no mention of base url in retrieved page')


class CWTIdentTC(CubicWebTestTC):
    test_db_id = 'webtest-ident'
    anonymous_allowed = False
    tags = CubicWebTestTC.tags | Tags(('auth',))

    def test_reponse_denied(self):
        res = self.webapp.get('/', expect_errors=True)
        self.assertEqual(http_client.FORBIDDEN, res.status_int)

    def test_login(self):
        res = self.webapp.get('/', expect_errors=True)
        self.assertEqual(http_client.FORBIDDEN, res.status_int)

        self.login(self.admlogin, self.admpassword)
        res = self.webapp.get('/')
        self.assertEqual(http_client.OK, res.status_int)

        self.logout()
        res = self.webapp.get('/', expect_errors=True)
        self.assertEqual(http_client.FORBIDDEN, res.status_int)


if __name__ == '__main__':
    import unittest
    unittest.main()
