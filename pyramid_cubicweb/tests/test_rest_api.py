from __future__ import absolute_import

from pyramid_cubicweb.rest_api import EntityResource
from pyramid_cubicweb.core import CubicWebPyramidRequest
from pyramid.view import view_config

from pyramid_cubicweb.tests import PyramidCWTest


class RestApiTest(PyramidCWTest):
    def includeme(self, config):
        config.include('pyramid_cubicweb.rest_api')
        config.include('pyramid_cubicweb.tests.test_rest_api')

    def test_delete(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.create_entity('CWGroup', name=u'tmp')
            cnx.commit()

        self.login()
        res = self.webapp.delete('/cwgroup/tmp')
        self.assertEqual(res.status_int, 204)

        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.find('CWGroup', name=u'tmp').rowcount, 0)

    def test_rql_execute(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.create_entity('CWGroup', name=u'tmp')
            cnx.commit()
        self.login()
        params = {'test_rql_execute': 'test'}
        self.webapp.get('/cwgroup/tmp', params=params)


@view_config(
    route_name='cwentities',
    context=EntityResource,
    request_method='GET',
    request_param=('test_rql_execute',)
)
def rql_execute_view(context, request):
    """Return 500 response if rset.req is not a CubicWeb request.
    """
    if isinstance(context.rset.req, CubicWebPyramidRequest):
        request.response.status_int = 204
    else:
        request.response.status_int = 500
        request.response.text = 'rset.req is not a CubicWeb request'
    return request.response


def includeme(config):
    config.scan(__name__)


if __name__ == '__main__':
    from unittest import main
    main()
