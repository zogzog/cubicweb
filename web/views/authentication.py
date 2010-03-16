"""user authentication component

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import clear_cache

from cubicweb import AuthenticationError, BadConnectionId
from cubicweb.view import Component
from cubicweb.dbapi import repo_connect, ConnectionProperties
from cubicweb.web import ExplicitLogin, InvalidSession
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

    def authenticated(self, req, cnx, retreiver):
        """callback when return authentication information have opened a
        repository connection successfully
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
        assert self.authinforetreivers
        self.anoninfo = vreg.config.anonymous_user()

    def validate_session(self, req, session):
        """check session validity, and return eventually hijacked session

        :raise InvalidSession:
          if session is corrupted for a reason or another and should be closed
        """
        # with this authentication manager, session is actually a dbapi
        # connection
        cnx = session
        login = req.get_authorization()[0]
        try:
            # calling cnx.user() check connection validity, raise
            # BadConnectionId on failure
            user = cnx.user(req)
            # check cnx.login and not user.login, since in case of login by
            # email, login and cnx.login are the email while user.login is the
            # actual user login
            if login and cnx.login != login:
                cnx.close()
                raise InvalidSession('login mismatch')
        except BadConnectionId:
            # check if a connection should be automatically restablished
            if (login is None or login == cnx.login):
                cnx = self._authenticate(req, cnx.login, cnx.authinfo)
                user = cnx.user(req)
                # backport session's data
                cnx.data = session.data
            else:
                raise InvalidSession('bad connection id')
        # associate the connection to the current request
        req.set_connection(cnx, user)
        return cnx

    def authenticate(self, req):
        """authenticate user and return corresponding user object

        :raise ExplicitLogin: if authentication is required (no authentication
        info found or wrong user/password)

        Note: this method is violating AuthenticationManager interface by
        returning a session instance instead of the user. This is expected by
        the InMemoryRepositorySessionManager.
        """
        for retreiver in self.authinforetreivers:
            try:
                login, authinfo = retreiver.authentication_information(req)
            except NoAuthInfo:
                continue
            try:
                cnx = self._authenticate(req, login, authinfo)
            except ExplicitLogin:
                continue # the next one may succeed
            for retreiver_ in self.authinforetreivers:
                retreiver_.authenticated(req, cnx, retreiver)
            break
        else:
            # false if no authentication info found, eg this is not an
            # authentication failure
            if 'login' in locals():
                req.set_message(req._('authentication failure'))
            cnx = self._open_anonymous_connection(req)
        return cnx

    def _authenticate(self, req, login, authinfo):
        cnxprops = ConnectionProperties(self.vreg.config.repo_method,
                                        close=False, log=self.log_queries)
        try:
            cnx = repo_connect(self.repo, login, cnxprops=cnxprops, **authinfo)
        except AuthenticationError:
            raise ExplicitLogin()
        self._init_cnx(cnx, login, authinfo)
        # associate the connection to the current request
        req.set_connection(cnx)
        return cnx

    def _open_anonymous_connection(self, req):
        # restore an anonymous connection if possible
        login, password = self.anoninfo
        if login:
            return self._authenticate(req, login, {'password': password})
        raise ExplicitLogin()

    def _init_cnx(self, cnx, login, authinfo):
        # decorate connection
        if login == self.vreg.config.anonymous_user()[0]:
            cnx.anonymous_connection = True
        cnx.vreg = self.vreg
        cnx.login = login
        cnx.authinfo = authinfo

