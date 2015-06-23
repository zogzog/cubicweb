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
"""Set of static resources controllers for :

- /data/...
- /static/...
- /fckeditor/...
"""

import os
import os.path as osp
import hashlib
import mimetypes
import threading
import tempfile
from time import mktime
from datetime import datetime, timedelta
from logging import getLogger

from cubicweb import Forbidden
from cubicweb.web import NotFound
from cubicweb.web.http_headers import generateDateTime
from cubicweb.web.controller import Controller
from cubicweb.web.views.urlrewrite import URLRewriter



class StaticFileController(Controller):
    """an abtract class to serve static file

    Make sure to add your subclass to the STATIC_CONTROLLERS list"""
    __abstract__ = True
    directory_listing_allowed = False

    def max_age(self, path):
        """max cache TTL"""
        return 60*60*24*7

    def static_file(self, path):
        """Return full content of a static file.

        XXX iterable content would be better
        """
        debugmode = self._cw.vreg.config.debugmode
        if osp.isdir(path):
            if self.directory_listing_allowed:
                return u''
            raise Forbidden(path)
        if not osp.isfile(path):
            raise NotFound()
        if not debugmode:
            # XXX: Don't provide additional resource information to error responses
            #
            # the HTTP RFC recommands not going further than 1 year ahead
            expires = datetime.now() + timedelta(days=6*30)
            self._cw.set_header('Expires', generateDateTime(mktime(expires.timetuple())))

        # XXX system call to os.stats could be cached once and for all in
        # production mode (where static files are not expected to change)
        #
        # Note that: we do a osp.isdir + osp.isfile before and a potential
        # os.read after. Improving this specific call will not help
        #
        # Real production environment should use dedicated static file serving.
        self._cw.set_header('last-modified', generateDateTime(os.stat(path).st_mtime))
        if self._cw.is_client_cache_valid():
            return ''
        # XXX elif uri.startswith('/https/'): uri = uri[6:]
        mimetype, encoding = mimetypes.guess_type(path)
        if mimetype is None:
            mimetype = 'application/octet-stream'
        self._cw.set_content_type(mimetype, osp.basename(path), encoding)
        with open(path, 'rb') as resource:
            return resource.read()

    @property
    def relpath(self):
        """path of a requested file relative to the controller"""
        path = self._cw.form.get('static_relative_path')
        if path is None:
            path = self._cw.relative_path(includeparams=True)
        return path


class ConcatFilesHandler(object):
    """Emulating the behavior of modconcat

    this serve multiple file as a single one.
    """

    def __init__(self, config):
        self._resources = {}
        self.config = config
        self.logger = getLogger('cubicweb.web')
        self.lock = threading.Lock()

    def _resource(self, path):
        """get the resouce"""
        try:
            return self._resources[path]
        except KeyError:
            self._resources[path] = self.config.locate_resource(path)
            return self._resources[path]

    def _up_to_date(self, filepath, paths):
        """
        The concat-file is considered up-to-date if it exists.
        In debug mode, an additional check is performed to make sure that
        concat-file is more recent than all concatenated files
        """
        if not osp.isfile(filepath):
            return False
        if self.config.debugmode:
            concat_lastmod = os.stat(filepath).st_mtime
            for path in paths:
                dirpath, rid = self._resource(path)
                if rid is None:
                    raise NotFound(path)
                path = osp.join(dirpath, rid)
                if os.stat(path).st_mtime > concat_lastmod:
                    return False
        return True

    def build_filepath(self, paths):
        """return the filepath that will be used to cache concatenation of `paths`
        """
        _, ext = osp.splitext(paths[0])
        fname = 'cache_concat_' + hashlib.md5(';'.join(paths)).hexdigest() + ext
        return osp.join(self.config.appdatahome, 'uicache', fname)

    def concat_cached_filepath(self, paths):
        filepath = self.build_filepath(paths)
        if not self._up_to_date(filepath, paths):
            with self.lock:
                if self._up_to_date(filepath, paths):
                    # first check could have raced with some other thread
                    # updating the file
                    return filepath
                fd, tmpfile = tempfile.mkstemp(dir=os.path.dirname(filepath))
                try:
                    f = os.fdopen(fd, 'wb')
                    for path in paths:
                        dirpath, rid = self._resource(path)
                        if rid is None:
                            # In production mode log an error, do not return a 404
                            # XXX the erroneous content is cached anyway
                            self.logger.error('concatenated data url error: %r file '
                                              'does not exist', path)
                            if self.config.debugmode:
                                raise NotFound(path)
                        else:
                            with open(osp.join(dirpath, rid), 'rb') as source:
                                for line in source:
                                    f.write(line)
                            f.write('\n')
                    f.close()
                except:
                    os.remove(tmpfile)
                    raise
                else:
                    os.rename(tmpfile, filepath)
        return filepath


