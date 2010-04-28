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
"""HTTP cache managers


"""
__docformat__ = "restructuredtext en"

from time import mktime
from datetime import datetime

# time delta usable to convert localized time to GMT time
GMTOFFSET = - (datetime.now() - datetime.utcnow())

class NoHTTPCacheManager(object):
    """default cache manager: set no-cache cache control policy"""
    def __init__(self, view):
        self.view = view
        self.req = view._cw
        self.cw_rset = view.cw_rset

    def set_headers(self):
        self.req.set_header('Cache-control', 'no-cache')


class MaxAgeHTTPCacheManager(NoHTTPCacheManager):
    """max-age cache manager: set max-age cache control policy, with max-age
    specified with the `cache_max_age` attribute of the view
    """
    def set_headers(self):
        self.req.set_header('Cache-control',
                            'max-age=%s' % self.view.cache_max_age)


class EtagHTTPCacheManager(NoHTTPCacheManager):
    """etag based cache manager for startup views

    * etag is generated using the view name and the user's groups
    * set policy to 'must-revalidate' and expires to the current time to force
      revalidation on each request
    """

    def etag(self):
        if not self.req.cnx: # session without established connection to the repo
            return self.view.__regid__
        return self.view.__regid__ + '/' + ','.join(sorted(self.req.user.groups))

    def max_age(self):
        # 0 to actually force revalidation
        return 0

    def last_modified(self):
        """return view's last modified GMT time"""
        return self.view.last_modified()

    def set_headers(self):
        req = self.req
        try:
            req.set_header('Etag', '"%s"' % self.etag())
        except NoEtag:
            self.req.set_header('Cache-control', 'no-cache')
            return
        req.set_header('Cache-control',
                       'must-revalidate;max-age=%s' % self.max_age())
        mdate = self.last_modified()
        # use a timestamp, not a formatted raw header, and let
        # the front-end correctly generate it
        # ("%a, %d %b %Y %H:%M:%S GMT" return localized date that
        # twisted don't parse correctly)
        req.set_header('Last-modified', mktime(mdate.timetuple()), raw=False)


class EntityHTTPCacheManager(EtagHTTPCacheManager):
    """etag based cache manager for view displaying a single entity

    * etag is generated using entity's eid, the view name and the user's groups
    * get last modified time from the entity definition (this may not be the
      entity's modification time since a view may include some related entities
      with a modification time to consider) using the `last_modified` method
    """
    def etag(self):
        if self.cw_rset is None or len(self.cw_rset) == 0: # entity startup view for instance
            return super(EntityHTTPCacheManager, self).etag()
        if len(self.cw_rset) > 1:
            raise NoEtag()
        etag = super(EntityHTTPCacheManager, self).etag()
        eid = self.cw_rset[0][0]
        if self.req.user.owns(eid):
            etag += ',owners'
        return str(eid) + '/' + etag


class NoEtag(Exception):
    """an etag can't be generated"""

__all__ = ('GMTOFFSET',
           'NoHTTPCacheManager', 'MaxAgeHTTPCacheManager',
           'EtagHTTPCacheManager', 'EntityHTTPCacheManager')

# monkey patching, so view doesn't depends on this module and we have all
# http cache related logic here

from cubicweb import view as viewmod

def set_http_cache_headers(self):
    self.http_cache_manager(self).set_headers()
viewmod.View.set_http_cache_headers = set_http_cache_headers


def last_modified(self):
    """return the date/time where this view should be considered as
    modified. Take care of possible related objects modifications.

    /!\ must return GMT time /!\
    """
    # XXX check view module's file modification time in dev mod ?
    ctime = datetime.utcnow()
    if self.cache_max_age:
        mtime = self._cw.header_if_modified_since()
        if mtime:
            tdelta = (ctime - mtime)
            if tdelta.days * 24*60*60 + tdelta.seconds <= self.cache_max_age:
                return mtime
    # mtime = ctime will force page rerendering
    return ctime
viewmod.View.last_modified = last_modified


# configure default caching
viewmod.View.http_cache_manager = NoHTTPCacheManager
# max-age=0 to actually force revalidation when needed
viewmod.View.cache_max_age = 0

viewmod.StartupView.http_cache_manager = MaxAgeHTTPCacheManager
viewmod.StartupView.cache_max_age = 60*60*2 # stay in http cache for 2 hours by default
