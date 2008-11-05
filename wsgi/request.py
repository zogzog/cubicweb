"""WSGI request adapter for cubicweb

NOTE: each docstring tagged with ``COME FROM DJANGO`` means that
the code has been taken (or adapted) from Djanco source code :
  http://www.djangoproject.com/

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

__docformat__ = "restructuredtext en"

from StringIO import StringIO
from urllib import quote

from logilab.common.decorators import cached

from cubicweb.web.request import CubicWebRequestBase
from cubicweb.wsgi import (pformat, qs2dict, safe_copyfileobj, parse_file_upload,
                        normalize_header)



class CubicWebWsgiRequest(CubicWebRequestBase):
    """most of this code COMES FROM DJANO
    """
    
    def __init__(self, environ, vreg, base_url=None):
        self.environ = environ
        self.path = environ['PATH_INFO']
        self.method = environ['REQUEST_METHOD'].upper()
        self._headers = dict([(normalize_header(k[5:]), v) for k, v in self.environ.items()
                              if k.startswith('HTTP_')])
        https = environ.get("HTTPS") in ('yes', 'on', '1')
        self._base_url = base_url or self.application_uri()
        post, files = self.get_posted_data()
        super(CubicWebWsgiRequest, self).__init__(vreg, https, post)
        if files is not None:
            for fdef in files.itervalues():
                fdef[0] = unicode(fdef[0], self.encoding)
            self.form.update(files)
        # prepare output headers
        self.headers_out = {}
        
    def __repr__(self):
        # Since this is called as part of error handling, we need to be very
        # robust against potentially malformed input.
        form = pformat(self.form)
        meta = pformat(self.environ)
        return '<CubicWebWsgiRequest\FORM:%s,\nMETA:%s>' % \
            (form, meta)

    ## cubicweb request interface ################################################
    
    def base_url(self):
        return self._base_url

    def http_method(self):
        """returns 'POST', 'GET', 'HEAD', etc."""
        return self.method
    
    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the application's root, but some other normalization may be needed
        so that the returned path may be used to compare to generated urls

        :param includeparams:
           boolean indicating if GET form parameters should be kept in the path
        """
        path = self.environ['PATH_INFO']
        path = path[1:] # remove leading '/'
        if includeparams:
            qs = self.environ.get('QUERY_STRING')
            if qs:
                return '%s?%s' % (path, qs)
        
        return path

    def get_header(self, header, default=None):
        """return the value associated with the given input HTTP header,
        raise KeyError if the header is not set
        """
        return self._headers.get(normalize_header(header), default)
    
    def set_header(self, header, value, raw=True):
        """set an output HTTP header"""
        assert raw, "don't know anything about non-raw headers for wsgi requests"
        self.headers_out[header] = value

    def add_header(self, header, value):
        """add an output HTTP header"""
        self.headers_out[header] = value
    
    def remove_header(self, header):
        """remove an output HTTP header"""
        self.headers_out.pop(header, None)

    def header_if_modified_since(self):
        """If the HTTP header If-modified-since is set, return the equivalent
        mx date time value (GMT), else return None
        """
        return None
        
    ## wsgi request helpers ###################################################
    
    def application_uri(self):
        """Return the application's base URI (no PATH_INFO or QUERY_STRING)

        see python2.5's wsgiref.util.application_uri code
        """
        environ = self.environ
        url = environ['wsgi.url_scheme'] + '://'
        if environ.get('HTTP_HOST'):
            url += environ['HTTP_HOST']
        else:
            url += environ['SERVER_NAME']
            if environ['wsgi.url_scheme'] == 'https':
                if environ['SERVER_PORT'] != '443':
                    url += ':' + environ['SERVER_PORT']
            else:
                if environ['SERVER_PORT'] != '80':
                    url += ':' + environ['SERVER_PORT']
        url += quote(environ.get('SCRIPT_NAME') or '/')
        return url
        
    def get_full_path(self):
        return '%s%s' % (self.path, self.environ.get('QUERY_STRING', '') and ('?' + self.environ.get('QUERY_STRING', '')) or '')

    def is_secure(self):
        return 'wsgi.url_scheme' in self.environ \
            and self.environ['wsgi.url_scheme'] == 'https'

    def get_posted_data(self):
        files = None
        if self.method == 'POST':
            if self.environ.get('CONTENT_TYPE', '').startswith('multipart'):
                header_dict = dict((normalize_header(k[5:]), v)
                                   for k, v in self.environ.items()
                                   if k.startswith('HTTP_'))
                header_dict['Content-Type'] = self.environ.get('CONTENT_TYPE', '')
                post, files = parse_file_upload(header_dict, self.raw_post_data)
            else:
                post = qs2dict(self.raw_post_data)
        else:
            # The WSGI spec says 'QUERY_STRING' may be absent.
            post = qs2dict(self.environ.get('QUERY_STRING', ''))
        return post, files

    @property
    @cached
    def raw_post_data(self):
        buf = StringIO()
        try:
            # CONTENT_LENGTH might be absent if POST doesn't have content at all (lighttpd)
            content_length = int(self.environ.get('CONTENT_LENGTH', 0))
        except ValueError: # if CONTENT_LENGTH was empty string or not an integer
            content_length = 0
        if content_length > 0:
            safe_copyfileobj(self.environ['wsgi.input'], buf,
                    size=content_length)
        postdata = buf.getvalue()
        buf.close()
        return postdata

    def _validate_cache(self):
        """raise a `DirectResponse` exception if a cached page along the way
        exists and is still usable
        """
        # XXX
#         if self.get_header('Cache-Control') in ('max-age=0', 'no-cache'):
#             # Expires header seems to be required by IE7
#             self.add_header('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')
#             return
#         try:
#             http.checkPreconditions(self._twreq, _PreResponse(self))
#         except http.HTTPError, ex:
#             self.info('valid http cache, no actual rendering')
#             raise DirectResponse(ex.response)
        # Expires header seems to be required by IE7
        self.add_header('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')
