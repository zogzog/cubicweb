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
"""user authentication component

"""
from __future__ import with_statement

__docformat__ = "restructuredtext en"

from threading import Lock

from logilab.common.decorators import clear_cache

from cubicweb import AuthenticationError, BadConnectionId
from cubicweb.view import Component
from cubicweb.dbapi import repo_connect, ConnectionProperties
from cubicweb.web import InvalidSession
from cubicweb.web.application import AbstractAuthenticationManager

class NoAuthInfo(Exception): pass


class WebAuthInfoRetreiver(Component):
    __registry__ = 'webauth'
    order = None

    def authentication_information(self, req):
        """retreive authentication information from the given request, raise
        NoAuthInfo if expected information is not found.
        """
        raise NotImplementedError()

    def authenticated(self, retreiver, req, cnx, login, authinfo):
        """callback when return authentication information have opened a
        repository connection successfully. Take care req has no session
        attached yet, hence req.execute isn't available.
        """
        pass


class LoginPasswordRetreiver(WebAuthInfoRetreiver):
    __regid__ = 'loginpwdauth'
    order = 10

    def authentication_information(self, req):
        """retreive authentication information from the given request, raise
        NoAuthInfo if expected information is not found.
        """
        login, password = req.get_authorization()
        if not login:
            raise NoAuthInfo()
        return login, {'password': password}


class RepositoryAuthenticationManager(AbstractAuthenticationManager):
    """authenticate user associated to a request and check session validity"""

    def __init__(self, vreg):
        super(RepositoryAuthenticationManager, self).__init__(vreg)
        self.repo = vreg.config.repository(vreg)
        self.log_queries = vreg.config['query-log-file']
        self.authinforetreivers = sorted(vreg['webauth'].possible_objects(vreg),
                                    key=lambda x: x.order)
        # 2-uple login / password, login is None when no anonymous access
        # configured
        self.anoninfo = vreg.config.anonymous_user()
        if self.anoninfo[0]:
            self.anoninfo = (self.anoninfo[0], {'password': self.anoninfo[1]})

    def validate_session(self, req, session):
        """check session validity, reconnecting it to the repository if the
        associated connection expired in the repository side (hence the
        necessity for this method). Return the connected user on success.

        raise :exc:`InvalidSession` if session is corrupted for a reason or
        another and should be closed
        """
        # with this authentication manager, session is actually a dbapi
        # connection
        login = req.get_authorization()[0]
        # check session.login and not user.login, since in case of login by
        # email, login and cnx.login are the email while user.login is the
        # actual user login
        if login and session.login != login:
            raise InvalidSession('login mismatch')
        try:
            lock = session.reconnection_lock
        except AttributeError:
            lock = session.reconnection_lock = Lock()
        # need to be locked two avoid duplicated reconnections on concurrent
        # requests
        with lock:
            cnx = session.cnx
            try:
                # calling cnx.user() check connection validity, raise
                # BadConnectionId on failure
                user = cnx.user(req)
            except BadConnectionId:
                # check if a connection should be automatically restablished
                if (login is None or login == session.login):
                    cnx = self._authenticate(session.login, session.authinfo)
                    user = cnx.user(req)
                    session.cnx = cnx
                else:
                    raise InvalidSession('bad connection id')
        return user

    def authenticate(self, req):
        """authenticate user using connection information found in the request,
        and return corresponding a :class:`~cubicweb.dbapi.Connection` instance,
        as well as login and authentication information dictionary used to open
        the connection.

        raise :exc:`cubicweb.AuthenticationError` if authentication failed
        (no authentication info found or wrong user/password)
        """
        for retreiver in self.authinforetreivers:
            try:
                login, authinfo = retreiver.authentication_information(req)
            except NoAuthInfo:
                continue
            try:
                cnx = self._authenticate(login, authinfo)
            except AuthenticationError:
                continue # the next one may succeed
            for retreiver_ in self.authinforetreivers:
                retreiver_.authenticated(retreiver, req, cnx, login, authinfo)
            return cnx, login, authinfo
        # false if no authentication info found, eg this is not an
        # authentication failure
        if 'login' in locals():
            req.set_message(req._('authentication failure'))
        login, authinfo = self.anoninfo
        if login:
            cnx = self._authenticate(login, authinfo)
            cnx.anonymous_connection = True
            return cnx, login, authinfo
        raise AuthenticationError()

    def _authenticate(self, login, authinfo):
        cnxprops = ConnectionProperties(self.vreg.config.repo_method,
                                        close=False, log=self.log_queries)
        cnx = repo_connect(self.repo, login, cnxprops=cnxprops, **authinfo)
        # decorate connection
        cnx.vreg = self.vreg
        return cnx

