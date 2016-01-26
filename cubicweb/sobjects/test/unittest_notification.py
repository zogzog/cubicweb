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
"""Tests for notification sobjects"""

from cubicweb.devtools.testlib import CubicWebTC, MAILBOX


class NotificationTC(CubicWebTC):

    def test_recipients_finder(self):
        with self.admin_access.web_request() as req:
            urset = req.execute('CWUser X WHERE X login "admin"')
            req.execute('INSERT EmailAddress X: X address "admin@logilab.fr", U primary_email X '
                        'WHERE U eid %(x)s', {'x': urset[0][0]})
            req.execute('INSERT CWProperty X: X pkey "ui.language", X value "fr", X for_user U '
                        'WHERE U eid %(x)s', {'x': urset[0][0]})
            req.cnx.commit()  # commit so that admin get its properties updated
            finder = self.vreg['components'].select('recipients_finder',
                                                    req, rset=urset)
            self.set_option('default-recipients-mode', 'none')
            self.assertEqual(finder.recipients(), [])
            self.set_option('default-recipients-mode', 'users')
            self.assertEqual(finder.recipients(), [req.user])
            self.set_option('default-recipients-mode', 'default-dest-addrs')
            self.set_option('default-dest-addrs', 'abcd@logilab.fr, efgh@logilab.fr')
            self.assertEqual(list(finder.recipients()),
                             [('abcd@logilab.fr', 'en'), ('efgh@logilab.fr', 'en')])

    def test_status_change_view(self):
        with self.admin_access.web_request() as req:
            u = self.create_user(req, 'toto')
            iwfable = u.cw_adapt_to('IWorkflowable')
            iwfable.fire_transition('deactivate', comment=u'yeah')
            self.assertFalse(MAILBOX)
            req.cnx.commit()
            self.assertEqual(len(MAILBOX), 1)
            email = MAILBOX[0]
            self.assertEqual(email.content,
                             '''
admin changed status from <activated> to <deactivated> for entity
'toto'

yeah

url: http://testing.fr/cubicweb/cwuser/toto
''')
            self.assertEqual(email.subject,
                             'status changed CWUser #%s (admin)' % u.eid)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
