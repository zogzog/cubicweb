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
"""Twisted request handler for CubicWeb

"""
__docformat__ = "restructuredtext en"

from datetime import datetime

from twisted.web import http

from cubicweb.web import DirectResponse
from cubicweb.web.request import CubicWebRequestBase
from cubicweb.web.httpcache import GMTOFFSET
from cubicweb.web.http_headers import Headers
from cubicweb.etwist.http import not_modified_response


class CubicWebTwistedRequestAdapter(CubicWebRequestBase):
    def __init__(self, req, vreg, https, base_url):
        self._twreq = req
        self._base_url = base_url
        super(CubicWebTwistedRequestAdapter, self).__init__(vreg, https, req.args)
        for key, (name, stream) in req.files.iteritems():
            if name is None:
                self.form[key] = (name, stream)
            else:
                self.form[key] = (unicode(name, self.encoding), stream)
        # XXX can't we keep received_headers?
        self._headers_in = Headers()
        for k, v in req.received_headers.iteritems():
            self._headers_in.addRawHeader(k, v)

    def base_url(self):
        """return the root url of the instance"""
        return self._base_url

    def http_method(self):
        """returns 'POST', 'GET', 'HEAD', etc."""
        return self._twreq.method

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the instance's root, but some other normalization may be needed
        so that the returned path may be used to compare to generated urls

        :param includeparams:
           boolean indicating if GET form parameters should be kept in the path
        """
        path = self._twreq.uri[1:] # remove the root '/'
        if not includeparams:
            path = path.split('?', 1)[0]
        return path

    def get_header(self, header, default=None, raw=True):
        """return the value associated with the given input header,
        raise KeyError if the header is not set
        """
        if raw:
            return self._headers_in.getRawHeaders(header, [default])[0]
        return self._headers_in.getHeader(header, default)

    def _validate_cache(self):
        """raise a `DirectResponse` exception if a cached page along the way
        exists and is still usable
        """
        if self.get_header('Cache-Control') in ('max-age=0', 'no-cache'):
            # Expires header seems to be required by IE7
            self.add_header('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')
            return

        # when using both 'Last-Modified' and 'ETag' response headers
        # (i.e. using respectively If-Modified-Since and If-None-Match request
        # headers, see
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.3.4 for
        # reference

        cached_because_not_modified_since = False

        last_modified = self.headers_out.getHeader('last-modified')
        if last_modified is not None:
            cached_because_not_modified_since = (self._twreq.setLastModified(last_modified)
                                                 == http.CACHED)

        if not cached_because_not_modified_since:
            return

        cached_because_etag_is_same = False
        etag = self.headers_out.getRawHeaders('etag')
        if etag is not None:
            cached_because_etag_is_same = self._twreq.setETag(etag[0]) == http.CACHED

        if cached_because_etag_is_same:
            response = not_modified_response(self._twreq, self._headers_in)
            raise DirectResponse(response)

        # Expires header seems to be required by IE7
        self.add_header('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')

    def header_accept_language(self):
        """returns an ordered list of preferred languages"""
        acceptedlangs = self.get_header('Accept-Language', raw=False) or {}
        for lang, _ in sorted(acceptedlangs.iteritems(), key=lambda x: x[1],
                              reverse=True):
            lang = lang.split('-')[0]
            yield lang

    def header_if_modified_since(self):
        """If the HTTP header If-modified-since is set, return the equivalent
        date time value (GMT), else return None
        """
        mtime = self.get_header('If-modified-since', raw=False)
        if mtime:
            # :/ twisted is returned a localized time stamp
            return datetime.fromtimestamp(mtime) + GMTOFFSET
        return None
