#!/usr/bin/env python
# pylint: disable=W0142,W0403,W0404,W0613,W0622,W0622,W0704,R0904,C0103,E0611
#
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
"""Generic Setup script, takes package info from __pkginfo__.py file
"""

import io
import os
import sys
import shutil
from os.path import dirname, exists, isdir, join

from setuptools import setup
from setuptools.command import develop, install_lib
from distutils.command import install_data

here = dirname(__file__)

# import required features
pkginfo = join(here, 'cubicweb', '__pkginfo__.py')
__pkginfo__ = {}
with open(pkginfo) as f:
    exec(f.read(), __pkginfo__)
modname = __pkginfo__['modname']
version = __pkginfo__['version']
license = __pkginfo__['license']
description = __pkginfo__['description']
web = __pkginfo__['web']
author = __pkginfo__['author']
author_email = __pkginfo__['author_email']

with io.open('README', encoding='utf-8') as f:
    long_description = f.read()

# import optional features
distname = __pkginfo__['distname']
scripts = __pkginfo__['scripts']
include_dirs = __pkginfo__['include_dirs']
data_files = __pkginfo__['data_files']
package_data = __pkginfo__['package_data']

BASE_BLACKLIST = ('CVS', 'dist', 'build', '__buildlog')
IGNORED_EXTENSIONS = ('.pyc', '.pyo', '.elc')


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


def get_packages(directory, prefix):
    """return a list of subpackages for the given directory
    """
    result = []
    for package in os.listdir(directory):
        absfile = join(directory, package)
        if isdir(absfile):
            if exists(join(absfile, '__init__.py')) or \
                   package in ('test', 'tests'):
                if prefix:
                    result.append('%s.%s' % (prefix, package))
                else:
                    result.append(package)
                result += get_packages(absfile, result[-1])
    return result

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
    else:
        if verbose:
            print('created %s directory' % to_dir)
    for dirpath, dirnames, filenames in os.walk(from_dir):
        for norecurs in blacklist:
            try:
                dirnames.remove(norecurs)
            except ValueError:
                pass
            else:
                if verbose:
                    print('not recursing in %s' % join(dirpath, norecurs))
        for dirname in dirnames:
            src = join(dirpath, dirname)
            dest = to_dir + src[len(from_dir):]
            if not exists(dest):
                if verbose:
                    print('creating %s directory' % dest)
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
                print('copying %s to %s' % (src, dest))
            shutil.copy2(src, dest)


class MyInstallLib(install_lib.install_lib):
    """extend install_lib command to handle  package __init__.py and
    include_dirs variable if necessary
    """
    def run(self):
        """overridden from install_lib class"""
        install_lib.install_lib.run(self)
        # create Products.__init__.py if needed
        # manually install included directories if any
        if include_dirs:
            for directory in include_dirs:
                src = join(modname, directory)
                dest = join(self.install_dir, src)
                export(src, dest, verbose=self.verbose)


# re-enable copying data files in sys.prefix
# overwrite install_data to use sys.prefix instead of the egg directory
class MyInstallData(install_data.install_data):
    """A class that manages data files installation"""
    def run(self):
        _old_install_dir = self.install_dir
        if self.install_dir.endswith('egg'):
            self.install_dir = sys.prefix
        install_data.install_data.run(self)
        self.install_dir = _old_install_dir
try:
    import setuptools.command.easy_install # only if easy_install available
    # monkey patch: Crack SandboxViolation verification
    from setuptools.sandbox import DirectorySandbox as DS
    old_ok = DS._ok
    def _ok(self, path):
        """Return True if ``path`` can be written during installation."""
        out = old_ok(self, path) # here for side effect from setuptools
        realpath = os.path.normcase(os.path.realpath(path))
        allowed_path = os.path.normcase(sys.prefix)
        if realpath.startswith(allowed_path):
            out = True
        return out
    DS._ok = _ok
except ImportError:
    pass


setup(
    name=distname,
    version=version,
    license=license,
    url=web,
    description=description,
    long_description=long_description,
    author=author,
    author_email=author_email,
    packages=[modname] + get_packages(join(here, modname), modname),
    package_data=package_data,
    scripts=ensure_scripts(scripts),
    data_files=data_files,
    install_requires=[
        'six >= 1.4.0',
        'logilab-common >= 1.4.0',
        'logilab-mtconverter >= 0.8.0',
        'rql >= 0.34.0',
        'yams >= 0.45.0',
        'lxml',
        'logilab-database >= 1.15.0',
        'passlib >= 1.7.0',
        'pytz',
        'Markdown',
        'unittest2 >= 0.7.0',
    ],
    entry_points={
        'paste.app_factory': [
            'pyramid_main=cubicweb.pyramid:pyramid_app',
        ],
    },
    extras_require={
        'captcha': [
            'Pillow',
        ],
        'crypto': [
            'pycrypto',
        ],
        'etwist': [
            'Twisted < 16.0.0',
        ],
        'ext': [
            'docutils >= 0.6',
        ],
        'ical': [
            'vobject >= 0.6.0',
        ],
        'pyramid': [
            'pyramid >= 1.5.0',
            'waitress >= 0.8.9',
            'wsgicors >= 0.3',
            'pyramid_multiauth',
            'repoze.lru',
        ],
        'rdf': [
            'rdflib',
        ],
        'sparql': [
            'fyzz >= 0.1.0',
        ],
        'zmq': [
            'pyzmq',
        ],
    },
    cmdclass={
        'install_lib': MyInstallLib,
        'install_data': MyInstallData,
    },
    zip_safe=False,
)
