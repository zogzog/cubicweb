import webtest.app
from StringIO import StringIO

from cubicweb.devtools.webtest import CubicWebTestTC

from cubicweb.wsgi.request import CubicWebWsgiRequest


class WSGIAppTC(CubicWebTestTC):
    def test_content_type(self):
        r = webtest.app.TestRequest.blank('/', {'CONTENT_TYPE': 'text/plain'})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual('text/plain', req.get_header('Content-Type'))

    def test_content_body(self):
        r = webtest.app.TestRequest.blank('/', {
            'CONTENT_LENGTH': 12,
            'CONTENT_TYPE': 'text/plain',
            'wsgi.input': StringIO('some content')})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual('some content', req.content.read())

    def test_http_scheme(self):
        r = webtest.app.TestRequest.blank('/', {
            'wsgi.url_scheme': 'http'})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertFalse(req.https)

    def test_https_scheme(self):
        r = webtest.app.TestRequest.blank('/', {
            'wsgi.url_scheme': 'https'})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertTrue(req.https)

    def test_https_prefix(self):
        r = webtest.app.TestRequest.blank('/https/', {
            'wsgi.url_scheme': 'http'})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertTrue(req.https)

    def test_big_content(self):
        content = 'x'*100001
        r = webtest.app.TestRequest.blank('/', {
            'CONTENT_LENGTH': len(content),
            'CONTENT_TYPE': 'text/plain',
            'wsgi.input': StringIO(content)})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual(content, req.content.read())

    @classmethod
    def init_config(cls, config):
        super(WSGIAppTC, cls).init_config(config)
        config.https_uiprops = None
        config.https_datadir_url = None
