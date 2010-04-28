# -*- coding: iso-8859-1 -*-
"""unit tests for cubicweb.web.application

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.devtools.testlib import CubicWebTC

class SessionTC(CubicWebTC):

    def test_auto_reconnection(self):
        sm = self.app.session_handler.session_manager
        # make is if the web session has been opened by the session manager
        sm._sessions[self.cnx.sessionid] = self.websession
        sessionid = self.websession.sessionid
        self.assertEquals(len(sm._sessions), 1)
        self.assertEquals(self.websession.sessionid, self.websession.cnx.sessionid)
        # fake the repo session is expiring
        self.repo.close(sessionid)
        # fake an incoming http query with sessionid in session cookie
        # don't use self.request() which try to call req.set_session
        req = self.requestcls(self.vreg)
        websession = sm.get_session(req, sessionid)
        self.assertEquals(len(sm._sessions), 1)
        self.assertIs(websession, self.websession)
        self.assertEquals(websession.sessionid, sessionid)
        self.assertNotEquals(websession.sessionid, websession.cnx.sessionid)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
