# -*- coding: utf8 -*-
from StringIO import StringIO

import webtest

import pyramid.request

from pyramid_cubicweb.core import CubicWebPyramidRequest
from pyramid_cubicweb.tests import PyramidCWTest


class WSGIAppTest(PyramidCWTest):
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
                'wsgi.input': StringIO('some content')}))

        self.assertEqual('some content', req.content.read())

    def test_http_scheme(self):
        req = CubicWebPyramidRequest(
            self.make_request('/', {
                'wsgi.url_scheme': 'http'}))

        self.assertFalse(req.https)

    def test_https_scheme(self):
        req = CubicWebPyramidRequest(
            self.make_request('/', {
                'wsgi.url_scheme': 'https'}))

        self.assertTrue(req.https)

    def test_https_prefix(self):
        r = self.webapp.get('/https/')
        self.assertIn('https://', r.body)

    def test_big_content(self):
        content = 'x'*100001

        req = CubicWebPyramidRequest(
            self.make_request('/', {
                'CONTENT_LENGTH': len(content),
                'CONTENT_TYPE': 'text/plain',
                'wsgi.input': StringIO(content)}))

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
            (), (('filefield', 'aname', 'acontent'),))
        req = CubicWebPyramidRequest(
            self.make_request('/', POST=params, content_type=content_type))
        self.assertIn('filefield', req.form)
        fieldvalue = req.form['filefield']
        self.assertEqual(u'aname', fieldvalue[0])
        self.assertEqual('acontent', fieldvalue[1].read())

    def test_post_unicode_urlencoded(self):
        params = 'arg=%C3%A9'
        req = CubicWebPyramidRequest(
            self.make_request(
                '/', POST=params,
                content_type='application/x-www-form-urlencoded'))
        self.assertEqual(u"é", req.form['arg'])

    @classmethod
    def init_config(cls, config):
        super(WSGIAppTest, cls).init_config(config)
        config.https_uiprops = None
        config.https_datadir_url = None
