from pyramid_cubicweb.tests import PyramidCWTest
from pyramid_cubicweb import tools


class ToolsTest(PyramidCWTest):
    anonymous_allowed = True

    def test_clone_user(self):
        with self.admin_access.repo_cnx() as cnx:
            user = cnx.find('CWUser', login='anon').one()
            user.login  # fill the cache
            clone = tools.clone_user(self.repo, user)

            self.assertEqual(clone.eid, user.eid)
            self.assertEqual(clone.login, user.login)

            self.assertEqual(clone.cw_rset.rows, user.cw_rset.rows)
            self.assertEqual(clone.cw_rset.rql, user.cw_rset.rql)

    def test_cnx_attach_entity(self):
        with self.admin_access.repo_cnx() as cnx:
            user = cnx.find('CWUser', login='anon').one()

        with self.admin_access.repo_cnx() as cnx:
            tools.cnx_attach_entity(cnx, user)
            self.assertEqual(user.login, 'anon')


if __name__ == '__main__':
    from unittest import main
    main()
