"""twisted server for CubicWeb web instances

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"

from cubicweb.web.http_headers import Headers

class HTTPResponse(object):
    """An object representing an HTTP Response to be sent to the client.
    """
    def __init__(self, twisted_request, code=None, headers=None, stream=None):
        self._headers_out = headers
        self._twreq = twisted_request
        self._stream = stream
        self._code = code

        self._init_headers()
        self._finalize()

    def _init_headers(self):
        if self._headers_out is None:
            return

        # initialize cookies
        cookies = self._headers_out.getHeader('set-cookie') or []
        for cookie in cookies:
            self._twreq.addCookie(cookie.name, cookie.value, cookie.expires,
                                  cookie.domain, cookie.path, #TODO max-age
                                  comment = cookie.comment, secure=cookie.secure)
        self._headers_out.removeHeader('set-cookie')

        # initialize other headers
        for k, v in self._headers_out.getAllRawHeaders():
            self._twreq.setHeader(k, v[0])

        # add content-length if not present
        if (self._headers_out.getHeader('content-length') is None
            and self._stream is not None):
           self._twreq.setHeader('content-length', len(self._stream))


    def _finalize(self):
        # we must set code before writing anything, else it's too late
        if self._code is not None:
            self._twreq.setResponseCode(self._code)
        if self._stream is not None:
            self._twreq.write(str(self._stream))
        self._twreq.finish()

    def __repr__(self):
        return "<%s.%s code=%d>" % (self.__module__, self.__class__.__name__, self._code)


def not_modified_response(twisted_request, headers_in):
    headers_out = Headers()

    for header in (
        # Required from sec 10.3.5:
        'date', 'etag', 'content-location', 'expires',
        'cache-control', 'vary',
        # Others:
        'server', 'proxy-authenticate', 'www-authenticate', 'warning'):
        value = headers_in.getRawHeaders(header)
        if value is not None:
            headers_out.setRawHeaders(header, value)
    return HTTPResponse(twisted_request=twisted_request,
                        headers=headers_out)
