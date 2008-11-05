from cubicweb import ConnectionError
from cubicweb.dbapi import ProgrammingError
from cubicweb.devtools.apptest import EnvBasedTC


class DBAPITC(EnvBasedTC):
    @property
    def cnx(self):
        return self.login('anon')

    def test_public_repo_api(self):
        cnx = self.cnx
        self.assertEquals(cnx.get_schema(), self.env.repo.schema)
        self.assertEquals(cnx.source_defs(), {'system': {'adapter': 'native', 'uri': 'system'}})
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ProgrammingError, cnx.get_schema)
        self.assertRaises(ProgrammingError, cnx.source_defs)

    def test_db_api(self):
        cnx = self.cnx
        self.assertEquals(cnx.rollback(), None)
        self.assertEquals(cnx.commit(), None)
        self.restore_connection() # proper way to close cnx
        #self.assertEquals(cnx.close(), None)
        self.assertRaises(ProgrammingError, cnx.rollback)
        self.assertRaises(ProgrammingError, cnx.commit)
        self.assertRaises(ProgrammingError, cnx.close)

    def test_api(self):
        cnx = self.cnx
        self.assertEquals(cnx.user(None).login, 'anon')
        self.assertEquals(cnx.describe(1), (u'EGroup', u'system', None))
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ConnectionError, cnx.user, None)
        self.assertRaises(ConnectionError, cnx.describe, 1)

    def test_session_data_api(self):
        cnx = self.cnx
        self.assertEquals(cnx.get_session_data('data'), None)
        self.assertEquals(cnx.session_data(), {})
        cnx.set_session_data('data', 4)
        self.assertEquals(cnx.get_session_data('data'), 4)
        self.assertEquals(cnx.session_data(), {'data': 4})
        cnx.del_session_data('data')
        cnx.del_session_data('whatever')
        self.assertEquals(cnx.get_session_data('data'), None)
        self.assertEquals(cnx.session_data(), {})
        cnx.session_data()['data'] = 4
        self.assertEquals(cnx.get_session_data('data'), 4)
        self.assertEquals(cnx.session_data(), {'data': 4})

    def test_shared_data_api(self):
        cnx = self.cnx
        self.assertEquals(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEquals(cnx.get_shared_data('data'), 4)
        cnx.get_shared_data('data', pop=True)
        cnx.get_shared_data('whatever', pop=True)
        self.assertEquals(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEquals(cnx.get_shared_data('data'), 4)
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ConnectionError, cnx.check)
        self.assertRaises(ConnectionError, cnx.set_shared_data, 'data', 0)
        self.assertRaises(ConnectionError, cnx.get_shared_data, 'data')


# class DBAPICursorTC(EnvBasedTC):

#     @property
#     def cursor(self):
#         return self.env.cnx.cursor()

#     def test_api(self):
#         cu = self.cursor
#         self.assertEquals(cu.describe(1), (u'EGroup', u'system', None))
#         #cu.close()
#         #self.assertRaises(ConnectionError, cu.describe, 1)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
