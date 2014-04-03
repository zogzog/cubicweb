# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from cubicweb.req import RequestSessionBase, FindEntityError
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

    def test_base_url(self):
        base_url = self.config['base-url']
        with self.admin_access.repo_cnx() as session:
            self.assertEqual(session.base_url(), base_url)
            assert 'https-url' not in self.config
            self.assertEqual(session.base_url(secure=True), base_url)
            secure_base_url = base_url.replace('http', 'https')
            self.config.global_set_option('https-url', secure_base_url)
            self.assertEqual(session.base_url(secure=True), secure_base_url)

    def test_view_catch_ex(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWUser X WHERE X login "hop"')
            self.assertEqual(req.view('oneline', rset, 'null'), '')
            self.assertRaises(ObjectNotFound, req.view, 'onelinee', rset, 'null')

    def test_find_one_entity(self):
        with self.admin_access.web_request() as req:
            req.create_entity(
                'CWUser', login=u'cdevienne', upassword=u'cdevienne',
                surname=u'de Vienne', firstname=u'Christophe',
                in_group=req.find('CWGroup', name=u'users').one())

            req.create_entity(
                'CWUser', login=u'adim', upassword='adim', surname=u'di mascio',
                firstname=u'adrien',
                in_group=req.find('CWGroup', name=u'users').one())

            u = req.find_one_entity('CWUser', login=u'cdevienne')
            self.assertEqual(u.firstname, u"Christophe")

            with self.assertRaises(FindEntityError):
                req.find_one_entity('CWUser', login=u'patanok')

            with self.assertRaises(FindEntityError):
                req.find_one_entity('CWUser')

    def test_find_entities(self):
        with self.admin_access.web_request() as req:
            req.create_entity(
                'CWUser', login=u'cdevienne', upassword=u'cdevienne',
                surname=u'de Vienne', firstname=u'Christophe',
                in_group=req.find('CWGroup', name=u'users').one())

            req.create_entity(
                'CWUser', login=u'adim', upassword='adim', surname=u'di mascio',
                firstname=u'adrien',
                in_group=req.find('CWGroup', name=u'users').one())

            l = list(req.find_entities('CWUser', login=u'cdevienne'))
            self.assertEqual(1, len(l))
            self.assertEqual(l[0].firstname, u"Christophe")

            l = list(req.find_entities('CWUser', login=u'patanok'))
            self.assertEqual(0, len(l))

            l = list(req.find_entities('CWUser'))
            self.assertEqual(4, len(l))

    def test_find(self):
        with self.admin_access.web_request() as req:
            req.create_entity(
                'CWUser', login=u'cdevienne', upassword=u'cdevienne',
                surname=u'de Vienne', firstname=u'Christophe',
                in_group=req.find('CWGroup', name=u'users').one())

            req.create_entity(
                'CWUser', login=u'adim', upassword='adim', surname=u'di mascio',
                firstname=u'adrien',
                in_group=req.find('CWGroup', name=u'users').one())

            u = req.find('CWUser', login=u'cdevienne').one()
            self.assertEqual(u.firstname, u"Christophe")

            users = list(req.find('CWUser').entities())
            self.assertEqual(len(users), 4)

            groups = list(
                req.find('CWGroup', reverse_in_group=u).entities())
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].name, u'users')

            users = req.find('CWUser', in_group=groups[0]).entities()
            users = list(users)
            self.assertEqual(len(users), 2)

            with self.assertRaises(AssertionError):
                req.find('CWUser', chapeau=u"melon")

            with self.assertRaises(AssertionError):
                req.find('CWUser', reverse_buddy=users[0])

            with self.assertRaises(NotImplementedError):
                req.find('CWUser', in_group=[1, 2])

if __name__ == '__main__':
    unittest_main()
