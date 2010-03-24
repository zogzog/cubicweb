"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from __future__ import with_statement
from copy import copy

from cubicweb import ConnectionError
from cubicweb.dbapi import ProgrammingError
from cubicweb.devtools.testlib import CubicWebTC

class DBAPITC(CubicWebTC):

    def test_public_repo_api(self):
        cnx = self.login('anon')
        self.assertEquals(cnx.get_schema(), self.repo.schema)
        self.assertEquals(cnx.source_defs(), {'system': {'adapter': 'native', 'uri': 'system'}})
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ProgrammingError, cnx.get_schema)
        self.assertRaises(ProgrammingError, cnx.source_defs)

    def test_db_api(self):
        cnx = self.login('anon')
        self.assertEquals(cnx.rollback(), None)
        self.assertEquals(cnx.commit(), None)
        self.restore_connection() # proper way to close cnx
        #self.assertEquals(cnx.close(), None)
        self.assertRaises(ProgrammingError, cnx.rollback)
        self.assertRaises(ProgrammingError, cnx.commit)
        self.assertRaises(ProgrammingError, cnx.close)

    def test_api(self):
        cnx = self.login('anon')
        self.assertEquals(cnx.user(None).login, 'anon')
        self.assertEquals(cnx.describe(1), (u'CWGroup', u'system', None))
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ProgrammingError, cnx.user, None)
        self.assertRaises(ProgrammingError, cnx.describe, 1)

    def test_session_data_api(self):
        cnx = self.login('anon')
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
        cnx = self.login('anon')
        self.assertEquals(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEquals(cnx.get_shared_data('data'), 4)
        cnx.get_shared_data('data', pop=True)
        cnx.get_shared_data('whatever', pop=True)
        self.assertEquals(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEquals(cnx.get_shared_data('data'), 4)
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ProgrammingError, cnx.check)
        self.assertRaises(ProgrammingError, cnx.set_shared_data, 'data', 0)
        self.assertRaises(ProgrammingError, cnx.get_shared_data, 'data')


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
