# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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


import contextlib
import http.client as http_client
import json
import sys
from time import process_time, time
from contextlib import contextmanager

from rql import BadRQLQuery

from cubicweb import set_log_methods
from cubicweb import (
    CW_EVENT_MANAGER, ValidationError, Unauthorized, Forbidden,
    AuthenticationError, NoSelectableObject)
from cubicweb.repoapi import anonymous_cnx
from cubicweb.web import cors
from cubicweb.web import (
    LOGGER, DirectResponse, Redirect, NotFound, LogOut,
    RemoteCallFailed, InvalidSession, RequestError, PublishException)

# make session manager available through a global variable so the debug view can
# print information about web session
SESSION_MANAGER = None


@contextmanager
def anonymized_request(req):
    from cubicweb.web.views.authentication import Session

    orig_cnx = req.cnx
    anon_cnx = anonymous_cnx(orig_cnx.repo)
    try:
        with anon_cnx:
            # web request expect a session attribute on cnx referencing the web session
            anon_cnx.session = Session(orig_cnx.repo, anon_cnx.user)
            req.set_cnx(anon_cnx)
            yield req
    finally:
        req.set_cnx(orig_cnx)


class CookieSessionHandler(object):
    """a session handler using a cookie to store the session identifier"""

    def __init__(self, appli):
        self.repo = appli.repo
        self.vreg = appli.vreg
        self.session_manager = self.vreg['sessions'].select('sessionmanager',
                                                            repo=self.repo)
        global SESSION_MANAGER
        SESSION_MANAGER = self.session_manager
        if self.vreg.config.mode != 'test':
            # don't try to reset session manager during test, this leads to
            # weird failures when running multiple tests
            CW_EVENT_MANAGER.bind('after-registry-reload',
                                  self.reset_session_manager)

    def reset_session_manager(self):
        data = self.session_manager.dump_data()
        self.session_manager = self.vreg['sessions'].select('sessionmanager',
                                                            repo=self.repo)
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
        return '__%s_session' % self.vreg.config.appid

    def get_session(self, req):
        """Return a session object corresponding to credentials held by the req

        Session id is searched from :
        - # form variable
        - cookie

        If no session id is found, try opening a new session with credentials
        found in the request.

        Raises AuthenticationError if no session can be found or created.
        """
        cookie = req.get_cookie()
        sessioncookie = self.session_cookie(req)
        try:
            sessionid = str(cookie[sessioncookie].value)
            session = self.get_session_by_id(req, sessionid)
        except (KeyError, InvalidSession):  # no valid session cookie
            session = self.open_session(req)
        return session

    def get_session_by_id(self, req, sessionid):
        session = self.session_manager.get_session(req, sessionid)
        session.mtime = time()
        return session

    def open_session(self, req):
        session = self.session_manager.open_session(req)
        sessioncookie = self.session_cookie(req)
        secure = req.base_url().startswith('https://')
        req.set_cookie(sessioncookie, session.sessionid,
                       maxage=None, secure=secure, httponly=True)
        if not session.anonymous_session:
            self.session_manager.postlogin(req, session)
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
    info = warning = error = critical = exception = debug = lambda msg, *a, **kw: None


