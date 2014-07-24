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
