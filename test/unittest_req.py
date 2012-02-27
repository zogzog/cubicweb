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

from logilab.common.testlib import TestCase, unittest_main
from cubicweb import ObjectNotFound
from cubicweb.req import RequestSessionBase
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb import Unauthorized

class RequestTC(TestCase):
    def test_rebuild_url(self):
        rebuild_url = RequestSessionBase(None).rebuild_url
        self.assertEqual(rebuild_url('http://logilab.fr?__message=pouet', __message='hop'),
                          'http://logilab.fr?__message=hop')
        self.assertEqual(rebuild_url('http://logilab.fr', __message='hop'),
                          'http://logilab.fr?__message=hop')
        self.assertEqual(rebuild_url('http://logilab.fr?vid=index', __message='hop'),
                          'http://logilab.fr?__message=hop&vid=index')

    def test_build_url(self):
        req = RequestSessionBase(None)
        req.from_controller = lambda : 'view'
        req.relative_path = lambda includeparams=True: None
        req.base_url = lambda secure=None: 'http://testing.fr/cubicweb/'
        self.assertEqual(req.build_url(), u'http://testing.fr/cubicweb/view')
        self.assertEqual(req.build_url(None), u'http://testing.fr/cubicweb/view')
        self.assertEqual(req.build_url('one'), u'http://testing.fr/cubicweb/one')
        self.assertEqual(req.build_url(param='ok'), u'http://testing.fr/cubicweb/view?param=ok')
        self.assertRaises(AssertionError, req.build_url, 'one', 'two not allowed')
        self.assertRaises(AssertionError, req.build_url, 'view', test=None)

    def test_ensure_no_rql(self):
        req = RequestSessionBase(None)
        self.assertEqual(req.ensure_ro_rql('Any X WHERE X is CWUser'), None)
        self.assertEqual(req.ensure_ro_rql('  Any X WHERE X is CWUser  '), None)
        self.assertRaises(Unauthorized, req.ensure_ro_rql, 'SET X login "toto" WHERE X is CWUser')
        self.assertRaises(Unauthorized, req.ensure_ro_rql, '   SET X login "toto" WHERE X is CWUser   ')


class RequestCWTC(CubicWebTC):
    def test_view_catch_ex(self):
        req = self.request()
        rset = self.execute('CWUser X WHERE X login "hop"')
        self.assertEqual(req.view('oneline', rset, 'null'), '')
        self.assertRaises(ObjectNotFound, req.view, 'onelinee', rset, 'null')

if __name__ == '__main__':
    unittest_main()