class CubicWebPublisher(object):
    """the publisher is a singleton hold by the web frontend, and is responsible
    to publish HTTP request.

    The http server will call its main entry point ``application.handle_request``.

    .. automethod:: cubicweb.web.application.CubicWebPublisher.main_handle_request

    You have to provide both a repository and web-server config at
    initialization. In all in one instance both config will be the same.
    """

    def __init__(self, repo, config, session_handler_fact=CookieSessionHandler):
        self.info('starting web instance from %s', config.apphome)
        self.repo = repo
        self.vreg = repo.vreg
        # get instance's schema
        if not self.vreg.initialized:
            config.init_cubes(self.repo.get_cubes())
            self.vreg.init_properties(self.repo.properties())
            self.vreg.set_schema(self.repo.get_schema())
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

    def get_session(self, req):
        """Return a session object corresponding to credentials held by the req

        May raise AuthenticationError.
        """
        return self.session_handler.get_session(req)

    # publish methods #########################################################

    def log_handle_request(self, req):
        """wrapper around _publish to log all queries executed for a given
        accessed path
        """
        def wrap_set_cnx(func):

            def wrap_execute(cnx):
                orig_execute = cnx.execute

                def execute(rql, kwargs=None, build_descr=True):
                    tstart, cstart = time(), process_time()
                    rset = orig_execute(rql, kwargs, build_descr=build_descr)
                    cnx.executed_queries.append((rql, kwargs, time() - tstart,
                                                 process_time() - cstart))
                    return rset

                return execute

            def set_cnx(cnx):
                func(cnx)
                cnx.execute = wrap_execute(cnx)
                cnx.executed_queries = []

            return set_cnx

        req.set_cnx = wrap_set_cnx(req.set_cnx)
        tstart, cstart = time(), process_time()
        try:
            return self.main_handle_request(req)
        finally:
            cnx = req.cnx
            if cnx and cnx.executed_queries:
                with self._logfile_lock:
                    tend, cend = time(), process_time()
                    try:
                        result = ['\n' + '*' * 80]
                        result.append('%s -- (%.3f sec, %.3f CPU sec)' % (
                            req.url(), tend - tstart, cend - cstart))
                        result += ['%s %s -- (%.3f sec, %.3f CPU sec)' % q
                                   for q in cnx.executed_queries]
                        cnx.executed_queries = []
                        self._query_log.write('\n'.join(result))
                        self._query_log.flush()
                    except Exception:
                        self.exception('error while logging queries')

    def main_handle_request(self, req):
        """Process an HTTP request `req`

        :type req: `web.Request`
        :param req: the request object

        It returns the content of the http response. HTTP header and status are
        set on the Request object.
        """
        if req.authmode == 'http':
            # activate realm-based auth
            realm = self.vreg.config['realm']
            req.set_header('WWW-Authenticate', [('Basic', {'realm': realm})], raw=False)
        content = b''
        try:
            try:
                session = self.get_session(req)
                cnx = session.new_cnx()
                with cnx:  # may need an open connection to access to e.g. properties
                    req.set_cnx(cnx)
                cnx._open = None  # XXX needed to reuse it a few line later :'(
            except AuthenticationError:
                # Keep the dummy session set at initialisation.  such session will work to some
                # extend but raise an AuthenticationError on any database access.
                # XXX We want to clean up this approach in the future. But several cubes like
                # registration or forgotten password rely on this principle.
                @contextlib.contextmanager
                def dummy():
                    yield
                cnx = dummy()
            # nested try to allow LogOut to delegate logic to AuthenticationError
            # handler
            try:
                # Try to generate the actual request content
                with cnx:
                    content = self.core_handle(req)
            # Handle user log-out
            except LogOut as ex:
                # When authentification is handled by cookie the code that
                # raised LogOut must has invalidated the cookie. We can just
                # reload the original url without authentification
                if self.vreg.config['auth-mode'] == 'cookie' and ex.url:
                    req.headers_out.setHeader('location', str(ex.url))
                if ex.status is not None:
                    req.status_out = http_client.SEE_OTHER
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
        except Redirect as ex:
            # authentication needs redirection (eg openid)
            content = self.redirect_handler(req, ex)
        # Wrong, absent or Reseted credential
        except AuthenticationError:
            # We assume here that in http auth mode the user *May* provide
            # Authentification Credential if asked kindly.
            if self.vreg.config['auth-mode'] == 'http':
                req.status_out = http_client.UNAUTHORIZED
            # In the other case (coky auth) we assume that there is no way
            # for the user to provide them...
            # XXX But WHY ?
            else:
                req.status_out = http_client.FORBIDDEN
            # If previous error handling already generated a custom content
            # do not overwrite it. This is used by LogOut Except
            # XXX ensure we don't actually serve content
            if not content:
                content = self.need_login_content(req)
        assert isinstance(content, bytes)
        return content

    def core_handle(self, req):
        """method called by the main publisher to process <req> relative path

        should return a string containing the resulting page or raise a
        `NotFound` exception

        :type req: `web.Request`
        :param req: the request object

        :rtype: str
        :return: the result of the pusblished url
        """
        path = req.relative_path(False)
        # don't log form values they may contains sensitive information
        self.debug('publish "%s" (%s, form params: %s)', path,
                   req.session.sessionid, list(req.form))
        # remove user callbacks on a new request (except for json controllers
        # to avoid callbacks being unregistered before they could be called)
        tstart = process_time()
        commited = False
        try:
            # standard processing of the request
            try:
                # apply CORS sanity checks
                cors.process_request(req, self.vreg.config)
                ctrlid, rset = self.url_resolver.process(req, path)
                try:
                    controller = self.vreg['controllers'].select(ctrlid, req,
                                                                 appli=self)
                except NoSelectableObject:
                    raise Unauthorized(req._('not authorized'))
                req.update_search_state()
                result = controller.publish(rset=rset)
            except cors.CORSPreflight:
                # Return directly an empty 200
                req.status_out = 200
                result = b''
            except Redirect as ex:
                # Redirect may be raised by edit controller when everything went
                # fine, so attempt to commit
                result = self.redirect_handler(req, ex)
            if req.cnx:
                txuuid = req.cnx.commit()
                commited = True
                if txuuid is not None:
                    req.data['last_undoable_transaction'] = txuuid
        # error case
        except NotFound as ex:
            result = self.notfound_content(req)
            req.status_out = ex.status
        except ValidationError as ex:
            result = self.validation_error_handler(req, ex)
        except RemoteCallFailed as ex:
            result = self.ajax_error_handler(req, ex)
        except Unauthorized as ex:
            req.data['errmsg'] = req._(
                'You\'re not authorized to access this page. '
                'If you think you should, please contact the site administrator.')
            req.status_out = http_client.FORBIDDEN
            result = self.error_handler(req, ex, tb=False)
        except Forbidden as ex:
            req.data['errmsg'] = req._(
                'This action is forbidden. '
                'If you think it should be allowed, please contact the site administrator.')
            req.status_out = http_client.FORBIDDEN
            result = self.error_handler(req, ex, tb=False)
        except (BadRQLQuery, RequestError) as ex:
            result = self.error_handler(req, ex, tb=False)
        # pass through exception
        except DirectResponse:
            if req.cnx:
                req.cnx.commit()
            raise
        except (AuthenticationError, LogOut):
            # the rollback is handled in the finally
            raise
        # Last defense line
        except BaseException as ex:
            req.status_out = http_client.INTERNAL_SERVER_ERROR
            result = self.error_handler(req, ex, tb=True)
        finally:
            if req.cnx and not commited:
                try:
                    req.cnx.rollback()
                except Exception:
                    pass  # ignore rollback error at this point
        self.add_undo_link_to_msg(req)
        self.debug('query %s executed in %s sec', path, process_time() - tstart)
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
        return b''

    def validation_error_handler(self, req, ex):
        ex.translate(req._)  # translate messages using ui language
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
            req.status_out = http_client.SEE_OTHER
            return b''
        req.status_out = http_client.CONFLICT
        return self.error_handler(req, ex, tb=False)

    def error_handler(self, req, ex, tb=False):
        excinfo = sys.exc_info()
        if tb:
            self.exception(repr(ex))
        req.set_header('Cache-Control', 'no-cache')
        req.remove_header('Etag')
        req.remove_header('Content-disposition')
        req.reset_message()
        req.reset_headers()
        if req.ajax_request:
            return self.ajax_error_handler(req, ex)
        try:
            req.data['ex'] = ex
            if tb:
                req.data['excinfo'] = excinfo
            errview = self.vreg['views'].select('error', req)
            template = self.main_template_id(req)
            content = self.vreg['views'].main_template(req, template, view=errview)
        except Exception:
            content = self.vreg['views'].main_template(req, 'error-template')
        if isinstance(ex, PublishException) and ex.status is not None:
            req.status_out = ex.status
        return content

    def add_undo_link_to_msg(self, req):
        txuuid = req.data.get('last_undoable_transaction')
        if txuuid is not None:
            msg = u'<span class="undo">[<a href="%s">%s</a>]</span>' % (
                req.build_url('undo', txuuid=txuuid), req._('undo'))
            req.append_to_redirect_message(msg)

    def ajax_error_handler(self, req, ex):
        req.set_header('content-type', 'application/json')
        status = http_client.INTERNAL_SERVER_ERROR
        if isinstance(ex, PublishException) and ex.status is not None:
            status = ex.status
        if req.status_out < 400:
            # don't overwrite it if it's already set
            req.status_out = status
        json_dumper = getattr(ex, 'dumps', lambda: json.dumps({'reason': str(ex)}))
        return json_dumper().encode('utf-8')

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
    info = warning = error = critical = exception = debug = lambda msg, *a, **kw: None


set_log_methods(CubicWebPublisher, LOGGER)
set_log_methods(CookieSessionHandler, LOGGER)
