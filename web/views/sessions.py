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

from cubicweb import (RepositoryError, Unauthorized, AuthenticationError,
                      BadConnectionId)
from cubicweb.web import InvalidSession, Redirect
from cubicweb.web.application import AbstractSessionManager
from cubicweb.dbapi import ProgrammingError, DBAPISession


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
        if session.cnx:
            try:
                user = self.authmanager.validate_session(req, session)
            except InvalidSession:
                # invalid session
                self.close_session(session)
                raise
            # associate the connection to the current request
            req.set_session(session, user)
        return session

    def open_session(self, req, allow_no_cnx=True):
        """open and return a new session for the given request. The session is
        also bound to the request.

        raise :exc:`cubicweb.AuthenticationError` if authentication failed
        (no authentication info found or wrong user/password)
        """
        try:
            cnx, login = self.authmanager.authenticate(req)
        except AuthenticationError:
            if allow_no_cnx:
                session = DBAPISession(None)
            else:
                raise
        else:
            session = DBAPISession(cnx, login)
        self._sessions[session.sessionid] = session
        # associate the connection to the current request
        req.set_session(session)
        return session

    def postlogin(self, req):
        """postlogin: the user has been authenticated, redirect to the original
        page (index by default) with a welcome message
        """
        # Update last connection date
        # XXX: this should be in a post login hook in the repository, but there
        #      we can't differentiate actual login of automatic session
        #      reopening. Is it actually a problem?
        if 'last_login_time' in req.vreg.schema:
            self._update_last_login_time(req)
        req.set_message(req._('welcome %s!') % req.user.login)

    def _update_last_login_time(self, req):
        # XXX should properly detect missing permission / non writeable source
        # and avoid "except (RepositoryError, Unauthorized)" below
        try:
            req.execute('SET X last_login_time NOW WHERE X eid %(x)s',
                        {'x' : req.user.eid})
            req.cnx.commit()
        except (RepositoryError, Unauthorized):
            req.cnx.rollback()
        except Exception:
            req.cnx.rollback()
            raise

    def close_session(self, session):
        """close session on logout or on invalid session detected (expired out,
        corrupted...)
        """
        self.info('closing http session %s' % session.sessionid)
        del self._sessions[session.sessionid]
        if session.cnx:
            try:
                session.cnx.close()
            except (ProgrammingError, BadConnectionId): # expired on the repository side
                pass
            session.cnx = None
