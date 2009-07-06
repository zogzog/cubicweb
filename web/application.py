"""CubicWeb web client application object

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
from time import clock, time

from rql import BadRQLQuery

from cubicweb import set_log_methods
from cubicweb import (ValidationError, Unauthorized, AuthenticationError,
                      NoSelectableObject, RepositoryError)
from cubicweb.cwvreg import CubicWebRegistry
from cubicweb.web import (LOGGER, StatusResponse, DirectResponse, Redirect,
                          NotFound, RemoteCallFailed, ExplicitLogin,
                          InvalidSession, RequestError)
from cubicweb.web.component import Component

# make session manager available through a global variable so the debug view can
# print information about web session
SESSION_MANAGER = None

class AbstractSessionManager(Component):
    """manage session data associated to a session identifier"""
    id = 'sessionmanager'

    def __init__(self):
        self.session_time = self.vreg.config['http-session-time'] or None
        assert self.session_time is None or self.session_time > 0
        self.cleanup_session_time = self.vreg.config['cleanup-session-time'] or 43200
        assert self.cleanup_session_time > 0
        self.cleanup_anon_session_time = self.vreg.config['cleanup-anonymous-session-time'] or 120
        assert self.cleanup_anon_session_time > 0
        if self.session_time:
            assert self.cleanup_session_time < self.session_time
            assert self.cleanup_anon_session_time < self.session_time
        self.authmanager = self.vreg.select_component('authmanager')
        assert self.authmanager, 'no authentication manager found'

    def clean_sessions(self):
        """cleanup sessions which has not been unused since a given amount of
        time. Return the number of sessions which have been closed.
        """
        self.debug('cleaning http sessions')
        closed, total = 0, 0
        for session in self.current_sessions():
            no_use_time = (time() - session.last_usage_time)
            total += 1
            if session.anonymous_connection:
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
        """open and return a new session for the given request

        :raise ExplicitLogin: if authentication is required
        """
        raise NotImplementedError()

    def close_session(self, session):
        """close session on logout or on invalid session detected (expired out,
        corrupted...)
        """
        raise NotImplementedError()


class AbstractAuthenticationManager(Component):
    """authenticate user associated to a request and check session validity"""
    id = 'authmanager'

    def authenticate(self, req):
        """authenticate user and return corresponding user object

        :raise ExplicitLogin: if authentication is required (no authentication
        info found or wrong user/password)
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
        self.session_manager = appli.vreg.select_component('sessionmanager')
        assert self.session_manager, 'no session manager found'
        global SESSION_MANAGER
        SESSION_MANAGER = self.session_manager
        if not 'last_login_time' in appli.vreg.schema:
            self._update_last_login_time = lambda x: None

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
        assert req.cnx is None # at this point no cnx should be set on the request
        cookie = req.get_cookie()
        try:
            sessionid = str(cookie[self.SESSION_VAR].value)
        except KeyError: # no session cookie
            session = self.open_session(req)
        else:
            try:
                session = self.get_session(req, sessionid)
            except InvalidSession:
                try:
                    session = self.open_session(req)
                except ExplicitLogin:
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
        if not session.anonymous_connection:
            self._postlogin(req)
        return session

    def _update_last_login_time(self, req):
        try:
            req.execute('SET X last_login_time NOW WHERE X eid %(x)s',
                        {'x' : req.user.eid}, 'x')
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
        args['__message'] = req._('welcome %s !') % req.user.login
        if 'vid' in req.form:
            args['vid'] = req.form['vid']
        if 'rql' in req.form:
            args['rql'] = req.form['rql']
        path = req.relative_path(False)
        if path == 'login':
            path = 'view'
        raise Redirect(req.build_url(path, **args))

    def logout(self, req):
        """logout from the application by cleaning the session and raising
        `AuthenticationError`
        """
        self.session_manager.close_session(req.cnx)
        req.remove_cookie(req.get_cookie(), self.SESSION_VAR)
        raise AuthenticationError()


