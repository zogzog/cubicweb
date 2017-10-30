# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
        req.from_controller = lambda: 'view'
        req.relative_path = lambda includeparams=True: None
        req.base_url = lambda: 'http://testing.fr/cubicweb/'
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
        self.assertRaises(Unauthorized, req.ensure_ro_rql,
                          'SET X login "toto" WHERE X is CWUser')
        self.assertRaises(Unauthorized, req.ensure_ro_rql,
                          '   SET X login "toto" WHERE X is CWUser   ')


class RequestCWTC(CubicWebTC):

    def test_base_url(self):
        base_url = self.config['base-url']
        with self.admin_access.repo_cnx() as session:
            self.assertEqual(session.base_url(), base_url)

    def test_secure_deprecated(self):
        with self.admin_access.cnx() as cnx:
            with self.assertWarns(DeprecationWarning):
                cnx.base_url(secure=True)
            with self.assertRaises(TypeError):
                cnx.base_url(thing=42)
            with self.assertWarns(DeprecationWarning):
                cnx.build_url('ah', __secure__='whatever')

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

            users = list(req.find_entities('CWUser', login=u'cdevienne'))
            self.assertEqual(1, len(users))
            self.assertEqual(users[0].firstname, u"Christophe")

            users = list(req.find_entities('CWUser', login=u'patanok'))
            self.assertEqual(0, len(users))

            users = list(req.find_entities('CWUser'))
            self.assertEqual(4, len(users))

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

            rset = req.find('CWUser', login=u'cdevienne')
            self.assertEqual(rset.printable_rql(),
                             'Any X WHERE X is CWUser, X login "cdevienne"')
            u = rset.one()
            self.assertEqual(u.firstname, u"Christophe")

            users = list(req.find('CWUser').entities())
            self.assertEqual(len(users), 4)

            groups = list(
                req.find('CWGroup', reverse_in_group=u).entities())
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0].name, u'users')

            rset = req.find('CWUser', in_group=groups[0])
            self.assertEqual(rset.printable_rql(),
                             'Any X WHERE X is CWUser, X in_group A, '
                             'A eid {0}'.format(groups[0].eid))
            users = list(rset.entities())
            self.assertEqual(len(users), 2)

            with self.assertRaisesRegexp(
                KeyError, "^'chapeau not in CWUser subject relations'$"
            ):
                req.find('CWUser', chapeau=u"melon")

            with self.assertRaisesRegexp(
                KeyError, "^'buddy not in CWUser object relations'$"
            ):
                req.find('CWUser', reverse_buddy=users[0])

            with self.assertRaisesRegexp(
                NotImplementedError, '^in_group: list of values are not supported$'
            ):
                req.find('CWUser', in_group=[1, 2])


if __name__ == '__main__':
    unittest_main()
