"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import unittest_main

from cubicweb.devtools.testlib import CubicWebTC

class ActionsTC(CubicWebTC):
    def test_view_action(self):
        req = self.request(__message='bla bla bla', vid='rss', rql='CWUser X')
        rset = self.execute('CWUser X')
        actions = self.vreg['actions'].poss_visible_objects(req, rset=rset)
        vaction = [action for action in actions if action.__regid__ == 'view'][0]
        self.assertEquals(vaction.url(), 'http://testing.fr/cubicweb/view?rql=CWUser%20X')

    def test_sendmail_action(self):
        req = self.request()
        rset = self.execute('Any X WHERE X login "admin"', req=req)
        actions = self.vreg['actions'].poss_visible_objects(req, rset=rset)
        self.failUnless([action for action in actions if action.__regid__ == 'sendemail'])
        self.login('anon')
        req = self.request()
        rset = self.execute('Any X WHERE X login "anon"', req=req)
        actions = self.vreg['actions'].poss_visible_objects(req, rset=rset)
        self.failIf([action for action in actions if action.__regid__ == 'sendemail'])

if __name__ == '__main__':
    unittest_main()
