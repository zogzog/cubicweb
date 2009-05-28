"""persistent sessions stored in big table

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr

XXX TODO:
* cleanup persistent session
* use user as ancestor?
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from pickle import loads, dumps
from time import localtime, strftime

from logilab.common.decorators import cached, clear_cache

from cubicweb import BadConnectionId
from cubicweb.dbapi import Connection, ConnectionProperties, repo_connect
from cubicweb.selectors import none_rset, match_user_groups
from cubicweb.server.session import Session
from cubicweb.web import InvalidSession
from cubicweb.web.application import AbstractSessionManager
from cubicweb.web.application import AbstractAuthenticationManager

from google.appengine.api.datastore import Key, Entity, Get, Put, Delete, Query
from google.appengine.api.datastore_errors import EntityNotFoundError
from google.appengine.api.datastore_types import Blob

try:
    del Connection.__del__
except AttributeError:
    pass # already deleted


class GAEAuthenticationManager(AbstractAuthenticationManager):
    """authenticate user associated to a request and check session validity,
    using google authentication service
    """

    def __init__(self, *args, **kwargs):
        super(GAEAuthenticationManager, self).__init__(*args, **kwargs)
        self._repo = self.config.repository(vreg=self.vreg)

    def authenticate(self, req, _login=None, _password=None):
        """authenticate user and return an established connection for this user

        :raise ExplicitLogin: if authentication is required (no authentication
        info found or wrong user/password)
        """
        if _login is not None:
            login, password = _login, _password
        else:
            login, password = req.get_authorization()
        # remove possibly cached cursor coming from closed connection
        clear_cache(req, 'cursor')
        cnxprops = ConnectionProperties(self.vreg.config.repo_method,
                                        close=False, log=False)
        cnx = repo_connect(self._repo, login, password, cnxprops=cnxprops)
        self._init_cnx(cnx, login, password)
        # associate the connection to the current request
        req.set_connection(cnx)
        return cnx

    def _init_cnx(self, cnx, login, password):
        cnx.anonymous_connection = self.config.is_anonymous_user(login)
        cnx.vreg = self.vreg
        cnx.login = login
        cnx.password = password


class GAEPersistentSessionManager(AbstractSessionManager):
    """manage session data associated to a session identifier"""

    def __init__(self, *args, **kwargs):
        super(GAEPersistentSessionManager, self).__init__(*args, **kwargs)
        self._repo = self.config.repository(vreg=self.vreg)

    def get_session(self, req, sessionid):
        """return existing session for the given session identifier"""
        # search a record for the given session
        key = Key.from_path('CubicWebSession', 'key_' + sessionid, parent=None)
        try:
            record = Get(key)
        except EntityNotFoundError:
            raise InvalidSession()
        repo = self._repo
        if self.has_expired(record):
            repo._sessions.pop(sessionid, None)
            Delete(record)
            raise InvalidSession()
        # associate it with a repository session
        try:
            reposession = repo._get_session(sessionid)
            user = reposession.user
            # touch session to avoid closing our own session when sessions are
            # cleaned (touch is done on commit/rollback on the server side, too
            # late in that case)
            reposession._touch()
        except BadConnectionId:
            # can't found session in the repository, this probably mean the
            # session is not yet initialized on this server, hijack the repo
            # to create it
            # use an internal connection
            ssession = repo.internal_session()
            # try to get a user object
            try:
                user = repo.authenticate_user(ssession, record['login'],
                                              record['password'])
            finally:
                ssession.close()
            reposession = Session(user, self._repo, _id=sessionid)
            self._repo._sessions[sessionid] = reposession
        cnx = Connection(self._repo, sessionid)
        return self._get_proxy(req, record, cnx, user)

    def open_session(self, req):
        """open and return a new session for the given request"""
        cnx = self.authmanager.authenticate(req)
        # avoid rebuilding a user
        user = self._repo._get_session(cnx.sessionid).user
        # build persistent record for session data
        record = Entity('CubicWebSession', name='key_' + cnx.sessionid)
        record['login'] = cnx.login
        record['password'] = cnx.password
        record['anonymous_connection'] = cnx.anonymous_connection
        Put(record)
        return self._get_proxy(req, record, cnx, user)

    def close_session(self, proxy):
        """close session on logout or on invalid session detected (expired out,
        corrupted...)
        """
        proxy.close()

    def current_sessions(self):
        for record in Query('CubicWebSession').Run():
            yield ConnectionProxy(record)

    def _get_proxy(self, req, record, cnx, user):
        proxy = ConnectionProxy(record, cnx, user)
        user.req = req
        req.set_connection(proxy, user)
        return proxy


class ConnectionProxy(object):

    def __init__(self, record, cnx=None, user=None):
        self.__record = record
        self.__cnx = cnx
        self.__user = user
        self.__data = None
        self.__is_dirty = False
        self.sessionid = record.key().name()[4:] # remove 'key_' prefix

    def __repr__(self):
        sstr = '<ConnectionProxy %s' % self.sessionid
        if self.anonymous_connection:
            sstr += ' (anonymous)'
        elif self.__user:
            sstr += ' for %s' % self.__user.login
        sstr += ', last used %s>' % strftime('%T', localtime(self.last_usage_time))
        return sstr

    def __getattribute__(self, name):
        try:
            return super(ConnectionProxy, self).__getattribute__(name)
        except AttributeError:
            return getattr(self.__cnx, name)

    def _set_last_usage_time(self, value):
        self.__is_dirty = True
        self.__record['last_usage_time'] = value
    def _get_last_usage_time(self):
        return self.__record['last_usage_time']

    last_usage_time = property(_get_last_usage_time, _set_last_usage_time)

    @property
    def anonymous_connection(self):
        # use get() for bw compat if sessions without anonymous information are
        # found. Set default to True to limit lifetime of those sessions.
        return self.__record.get('anonymous_connection', True)

    @property
    @cached
    def data(self):
        if self.__record.get('data') is not None:
            try:
                return loads(self.__record['data'])
            except:
                self.__is_dirty = True
                self.exception('corrupted session data for session %s',
                               self.__cnx)
        return {}

    def get_session_data(self, key, default=None, pop=False):
        """return value associated to `key` in session data"""
        if pop:
            try:
                value = self.data.pop(key)
                self.__is_dirty = True
                return value
            except KeyError:
                return default
        else:
            return self.data.get(key, default)

    def set_session_data(self, key, value):
        """set value associated to `key` in session data"""
        self.data[key] = value
        self.__is_dirty = True

    def del_session_data(self, key):
        """remove value associated to `key` in session data"""
        try:
            del self.data[key]
            self.__is_dirty = True
        except KeyError:
            pass

    def commit(self):
        if self.__is_dirty:
            self.__save()
        self.__cnx.commit()

    def rollback(self):
        self.__save()
        self.__cnx.rollback()

    def close(self):
        if self.__cnx is not None:
            self.__cnx.close()
        Delete(self.__record)

    def __save(self):
        if self.__is_dirty:
            self.__record['data'] = Blob(dumps(self.data))
            Put(self.__record)
            self.__is_dirty = False

    def user(self, req=None, props=None):
        """return the User object associated to this connection"""
        return self.__user


import logging
from cubicweb import set_log_methods
set_log_methods(ConnectionProxy, logging.getLogger('cubicweb.web.goa.session'))


from cubicweb.common.view import StartupView
from cubicweb.web import application

class SessionsCleaner(StartupView):
    id = 'cleansessions'
    __select__ = none_rset() & match_user_groups('managers')

    def call(self):
        # clean web session
        session_manager = application.SESSION_MANAGER
        nbclosed, remaining = session_manager.clean_sessions()
        self.w(u'<div class="message">')
        self.w(u'%s web sessions closed<br/>\n' % nbclosed)
        # clean repository sessions
        repo = self.config.repository(vreg=self.vreg)
        nbclosed = repo.clean_sessions()
        self.w(u'%s repository sessions closed<br/>\n' % nbclosed)
        self.w(u'%s remaining sessions<br/>\n' % remaining)
        self.w(u'</div>')


def registration_callback(vreg):
    vreg.register(SessionsCleaner)
    vreg.register(GAEAuthenticationManager, clear=True)
    vreg.register(GAEPersistentSessionManager, clear=True)
