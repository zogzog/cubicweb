# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""web session: by default the session is actually the db connection """


from time import time
from logging import getLogger

from logilab.common.registry import RegistrableObject, yes

from cubicweb import RepositoryError, Unauthorized, set_log_methods
from cubicweb.web import InvalidSession

from cubicweb.web.views import authentication


class AbstractSessionManager(RegistrableObject):
    """manage session data associated to a session identifier"""
    __abstract__ = True
    __select__ = yes()
    __registry__ = 'sessions'
    __regid__ = 'sessionmanager'

    def __init__(self, repo):
        vreg = repo.vreg
        self.session_time = vreg.config['http-session-time'] or None
        self.authmanager = authentication.RepositoryAuthenticationManager(repo)
        interval = (self.session_time or 0) / 2.
        if vreg.config.anonymous_user()[0] is not None:
            self.cleanup_anon_session_time = vreg.config['cleanup-anonymous-session-time'] or 5 * 60
            assert self.cleanup_anon_session_time > 0
            if self.session_time is not None:
                self.cleanup_anon_session_time = min(self.session_time,
                                                     self.cleanup_anon_session_time)
            interval = self.cleanup_anon_session_time / 2.
        # we don't want to check session more than once every 5 minutes
        self.clean_sessions_interval = max(5 * 60, interval)

    def clean_sessions(self):
        """cleanup sessions which has not been unused since a given amount of
        time. Return the number of sessions which have been closed.
        """
        self.debug('cleaning http sessions')
        session_time = self.session_time
        closed, total = 0, 0
        for session in self.current_sessions():
            total += 1
            last_usage_time = session.mtime
            no_use_time = (time() - last_usage_time)
            if session.anonymous_session:
                if no_use_time >= self.cleanup_anon_session_time:
                    self.close_session(session)
                    closed += 1
            elif session_time is not None and no_use_time >= session_time:
                self.close_session(session)
                closed += 1
        return closed, total - closed

    def current_sessions(self):
        """return currently open sessions"""
        raise NotImplementedError()

    def get_session(self, req, sessionid):
        """return existing session for the given session identifier"""
        raise NotImplementedError()

    def open_session(self, req):
        """open and return a new session for the given request.

        raise :exc:`cubicweb.AuthenticationError` if authentication failed
        (no authentication info found or wrong user/password)
        """
        raise NotImplementedError()

    def close_session(self, session):
        """close session on logout or on invalid session detected (expired out,
        corrupted...)
        """
        raise NotImplementedError()


set_log_methods(AbstractSessionManager, getLogger('cubicweb.sessionmanager'))


class InMemoryRepositorySessionManager(AbstractSessionManager):
    """manage session data associated to a session identifier"""

    def __init__(self, *args, **kwargs):
        super(InMemoryRepositorySessionManager, self).__init__(*args, **kwargs)
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
            with session.new_cnx() as cnx:
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
