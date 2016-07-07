from pyramid_cubicweb.tests import PyramidCWTest

from cubicweb.view import View
from cubicweb.web import Redirect
from cubicweb import ValidationError


class Redirector(View):
    __regid__ = 'redirector'

    def call(self, rset=None):
        self._cw.set_header('Cache-Control', 'no-cache')
        raise Redirect('http://example.org')


def put_in_uncommitable_state(request):
    try:
        request.cw_cnx.execute('SET U login NULL WHERE U login "anon"')
    except ValidationError:
        pass
    request.response.body = b'OK'
    return request.response


class CoreTest(PyramidCWTest):
    anonymous_allowed = True

    def includeme(self, config):
        config.add_route('uncommitable', '/uncommitable')
        config.add_view(put_in_uncommitable_state, route_name='uncommitable')

    def test_cw_to_pyramid_copy_headers_on_redirect(self):
        self.vreg.register(Redirector)
        try:
            res = self.webapp.get('/?vid=redirector', expect_errors=True)
            self.assertEqual(res.status_int, 303)
            self.assertEqual(res.headers['Cache-Control'], 'no-cache')
        finally:
            self.vreg.unregister(Redirector)

    def test_uncommitable_cnx(self):
        res = self.webapp.get('/uncommitable')
        self.assertEqual(res.text, 'OK')
        self.assertEqual(res.status_int, 200)


if __name__ == '__main__':
    from unittest import main
    main()
