"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.devtools.apptest import EnvBasedTC

class EmailAddressHooksTC(EnvBasedTC):

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


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
