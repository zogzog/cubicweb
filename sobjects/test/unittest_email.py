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
"""

"""

from cubicweb import Unauthorized
from cubicweb.devtools.testlib import CubicWebTC

class EmailAddressHooksTC(CubicWebTC):

    def test_use_email_set_primary_email(self):
        self.execute('INSERT EmailAddress X: X address "admin@logilab.fr", U use_email X WHERE U login "admin"')
        self.assertEquals(self.execute('Any A WHERE U primary_email X, U login "admin", X address A').rows,
                          [])
        self.commit()
        self.assertEquals(self.execute('Any A WHERE U primary_email X, U login "admin", X address A')[0][0],
                          'admin@logilab.fr')
        # having another email should'nt change anything
        self.execute('INSERT EmailAddress X: X address "a@logilab.fr", U use_email X WHERE U login "admin"')
        self.commit()
        self.assertEquals(self.execute('Any A WHERE U primary_email X, U login "admin", X address A')[0][0],
                          'admin@logilab.fr')

    def test_primary_email_set_use_email(self):
        self.execute('INSERT EmailAddress X: X address "admin@logilab.fr", U primary_email X WHERE U login "admin"')
        self.assertEquals(self.execute('Any A WHERE U use_email X, U login "admin", X address A').rows,
                          [])
        self.commit()
        self.assertEquals(self.execute('Any A WHERE U use_email X, U login "admin", X address A')[0][0],
                          'admin@logilab.fr')

    def test_cardinality_check(self):
        email1 = self.execute('INSERT EmailAddress E: E address "client@client.com", U use_email E WHERE U login "admin"')[0][0]
        self.commit()
        self.execute('SET U primary_email E WHERE U login "anon", E address "client@client.com"')
        self.commit()
        rset = self.execute('Any X WHERE X use_email E, E eid %(e)s', {'e': email1})
        self.failIf(rset.rowcount != 1, rset)

    def test_security_check(self):
        self.create_user('toto')
        email1 = self.execute('INSERT EmailAddress E: E address "client@client.com", U use_email E WHERE U login "admin"')[0][0]
        self.commit()
        cnx = self.login('toto')
        cu = cnx.cursor()
        self.assertRaises(Unauthorized,
                          cu.execute, 'SET U primary_email E WHERE E eid %(e)s, U login "toto"',
                          {'e': email1})
        cnx.close()

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
