# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""unittest for cubicweb.dbapi"""

from __future__ import with_statement

from copy import copy

from logilab.common import tempattr

from cubicweb import ConnectionError, cwconfig
from cubicweb.dbapi import ProgrammingError
from cubicweb.devtools.testlib import CubicWebTC

class DBAPITC(CubicWebTC):

    def test_public_repo_api(self):
        cnx = self.login('anon')
        self.assertEqual(cnx.get_schema(), self.repo.schema)
        self.assertEqual(cnx.source_defs(), {'system': {'type': 'native', 'uri': 'system'}})
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ProgrammingError, cnx.get_schema)
        self.assertRaises(ProgrammingError, cnx.source_defs)

    def test_db_api(self):
        cnx = self.login('anon')
        self.assertEqual(cnx.rollback(), None)
        self.assertEqual(cnx.commit(), None)
        self.restore_connection() # proper way to close cnx
        #self.assertEqual(cnx.close(), None)
        self.assertRaises(ProgrammingError, cnx.rollback)
        self.assertRaises(ProgrammingError, cnx.commit)
        self.assertRaises(ProgrammingError, cnx.close)

    def test_api(self):
        cnx = self.login('anon')
        self.assertEqual(cnx.user(None).login, 'anon')
        self.assertEqual(cnx.describe(1), (u'CWSource', u'system', None))
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ProgrammingError, cnx.user, None)
        self.assertRaises(ProgrammingError, cnx.describe, 1)

    def test_shared_data_api(self):
        cnx = self.login('anon')
        self.assertEqual(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEqual(cnx.get_shared_data('data'), 4)
        cnx.get_shared_data('data', pop=True)
        cnx.get_shared_data('whatever', pop=True)
        self.assertEqual(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEqual(cnx.get_shared_data('data'), 4)
        self.restore_connection() # proper way to close cnx
        self.assertRaises(ProgrammingError, cnx.check)
        self.assertRaises(ProgrammingError, cnx.set_shared_data, 'data', 0)
        self.assertRaises(ProgrammingError, cnx.get_shared_data, 'data')

    def test_web_compatible_request(self):
        config = cwconfig.CubicWebNoAppConfiguration()
        with tempattr(self.cnx.vreg, 'config', config):
            self.cnx.use_web_compatible_requests('http://perdu.com')
            req = self.cnx.request()
            self.assertEqual(req.base_url(), 'http://perdu.com')
            self.assertEqual(req.from_controller(), 'view')
            self.assertEqual(req.relative_path(), '')
            req.ajax_replace_url('domid') # don't crash
            req.user.cw_adapt_to('IBreadCrumbs') # don't crash

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
