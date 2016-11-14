from os.path import join
from shutil import rmtree

from cubicweb.pyramid.test import PyramidCWTest


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

        cookies = self.webapp.cookiejar._cookies['localhost.local']['/']
        self.assertNotIn('pauth_tkt', cookies)
        self.assertIn('auth_tkt', cookies)
        self.assertIsNone(cookies['auth_tkt'].expires)

        res = self.webapp.get('/logout')
        self.assertEqual(res.status_int, 303)

        self.assertNotIn('auth_tkt', cookies)
        self.assertNotIn('pauth_tkt', cookies)

        res = self.webapp.post('/login', {
            '__login': self.admlogin, '__password': self.admpassword,
            '__setauthcookie': 1})
        self.assertEqual(res.status_int, 303)

        cookies = self.webapp.cookiejar._cookies['localhost.local']['/']
        self.assertNotIn('auth_tkt', cookies)
        self.assertIn('pauth_tkt', cookies)
        self.assertIsNotNone(cookies['pauth_tkt'].expires)

    def test_login_bad_password(self):
        self.config.i18ncompile(['en', 'fr'])
        try:
            self.config._gettext_init()
            res = self.webapp.post(
                '/login',
                {'__login': self.admlogin, '__password': 'empty'},
                headers={'Accept-Language': 'fr'},
                status=403)
        finally:
            rmtree(join(self.config.apphome, 'i18n'))
        self.assertIn(u"\xc9chec de l'authentification", res.text)


if __name__ == '__main__':
    from unittest import main
    main()
