# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from copy import copy

from logilab.common import tempattr

from cubicweb import ConnectionError, cwconfig, NoSelectableObject
from cubicweb.dbapi import ProgrammingError, _repo_connect
from cubicweb.devtools.testlib import CubicWebTC


class DBAPITC(CubicWebTC):

    def test_public_repo_api(self):
        cnx = _repo_connect(self.repo, login='anon', password='anon')
        self.assertEqual(cnx.get_schema(), self.repo.schema)
        self.assertEqual(cnx.source_defs(), {'system': {'type': 'native', 'uri': 'system',
                                                        'use-cwuri-as-url': False}})
        cnx.close()
        self.assertRaises(ProgrammingError, cnx.get_schema)
        self.assertRaises(ProgrammingError, cnx.source_defs)

    def test_db_api(self):
        cnx = _repo_connect(self.repo, login='anon', password='anon')
        self.assertEqual(cnx.rollback(), None)
        self.assertEqual(cnx.commit(), None)
        cnx.close()
        self.assertRaises(ProgrammingError, cnx.rollback)
        self.assertRaises(ProgrammingError, cnx.commit)
        self.assertRaises(ProgrammingError, cnx.close)

    def test_api(self):
        cnx = _repo_connect(self.repo, login='anon', password='anon')
        self.assertEqual(cnx.user(None).login, 'anon')
        self.assertEqual({'type': u'CWSource', 'source': u'system', 'extid': None},
                         cnx.entity_metas(1))
        self.assertEqual(cnx.describe(1), (u'CWSource', u'system', None))
        cnx.close()
        self.assertRaises(ProgrammingError, cnx.user, None)
        self.assertRaises(ProgrammingError, cnx.entity_metas, 1)
        self.assertRaises(ProgrammingError, cnx.describe, 1)

    def test_shared_data_api(self):
        cnx = _repo_connect(self.repo, login='anon', password='anon')
        self.assertEqual(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEqual(cnx.get_shared_data('data'), 4)
        cnx.get_shared_data('data', pop=True)
        cnx.get_shared_data('whatever', pop=True)
        self.assertEqual(cnx.get_shared_data('data'), None)
        cnx.set_shared_data('data', 4)
        self.assertEqual(cnx.get_shared_data('data'), 4)
        cnx.close()
        self.assertRaises(ProgrammingError, cnx.check)
        self.assertRaises(ProgrammingError, cnx.set_shared_data, 'data', 0)
        self.assertRaises(ProgrammingError, cnx.get_shared_data, 'data')

    def test_web_compatible_request(self):
        config = cwconfig.CubicWebNoAppConfiguration()
        cnx = _repo_connect(self.repo, login='admin', password='gingkow')
        with tempattr(cnx.vreg, 'config', config):
            cnx.use_web_compatible_requests('http://perdu.com')
            req = cnx.request()
            self.assertEqual(req.base_url(), 'http://perdu.com/')
            self.assertEqual(req.from_controller(), 'view')
            self.assertEqual(req.relative_path(), '')
            req.ajax_replace_url('domid') # don't crash
            req.user.cw_adapt_to('IBreadCrumbs') # don't crash

    def test_call_service(self):
        ServiceClass = self.vreg['services']['test_service'][0]
        for _cw in (self.request(), self.session):
            ret_value = _cw.call_service('test_service', msg='coucou')
            self.assertEqual('coucou', ServiceClass.passed_here.pop())
            self.assertEqual('babar', ret_value)
        with self.login('anon') as ctm:
            for _cw in (self.request(), self.session):
                with self.assertRaises(NoSelectableObject):
                    _cw.call_service('test_service', msg='toto')
                self.rollback()
                self.assertEqual([], ServiceClass.passed_here)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
