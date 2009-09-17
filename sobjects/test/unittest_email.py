"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
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
        cu.execute('SET U primary_email E WHERE E eid %(e)s, U login "toto"',
                   {'e': email1})
        self.assertRaises(Unauthorized, cnx.commit)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
