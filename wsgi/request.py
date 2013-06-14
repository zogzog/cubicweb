# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""WSGI request adapter for cubicweb

NOTE: each docstring tagged with ``COME FROM DJANGO`` means that
the code has been taken (or adapted) from Djanco source code :
  http://www.djangoproject.com/

"""

__docformat__ = "restructuredtext en"

from StringIO import StringIO
from urllib import quote

from logilab.common.decorators import cached

from cubicweb.web.request import CubicWebRequestBase
from cubicweb.wsgi import (pformat, qs2dict, safe_copyfileobj, parse_file_upload,
                           normalize_header)
from cubicweb.web.http_headers import Headers



class CubicWebWsgiRequest(CubicWebRequestBase):
    """most of this code COMES FROM DJANGO
    """

    def __init__(self, environ, vreg):
        self.environ = environ
        self.path = environ['PATH_INFO']
        self.method = environ['REQUEST_METHOD'].upper()
        self.content = environ['wsgi.input']

        headers_in = dict((normalize_header(k[5:]), v) for k, v in self.environ.items()
                          if k.startswith('HTTP_'))
        https = environ.get("HTTPS") in ('yes', 'on', '1')
        post, files = self.get_posted_data()

        super(CubicWebWsgiRequest, self).__init__(vreg, https, post,
                                                  headers= headers_in)
        if files is not None:
            for key, (name, _, stream) in files.iteritems():
                if name is not None:
                    name = unicode(name, self.encoding)
                self.form[key] = (name, stream)

    def __repr__(self):
        # Since this is called as part of error handling, we need to be very
        # robust against potentially malformed input.
        form = pformat(self.form)
        meta = pformat(self.environ)
        return '<CubicWebWsgiRequest\FORM:%s,\nMETA:%s>' % \
            (form, meta)

    ## cubicweb request interface ################################################

    def http_method(self):
        """returns 'POST', 'GET', 'HEAD', etc."""
        return self.method

    def relative_path(self, includeparams=True):
        """return the normalized path of the request (ie at least relative
        to the instance's root, but some other normalization may be needed
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

    ## wsgi request helpers ###################################################

    def instance_uri(self):
        """Return the instance's base URI (no PATH_INFO or QUERY_STRING)

        see python2.5's wsgiref.util.instance_uri code
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
        # The WSGI spec says 'QUERY_STRING' may be absent.
        post = qs2dict(self.environ.get('QUERY_STRING', ''))
        files = None
        if self.method == 'POST':
            if self.environ.get('CONTENT_TYPE', '').startswith('multipart'):
                header_dict = dict((normalize_header(k[5:]), v)
                                   for k, v in self.environ.items()
                                   if k.startswith('HTTP_'))
                header_dict['Content-Type'] = self.environ.get('CONTENT_TYPE', '')
                post_, files = parse_file_upload(header_dict, self.raw_post_data)
                post.update(post_)
            else:
                post.update(qs2dict(self.raw_post_data))
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
