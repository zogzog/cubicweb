"""user authentication component

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import clear_cache

from cubicweb import AuthenticationError, BadConnectionId
from cubicweb.dbapi import repo_connect, ConnectionProperties
from cubicweb.web import ExplicitLogin, InvalidSession
from cubicweb.web.application import AbstractAuthenticationManager
    

class RepositoryAuthenticationManager(AbstractAuthenticationManager):
    """authenticate user associated to a request and check session validity"""
    
    def __init__(self):
        self.repo = self.config.repository(self.vreg)
        self.log_queries = self.config['query-log-file']

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
            if login and user.login != login:
                cnx.close()
                raise InvalidSession('login mismatch')
        except BadConnectionId:
            # check if a connection should be automatically restablished
            if (login is None or login == cnx.login):
                login, password = cnx.login, cnx.password
                cnx = self.authenticate(req, login, password)
                user = cnx.user(req)
                # backport session's data
                cnx.data = session.data
            else:
                raise InvalidSession('bad connection id')
        # associate the connection to the current request
        req.set_connection(cnx, user)
        return cnx

    def login_from_email(self, login):
        session = self.repo.internal_session()
        try:
            rset = session.execute('Any L WHERE U login L, U primary_email M, '
                                   'M address %(login)s', {'login': login})
            if rset.rowcount == 1:
                login = rset[0][0]
        finally:
            session.close()
        return login

    def authenticate(self, req, _login=None, _password=None):
        """authenticate user and return corresponding user object

        :raise ExplicitLogin: if authentication is required (no authentication
        info found or wrong user/password)

        Note: this method is violating AuthenticationManager interface by
        returning a session instance instead of the user. This is expected by
        the InMemoryRepositorySessionManager.
        """
        if _login is not None:
            login, password = _login, _password
        else:
            login, password = req.get_authorization()
        if self.vreg.config['allow-email-login'] and '@' in (login or u''):
            login = self.login_from_email(login)
        if not login:
            # No session and no login -> try anonymous
            login, password = self.vreg.config.anonymous_user()
            if not login: # anonymous not authorized
                raise ExplicitLogin()
        # remove possibly cached cursor coming from closed connection
        clear_cache(req, 'cursor')
        cnxprops = ConnectionProperties(self.vreg.config.repo_method,
                                        close=False, log=self.log_queries)
        try:
            cnx = repo_connect(self.repo, login, password, cnxprops=cnxprops)
        except AuthenticationError:
            req.set_message(req._('authentication failure'))
            # restore an anonymous connection if possible
            anonlogin, anonpassword = self.vreg.config.anonymous_user()
            if anonlogin and anonlogin != login:
                cnx = repo_connect(self.repo, anonlogin, anonpassword,
                                   cnxprops=cnxprops)
                self._init_cnx(cnx, anonlogin, anonpassword)
            else:
                raise ExplicitLogin()
        else:
            self._init_cnx(cnx, login, password)
        # associate the connection to the current request
        req.set_connection(cnx)
        return cnx

    def _init_cnx(self, cnx, login, password):
        # decorate connection
        if login == self.vreg.config.anonymous_user()[0]:
            cnx.anonymous_connection = True
        cnx.vreg = self.vreg
        cnx.login = login
        cnx.password = password

