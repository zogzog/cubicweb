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
"""CubicWeb web client application object

"""
from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
from time import clock, time

from logilab.common.deprecation import deprecated

from rql import BadRQLQuery

from cubicweb import set_log_methods, cwvreg
from cubicweb import (
    ValidationError, Unauthorized, AuthenticationError, NoSelectableObject,
    RepositoryError, CW_EVENT_MANAGER)
from cubicweb.dbapi import DBAPISession
from cubicweb.web import LOGGER, component
from cubicweb.web import (
    StatusResponse, DirectResponse, Redirect, NotFound, LogOut,
    RemoteCallFailed, InvalidSession, RequestError)

# make session manager available through a global variable so the debug view can
# print information about web session
SESSION_MANAGER = None

class AbstractSessionManager(component.Component):
    """manage session data associated to a session identifier"""
    __regid__ = 'sessionmanager'

    def __init__(self, vreg):
        self.session_time = vreg.config['http-session-time'] or None
        if self.session_time is not None:
            assert self.session_time > 0
            self.cleanup_session_time = self.session_time
        else:
            self.cleanup_session_time = vreg.config['cleanup-session-time'] or 1440 * 60
            assert self.cleanup_session_time > 0
        self.cleanup_anon_session_time = vreg.config['cleanup-anonymous-session-time'] or 5 * 60
        assert self.cleanup_anon_session_time > 0
        self.authmanager = vreg['components'].select('authmanager', vreg=vreg)
        if vreg.config.anonymous_user() is not None:
            self.clean_sessions_interval = min(
                5 * 60,
                self.cleanup_session_time / 2.,
                self.cleanup_anon_session_time / 2.)
        else:
            self.clean_sessions_interval = min(
                5 * 60,
                self.cleanup_session_time / 2.)

    def clean_sessions(self):
        """cleanup sessions which has not been unused since a given amount of
        time. Return the number of sessions which have been closed.
        """
        self.debug('cleaning http sessions')
        closed, total = 0, 0
        for session in self.current_sessions():
            no_use_time = (time() - session.last_usage_time)
            total += 1
            if session.anonymous_session:
                if no_use_time >= self.cleanup_anon_session_time:
                    self.close_session(session)
                    closed += 1
            elif no_use_time >= self.cleanup_session_time:
                self.close_session(session)
                closed += 1
        return closed, total - closed

    def has_expired(self, session):
        """return True if the web session associated to the session is expired
        """
        return not (self.session_time is None or
                    time() < session.last_usage_time + self.session_time)

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
    id = 'authmanager'
    vreg = None # XXX necessary until property for deprecation warning is on appobject

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
    """a session handler using a cookie to store the session identifier

    :cvar SESSION_VAR:
      string giving the name of the variable used to store the session
      identifier
    """
    SESSION_VAR = '__session'

    def __init__(self, appli):
        self.vreg = appli.vreg
        self.session_manager = self.vreg['components'].select('sessionmanager',
                                                              vreg=self.vreg)
        global SESSION_MANAGER
        SESSION_MANAGER = self.session_manager
        if not 'last_login_time' in self.vreg.schema:
            self._update_last_login_time = lambda x: None
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

    def set_session(self, req):
        """associate a session to the request

        Session id is searched from :
        - # form variable
        - cookie

        if no session id is found, open a new session for the connected user
        or request authentification as needed

        :raise Redirect: if authentication has occured and succeed
        """
        cookie = req.get_cookie()
        try:
            sessionid = str(cookie[self.SESSION_VAR].value)
        except KeyError: # no session cookie
            session = self.open_session(req)
        else:
            try:
                session = self.get_session(req, sessionid)
            except InvalidSession:
                # try to open a new session, so we get an anonymous session if
                # allowed
                try:
                    session = self.open_session(req)
                except AuthenticationError:
                    req.remove_cookie(cookie, self.SESSION_VAR)
                    raise
        # remember last usage time for web session tracking
        session.last_usage_time = time()

    def get_session(self, req, sessionid):
        return self.session_manager.get_session(req, sessionid)

    def open_session(self, req):
        session = self.session_manager.open_session(req)
        cookie = req.get_cookie()
        cookie[self.SESSION_VAR] = session.sessionid
        req.set_cookie(cookie, self.SESSION_VAR, maxage=None)
        # remember last usage time for web session tracking
        session.last_usage_time = time()
        if not session.anonymous_session:
            self._postlogin(req)
        return session

    def _update_last_login_time(self, req):
        try:
            req.execute('SET X last_login_time NOW WHERE X eid %(x)s',
                        {'x' : req.user.eid})
            req.cnx.commit()
        except (RepositoryError, Unauthorized):
            # ldap user are not writeable for instance
            req.cnx.rollback()
        except:
            req.cnx.rollback()
            raise

    def _postlogin(self, req):
        """postlogin: the user has been authenticated, redirect to the original
        page (index by default) with a welcome message
        """
        # Update last connection date
        # XXX: this should be in a post login hook in the repository, but there
        #      we can't differentiate actual login of automatic session
        #      reopening. Is it actually a problem?
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

    def logout(self, req, goto_url):
        """logout from the instance by cleaning the session and raising
        `AuthenticationError`
        """
        self.session_manager.close_session(req.cnx)
        req.remove_cookie(req.get_cookie(), self.SESSION_VAR)
        raise LogOut(url=goto_url)


