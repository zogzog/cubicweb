# copyright 2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

__docformat__ = "restructuredtext en"

import re
import os
import os.path as osp

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
        self._percent_rgx = re.compile('%(?!\()')

    def lazystr(self, str):
        return lazystr(str, self)

    def reset(self):
        self.clear()
        self._ordered_propfiles = []
        self._propfile_mtime = {}
        self._sourcefile_mtime = {}
        self._cache = {}

    def load(self, fpath):
        scriptglobals = self.context.copy()
        scriptglobals['__file__'] = fpath
        execfile(fpath, scriptglobals, self)
        for name, type in TYPE_CHECKS:
            if name in self:
                if not isinstance(self[name], type):
                    msg = "Configuration error: %s.%s should be a %s" % (fpath, name, type)
                    raise Exception(msg)
        self._propfile_mtime[fpath] = os.stat(fpath)[-2]
        self._ordered_propfiles.append(fpath)

    def need_reload(self):
        for rid, (adirectory, rdirectory, mtime) in self._cache.items():
            if os.stat(osp.join(rdirectory, rid))[-2] > mtime:
                del self._cache[rid]
        for fpath, mtime in self._propfile_mtime.iteritems():
            if os.stat(fpath)[-2] > mtime:
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
        try:
            return self._cache[rid][0]
        except KeyError:
            cachefile = osp.join(self._cache_directory, rid)
            self.debug('caching processed %s/%s into %s',
                       rdirectory, rid, cachefile)
            rcachedir = osp.dirname(cachefile)
            if not osp.exists(rcachedir):
                os.makedirs(rcachedir)
            sourcefile = osp.join(rdirectory, rid)
            content = file(sourcefile).read()
            # XXX replace % not followed by a paren by %% to avoid having to do
            # this in the source css file ?
            try:
                content = self.compile(content)
            except ValueError as ex:
                self.error("can't process %s/%s: %s", rdirectory, rid, ex)
                adirectory = rdirectory
            else:
                stream = file(cachefile, 'w')
                stream.write(content)
                stream.close()
                adirectory = self._cache_directory
            self._cache[rid] = (adirectory, rdirectory, os.stat(sourcefile)[-2])
            return adirectory

    def compile(self, content):
        return self._percent_rgx.sub('%%', content) % self

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

from cubicweb.web import LOGGER
from logilab.common.logging_ext import set_log_methods
set_log_methods(PropertySheet, LOGGER)
