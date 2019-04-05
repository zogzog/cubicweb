# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""WSGI request handler for cubicweb"""



from itertools import chain, repeat

from cubicweb import AuthenticationError
from cubicweb.web import DirectResponse
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
        self.status =  '%d %s' % (code, text)
        self.headers = list(chain(*[zip(repeat(k), v)
                                    for k, v in req.headers_out.getAllRawHeaders()]))
        self.headers = [(str(k), str(v)) for k, v in self.headers]
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
    """

    def __init__(self, config):
        self.appli = CubicWebPublisher(config.repository(), config)
        self.config = config
        self.base_url = self.config['base-url']
        self.url_rewriter = self.appli.vreg['components'].select_or_none('urlrewriter')

    def _render(self, req):
        """this function performs the actual rendering
        """
        try:
            result = self.appli.handle_request(req)
        except DirectResponse as ex:
            return ex.response
        return WSGIResponse(req.status_out, req, result)


    def __call__(self, environ, start_response):
        """WSGI protocol entry point"""
        req = CubicWebWsgiRequest(environ, self.appli.vreg)
        response = self._render(req)
        start_response(response.status, response.headers)
        return response.body



    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(CubicWebWSGIApplication, getLogger('cubicweb.wsgi'))