class DataController(StaticFileController):
    """Controller in charge of serving static files in /data/

    Handles mod_concat-like URLs.
    """

    __regid__ = 'data'

    def __init__(self, *args, **kwargs):
        super(DataController, self).__init__(*args, **kwargs)
        config = self._cw.vreg.config
        md5_version = config.instance_md5_version()
        self.base_datapath = config.data_relpath()
        self.data_modconcat_basepath = '%s??' % self.base_datapath
        self.concat_files_registry = ConcatFilesHandler(config)

    def publish(self, rset=None):
        config = self._cw.vreg.config
        # includeparams=True for modconcat-like urls
        relpath = self.relpath
        if relpath.startswith(self.data_modconcat_basepath):
            paths = relpath[len(self.data_modconcat_basepath):].split(',')
            filepath = self.concat_files_registry.concat_cached_filepath(paths)
        else:
            # skip leading '/data/' and url params
            if relpath.startswith(self.base_datapath):
                prefix = self.base_datapath
            else:
                prefix = 'data/'
            relpath = relpath[len(prefix):]
            relpath = relpath.split('?', 1)[0]
            dirpath, rid = config.locate_resource(relpath)
            if dirpath is None:
                raise NotFound()
            filepath = osp.join(dirpath, rid)
        return self.static_file(filepath)


class FCKEditorController(StaticFileController):
    """Controller in charge of serving FCKEditor related file

    The motivational for a dedicated controller have been lost.
    """

    __regid__ = 'fckeditor'

    def publish(self, rset=None):
        config = self._cw.vreg.config
        if self._cw.https:
            uiprops = config.https_uiprops
        else:
            uiprops = config.uiprops
        relpath = self.relpath
        if relpath.startswith('fckeditor/'):
            relpath = relpath[len('fckeditor/'):]
        relpath = relpath.split('?', 1)[0]
        return self.static_file(osp.join(uiprops['FCKEDITOR_PATH'], relpath))


class StaticDirectoryController(StaticFileController):
    """Controller in charge of serving static file in /static/
    """
    __regid__ = 'static'

    def publish(self, rset=None):
        staticdir = self._cw.vreg.config.static_directory
        relpath = self.relpath[len(self.__regid__) + 1:]
        return self.static_file(osp.join(staticdir, relpath))

STATIC_CONTROLLERS = [DataController, FCKEditorController,
                      StaticDirectoryController]

class StaticControlerRewriter(URLRewriter):
    """a quick and dirty rewritter in charge of server static file.

    This is a work around the flatness of url handling in cubicweb."""

    __regid__ = 'static'

    priority = 10

    def rewrite(self, req, uri):
        for ctrl in STATIC_CONTROLLERS:
            if uri.startswith('/%s/' % ctrl.__regid__):
                break
        else:
            self.debug("not a static file uri: %s", uri)
            raise KeyError(uri)
        relpath = self._cw.relative_path(includeparams=False)
        self._cw.form['static_relative_path'] = self._cw.relative_path(includeparams=True)
        return ctrl.__regid__, None
