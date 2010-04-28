#!/usr/bin/env python
# pylint: disable-msg=W0404,W0622,W0704,W0613,W0152
# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr

__docformat__ = "restructuredtext en"

import os
import sys
import shutil
from os.path import isdir, exists, join, walk

try:
    if os.environ.get('NO_SETUPTOOLS'):
        raise ImportError()
    from setuptools import setup
    from setuptools.command import install_lib
    USE_SETUPTOOLS = 1
except ImportError:
    from distutils.core import setup
    from distutils.command import install_lib
    USE_SETUPTOOLS = 0


sys.modules.pop('__pkginfo__', None)
# import required features
from __pkginfo__ import modname, version, license, description, \
     web, author, author_email
# import optional features
import __pkginfo__
distname = getattr(__pkginfo__, 'distname', modname)
scripts = getattr(__pkginfo__, 'scripts', [])
data_files = getattr(__pkginfo__, 'data_files', None)
include_dirs = getattr(__pkginfo__, 'include_dirs', [])
ext_modules = getattr(__pkginfo__, 'ext_modules', None)
dependency_links = getattr(__pkginfo__, 'dependency_links', [])

STD_BLACKLIST = ('CVS', '.svn', '.hg', 'debian', 'dist', 'build')

IGNORED_EXTENSIONS = ('.pyc', '.pyo', '.elc', '~')

if exists('README'):
    long_description = file('README').read()
else:
    long_description = ''
if USE_SETUPTOOLS:
   requires = {}
   for entry in ("__depends__", "__recommends__"):
      requires.update(getattr(__pkginfo__, entry, {}))
   install_requires = [("%s %s" % (d, v and v or "")).strip()
                       for d, v in requires.iteritems()]
else:
   install_requires = []


def ensure_scripts(linux_scripts):
    """Creates the proper script names required for each platform
    (taken from 4Suite)
    """
    from distutils import util
    if util.get_platform()[:3] == 'win':
        scripts_ = [script + '.bat' for script in linux_scripts]
    else:
        scripts_ = linux_scripts
    return scripts_

def get_packages(directory, prefix):
    """return a list of subpackages for the given directory"""
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
           blacklist=STD_BLACKLIST,
           ignore_ext=IGNORED_EXTENSIONS,
           verbose=True):
    """make a mirror of from_dir in to_dir, omitting directories and files
    listed in the black list
    """
    def make_mirror(arg, directory, fnames):
        """walk handler"""
        for norecurs in blacklist:
            try:
                fnames.remove(norecurs)
            except ValueError:
                pass
        for filename in fnames:
            # don't include binary files
            if filename[-4:] in ignore_ext:
                continue
            if filename[-1] == '~':
                continue
            src = join(directory, filename)
            dest = to_dir + src[len(from_dir):]
            if verbose:
                print >> sys.stderr, src, '->', dest
            if os.path.isdir(src):
                if not exists(dest):
                    os.mkdir(dest)
            else:
                if exists(dest):
                    os.remove(dest)
                shutil.copy2(src, dest)
    try:
        os.mkdir(to_dir)
    except OSError, ex:
        # file exists ?
        import errno
        if ex.errno != errno.EEXIST:
            raise
    walk(from_dir, make_mirror, None)


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

def install(**kwargs):
    """setup entry point"""
    if USE_SETUPTOOLS:
        if '--force-manifest' in sys.argv:
            sys.argv.remove('--force-manifest')
    # install-layout option was introduced in 2.5.3-1~exp1
    elif sys.version_info < (2, 5, 4) and '--install-layout=deb' in sys.argv:
        sys.argv.remove('--install-layout=deb')
    kwargs['package_dir'] = {modname : '.'}
    packages = [modname] + get_packages(os.getcwd(), modname)
    if USE_SETUPTOOLS and install_requires:
        kwargs['install_requires'] = install_requires
        kwargs['dependency_links'] = dependency_links
    kwargs['packages'] = packages
    return setup(name = distname,
                 version = version,
                 license = license,
                 description = description,
                 long_description = long_description,
                 author = author,
                 author_email = author_email,
                 url = web,
                 scripts = ensure_scripts(scripts),
                 data_files = data_files,
                 ext_modules = ext_modules,
                 cmdclass = {'install_lib': MyInstallLib},
                 **kwargs
                 )

if __name__ == '__main__' :
    install()
