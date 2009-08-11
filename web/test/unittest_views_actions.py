"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import unittest_main

from cubicweb.devtools.testlib import CubicWebTC

class ActionsTC(CubicWebTC):
    def test_view_action(self):
        req = self.request(__message='bla bla bla', vid='rss', rql='CWUser X')
        rset = self.execute('CWUser X')
        vaction = [action for action in self.vreg['actions'].possible_vobjects(req, rset=rset)
                   if action.id == 'view'][0]
        self.assertEquals(vaction.url(), 'http://testing.fr/cubicweb/view?rql=CWUser%20X')

    def test_sendmail_action(self):
        req = self.request()
        rset = self.execute('Any X WHERE X login "admin"', req=req)
        self.failUnless([action for action in self.vreg['actions'].possible_vobjects(req, rset=rset)
                         if action.id == 'sendemail'])
        self.login('anon')
        req = self.request()
        rset = self.execute('Any X WHERE X login "anon"', req=req)
        self.failIf([action for action in self.vreg['actions'].possible_vobjects(req, rset=rset)
                     if action.id == 'sendemail'])

if __name__ == '__main__':
    unittest_main()
