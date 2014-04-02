# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""web session component: by dfault the session is actually the db connection
object :/
"""

__docformat__ = "restructuredtext en"

from time import time

from cubicweb import (RepositoryError, Unauthorized, AuthenticationError,
                      BadConnectionId)
from cubicweb.web import InvalidSession, Redirect
from cubicweb.web.application import AbstractSessionManager
from cubicweb.dbapi import ProgrammingError, DBAPISession
from cubicweb import repoapi


class InMemoryRepositorySessionManager(AbstractSessionManager):
    """manage session data associated to a session identifier"""

    def __init__(self, *args, **kwargs):
        AbstractSessionManager.__init__(self, *args, **kwargs)
        # XXX require a RepositoryAuthenticationManager which violates
        #     authenticate interface by returning a session instead of a user
        #assert isinstance(self.authmanager, RepositoryAuthenticationManager)
        self._sessions = {}

    # dump_data / restore_data to avoid loosing open sessions on registry
    # reloading
    def dump_data(self):
        return self._sessions
    def restore_data(self, data):
        self._sessions = data

    def current_sessions(self):
        return self._sessions.values()

    def get_session(self, req, sessionid):
        """return existing session for the given session identifier"""
        if sessionid not in self._sessions:
            raise InvalidSession()
        session = self._sessions[sessionid]
        try:
            user = self.authmanager.validate_session(req, session)
        except InvalidSession:
            self.close_session(session)
            raise
        if session.closed:
            self.close_session(session)
            raise InvalidSession()
        return session

    def open_session(self, req):
        """open and return a new session for the given request. The session is
        also bound to the request.

        raise :exc:`cubicweb.AuthenticationError` if authentication failed
        (no authentication info found or wrong user/password)
        """
        session, login = self.authmanager.authenticate(req)
        self._sessions[session.sessionid] = session
        session.mtime = time()
        return session

    def postlogin(self, req, session):
        """postlogin: the user have been related to a session

        Both req and session are passed to this function because actually
        linking the request to the session is not yet done and not the
        responsability of this object.
        """
        # Update last connection date
        # XXX: this should be in a post login hook in the repository, but there
        #      we can't differentiate actual login of automatic session
        #      reopening. Is it actually a problem?
        if 'last_login_time' in req.vreg.schema:
            self._update_last_login_time(session)
        req.set_message(req._('welcome %s!') % session.user.login)

    def _update_last_login_time(self, session):
        # XXX should properly detect missing permission / non writeable source
        # and avoid "except (RepositoryError, Unauthorized)" below
        try:
            cnx = repoapi.ClientConnection(session)
            with cnx:
                cnx.execute('SET X last_login_time NOW WHERE X eid %(x)s',
                           {'x' : session.user.eid})
                cnx.commit()
        except (RepositoryError, Unauthorized):
            pass

    def close_session(self, session):
        """close session on logout or on invalid session detected (expired out,
        corrupted...)
        """
        self.info('closing http session %s' % session.sessionid)
        self._sessions.pop(session.sessionid, None)
        if not session.closed:
            session.repo.close(session.sessionid)
