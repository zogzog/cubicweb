"""Twisted request handler for CubicWeb

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from datetime import datetime

from twisted.web2 import http, http_headers

from cubicweb.web import DirectResponse
from cubicweb.web.request import CubicWebRequestBase
from cubicweb.web.httpcache import GMTOFFSET

def cleanup_files(dct, encoding):
    d = {}
    for k, infos in dct.items():
        for (filename, mt, stream) in infos:
            if filename:
                # XXX: suppose that no file submitted <-> no filename
                filename = unicode(filename, encoding)
                mt = u'%s/%s' % (mt.mediaType, mt.mediaSubtype)
                d[k] = (filename, mt, stream)
    return d


class CubicWebTwistedRequestAdapter(CubicWebRequestBase):
    def __init__(self, req, vreg, https, base_url):
        self._twreq = req
        self._base_url = base_url
        super(CubicWebTwistedRequestAdapter, self).__init__(vreg, https, req.args)
        self.form.update(cleanup_files(req.files, self.encoding))
        # prepare output headers
        self.headers_out = http_headers.Headers()
        self._headers = req.headers

    def base_url(self):
        """return the root url of the application"""
        return self._base_url

    def http_method(self):
        """returns 'POST', 'GET', 'HEAD', etc."""
        return self._twreq.method

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the application's root, but some other normalization may be needed
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
            return self._twreq.headers.getRawHeaders(header, [default])[0]
        return self._twreq.headers.getHeader(header, default)

    def set_header(self, header, value, raw=True):
        """set an output HTTP header"""
        if raw:
            # adding encoded header is important, else page content
            # will be reconverted back to unicode and apart unefficiency, this
            # may cause decoding problem (e.g. when downloading a file)
            self.headers_out.setRawHeaders(header, [str(value)])
        else:
            self.headers_out.setHeader(header, value)

    def add_header(self, header, value):
        """add an output HTTP header"""
        # adding encoded header is important, else page content
        # will be reconverted back to unicode and apart unefficiency, this
        # may cause decoding problem (e.g. when downloading a file)
        self.headers_out.addRawHeader(header, str(value))

    def remove_header(self, header):
        """remove an output HTTP header"""
        self.headers_out.removeHeader(header)

    def _validate_cache(self):
        """raise a `DirectResponse` exception if a cached page along the way
        exists and is still usable
        """
        if self.get_header('Cache-Control') in ('max-age=0', 'no-cache'):
            # Expires header seems to be required by IE7
            self.add_header('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')
            return
        try:
            http.checkPreconditions(self._twreq, _PreResponse(self))
        except http.HTTPError, ex:
            self.info('valid http cache, no actual rendering')
            raise DirectResponse(ex.response)
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
        mx date time value (GMT), else return None
        """
        mtime = self.get_header('If-modified-since', raw=False)
        if mtime:
            # :/ twisted is returned a localized time stamp
            return datetime.fromtimestamp(mtime) + GMTOFFSET
        return None


class _PreResponse(object):
    def __init__(self, request):
        self.headers = request.headers_out
        self.code = 200
