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
"""unittest for cubicweb.dbapi"""

from cubicweb import ValidationError
from cubicweb.web import Unauthorized
from cubicweb.devtools.testlib import CubicWebTC


class RegisterUserTC(CubicWebTC):

    def test_register_user_service(self):
        acc = self.new_access('admin')
        with acc.client_cnx() as cnx:
            cnx.call_service('register_user', login=u'foo1', password=u'bar1',
                             email=u'foo1@bar1.com', firstname=u'Foo1',
                             surname=u'Bar1')

        acc = self.new_access('anon')
        with acc.client_cnx() as cnx:
            self.assertRaises(Unauthorized, cnx.call_service, 'register_user',
                              login=u'foo2', password=u'bar2',
                              email=u'foo2@bar2.com', firstname=u'Foo2', surname=u'Bar2')

        with self.repo.internal_cnx() as cnx:
            cnx.call_service('register_user', login=u'foo3',
                             password=u'bar3', email=u'foo3@bar3.com',
                             firstname=u'Foo3', surname=u'Bar3')
            # same login
            with self.assertRaises(ValidationError):
                cnx.call_service('register_user', login=u'foo3',
                                 password=u'bar3')


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
