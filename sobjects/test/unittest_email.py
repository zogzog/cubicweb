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

from cubicweb import Unauthorized
from cubicweb.devtools.testlib import CubicWebTC

class EmailAddressHooksTC(CubicWebTC):

    def test_use_email_set_primary_email(self):
        with self.admin_access.client_cnx() as cnx:
            cnx.execute('INSERT EmailAddress X: X address "admin@logilab.fr", U use_email X WHERE U login "admin"')
            self.assertEqual(cnx.execute('Any A WHERE U primary_email X, U login "admin", X address A').rows,
                              [])
            cnx.commit()
            self.assertEqual(cnx.execute('Any A WHERE U primary_email X, U login "admin", X address A')[0][0],
                              'admin@logilab.fr')
            # having another email should'nt change anything
            cnx.execute('INSERT EmailAddress X: X address "a@logilab.fr", U use_email X WHERE U login "admin"')
            cnx.commit()
            self.assertEqual(cnx.execute('Any A WHERE U primary_email X, U login "admin", X address A')[0][0],
                              'admin@logilab.fr')

    def test_primary_email_set_use_email(self):
        with self.admin_access.client_cnx() as cnx:
            cnx.execute('INSERT EmailAddress X: X address "admin@logilab.fr", U primary_email X WHERE U login "admin"')
            self.assertEqual(cnx.execute('Any A WHERE U use_email X, U login "admin", X address A').rows,
                              [])
            cnx.commit()
            self.assertEqual(cnx.execute('Any A WHERE U use_email X, U login "admin", X address A')[0][0],
                              'admin@logilab.fr')

    def test_cardinality_check(self):
        with self.admin_access.client_cnx() as cnx:
            email1 = cnx.execute('INSERT EmailAddress E: E address "client@client.com", U use_email E WHERE U login "admin"')[0][0]
            cnx.commit()
            cnx.execute('SET U primary_email E WHERE U login "anon", E address "client@client.com"')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X use_email E, E eid %(e)s', {'e': email1})
            self.assertFalse(rset.rowcount != 1, rset)

    def test_security_check(self):
        with self.admin_access.client_cnx() as cnx:
            self.create_user(cnx, 'toto')
            email1 = cnx.execute('INSERT EmailAddress E: E address "client@client.com", U use_email E WHERE U login "admin"')[0][0]
            cnx.commit()
        with self.new_access('toto').client_cnx() as cnx:
            self.assertRaises(Unauthorized,
                              cnx.execute, 'SET U primary_email E WHERE E eid %(e)s, U login "toto"',
                              {'e': email1})

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
