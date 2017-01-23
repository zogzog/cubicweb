# encoding=utf-8

import webtest.app
from io import BytesIO

from cubicweb.devtools.webtest import CubicWebTestTC

from cubicweb.wsgi.request import CubicWebWsgiRequest
from cubicweb.multipart import MultipartError


class WSGIAppTC(CubicWebTestTC):
    def test_content_type(self):
        r = webtest.app.TestRequest.blank('/', {'CONTENT_TYPE': 'text/plain'})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual('text/plain', req.get_header('Content-Type'))

    def test_content_body(self):
        r = webtest.app.TestRequest.blank('/', {
            'CONTENT_LENGTH': 12,
            'CONTENT_TYPE': 'text/plain',
            'wsgi.input': BytesIO(b'some content')})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual(b'some content', req.content.read())

    def test_big_content(self):
        content = b'x'*100001
        r = webtest.app.TestRequest.blank('/', {
            'CONTENT_LENGTH': len(content),
            'CONTENT_TYPE': 'text/plain',
            'wsgi.input': BytesIO(content)})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual(content, req.content.read())

    def test_post(self):
        self.webapp.post(
            '/',
            params={'__login': self.admlogin, '__password': self.admpassword})

    def test_post_bad_form(self):
        with self.assertRaises(MultipartError):
            self.webapp.post(
                '/',
                params='badcontent',
                headers={'Content-Type': 'multipart/form-data'})

    def test_post_non_form(self):
        self.webapp.post(
            '/',
            params='{}',
            headers={'Content-Type': 'application/json'})

    def test_get_multiple_variables(self):
        r = webtest.app.TestRequest.blank('/?arg=1&arg=2')
        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual([u'1', u'2'], req.form['arg'])

    def test_post_multiple_variables(self):
        r = webtest.app.TestRequest.blank('/', POST='arg=1&arg=2')
        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual([u'1', u'2'], req.form['arg'])

    def test_post_files(self):
        content_type, params = self.webapp.encode_multipart(
            (), (('filefield', 'aname', b'acontent'),))
        r = webtest.app.TestRequest.blank(
            '/', POST=params, content_type=content_type)
        req = CubicWebWsgiRequest(r.environ, self.vreg)
        self.assertIn('filefield', req.form)
        fieldvalue = req.form['filefield']
        self.assertEqual(u'aname', fieldvalue[0])
        self.assertEqual(b'acontent', fieldvalue[1].read())

    def test_post_unicode_urlencoded(self):
        params = 'arg=%C3%A9'
        r = webtest.app.TestRequest.blank(
            '/', POST=params, content_type='application/x-www-form-urlencoded')
        req = CubicWebWsgiRequest(r.environ, self.vreg)
        self.assertEqual(u"é", req.form['arg'])


if __name__ == '__main__':
    import unittest
    unittest.main()
