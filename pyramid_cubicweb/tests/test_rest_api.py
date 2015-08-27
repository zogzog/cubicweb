from __future__ import absolute_import

from . import PyramidCWTest


class RestApiTest(PyramidCWTest):
    def includeme(self, config):
        config.include('pyramid_cubicweb.rest_api')

    def test_delete(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.create_entity('CWGroup', name=u'tmp')
            cnx.commit()

        self.login()
        res = self.webapp.delete('/cwgroup/tmp')
        self.assertEqual(res.status_int, 204)

        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.find('CWGroup', name=u'tmp').rowcount, 0)
