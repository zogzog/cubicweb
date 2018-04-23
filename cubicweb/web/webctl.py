# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb-ctl commands and command handlers common to twisted/modpython
web configuration
"""
from __future__ import print_function

import os
import os.path as osp
from shutil import copy, rmtree

from logilab.common.shellutils import ASK

from cubicweb import ExecutionError
from cubicweb.cwctl import CWCTL
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from cubicweb.toolsutils import Command, CommandHandler, underline_title
from cubicweb.web.webconfig import _DATA_DIR


try:
    from os import symlink as linkdir
except ImportError:
    from shutil import copytree as linkdir


def rmtreecontent(dst):
    """Delete the content of the dst directory (but NOT the directory
       itself)"""
    for fname in os.listdir(dst):
        fpath = osp.join(dst, fname)
        if osp.isfile(fpath) or osp.islink(fpath):
            os.unlink(fpath)
        else:
            rmtree(fpath)


class WebCreateHandler(CommandHandler):
    cmdname = 'create'

    def bootstrap(self, cubes, automatic=False, inputlevel=0):
        """bootstrap this configuration"""
        if not automatic:
            print('\n' + underline_title('Generic web configuration'))
            config = self.config
            config.input_config('web', inputlevel)
            if ASK.confirm('Allow anonymous access ?', False):
                config.global_set_option('anonymous-user', 'anon')
                config.global_set_option('anonymous-password', 'anon')

    def postcreate(self, *args, **kwargs):
        """hooks called once instance's initialization has been completed"""


class GenStaticDataDirMixIn(object):
    """Create a directory merging all data directory content from cubes and CW.
    """
    def generate_static_dir(self, config, dest=None, ask_clean=False, repo=None):
        if not dest:
            dest = config['staticdir-path']
        if not dest:
            dest = osp.join(config.appdatahome, 'data')
        if osp.exists(dest):
            if (config.verbosity
                    and (not ask_clean
                         or not (config.verbosity
                                 and ASK.confirm('Remove existing data directory %s?' % dest)))):
                raise ExecutionError('Directory %s already exists. '
                                     'Remove it first.' % dest)
            rmtreecontent(dest)
        config.quick_start = True  # notify this is not a regular start
        # list all resources (no matter their order)
        resources = set()
        for datadir in self._datadirs(config, repo=repo):
            for dirpath, dirnames, filenames in os.walk(datadir):
                rel_dirpath = dirpath[len(datadir) + 1:]
                resources.update(osp.join(rel_dirpath, f) for f in filenames)

        # locate resources and copy them to destination
        for resource in resources:
            dest_resource = osp.join(dest, resource)
            dirname = osp.dirname(dest_resource)
            if not osp.isdir(dirname):
                os.makedirs(dirname)
            resource_dir, resource_path = config.locate_resource(resource)
            copy(osp.join(resource_dir, resource_path), dest_resource)
        # handle md5 version subdirectory
        linkdir(dest, osp.join(dest, config.instance_md5_version()))
        # ensure generated files are owned by configured uid
        config.ensure_uid_directory(dest)
        print('You can use apache rewrite rule below :\n'
              'RewriteRule ^/data/(.*) %s/$1 [L]' % dest)

    def _datadirs(self, config, repo=None):
        if repo is None:
            repo = config.repository()
        if config._cubes is None:
            # web only config
            config.init_cubes(repo.get_cubes())
        for cube in repo.get_cubes():
            cube_datadir = osp.join(cwcfg.cube_dir(cube), 'data')
            if osp.isdir(cube_datadir):
                yield cube_datadir
        yield _DATA_DIR


class WebUpgradeHandler(CommandHandler, GenStaticDataDirMixIn):
    cmdname = 'upgrade'

    def postupgrade(self, repo):
        config = self.config
        if not config['generate-staticdir']:
            return
        self.generate_static_dir(config, ask_clean=True, repo=repo)


class GenStaticDataDir(Command, GenStaticDataDirMixIn):
    """Create a directory merging all data directory content from cubes and CW.
    """
    name = 'gen-static-datadir'
    arguments = '<instance> [dirpath]'
    min_args = 1
    max_args = 2

    options = ()

    def run(self, args):
        appid = args.pop(0)
        config = cwcfg.config_for(appid)
        dest = None
        if args:
            dest = args[0]
        self.generate_static_dir(config, dest)


CWCTL.register(GenStaticDataDir)
