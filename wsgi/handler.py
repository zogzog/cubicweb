"""WSGI request handler for cubicweb

:organization: Logilab
:copyright: 2008-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"

from cubicweb import AuthenticationError
from cubicweb.web import (NotFound, Redirect, DirectResponse, StatusResponse,
                          ExplicitLogin)
from cubicweb.web.application import CubicWebPublisher
from cubicweb.wsgi.request import CubicWebWsgiRequest

# See http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html
STATUS_CODE_TEXT = {
    100: 'CONTINUE',
    101: 'SWITCHING PROTOCOLS',
    200: 'OK',
    201: 'CREATED',
    202: 'ACCEPTED',
    203: 'NON-AUTHORITATIVE INFORMATION',
    204: 'NO CONTENT',
    205: 'RESET CONTENT',
    206: 'PARTIAL CONTENT',
    300: 'MULTIPLE CHOICES',
    301: 'MOVED PERMANENTLY',
    302: 'FOUND',
    303: 'SEE OTHER',
    304: 'NOT MODIFIED',
    305: 'USE PROXY',
    306: 'RESERVED',
    307: 'TEMPORARY REDIRECT',
    400: 'BAD REQUEST',
    401: 'UNAUTHORIZED',
    402: 'PAYMENT REQUIRED',
    403: 'FORBIDDEN',
    404: 'NOT FOUND',
    405: 'METHOD NOT ALLOWED',
    406: 'NOT ACCEPTABLE',
    407: 'PROXY AUTHENTICATION REQUIRED',
    408: 'REQUEST TIMEOUT',
    409: 'CONFLICT',
    410: 'GONE',
    411: 'LENGTH REQUIRED',
    412: 'PRECONDITION FAILED',
    413: 'REQUEST ENTITY TOO LARGE',
    414: 'REQUEST-URI TOO LONG',
    415: 'UNSUPPORTED MEDIA TYPE',
    416: 'REQUESTED RANGE NOT SATISFIABLE',
    417: 'EXPECTATION FAILED',
    500: 'INTERNAL SERVER ERROR',
    501: 'NOT IMPLEMENTED',
    502: 'BAD GATEWAY',
    503: 'SERVICE UNAVAILABLE',
    504: 'GATEWAY TIMEOUT',
    505: 'HTTP VERSION NOT SUPPORTED',
}


class WSGIResponse(object):
    """encapsulates the wsgi response parameters
    (code, headers and body if there is one)
    """
    def __init__(self, code, req, body=None):
        text = STATUS_CODE_TEXT.get(code, 'UNKNOWN STATUS CODE')
        self.status =  '%s %s' % (code, text)
        self.headers = [(str(k), str(v)) for k, v in req.headers_out.items()]
        if body:
            self.body = [body]
        else:
            self.body = []

    def __iter__(self):
        return iter(self.body)



class CubicWebWSGIApplication(object):
    """This is the wsgi application which will be called by the
    wsgi server with the WSGI ``environ`` and ``start_response``
    parameters.

    XXX: missing looping tasks and proper repository shutdown when
    the application is stopped.
    NOTE: no pyro
    """

    def __init__(self, config, debug=None, vreg=None):
        self.appli = CubicWebPublisher(config, debug=debug, vreg=vreg)
        self.debugmode = debug
        self.config = config
        self.base_url = None
#         self.base_url = config['base-url'] or config.default_base_url()
#         assert self.base_url[-1] == '/'
#         self.https_url = config['https-url']
#         assert not self.https_url or self.https_url[-1] == '/'
        self.url_rewriter = self.appli.vreg['components'].select_or_none('urlrewriter')

    def _render(self, req):
        """this function performs the actual rendering
        XXX missing: https handling, url rewriting, cache management,
                     authentication
        """
        if self.base_url is None:
            self.base_url = self.config._base_url = req.base_url()
        # XXX https handling needs to be implemented
        if req.authmode == 'http':
            # activate realm-based auth
            realm = self.config['realm']
            req.set_header('WWW-Authenticate', [('Basic', {'realm' : realm })], raw=False)
        try:
            self.appli.connect(req)
        except AuthenticationError:
            return self.request_auth(req)
        except Redirect, ex:
            return self.redirect(req, ex.location)
        path = req.path
        if not path or path == "/":
            path = 'view'
        try:
            result = self.appli.publish(path, req)
        except DirectResponse, ex:
            return WSGIResponse(200, req, ex.response)
        except StatusResponse, ex:
            return WSGIResponse(ex.status, req, ex.content)
        except NotFound:
            result = self.appli.notfound_content(req)
            return WSGIResponse(404, req, result)
        except ExplicitLogin:  # must be before AuthenticationError
            return self.request_auth(req)
        except AuthenticationError:
            if self.config['auth-mode'] == 'cookie':
                # in cookie mode redirecting to the index view is enough :
                # either anonymous connection is allowed and the page will
                # be displayed or we'll be redirected to the login form
                msg = req._('you have been logged out')
#                 if req.https:
#                     req._base_url =  self.base_url
#                     req.https = False
                url = req.build_url('view', vid='index', __message=msg)
                return self.redirect(req, url)
            else:
                # in http we have to request auth to flush current http auth
                # information
                return self.request_auth(req, loggedout=True)
        except Redirect, ex:
            return self.redirect(req, ex.location)
        if not result:
            # no result, something went wrong...
            self.error('no data (%s)', req)
            # 500 Internal server error
            return self.redirect(req, req.build_url('error'))
        return WSGIResponse(200, req, result)


    def __call__(self, environ, start_response):
        """WSGI protocol entry point"""
        req = CubicWebWsgiRequest(environ, self.appli.vreg, self.base_url)
        response = self._render(req)
        start_response(response.status, response.headers)
        return response.body

    def redirect(self, req, location):
        """convenience function which builds a redirect WSGIResponse"""
        self.debug('redirecting to %s', location)
        req.set_header('location', str(location))
        return WSGIResponse(303, req)

    def request_auth(self, req, loggedout=False):
        """returns the appropriate WSGIResponse to require the user to log in
        """
#         if self.https_url and req.base_url() != self.https_url:
#             return self.redirect(self.https_url + 'login')
        if self.config['auth-mode'] == 'http':
            code = 401 # UNAUTHORIZED
        else:
            code = 403 # FORBIDDEN
        if loggedout:
#             if req.https:
#                 req._base_url =  self.base_url
#                 req.https = False
            content = self.appli.loggedout_content(req)
        else:
            content = self.appli.need_login_content(req)
        return WSGIResponse(code, req, content)


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(CubicWebWSGIApplication, getLogger('cubicweb.wsgi'))
