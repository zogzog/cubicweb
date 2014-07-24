import webtest.app

from cubicweb.devtools.webtest import CubicWebTestTC

from cubicweb.wsgi.request import CubicWebWsgiRequest


class WSGIAppTC(CubicWebTestTC):
    def test_content_type(self):
        r = webtest.app.TestRequest.blank('/', {'CONTENT_TYPE': 'text/plain'})

        req = CubicWebWsgiRequest(r.environ, self.vreg)

        self.assertEqual('text/plain', req.get_header('Content-Type'))
