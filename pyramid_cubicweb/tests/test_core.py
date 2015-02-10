from pyramid_cubicweb.tests import PyramidCWTest

from cubicweb.view import View
from cubicweb.web import Redirect


class Redirector(View):
    __regid__ = 'redirector'

    def call(self, rset=None):
        self._cw.set_header('Cache-Control', 'no-cache')
        raise Redirect('http://example.org')


class CoreTest(PyramidCWTest):
    anonymous_allowed = True

    def test_cw_to_pyramid_copy_headers_on_redirect(self):
        self.vreg.register(Redirector)
        try:
            res = self.webapp.get('/?vid=redirector', expect_errors=True)
            self.assertEqual(res.status_int, 303)
            self.assertEqual(res.headers['Cache-Control'], 'no-cache')
        finally:
            self.vreg.unregister(Redirector)
