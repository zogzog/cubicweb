# -*- coding: utf-8 -*-
from io import BytesIO

import webtest

import pyramid.request

from cubicweb.pyramid.core import CubicWebPyramidRequest
from cubicweb.pyramid.test import PyramidCWTest


class WSGIAppTest(PyramidCWTest):
    settings = {'cubicweb.bwcompat': True}

    def make_request(self, path, environ=None, **kw):
        r = webtest.app.TestRequest.blank(path, environ, **kw)

        request = pyramid.request.Request(r.environ)
        request.registry = self.pyr_registry

        return request

    def test_content_type(self):
        req = CubicWebPyramidRequest(
            self.make_request('/', {'CONTENT_TYPE': 'text/plain'}))

        self.assertEqual('text/plain', req.get_header('Content-Type'))

    def test_content_body(self):
        req = CubicWebPyramidRequest(
            self.make_request('/', {
                'CONTENT_LENGTH': 12,
                'CONTENT_TYPE': 'text/plain',
                'wsgi.input': BytesIO(b'some content')}))

        self.assertEqual(b'some content', req.content.read())

    def test_big_content(self):
        content = b'x' * 100001

        req = CubicWebPyramidRequest(
            self.make_request('/', {
                'CONTENT_LENGTH': len(content),
                'CONTENT_TYPE': 'text/plain',
                'wsgi.input': BytesIO(content)}))

        self.assertEqual(content, req.content.read())

    def test_post(self):
        self.webapp.post(
            '/',
            params={'__login': self.admlogin, '__password': self.admpassword})

    def test_get_multiple_variables(self):
        req = CubicWebPyramidRequest(
            self.make_request('/?arg=1&arg=2'))

        self.assertEqual([u'1', u'2'], req.form['arg'])

    def test_post_multiple_variables(self):
        req = CubicWebPyramidRequest(
            self.make_request('/', POST='arg=1&arg=2'))

        self.assertEqual([u'1', u'2'], req.form['arg'])

    def test_post_files(self):
        content_type, params = self.webapp.encode_multipart(
            (), (('filefield', 'aname', b'acontent'),))
        req = CubicWebPyramidRequest(
            self.make_request('/', POST=params, content_type=content_type))
        self.assertIn('filefield', req.form)
        fieldvalue = req.form['filefield']
        self.assertEqual(u'aname', fieldvalue[0])
        self.assertEqual(b'acontent', fieldvalue[1].read())

    def test_post_unicode_urlencoded(self):
        params = 'arg=%C3%A9'
        req = CubicWebPyramidRequest(
            self.make_request(
                '/', POST=params,
                content_type='application/x-www-form-urlencoded'))
        self.assertEqual(u"é", req.form['arg'])

    def test_404(self):
        r = self.webapp.get('/unexisting/', status=404)
        self.assertNotIn('error occurred', r.text)
        self.assertIn('resource does not exist', r.text)


if __name__ == '__main__':
    from unittest import main
    main()
