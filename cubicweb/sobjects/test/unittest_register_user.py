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
"""unittest for cubicweb user registration service"""

from cubicweb import ValidationError
from cubicweb.web import Unauthorized
from cubicweb.devtools.testlib import CubicWebTC


class RegisterUserTC(CubicWebTC):

    def test_register_user_service_anon(self):
        with self.new_access('anon').client_cnx() as cnx:
            self.assertRaises(Unauthorized, cnx.call_service, 'register_user',
                              login=u'foo2', password=u'bar2',
                              email=u'foo2@bar2.com', firstname=u'Foo2', surname=u'Bar2')

    def test_register_user_service_unique_login(self):
        with self.admin_access.cnx() as cnx:
            cnx.call_service('register_user', login=u'foo3',
                             password=u'bar3', email=u'foo3@bar3.com',
                             firstname=u'Foo3', surname=u'Bar3')
            # same login
            with self.assertRaises(ValidationError) as cm:
                cnx.call_service('register_user', login=u'foo3',
                                 password=u'bar3')
            expected_errors = {
                '': u'some relations violate a unicity constraint',
                'login': u'%(KEY-rtype)s is part of violated unicity constraint',
            }
            self.assertEqual(cm.exception.errors, expected_errors)

    def test_register_user_service_unique_email(self):
        with self.admin_access.cnx() as cnx:
            cnx.call_service('register_user', login=u'foo3',
                             password=u'bar3', email=u'foo3@bar3.com',
                             firstname=u'Foo3', surname=u'Bar3')
            with self.assertRaises(ValidationError) as cm:
                cnx.call_service('register_user', login=u'foo3@bar3.com',
                                 password=u'bar3')
            expected_errors = {
                '': u'some relations violate a unicity constraint',
                'address': u'%(KEY-rtype)s is part of violated unicity constraint',
            }
            self.assertEqual(cm.exception.errors, expected_errors)

    def test_register_user_attributes(self):
        with self.admin_access.cnx() as cnx:
            cnx.call_service('register_user', login=u'foo3',
                             password=u'bar3', email=u'foo3@bar3.com',
                             firstname=u'Foo3', surname=u'Bar3')
            cnx.commit()

        with self.admin_access.client_cnx() as cnx:
            user = cnx.find('CWUser', login=u'foo3').one()
            self.assertEqual(user.firstname, u'Foo3')
            self.assertEqual(user.use_email[0].address, u'foo3@bar3.com')

    def test_register_user_groups(self):
        with self.admin_access.cnx() as cnx:
            # default
            cnx.call_service('register_user', login=u'foo_user',
                             password=u'bar_user', email=u'foo_user@bar_user.com',
                             firstname=u'Foo_user', surname=u'Bar_user')

            # group kwarg
            cnx.call_service('register_user', login=u'foo_admin',
                             password=u'bar_admin', email=u'foo_admin@bar_admin.com',
                             firstname=u'Foo_admin', surname=u'Bar_admin',
                             groups=('managers', 'users'))

            # class attribute
            from cubicweb.sobjects import services
            services.RegisterUserService.default_groups = ('guests',)
            cnx.call_service('register_user', login=u'foo_guest',
                             password=u'bar_guest', email=u'foo_guest@bar_guest.com',
                             firstname=u'Foo_guest', surname=u'Bar_guest')
            cnx.commit()

        with self.admin_access.client_cnx() as cnx:
            user = cnx.find('CWUser', login=u'foo_user').one()
            self.assertEqual([g.name for g in user.in_group], ['users'])

            admin = cnx.find('CWUser', login=u'foo_admin').one()
            self.assertEqual(sorted(g.name for g in admin.in_group), ['managers', 'users'])

            guest = cnx.find('CWUser', login=u'foo_guest').one()
            self.assertEqual([g.name for g in guest.in_group], ['guests'])


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