class CubicWebPublisher(object):
    """Central registry for the web application. This is one of the central
    object in the web application, coupling dynamically loaded objects with
    the application's schema and the application's configuration objects.

    It specializes the VRegistry by adding some convenience methods to
    access to stored objects. Currently we have the following registries
    of objects known by the web application (library may use some others
    additional registries):
    * controllers, which are directly plugged into the application
      object to handle request publishing
    * views
    * templates
    * components
    * actions
    """

    def __init__(self, config, debug=None,
                 session_handler_fact=CookieSessionHandler,
                 vreg=None):
        super(CubicWebPublisher, self).__init__()
        # connect to the repository and get application's schema
        if vreg is None:
            vreg = CubicWebRegistry(config, debug=debug)
        self.vreg = vreg
        self.info('starting web application from %s', config.apphome)
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
        self.url_resolver = vreg.select_component('urlpublisher')

    def connect(self, req):
        """return a connection for a logged user object according to existing
        sessions (i.e. a new connection may be created or an already existing
        one may be reused
        """
        self.session_handler.set_session(req)

    def select_controller(self, oid, req):
        """return the most specific view according to the resultset"""
        vreg = self.vreg
        try:
            return vreg.select(vreg.registry_objects('controllers', oid),
                               req=req, appli=self)
        except NoSelectableObject:
            raise Unauthorized(req._('not authorized'))

    # publish methods #########################################################

    def log_publish(self, path, req):
        """wrapper around _publish to log all queries executed for a given
        accessed path
        """
        try:
            return self.main_publish(path, req)
        finally:
            cnx = req.cnx
            self._logfile_lock.acquire()
            try:
                try:
                    result = ['\n'+'*'*80]
                    result.append(req.url())
                    result += ['%s %s -- (%.3f sec, %.3f CPU sec)' % q for q in cnx.executed_queries]
                    cnx.executed_queries = []
                    self._query_log.write('\n'.join(result).encode(req.encoding))
                    self._query_log.flush()
                except Exception:
                    self.exception('error while logging queries')
            finally:
                self._logfile_lock.release()

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
                controller = self.select_controller(ctrlid, req)
                req.update_search_state()
                result = controller.publish(rset=rset)
                if req.cnx is not None:
                    # req.cnx is None if anonymous aren't allowed and we are
                    # displaying the cookie authentication form
                    req.cnx.commit()
            except (StatusResponse, DirectResponse):
                req.cnx.commit()
                raise
            except Redirect:
                # redirect is raised by edit controller when everything went fine,
                # so try to commit
                try:
                    req.cnx.commit()
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
                        req.del_session_data(req.form['__errorurl'])
                    raise
            except (AuthenticationError, NotFound, RemoteCallFailed):
                raise
            except ValidationError, ex:
                self.validation_error_handler(req, ex)
            except (Unauthorized, BadRQLQuery, RequestError), ex:
                self.error_handler(req, ex, tb=False)
            except Exception, ex:
                self.error_handler(req, ex, tb=True)
        finally:
            if req.cnx is not None:
                try:
                    req.cnx.rollback()
                except:
                    pass # ignore rollback error at this point
        self.info('query %s executed in %s sec', req.relative_path(), clock() - tstart)
        return result

    def validation_error_handler(self, req, ex):
        ex.errors = dict((k, v) for k, v in ex.errors.items())
        if '__errorurl' in req.form:
            forminfo = {'errors': ex,
                        'values': req.form,
                        'eidmap': req.data.get('eidmap', {})
                        }
            req.set_session_data(req.form['__errorurl'], forminfo)
            raise Redirect(req.form['__errorurl'])
        self.error_handler(req, ex, tb=False)

    def error_handler(self, req, ex, tb=False):
        excinfo = sys.exc_info()
        self.exception(repr(ex))
        req.set_header('Cache-Control', 'no-cache')
        req.remove_header('Etag')
        req.message = None
        req.reset_headers()
        try:
            req.data['ex'] = ex
            if tb:
                req.data['excinfo'] = excinfo
            req.form['vid'] = 'error'
            errview = self.vreg.select_view('error', req, None)
            template = self.main_template_id(req)
            content = self.vreg.main_template(req, template, view=errview)
        except:
            content = self.vreg.main_template(req, 'error-template')
        raise StatusResponse(500, content)

    def need_login_content(self, req):
        return self.vreg.main_template(req, 'login')

    def loggedout_content(self, req):
        return self.vreg.main_template(req, 'loggedout')

    def notfound_content(self, req):
        req.form['vid'] = '404'
        view = self.vreg.select_view('404', req, None)
        template = self.main_template_id(req)
        return self.vreg.main_template(req, template, view=view)

    def main_template_id(self, req):
        template = req.form.get('__template', req.property_value('ui.main-template'))
        if template not in self.vreg.registry('views'):
            template = 'main-template'
        return template


set_log_methods(CubicWebPublisher, LOGGER)
set_log_methods(CookieSessionHandler, LOGGER)
