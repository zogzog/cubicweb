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
"""web session component: by dfault the session is actually the db connection
object :/
"""

__docformat__ = "restructuredtext en"

from cubicweb import RepositoryError, Unauthorized
from cubicweb.web import InvalidSession, Redirect
from cubicweb.web.application import AbstractSessionManager
from cubicweb.dbapi import DBAPISession


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
        if not sessionid in self._sessions:
            raise InvalidSession()
        session = self._sessions[sessionid]
        try:
            user = self.authmanager.validate_session(req, session)
        except InvalidSession:
            # invalid session
            self.close_session(session)
            raise
        # associate the connection to the current request
        req.set_session(session, user)
        return session

    def open_session(self, req):
        """open and return a new session for the given request. The session is
        also bound to the request.

        raise :exc:`cubicweb.AuthenticationError` if authentication failed
        (no authentication info found or wrong user/password)
        """
        cnx, login = self.authmanager.authenticate(req)
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
        args = req.form
        for forminternal_key in ('__form_id', '__domid', '__errorurl'):
            args.pop(forminternal_key, None)
        args['__message'] = req._('welcome %s !') % req.user.login
        if 'vid' in req.form:
            args['vid'] = req.form['vid']
        if 'rql' in req.form:
            args['rql'] = req.form['rql']
        path = req.relative_path(False)
        if path == 'login':
            path = 'view'
        raise Redirect(req.build_url(path, **args))

    def _update_last_login_time(self, req):
        # XXX should properly detect missing permission / non writeable source
        # and avoid "except (RepositoryError, Unauthorized)" below
        if req.user.cw_metainformation()['source']['type'] == 'ldapuser':
            return
        try:
            req.execute('SET X last_login_time NOW WHERE X eid %(x)s',
                        {'x' : req.user.eid})
            req.cnx.commit()
        except (RepositoryError, Unauthorized):
            req.cnx.rollback()
        except:
            req.cnx.rollback()
            raise

    def close_session(self, session):
        """close session on logout or on invalid session detected (expired out,
        corrupted...)
        """
        self.info('closing http session %s' % session.sessionid)
        del self._sessions[session.sessionid]
        try:
            session.cnx.close()
        except:
            # already closed, may occurs if the repository session expired but
            # not the web session
            pass
        session.cnx = None
