# copyright 2010-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""property sheets allowing configuration of the web ui"""



import errno
import re
import os
import os.path as osp
import tempfile


TYPE_CHECKS = [('STYLESHEETS', list), ('JAVASCRIPTS', list),
               ('STYLESHEETS_IE', list), ('STYLESHEETS_PRINT', list),
               ]


class lazystr(object):
    def __init__(self, string, context):
        self.string = string
        self.context = context

    def __str__(self):
        return self.string % self.context


class PropertySheet(dict):
    def __init__(self, cache_directory, **context):
        self._cache_directory = cache_directory
        self.context = context
        self.reset()
        context['sheet'] = self
        context['lazystr'] = self.lazystr
        self._percent_rgx = re.compile(r'%(?!\()')

    def lazystr(self, str):
        return lazystr(str, self)

    def reset(self):
        self.clear()
        self._ordered_propfiles = []
        self._propfile_mtime = {}

    def load(self, fpath):
        scriptglobals = self.context.copy()
        scriptglobals['__file__'] = fpath
        with open(fpath, 'rb') as fobj:
            code = compile(fobj.read(), fpath, 'exec')
        exec(code, scriptglobals, self)
        for name, type in TYPE_CHECKS:
            if name in self:
                if not isinstance(self[name], type):
                    msg = "Configuration error: %s.%s should be a %s" % (fpath, name, type)
                    raise Exception(msg)
        self._propfile_mtime[fpath] = os.stat(fpath).st_mtime
        self._ordered_propfiles.append(fpath)

    def need_reload(self):
        for fpath, mtime in self._propfile_mtime.items():
            if os.stat(fpath).st_mtime > mtime:
                return True
        return False

    def reload(self):
        ordered_files = self._ordered_propfiles
        self.reset()
        for fpath in ordered_files:
            self.load(fpath)

    def reload_if_needed(self):
        if self.need_reload():
            self.reload()

    def process_resource(self, rdirectory, rid):
        cachefile = osp.join(self._cache_directory, rid)
        self.debug('processing %s/%s into %s',
                   rdirectory, rid, cachefile)
        rcachedir = osp.dirname(cachefile)
        if not osp.exists(rcachedir):
            os.makedirs(rcachedir)
        sourcefile = osp.join(rdirectory, rid)
        with open(sourcefile) as f:
            content = f.read()
        # XXX replace % not followed by a paren by %% to avoid having to do
        # this in the source css file ?
        try:
            content = self.compile(content)
        except ValueError as ex:
            self.error("can't process %s/%s: %s", rdirectory, rid, ex)
            adirectory = rdirectory
        else:
            tmpfd, tmpfile = tempfile.mkstemp(dir=rcachedir, prefix=osp.basename(cachefile))
            with os.fdopen(tmpfd, 'w') as stream:
                stream.write(content)
            try:
                mode = os.stat(sourcefile).st_mode
                os.chmod(tmpfile, mode)
            except IOError:
                self.warning('Cannot set access mode for %s; you may encouter '
                             'file permissions issues', cachefile)
            try:
                os.rename(tmpfile, cachefile)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise
                # Under windows, os.rename won't overwrite an existing file
                os.unlink(cachefile)
                os.rename(tmpfile, cachefile)
            adirectory = self._cache_directory
        return adirectory

    def compile(self, content):
        return self._percent_rgx.sub('%%', content) % self

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

from cubicweb.web import LOGGER
from logilab.common.logging_ext import set_log_methods
set_log_methods(PropertySheet, LOGGER)
