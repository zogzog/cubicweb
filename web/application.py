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
"""CubicWeb web client application object"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
from time import clock, time
from contextlib import contextmanager
from warnings import warn

import httplib

from logilab.common.deprecation import deprecated

from rql import BadRQLQuery

from cubicweb import set_log_methods, cwvreg
from cubicweb import (
    ValidationError, Unauthorized, AuthenticationError, NoSelectableObject,
    BadConnectionId, CW_EVENT_MANAGER)
from cubicweb.dbapi import DBAPISession, anonymous_session
from cubicweb.web import LOGGER, component
from cubicweb.web import (
    StatusResponse, DirectResponse, Redirect, NotFound, LogOut,
    RemoteCallFailed, InvalidSession, RequestError)

from cubicweb.web.request import CubicWebRequestBase

# make session manager available through a global variable so the debug view can
# print information about web session
SESSION_MANAGER = None


@contextmanager
def anonymized_request(req):
    orig_session = req.session
    req.set_session(anonymous_session(req.vreg))
    try:
        yield req
    finally:
        req.set_session(orig_session)

class AbstractSessionManager(component.Component):
    """manage session data associated to a session identifier"""
    __regid__ = 'sessionmanager'

    def __init__(self, vreg):
        self.session_time = vreg.config['http-session-time'] or None
        self.authmanager = vreg['components'].select('authmanager', vreg=vreg)
        interval = (self.session_time or 0) / 2.
        if vreg.config.anonymous_user() is not None:
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
            try:
                last_usage_time = session.cnx.check()
            except AttributeError:
                last_usage_time = session.mtime
            except BadConnectionId:
                self.close_session(session)
                closed += 1
            else:
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
        """open and return a new session for the given request. The session is
        also bound to the request.

        raise :exc:`cubicweb.AuthenticationError` if authentication failed
        (no authentication info found or wrong user/password)
        """
        raise NotImplementedError()

    def close_session(self, session):
        """close session on logout or on invalid session detected (expired out,
        corrupted...)
        """
        raise NotImplementedError()


class AbstractAuthenticationManager(component.Component):
    """authenticate user associated to a request and check session validity"""
    __regid__ = 'authmanager'

    def __init__(self, vreg):
        self.vreg = vreg

    def validate_session(self, req, session):
        """check session validity, reconnecting it to the repository if the
        associated connection expired in the repository side (hence the
        necessity for this method).

        raise :exc:`InvalidSession` if session is corrupted for a reason or
        another and should be closed
        """
        raise NotImplementedError()

    def authenticate(self, req):
        """authenticate user using connection information found in the request,
        and return corresponding a :class:`~cubicweb.dbapi.Connection` instance,
        as well as login and authentication information dictionary used to open
        the connection.

        raise :exc:`cubicweb.AuthenticationError` if authentication failed
        (no authentication info found or wrong user/password)
        """
        raise NotImplementedError()


class CookieSessionHandler(object):
    """a session handler using a cookie to store the session identifier"""

    def __init__(self, appli):
        self.vreg = appli.vreg
        self.session_manager = self.vreg['components'].select('sessionmanager',
                                                              vreg=self.vreg)
        global SESSION_MANAGER
        SESSION_MANAGER = self.session_manager
        if self.vreg.config.mode != 'test':
            # don't try to reset session manager during test, this leads to
            # weird failures when running multiple tests
            CW_EVENT_MANAGER.bind('after-registry-reload',
                                  self.reset_session_manager)

    def reset_session_manager(self):
        data = self.session_manager.dump_data()
        self.session_manager = self.vreg['components'].select('sessionmanager',
                                                              vreg=self.vreg)
        self.session_manager.restore_data(data)
        global SESSION_MANAGER
        SESSION_MANAGER = self.session_manager

    @property
    def clean_sessions_interval(self):
        return self.session_manager.clean_sessions_interval

    def clean_sessions(self):
        """cleanup sessions which has not been unused since a given amount of
        time
        """
        self.session_manager.clean_sessions()

    def session_cookie(self, req):
        """return a string giving the name of the cookie used to store the
        session identifier.
        """
        if req.https:
            return '__%s_https_session' % self.vreg.config.appid
        return '__%s_session' % self.vreg.config.appid

    def set_session(self, req):
        """associate a session to the request

        Session id is searched from :
        - # form variable
        - cookie

        if no session id is found, open a new session for the connected user
        or request authentification as needed

        :raise Redirect: if authentication has occurred and succeed
        """
        cookie = req.get_cookie()
        sessioncookie = self.session_cookie(req)
        try:
            sessionid = str(cookie[sessioncookie].value)
        except KeyError: # no session cookie
            session = self.open_session(req)
        else:
            try:
                session = self.get_session(req, sessionid)
            except InvalidSession:
                # try to open a new session, so we get an anonymous session if
                # allowed
                session = self.open_session(req)
            else:
                if not session.cnx:
                    # session exists but is not bound to a connection. We should
                    # try to authenticate
                    loginsucceed = False
                    try:
                        if self.open_session(req, allow_no_cnx=False):
                            loginsucceed = True
                    except Redirect:
                        # may be raised in open_session (by postlogin mechanism)
                        # on successful connection
                        loginsucceed = True
                        raise
                    except AuthenticationError:
                        # authentication failed, continue to use this session
                        req.set_session(session)
                    finally:
                        if loginsucceed:
                            # session should be replaced by new session created
                            # in open_session
                            self.session_manager.close_session(session)

    def get_session(self, req, sessionid):
        session = self.session_manager.get_session(req, sessionid)
        session.mtime = time()
        return session

    def open_session(self, req, allow_no_cnx=True):
        session = self.session_manager.open_session(req, allow_no_cnx=allow_no_cnx)
        sessioncookie = self.session_cookie(req)
        secure = req.https and req.base_url().startswith('https://')
        req.set_cookie(sessioncookie, session.sessionid,
                       maxage=None, secure=secure)
        if not session.anonymous_session:
            self.session_manager.postlogin(req)
        return session

    def logout(self, req, goto_url):
        """logout from the instance by cleaning the session and raising
        `AuthenticationError`
        """
        self.session_manager.close_session(req.session)
        req.remove_cookie(self.session_cookie(req))
        raise LogOut(url=goto_url)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

class CubicWebPublisher(object):
    """the publisher is a singleton hold by the web frontend, and is responsible
    to publish HTTP request.
    """

    def __init__(self, config,
                 session_handler_fact=CookieSessionHandler,
                 vreg=None):
        self.info('starting web instance from %s', config.apphome)
        if vreg is None:
            vreg = cwvreg.CWRegistryStore(config)
        self.vreg = vreg
        # connect to the repository and get instance's schema
        self.repo = config.repository(vreg)
        if not vreg.initialized:
            config.init_cubes(self.repo.get_cubes())
            vreg.init_properties(self.repo.properties())
            vreg.set_schema(self.repo.get_schema())
        # set the correct publish method
        if config['query-log-file']:
            from threading import Lock
            self._query_log = open(config['query-log-file'], 'a')
            self.handle_request = self.log_handle_request
            self._logfile_lock = Lock()
        else:
            self._query_log = None
            self.handle_request = self.main_handle_request
        # instantiate session and url resolving helpers
        self.session_handler = session_handler_fact(self)
        self.set_urlresolver()
        CW_EVENT_MANAGER.bind('after-registry-reload', self.set_urlresolver)

    def set_urlresolver(self):
        self.url_resolver = self.vreg['components'].select('urlpublisher',
                                                           vreg=self.vreg)

    def connect(self, req):
        """return a connection for a logged user object according to existing
        sessions (i.e. a new connection may be created or an already existing
        one may be reused
        """
        self.session_handler.set_session(req)

    # publish methods #########################################################

    def log_handle_request(self, req, path):
        """wrapper around _publish to log all queries executed for a given
        accessed path
        """
        try:
            return self.main_handle_request(req, path)
        finally:
            cnx = req.cnx
            if cnx:
                with self._logfile_lock:
                    try:
                        result = ['\n'+'*'*80]
                        result.append(req.url())
                        result += ['%s %s -- (%.3f sec, %.3f CPU sec)' % q
                                   for q in cnx.executed_queries]
                        cnx.executed_queries = []
                        self._query_log.write('\n'.join(result).encode(req.encoding))
                        self._query_log.flush()
                    except Exception:
                        self.exception('error while logging queries')



    def main_handle_request(self, req, path):
        if not isinstance(req, CubicWebRequestBase):
            warn('[3.15] Application entry poin arguments are now (req, path) '
                 'not (path, req)', DeprecationWarning, 2)
            req, path = path, req
        if req.authmode == 'http':
            # activate realm-based auth
            realm = self.vreg.config['realm']
            req.set_header('WWW-Authenticate', [('Basic', {'realm' : realm })], raw=False)
        content = ''
        try:
            self.connect(req)
            # DENY https acces for anonymous_user
            if (req.https
                and req.session.anonymous_session
                and self.vreg.config['https-deny-anonymous']):
                # don't allow anonymous on https connection
                raise AuthenticationError()
            # nested try to allow LogOut to delegate logic to AuthenticationError
            # handler
            try:
                ### Try to generate the actual request content
                content = self.core_handle(req, path)
            # Handle user log-out
            except LogOut, ex:
                # When authentification is handled by cookie the code that
                # raised LogOut must has invalidated the cookie. We can just
                # reload the original url without authentification
                if self.vreg.config['auth-mode'] == 'cookie' and ex.url:
                    req.headers_out.setHeader('location', str(ex.url))
                if ex.status is not None:
                    req.status_out = httplib.SEE_OTHER
                # When the authentification is handled by http we must
                # explicitly ask for authentification to flush current http
                # authentification information
                else:
                    # Render "logged out" content.
                    # assignement to ``content`` prevent standard
                    # AuthenticationError code to overwrite it.
                    content = self.loggedout_content(req)
                    # let the explicitly reset http credential
                    raise AuthenticationError()
        except Redirect, ex:
            # authentication needs redirection (eg openid)
            content = self.redirect_handler(req, ex)
        # Wrong, absent or Reseted credential
        except AuthenticationError:
            # If there is an https url configured and
            # the request do not used https, redirect to login form
            https_url = self.vreg.config['https-url']
            if https_url and req.base_url() != https_url:
                req.status_out = httplib.SEE_OTHER
                req.headers_out.setHeader('location', https_url + 'login')
            else:
                # We assume here that in http auth mode the user *May* provide
                # Authentification Credential if asked kindly.
                if self.vreg.config['auth-mode'] == 'http':
                    req.status_out = httplib.UNAUTHORIZED
                # In the other case (coky auth) we assume that there is no way
                # for the user to provide them...
                # XXX But WHY ?
                else:
                    req.status_out = httplib.FORBIDDEN
                # If previous error handling already generated a custom content
                # do not overwrite it. This is used by LogOut Except
                # XXX ensure we don't actually serve content
                if not content:
                    content = self.need_login_content(req)
        return content

    def core_handle(self, req, path):
        """method called by the main publisher to process <path>

        should return a string containing the resulting page or raise a
        `NotFound` exception

        :type path: str
        :param path: the path part of the url to publish

        :type req: `web.Request`
        :param req: the request object

        :rtype: str
        :return: the result of the pusblished url
        """
        # don't log form values they may contains sensitive information
        self.debug('publish "%s" (%s, form params: %s)',
                   path, req.session.sessionid, req.form.keys())
        # remove user callbacks on a new request (except for json controllers
        # to avoid callbacks being unregistered before they could be called)
        tstart = clock()
        commited = False
        try:
            ### standard processing of the request
            try:
                ctrlid, rset = self.url_resolver.process(req, path)
                try:
                    controller = self.vreg['controllers'].select(ctrlid, req,
                                                                 appli=self)
                except NoSelectableObject:
                    raise Unauthorized(req._('not authorized'))
                req.update_search_state()
                result = controller.publish(rset=rset)
            except StatusResponse, ex:
                warn('StatusResponse is deprecated use req.status_out',
                     DeprecationWarning)
                result = ex.content
                req.status_out = ex.status
            except Redirect, ex:
                # Redirect may be raised by edit controller when everything went
                # fine, so attempt to commit
                result = self.redirect_handler(req, ex)
            if req.cnx:
                txuuid = req.cnx.commit()
                commited = True
                if txuuid is not None:
                    req.data['last_undoable_transaction'] = txuuid
        ### error case
        except NotFound, ex:
            result = self.notfound_content(req)
            req.status_out = ex.status
        except ValidationError, ex:
            req.status_out = httplib.CONFLICT
            result = self.validation_error_handler(req, ex)
        except RemoteCallFailed, ex:
            result = self.ajax_error_handler(req, ex)
        except Unauthorized, ex:
            req.data['errmsg'] = req._('You\'re not authorized to access this page. '
                                       'If you think you should, please contact the site administrator.')
            req.status_out = httplib.UNAUTHORIZED
            result = self.error_handler(req, ex, tb=False)
        except (BadRQLQuery, RequestError), ex:
            result = self.error_handler(req, ex, tb=False)
        ### pass through exception
        except DirectResponse:
            if req.cnx:
                req.cnx.commit()
            raise
        except (AuthenticationError, LogOut):
            # the rollback is handled in the finally
            raise
        ### Last defence line
        except BaseException, ex:
            result = self.error_handler(req, ex, tb=True)
        finally:
            if req.cnx and not commited:
                try:
                    req.cnx.rollback()
                except Exception:
                    pass # ignore rollback error at this point
            # request may be referenced by "onetime callback", so clear its entity
            # cache to avoid memory usage
            req.drop_entity_cache()
        self.add_undo_link_to_msg(req)
        self.debug('query %s executed in %s sec', req.relative_path(), clock() - tstart)
        return result

    # Error handlers

    def redirect_handler(self, req, ex):
        """handle redirect
        - comply to ex status
        - set header field
        - return empty content
        """
        self.debug('redirecting to %s', str(ex.location))
        req.headers_out.setHeader('location', str(ex.location))
        assert 300 <= ex.status < 400
        req.status_out = ex.status
        return ''

    def validation_error_handler(self, req, ex):
        ex.errors = dict((k, v) for k, v in ex.errors.items())
        if '__errorurl' in req.form:
            forminfo = {'error': ex,
                        'values': req.form,
                        'eidmap': req.data.get('eidmap', {})
                        }
            req.session.data[req.form['__errorurl']] = forminfo
            # XXX form session key / __error_url should be differentiated:
            # session key is 'url + #<form dom id', though we usually don't want
            # the browser to move to the form since it hides the global
            # messages.
            location = req.form['__errorurl'].rsplit('#', 1)[0]
            req.headers_out.setHeader('location', str(location))
            req.status_out = httplib.SEE_OTHER
            return ''
        return self.error_handler(req, ex, tb=False)

    def error_handler(self, req, ex, tb=False):
        excinfo = sys.exc_info()
        if tb:
            self.exception(repr(ex))
        req.set_header('Cache-Control', 'no-cache')
        req.remove_header('Etag')
        req.reset_message()
        req.reset_headers()
        if req.ajax_request:
            return ajax_error_handler(req, ex)
        try:
            req.data['ex'] = ex
            if tb:
                req.data['excinfo'] = excinfo
            req.form['vid'] = 'error'
            errview = self.vreg['views'].select('error', req)
            template = self.main_template_id(req)
            content = self.vreg['views'].main_template(req, template, view=errview)
        except Exception:
            content = self.vreg['views'].main_template(req, 'error-template')
        if getattr(ex, 'status', None) is not None:
            req.status_out = ex.status
        return content

    def add_undo_link_to_msg(self, req):
        txuuid = req.data.get('last_undoable_transaction')
        if txuuid is not None:
            msg = u'<span class="undo">[<a href="%s">%s</a>]</span>' %(
            req.build_url('undo', txuuid=txuuid), req._('undo'))
            req.append_to_redirect_message(msg)

    def ajax_error_handler(self, req, ex):
        req.set_header('content-type', 'application/json')
        status = ex.status
        if status is None:
            status = httplib.INTERNAL_SERVER_ERROR
        json_dumper = getattr(ex, 'dumps', lambda : unicode(ex))
        req.status_out = status
        return json_dumper()

    # special case handling

    def need_login_content(self, req):
        return self.vreg['views'].main_template(req, 'login')

    def loggedout_content(self, req):
        return self.vreg['views'].main_template(req, 'loggedout')

    def notfound_content(self, req):
        req.form['vid'] = '404'
        view = self.vreg['views'].select('404', req)
        template = self.main_template_id(req)
        return self.vreg['views'].main_template(req, template, view=view)

    # template stuff

    def main_template_id(self, req):
        template = req.form.get('__template', req.property_value('ui.main-template'))
        if template not in self.vreg['views']:
            template = 'main-template'
        return template

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

set_log_methods(CubicWebPublisher, LOGGER)
set_log_methods(CookieSessionHandler, LOGGER)
