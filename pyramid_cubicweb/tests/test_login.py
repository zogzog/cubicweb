from pyramid_cubicweb.tests import PyramidCWTest


class LoginTest(PyramidCWTest):
    def test_login_form(self):
        res = self.webapp.get('/login')
        self.assertIn('__login', res.text)

    def test_login_password_login(self):
        res = self.webapp.post('/login', {
            '__login': self.admlogin, '__password': self.admpassword})
        self.assertEqual(res.status_int, 303)

        res = self.webapp.get('/login')
        self.assertEqual(res.status_int, 303)

    def test_login_password_login_cookie_expires(self):
        res = self.webapp.post('/login', {
            '__login': self.admlogin, '__password': self.admpassword})
        self.assertEqual(res.status_int, 303)
        cookie = self.webapp.cookiejar._cookies[
            'localhost.local']['/']['auth_tkt']
        self.assertIsNone(cookie.expires)

        res = self.webapp.get('/logout')
        self.assertEqual(res.status_int, 303)

        res = self.webapp.post('/login', {
            '__login': self.admlogin, '__password': self.admpassword,
            '__setauthcookie': 1})
        self.assertEqual(res.status_int, 303)
        cookie = self.webapp.cookiejar._cookies[
            'localhost.local']['/']['auth_tkt']
        self.assertIsNotNone(cookie.expires)
