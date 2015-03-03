#!/usr/bin/env python
# pylint: disable=W0142,W0403,W0404,W0613,W0622,W0622,W0704,R0904,C0103,E0611
#
# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of a CubicWeb cube.
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
# You should have received a copy of the GNU Lesser General Public License
# along with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Generic Setup script, takes package info from __pkginfo__.py file
"""
__docformat__ = "restructuredtext en"

import os
import sys
import shutil
from os.path import exists, join, dirname

try:
    if os.environ.get('NO_SETUPTOOLS'):
        raise ImportError()  # do as there is no setuptools
    from setuptools import setup
    from setuptools.command import install_lib
    USE_SETUPTOOLS = True
except ImportError:
    from distutils.core import setup
    from distutils.command import install_lib
    USE_SETUPTOOLS = False
from distutils.command import install_data


# load metadata from the __pkginfo__.py file so there is no risk of conflict
# see https://packaging.python.org/en/latest/single_source_version.html
base_dir = dirname(__file__)
pkginfo = {}
with open(join(base_dir, "__pkginfo__.py")) as f:
    exec(f.read(), pkginfo)

# get required metadatas
modname = pkginfo['modname']
version = pkginfo['version']
license = pkginfo['license']
description = pkginfo['description']
web = pkginfo['web']
author = pkginfo['author']
author_email = pkginfo['author_email']
classifiers = pkginfo['classifiers']

with open(join(base_dir, 'README')) as f:
    long_description = f.read()

# get optional metadatas
distname = pkginfo.get('distname', modname)
scripts = pkginfo.get('scripts', ())
include_dirs = pkginfo.get('include_dirs', ())
data_files = pkginfo.get('data_files', None)
ext_modules = pkginfo.get('ext_modules', None)
dependency_links = pkginfo.get('dependency_links', ())

if USE_SETUPTOOLS:
    requires = {}
    for entry in ("__depends__",):  # "__recommends__"):
        requires.update(pkginfo.get(entry, {}))
    install_requires = [("%s %s" % (d, v and v or "")).strip()
                        for d, v in requires.items()]
else:
    install_requires = []

BASE_BLACKLIST = ('CVS', '.svn', '.hg', '.git', 'debian', 'dist', 'build')
IGNORED_EXTENSIONS = ('.pyc', '.pyo', '.elc', '~')


def ensure_scripts(linux_scripts):
    """
    Creates the proper script names required for each platform
    (taken from 4Suite)
    """
    from distutils import util
    if util.get_platform()[:3] == 'win':
        scripts_ = [script + '.bat' for script in linux_scripts]
    else:
        scripts_ = linux_scripts
    return scripts_


def export(from_dir, to_dir,
           blacklist=BASE_BLACKLIST,
           ignore_ext=IGNORED_EXTENSIONS,
           verbose=True):
    try:
        os.mkdir(to_dir)
    except OSError as ex:
        # file exists ?
        import errno
        if ex.errno != errno.EEXIST:
            raise
    for dirpath, dirnames, filenames in os.walk(from_dir):
        for norecurs in blacklist:
            try:
                dirnames.remove(norecurs)
            except ValueError:
                pass
        for dir_name in dirnames:
            dest = join(to_dir, dir_name)
            if not exists(dest):
                os.mkdir(dest)
        for filename in filenames:
            # don't include binary files
            src = join(dirpath, filename)
            dest = to_dir + src[len(from_dir):]
            if filename[-4:] in ignore_ext:
                continue
            if filename[-1] == '~':
                continue
            if exists(dest):
                os.remove(dest)
            if verbose:
                sys.stderr.write('%s -> %s\n' % (src, dest))
            shutil.copy2(src, dest)


class MyInstallLib(install_lib.install_lib):
    """extend install_lib command to handle  package __init__.py and
    include_dirs variable if necessary
    """
    def run(self):
        """overridden from install_lib class"""
        install_lib.install_lib.run(self)
        # manually install included directories if any
        if include_dirs:
            base = modname
            for directory in include_dirs:
                dest = join(self.install_dir, base, directory)
                export(directory, dest, verbose=False)


# re-enable copying data files in sys.prefix
old_install_data = install_data.install_data
if USE_SETUPTOOLS:
    # overwrite InstallData to use sys.prefix instead of the egg directory
    class MyInstallData(old_install_data):
        """A class that manages data files installation"""
        def run(self):
            _old_install_dir = self.install_dir
            if self.install_dir.endswith('egg'):
                self.install_dir = sys.prefix
            old_install_data.run(self)
            self.install_dir = _old_install_dir
    try:
        # only if easy_install available
        import setuptools.command.easy_install  # noqa
        # monkey patch: Crack SandboxViolation verification
        from setuptools.sandbox import DirectorySandbox as DS
        old_ok = DS._ok

        def _ok(self, path):
            """Return True if ``path`` can be written during installation."""
            out = old_ok(self, path)  # here for side effect from setuptools
            realpath = os.path.normcase(os.path.realpath(path))
            allowed_path = os.path.normcase(sys.prefix)
            if realpath.startswith(allowed_path):
                out = True
            return out
        DS._ok = _ok
    except ImportError:
        pass


def install(**kwargs):
    """setup entry point"""
    if USE_SETUPTOOLS:
        if '--force-manifest' in sys.argv:
            sys.argv.remove('--force-manifest')
    # install-layout option was introduced in 2.5.3-1~exp1
    elif sys.version_info < (2, 5, 4) and '--install-layout=deb' in sys.argv:
        sys.argv.remove('--install-layout=deb')
    cmdclass = {'install_lib': MyInstallLib}
    if USE_SETUPTOOLS:
        kwargs['install_requires'] = install_requires
        kwargs['dependency_links'] = dependency_links
        kwargs['zip_safe'] = False
        cmdclass['install_data'] = MyInstallData

    return setup(name=distname,
                 version=version,
                 license=license,
                 description=description,
                 long_description=long_description,
                 author=author,
                 author_email=author_email,
                 url=web,
                 scripts=ensure_scripts(scripts),
                 data_files=data_files,
                 ext_modules=ext_modules,
                 cmdclass=cmdclass,
                 classifiers=classifiers,
                 **kwargs
                 )


if __name__ == '__main__':
    install()