class CubicWebPublisher(object):
    """the publisher is a singleton hold by the web frontend, and is responsible
    to publish HTTP request.
    """

    def __init__(self, config, debug=None,
                 session_handler_fact=CookieSessionHandler,
                 vreg=None):
        self.info('starting web instance from %s', config.apphome)
        if vreg is None:
            vreg = cwvreg.CubicWebVRegistry(config, debug=debug)
        self.vreg = vreg
        # connect to the repository and get instance's schema
        self.repo = config.repository(vreg)
        if not vreg.initialized:
            self.config.init_cubes(self.repo.get_cubes())
            vreg.init_properties(self.repo.properties())
            vreg.set_schema(self.repo.get_schema())
        # set the correct publish method
        if config['query-log-file']:
            from threading import Lock
            self._query_log = open(config['query-log-file'], 'a')
            self.publish = self.log_publish
            self._logfile_lock = Lock()
        else:
            self._query_log = None
            self.publish = self.main_publish
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
        try:
            self.session_handler.set_session(req)
        except AuthenticationError:
            req.set_session(DBAPISession(None))

    # publish methods #########################################################

    def log_publish(self, path, req):
        """wrapper around _publish to log all queries executed for a given
        accessed path
        """
        try:
            return self.main_publish(path, req)
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

    @deprecated("[3.4] use vreg['controllers'].select(...)")
    def select_controller(self, oid, req):
        try:
            return self.vreg['controllers'].select(oid, req=req, appli=self)
        except NoSelectableObject:
            raise Unauthorized(req._('not authorized'))

    def main_publish(self, path, req):
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
        path = path or 'view'
        # don't log form values they may contains sensitive information
        self.info('publish "%s" (form params: %s)', path, req.form.keys())
        # remove user callbacks on a new request (except for json controllers
        # to avoid callbacks being unregistered before they could be called)
        tstart = clock()
        try:
            try:
                ctrlid, rset = self.url_resolver.process(req, path)
                try:
                    controller = self.vreg['controllers'].select(ctrlid, req,
                                                                 appli=self)
                except NoSelectableObject:
                    raise Unauthorized(req._('not authorized'))
                req.update_search_state()
                result = controller.publish(rset=rset)
                if req.cnx:
                    # no req.cnx if anonymous aren't allowed and we are
                    # displaying some anonymous enabled view such as the cookie
                    # authentication form
                    req.cnx.commit()
            except (StatusResponse, DirectResponse):
                if req.cnx:
                    req.cnx.commit()
                raise
            except (AuthenticationError, LogOut):
                raise
            except Redirect:
                # redirect is raised by edit controller when everything went fine,
                # so try to commit
                try:
                    txuuid = req.cnx.commit()
                    if txuuid is not None:
                        msg = u'<span class="undo">[<a href="%s">%s</a>]</span>' %(
                            req.build_url('undo', txuuid=txuuid), req._('undo'))
                        req.append_to_redirect_message(msg)
                except ValidationError, ex:
                    self.validation_error_handler(req, ex)
                except Unauthorized, ex:
                    req.data['errmsg'] = req._('You\'re not authorized to access this page. '
                                               'If you think you should, please contact the site administrator.')
                    self.error_handler(req, ex, tb=False)
                except Exception, ex:
                    self.error_handler(req, ex, tb=True)
                else:
                    # delete validation errors which may have been previously set
                    if '__errorurl' in req.form:
                        req.session.data.pop(req.form['__errorurl'], None)
                    raise
            except RemoteCallFailed, ex:
                req.set_header('content-type', 'application/json')
                raise StatusResponse(500, ex.dumps())
            except NotFound:
                raise StatusResponse(404, self.notfound_content(req))
            except ValidationError, ex:
                self.validation_error_handler(req, ex)
            except (Unauthorized, BadRQLQuery, RequestError), ex:
                self.error_handler(req, ex, tb=False)
            except Exception, ex:
                self.error_handler(req, ex, tb=True)
            except:
                self.critical('Catch all triggered!!!')
                self.exception('this is what happened')
        finally:
            if req.cnx:
                try:
                    req.cnx.rollback()
                except:
                    pass # ignore rollback error at this point
        self.info('query %s executed in %s sec', req.relative_path(), clock() - tstart)
        return result

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
            raise Redirect(req.form['__errorurl'].rsplit('#', 1)[0])
        self.error_handler(req, ex, tb=False)

    def error_handler(self, req, ex, tb=False):
        excinfo = sys.exc_info()
        self.exception(repr(ex))
        req.set_header('Cache-Control', 'no-cache')
        req.remove_header('Etag')
        req.reset_message()
        req.reset_headers()
        if req.json_request:
            raise RemoteCallFailed(unicode(ex))
        try:
            req.data['ex'] = ex
            if tb:
                req.data['excinfo'] = excinfo
            req.form['vid'] = 'error'
            errview = self.vreg['views'].select('error', req)
            template = self.main_template_id(req)
            content = self.vreg['views'].main_template(req, template, view=errview)
        except:
            content = self.vreg['views'].main_template(req, 'error-template')
        raise StatusResponse(500, content)

    def need_login_content(self, req):
        return self.vreg['views'].main_template(req, 'login')

    def loggedout_content(self, req):
        return self.vreg['views'].main_template(req, 'loggedout')

    def notfound_content(self, req):
        req.form['vid'] = '404'
        view = self.vreg['views'].select('404', req)
        template = self.main_template_id(req)
        return self.vreg['views'].main_template(req, template, view=view)

    def main_template_id(self, req):
        template = req.form.get('__template', req.property_value('ui.main-template'))
        if template not in self.vreg['views']:
            template = 'main-template'
        return template


set_log_methods(CubicWebPublisher, LOGGER)
set_log_methods(CookieSessionHandler, LOGGER)
