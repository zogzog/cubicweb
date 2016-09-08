# -*- coding: utf-8 -*-
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
"""
.. _ResourceMode:

Resource mode
-------------

Standard resource mode
``````````````````````

A resource *mode* is a predefined set of settings for various resources
directories, such as cubes, instances, etc. to ease development with the
framework. There are two running modes with *CubicWeb*:

* **system**: resources are searched / created in the system directories (eg
  usually requiring root access):

  - instances are stored in :file:`<INSTALL_PREFIX>/etc/cubicweb.d`
  - temporary files (such as pid file) in :file:`<INSTALL_PREFIX>/var/run/cubicweb`

  where `<INSTALL_PREFIX>` is the detected installation prefix ('/usr/local' for
  instance).

* **user**: resources are searched / created in the user home directory:

  - instances are stored in :file:`~/etc/cubicweb.d`
  - temporary files (such as pid file) in :file:`/tmp`


.. _CubicwebWithinVirtualEnv:

Within virtual environment
``````````````````````````

If you are not administrator of you machine or if you need to play with some
specific version of |cubicweb| you can use virtualenv_ a tool to create
isolated Python environments.

- instances are stored in :file:`<VIRTUAL_ENV>/etc/cubicweb.d`
- temporary files (such as pid file) in :file:`<VIRTUAL_ENV>/var/run/cubicweb`

.. _virtualenv: http://pypi.python.org/pypi/virtualenv


Custom resource location
````````````````````````

Notice that each resource path may be explicitly set using an environment
variable if the default doesn't suit your needs. Here are the default resource
directories that are affected according to mode:

* **system**: ::

        CW_INSTANCES_DIR = <INSTALL_PREFIX>/etc/cubicweb.d/
        CW_INSTANCES_DATA_DIR = <INSTALL_PREFIX>/var/lib/cubicweb/instances/
        CW_RUNTIME_DIR = <INSTALL_PREFIX>/var/run/cubicweb/

* **user**: ::

        CW_INSTANCES_DIR = ~/etc/cubicweb.d/
        CW_INSTANCES_DATA_DIR = ~/etc/cubicweb.d/
        CW_RUNTIME_DIR = /tmp

Cubes search path is also affected, see the :ref:`Cube` section.


Setting Cubicweb Mode
`````````````````````

By default, the mode is set to 'system' for standard installation. The mode is
set to 'user' if `cubicweb is used from a mercurial repository`_. You can force
this by setting the :envvar:`CW_MODE` environment variable to either 'user' or
'system' so you can easily:

* use system wide installation but user specific instances and all, without root
  privileges on the system (`export CW_MODE=user`)

* use local checkout of cubicweb on system wide instances (requires root
  privileges on the system (`export CW_MODE=system`)

If you've a doubt about the mode you're currently running, check the first line
outputed by the :command:`cubicweb-ctl list` command.

.. _`cubicweb is used from a mercurial repository`: CubicwebDevelopmentMod_


.. _CubicwebDevelopmentMod:

Development Mode (source)
`````````````````````````

If :file:`.hg` directory is found into the cubicweb package, there are
specific resource rules.

`<CW_SOFTWARE_ROOT>` is the source checkout's ``cubicweb`` directory:

* main cubes directory is `<CW_SOFTWARE_ROOT>/../../cubes`. You can specify
  another one with :envvar:`CW_INSTANCES_DIR` environment variable or simply
  add some other directories by using :envvar:`CW_CUBES_PATH`

* cubicweb migration files are searched in `<CW_SOFTWARE_ROOT>/misc/migration`
  instead of `<INSTALL_PREFIX>/share/cubicweb/migration/`.


Development Mode (virtualenv)
`````````````````````````````

If a virtualenv is found to be activated (i.e. a VIRTUAL_ENV variable is found
in environment), the virtualenv root is used as `<INSTALL_PREFIX>`. This, in
particular, makes it possible to work in `setuptools development mode`_
(``python setup.py develop``) without any further configuration.

.. _`setuptools development mode`: https://pythonhosted.org/setuptools/setuptools.html#development-mode

.. _ConfigurationEnv:

Environment configuration
-------------------------

Python
``````

If you installed *CubicWeb* by cloning the Mercurial shell repository or from source
distribution, then you will need to update the environment variable PYTHONPATH by
adding the path to `cubicweb`:

Add the following lines to either :file:`.bashrc` or :file:`.bash_profile` to
configure your development environment ::

    export PYTHONPATH=/full/path/to/grshell-cubicweb

If you installed *CubicWeb* with packages, no configuration is required and your
new cubes will be placed in `/usr/share/cubicweb/cubes` and your instances will
be placed in `/etc/cubicweb.d`.


CubicWeb
````````

Here are all environment variables that may be used to configure *CubicWeb*:

.. envvar:: CW_MODE

   Resource mode: user or system, as explained in :ref:`ResourceMode`.

.. envvar:: CW_CUBES_PATH

   Augments the default search path for cubes. You may specify several
   directories using ':' as separator (';' under windows environment).

.. envvar:: CW_INSTANCES_DIR

   Directory where cubicweb instances will be found.

.. envvar:: CW_INSTANCES_DATA_DIR

   Directory where cubicweb instances data will be written (backup file...)

.. envvar:: CW_RUNTIME_DIR

   Directory where pid files will be written
"""
from __future__ import print_function

__docformat__ = "restructuredtext en"

import sys
import os
import stat
import logging
import logging.config
from smtplib import SMTP
from threading import Lock
from os.path import (exists, join, expanduser, abspath, normpath,
                     basename, isdir, dirname, splitext)
from warnings import warn, filterwarnings

from six import text_type

from logilab.common.decorators import cached, classproperty
from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods, init_log
from logilab.common.configuration import (Configuration, Method,
                                          ConfigurationMixIn, merge_options)

from cubicweb import (CW_SOFTWARE_ROOT, CW_MIGRATION_MAP,
                      ConfigurationError, Binary, _)
from cubicweb.toolsutils import create_dir

CONFIGURATIONS = []

SMTP_LOCK = Lock()


def configuration_cls(name):
    """return the configuration class registered with the given name"""
    try:
        return [c for c in CONFIGURATIONS if c.name == name][0]
    except IndexError:
        raise ConfigurationError('no such config %r (check it exists with "cubicweb-ctl list")' % name)

def possible_configurations(directory):
    """return a list of installed configurations in a directory
    according to \*-ctl files
    """
    return [name for name in ('repository', 'all-in-one')
            if exists(join(directory, '%s.conf' % name))]

def guess_configuration(directory):
    """try to guess the configuration to use for a directory. If multiple
    configurations are found, ConfigurationError is raised
    """
    modes = possible_configurations(directory)
    if len(modes) != 1:
        raise ConfigurationError('unable to guess configuration from %r %s'
                                 % (directory, modes))
    return modes[0]

def _find_prefix(start_path=None):
    """Return the prefix path of CubicWeb installation.

    Walk parent directories of `start_path` looking for one containing a
    'share/cubicweb' directory. The first matching directory is assumed as the
    prefix installation of CubicWeb.

    If run from within a virtualenv, the virtualenv root is used as
    `start_path`. Otherwise, `start_path` defaults to cubicweb package
    directory path.
    """
    if start_path is None:
        try:
            prefix = os.environ['VIRTUAL_ENV']
        except KeyError:
            prefix = CW_SOFTWARE_ROOT
    else:
        prefix = start_path
    if not isdir(prefix):
        prefix = dirname(prefix)
    old_prefix = None
    while (not isdir(join(prefix, 'share', 'cubicweb'))
           or prefix.endswith('.egg')):
        if prefix == old_prefix:
            return sys.prefix
        old_prefix = prefix
        prefix = dirname(prefix)
    return prefix

# persistent options definition
PERSISTENT_OPTIONS = (
    ('encoding',
     {'type' : 'string',
      'default': 'UTF-8',
      'help': _('user interface encoding'),
      'group': 'ui', 'sitewide': True,
      }),
    ('language',
     {'type' : 'string',
      'default': 'en',
      'vocabulary': Method('available_languages'),
      'help': _('language of the user interface'),
      'group': 'ui',
      }),
    ('date-format',
     {'type' : 'string',
      'default': '%Y/%m/%d',
      'help': _('how to format date in the ui (see <a href="http://docs.python.org/library/datetime.html#strftime-strptime-behavior">this page</a> for format description)'),
      'group': 'ui',
      }),
    ('datetime-format',
     {'type' : 'string',
      'default': '%Y/%m/%d %H:%M',
      'help': _('how to format date and time in the ui (see <a href="http://docs.python.org/library/datetime.html#strftime-strptime-behavior">this page</a> for format description)'),
      'group': 'ui',
      }),
    ('time-format',
     {'type' : 'string',
      'default': '%H:%M',
      'help': _('how to format time in the ui (see <a href="http://docs.python.org/library/datetime.html#strftime-strptime-behavior">this page</a> for format description)'),
      'group': 'ui',
      }),
    ('float-format',
     {'type' : 'string',
      'default': '%.3f',
      'help': _('how to format float numbers in the ui'),
      'group': 'ui',
      }),
    ('default-text-format',
     {'type' : 'choice',
      'choices': ('text/plain', 'text/rest', 'text/html', 'text/markdown'),
      'default': 'text/plain',
      'help': _('default text format for rich text fields.'),
      'group': 'ui',
      }),
    ('short-line-size',
     {'type' : 'int',
      'default': 80,
      'help': _('maximum number of characters in short description'),
      'group': 'navigation',
      }),
    )

def register_persistent_options(options):
    global PERSISTENT_OPTIONS
    PERSISTENT_OPTIONS = merge_options(PERSISTENT_OPTIONS + options)

CFGTYPE2ETYPE_MAP = {
    'string': 'String',
    'choice': 'String',
    'yn':     'Boolean',
    'int':    'Int',
    'float' : 'Float',
    }

_forced_mode = os.environ.get('CW_MODE')
assert _forced_mode in (None, 'system', 'user')

# CWDEV tells whether directories such as i18n/, web/data/, etc. (ie containing
# some other resources than python libraries) are located with the python code
# or as a 'shared' cube
CWDEV = exists(join(CW_SOFTWARE_ROOT, 'i18n'))

try:
    _INSTALL_PREFIX = os.environ['CW_INSTALL_PREFIX']
except KeyError:
    _INSTALL_PREFIX = _find_prefix()
_USR_INSTALL = _INSTALL_PREFIX == '/usr'

class CubicWebNoAppConfiguration(ConfigurationMixIn):
    """base class for cubicweb configuration without a specific instance directory
    """
    # to set in concrete configuration
    name = None
    # log messages format (see logging module documentation for available keys)
    log_format = '%(asctime)s - (%(name)s) %(levelname)s: %(message)s'
    # the format below can be useful to debug multi thread issues:
    # log_format = '%(asctime)s - [%(threadName)s] (%(name)s) %(levelname)s: %(message)s'
    # nor remove appobjects based on unused interface [???]
    cleanup_unused_appobjects = True

    quick_start = False

    if 'VIRTUAL_ENV' in os.environ:
        mode = _forced_mode or 'user'
        _CUBES_DIR = join(_INSTALL_PREFIX, 'share', 'cubicweb', 'cubes')
    elif CWDEV and _forced_mode != 'system':
        mode = 'user'
        _CUBES_DIR = join(CW_SOFTWARE_ROOT, '../../cubes')
    else:
        mode = _forced_mode or 'system'
        _CUBES_DIR = join(_INSTALL_PREFIX, 'share', 'cubicweb', 'cubes')

    CUBES_DIR = abspath(os.environ.get('CW_CUBES_DIR', _CUBES_DIR))
    CUBES_PATH = os.environ.get('CW_CUBES_PATH', '').split(os.pathsep)

    options = (
       ('log-threshold',
         {'type' : 'string', # XXX use a dedicated type?
          'default': 'WARNING',
          'help': 'server\'s log level',
          'group': 'main', 'level': 1,
          }),
        ('umask',
         {'type' : 'int',
          'default': 0o077,
          'help': 'permission umask for files created by the server',
          'group': 'main', 'level': 2,
          }),
        # common configuration options which are potentially required as soon as
        # you're using "base" application objects (ie to really server/web
        # specific)
        ('base-url',
         {'type' : 'string',
          'default': None,
          'help': 'web server root url',
          'group': 'main', 'level': 1,
          }),
        ('allow-email-login',
         {'type' : 'yn',
          'default': False,
          'help': 'allow users to login with their primary email if set',
          'group': 'main', 'level': 2,
          }),
        ('mangle-emails',
         {'type' : 'yn',
          'default': False,
          'help': "don't display actual email addresses but mangle them if \
this option is set to yes",
          'group': 'email', 'level': 3,
          }),
        )
    # static and class methods used to get instance independant resources ##
    @staticmethod
    def cubicweb_version():
        """return installed cubicweb version"""
        from logilab.common.changelog import Version
        from cubicweb import __pkginfo__
        version = __pkginfo__.numversion
        assert len(version) == 3, version
        return Version(version)

    @staticmethod
    def persistent_options_configuration():
        return Configuration(options=PERSISTENT_OPTIONS)

    @classmethod
    def shared_dir(cls):
        """return the shared data directory (i.e. directory where standard
        library views and data may be found)
        """
        if CWDEV:
            return join(CW_SOFTWARE_ROOT, 'web')
        return cls.cube_dir('shared')

    @classmethod
    def i18n_lib_dir(cls):
        """return instance's i18n directory"""
        if CWDEV:
            return join(CW_SOFTWARE_ROOT, 'i18n')
        return join(cls.shared_dir(), 'i18n')

    @classmethod
    def cw_languages(cls):
        for fname in os.listdir(join(cls.i18n_lib_dir())):
            if fname.endswith('.po'):
                yield splitext(fname)[0]


    @classmethod
    def available_cubes(cls):
        import re
        cubes = set()
        for directory in cls.cubes_search_path():
            if not exists(directory):
                cls.error('unexistant directory in cubes search path: %s'
                          % directory)
                continue
            for cube in os.listdir(directory):
                if cube == 'shared':
                    continue
                if not re.match('[_A-Za-z][_A-Za-z0-9]*$', cube):
                    continue # skip invalid python package name
                cubedir = join(directory, cube)
                if isdir(cubedir) and exists(join(cubedir, '__init__.py')):
                    cubes.add(cube)
        return sorted(cubes)

    @classmethod
    def cubes_search_path(cls):
        """return the path of directories where cubes should be searched"""
        path = [abspath(normpath(directory)) for directory in cls.CUBES_PATH
                if directory.strip() and exists(directory.strip())]
        if not cls.CUBES_DIR in path and exists(cls.CUBES_DIR):
            path.append(cls.CUBES_DIR)
        return path

    @classproperty
    def extrapath(cls):
        extrapath = {}
        for cubesdir in cls.cubes_search_path():
            if cubesdir != cls.CUBES_DIR:
                extrapath[cubesdir] = 'cubes'
        return extrapath

    @classmethod
    def cube_dir(cls, cube):
        """return the cube directory for the given cube id, raise
        `ConfigurationError` if it doesn't exist
        """
        for directory in cls.cubes_search_path():
            cubedir = join(directory, cube)
            if exists(cubedir):
                return cubedir
        raise ConfigurationError('no cube %r in %s' % (
            cube, cls.cubes_search_path()))

    @classmethod
    def cube_migration_scripts_dir(cls, cube):
        """cube migration scripts directory"""
        return join(cls.cube_dir(cube), 'migration')

    @classmethod
    def cube_pkginfo(cls, cube):
        """return the information module for the given cube"""
        cube = CW_MIGRATION_MAP.get(cube, cube)
        try:
            parent = __import__('cubes.%s.__pkginfo__' % cube)
            return getattr(parent, cube).__pkginfo__
        except Exception as ex:
            raise ConfigurationError(
                'unable to find packaging information for cube %s (%s: %s)'
                % (cube, ex.__class__.__name__, ex))

    @classmethod
    def cube_version(cls, cube):
        """return the version of the cube located in the given directory
        """
        from logilab.common.changelog import Version
        version = cls.cube_pkginfo(cube).numversion
        assert len(version) == 3, version
        return Version(version)

    @classmethod
    def _cube_deps(cls, cube, key, oldkey):
        """return cubicweb cubes used by the given cube"""
        pkginfo = cls.cube_pkginfo(cube)
        try:
            # explicit __xxx_cubes__ attribute
            deps = getattr(pkginfo, key)
        except AttributeError:
            # deduce cubes from generic __xxx__ attribute
            try:
                gendeps = getattr(pkginfo, key.replace('_cubes', ''))
            except AttributeError:
                deps = {}
            else:
                deps = dict( (x[len('cubicweb-'):], v)
                             for x, v in gendeps.items()
                             if x.startswith('cubicweb-'))
        for depcube in deps:
            try:
                newname = CW_MIGRATION_MAP[depcube]
            except KeyError:
                pass
            else:
                deps[newname] = deps.pop(depcube)
        return deps

    @classmethod
    def cube_depends_cubicweb_version(cls, cube):
        # XXX no backward compat (see _cube_deps above)
        try:
            pkginfo = cls.cube_pkginfo(cube)
            deps = getattr(pkginfo, '__depends__')
            return deps.get('cubicweb')
        except AttributeError:
            return None

    @classmethod
    def cube_dependencies(cls, cube):
        """return cubicweb cubes used by the given cube"""
        return cls._cube_deps(cube, '__depends_cubes__', '__use__')

    @classmethod
    def cube_recommends(cls, cube):
        """return cubicweb cubes recommended by the given cube"""
        return cls._cube_deps(cube, '__recommends_cubes__', '__recommend__')

    @classmethod
    def expand_cubes(cls, cubes, with_recommends=False):
        """expand the given list of top level cubes used by adding recursivly
        each cube dependencies
        """
        cubes = list(cubes)
        todo = cubes[:]
        if with_recommends:
            available = set(cls.available_cubes())
        while todo:
            cube = todo.pop(0)
            for depcube in cls.cube_dependencies(cube):
                if depcube not in cubes:
                    cubes.append(depcube)
                    todo.append(depcube)
            if with_recommends:
                for depcube in cls.cube_recommends(cube):
                    if depcube not in cubes and depcube in available:
                        cubes.append(depcube)
                        todo.append(depcube)
        return cubes

    @classmethod
    def reorder_cubes(cls, cubes):
        """reorder cubes from the top level cubes to inner dependencies
        cubes
        """
        from logilab.common.graph import ordered_nodes, UnorderableGraph
        graph = {}
        for cube in cubes:
            cube = CW_MIGRATION_MAP.get(cube, cube)
            graph[cube] = set(dep for dep in cls.cube_dependencies(cube)
                              if dep in cubes)
            graph[cube] |= set(dep for dep in cls.cube_recommends(cube)
                               if dep in cubes)
        try:
            return ordered_nodes(graph)
        except UnorderableGraph as ex:
            raise ConfigurationError(ex)

    @classmethod
    def cls_adjust_sys_path(cls):
        """update python path if necessary"""
        cubes_parent_dir = normpath(join(cls.CUBES_DIR, '..'))
        if not cubes_parent_dir in sys.path:
            sys.path.insert(0, cubes_parent_dir)
        try:
            import cubes
            cubes.__path__ = cls.cubes_search_path()
        except ImportError:
            return # cubes dir doesn't exists

    @classmethod
    def load_available_configs(cls):
        for confmod in ('web.webconfig',  'etwist.twconfig',
                        'server.serverconfig',):
            try:
                __import__('cubicweb.%s' % confmod)
            except ImportError:
                pass

    @classmethod
    def load_cwctl_plugins(cls):
        cls.cls_adjust_sys_path()
        for ctlmod in ('web.webctl',  'etwist.twctl', 'server.serverctl',
                       'devtools.devctl'):
            try:
                __import__('cubicweb.%s' % ctlmod)
            except ImportError:
                continue
            cls.info('loaded cubicweb-ctl plugin %s', ctlmod)
        for cube in cls.available_cubes():
            pluginfile = join(cls.cube_dir(cube), 'ccplugin.py')
            initfile = join(cls.cube_dir(cube), '__init__.py')
            if exists(pluginfile):
                try:
                    __import__('cubes.%s.ccplugin' % cube)
                    cls.info('loaded cubicweb-ctl plugin from %s', cube)
                except Exception:
                    cls.exception('while loading plugin %s', pluginfile)
            elif exists(initfile):
                try:
                    __import__('cubes.%s' % cube)
                except Exception:
                    cls.exception('while loading cube %s', cube)
            else:
                cls.warning('no __init__ file in cube %s', cube)

    @classmethod
    def init_available_cubes(cls):
        """cubes may register some sources (svnfile for instance) in their
        __init__ file, so they should be loaded early in the startup process
        """
        for cube in cls.available_cubes():
            try:
                __import__('cubes.%s' % cube)
            except Exception as ex:
                cls.warning("can't init cube %s: %s", cube, ex)

    cubicweb_appobject_path = set(['entities'])
    cube_appobject_path = set(['entities'])

    def __init__(self, debugmode=False):
        if debugmode:
            # in python 2.7, DeprecationWarning are not shown anymore by default
            filterwarnings('default', category=DeprecationWarning)
        register_stored_procedures()
        self._cubes = None
        super(CubicWebNoAppConfiguration, self).__init__()
        self.debugmode = debugmode
        self.adjust_sys_path()
        self.load_defaults()
        # will be properly initialized later by _gettext_init
        self.translations = {'en': (text_type, lambda ctx, msgid: text_type(msgid) )}
        self._site_loaded = set()
        # don't register ReStructured Text directives by simple import, avoid pb
        # with eg sphinx.
        # XXX should be done properly with a function from cw.uicfg
        try:
            from cubicweb.ext.rest import cw_rest_init
        except ImportError:
            pass
        else:
            cw_rest_init()

    def adjust_sys_path(self):
        # overriden in CubicWebConfiguration
        self.cls_adjust_sys_path()

    def init_log(self, logthreshold=None, logfile=None, syslog=False):
        """init the log service"""
        if logthreshold is None:
            if self.debugmode:
                logthreshold = 'DEBUG'
            else:
                logthreshold = self['log-threshold']
        if sys.platform == 'win32':
            # no logrotate on win32, so use logging rotation facilities
            # for now, hard code weekly rotation every sunday, and 52 weeks kept
            # idea: make this configurable?
            init_log(self.debugmode, syslog, logthreshold, logfile, self.log_format,
                     rotation_parameters={'when': 'W6', # every sunday
                                          'interval': 1,
                                          'backupCount': 52})
        else:
            init_log(self.debugmode, syslog, logthreshold, logfile, self.log_format)
        # configure simpleTal logger
        logging.getLogger('simpleTAL').setLevel(logging.ERROR)

    def appobjects_path(self):
        """return a list of files or directories where the registry will look
        for application objects. By default return nothing in NoApp config.
        """
        return []

    def build_appobjects_path(self, templpath, evobjpath=None, tvobjpath=None):
        """given a list of directories, return a list of sub files and
        directories that should be loaded by the instance objects registry.

        :param evobjpath:
          optional list of sub-directories (or files without the .py ext) of
          the cubicweb library that should be tested and added to the output list
          if they exists. If not give, default to `cubicweb_appobject_path` class
          attribute.
        :param tvobjpath:
          optional list of sub-directories (or files without the .py ext) of
          directories given in `templpath` that should be tested and added to
          the output list if they exists. If not give, default to
          `cube_appobject_path` class attribute.
        """
        vregpath = self.build_appobjects_cubicweb_path(evobjpath)
        vregpath += self.build_appobjects_cube_path(templpath, tvobjpath)
        return vregpath

    def build_appobjects_cubicweb_path(self, evobjpath=None):
        vregpath = []
        if evobjpath is None:
            evobjpath = self.cubicweb_appobject_path
        # NOTE: for the order, see http://www.cubicweb.org/ticket/2330799
        #       it is clearly a workaround
        for subdir in sorted(evobjpath, key=lambda x:x != 'entities'):
            path = join(CW_SOFTWARE_ROOT, subdir)
            if exists(path):
                vregpath.append(path)
        return vregpath

    def build_appobjects_cube_path(self, templpath, tvobjpath=None):
        vregpath = []
        if tvobjpath is None:
            tvobjpath = self.cube_appobject_path
        for directory in templpath:
            # NOTE: for the order, see http://www.cubicweb.org/ticket/2330799
            for subdir in sorted(tvobjpath, key=lambda x:x != 'entities'):
                path = join(directory, subdir)
                if exists(path):
                    vregpath.append(path)
                elif exists(path + '.py'):
                    vregpath.append(path + '.py')
        return vregpath

    apphome = None

    def load_site_cubicweb(self, cubes=()):
        """load site_cubicweb file for `cubes`"""
        for cube in reversed(cubes or self.cubes()):
            if cube in self._site_loaded:
                continue
            try:
                self._load_site_cubicweb(cube)
                self._site_loaded.add(cube)
            except ImportError:
                continue
        if self.apphome is not None:
            # Would occur, e.g., upon `cubicweb-ctl i18ncube <cube>`.
            self._load_site_cubicweb(None)

    def _load_site_cubicweb(self, cube):
        """Load site_cubicweb.py from `cube` (or apphome if cube is None)."""
        if cube is not None:
            modname = 'cubes.%s.site_cubicweb' % cube
            __import__(modname)
            return sys.modules[modname]
        else:
            import imp
            apphome_site = join(self.apphome, 'site_cubicweb.py')
            if exists(apphome_site):
                with open(apphome_site, 'rb') as f:
                    return imp.load_source('site_cubicweb', apphome_site, f)

    def cwproperty_definitions(self):
        cfg = self.persistent_options_configuration()
        for section, options in cfg.options_by_section():
            section = section.lower()
            for optname, optdict, value in options:
                key = '%s.%s' % (section, optname)
                type, vocab = self.map_option(optdict)
                default = cfg.option_default(optname, optdict)
                pdef = {'type': type, 'vocabulary': vocab, 'default': default,
                        'help': optdict['help'],
                        'sitewide': optdict.get('sitewide', False)}
                yield key, pdef

    def map_option(self, optdict):
        try:
            vocab = optdict['choices']
        except KeyError:
            vocab = optdict.get('vocabulary')
            if isinstance(vocab, Method):
                vocab = getattr(self, vocab.method, ())
        return CFGTYPE2ETYPE_MAP[optdict['type']], vocab

    def default_instance_id(self):
        """return the instance identifier, useful for option which need this
        as default value
        """
        return None

    _cubes = None

    def init_cubes(self, cubes):
        self._cubes = self.reorder_cubes(cubes)
        # load cubes'__init__.py file first
        for cube in cubes:
            __import__('cubes.%s' % cube)
        self.load_site_cubicweb()

    def cubes(self):
        """return the list of cubes used by this instance

        result is ordered from the top level cubes to inner dependencies
        cubes
        """
        assert self._cubes is not None, 'cubes not initialized'
        return self._cubes

    def cubes_path(self):
        """return the list of path to cubes used by this instance, from outer
        most to inner most cubes
        """
        return [self.cube_dir(p) for p in self.cubes()]

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    @classmethod
    def debug(cls, msg, *a, **kw):
        pass
    info = warning = error = critical = exception = debug


class CubicWebConfiguration(CubicWebNoAppConfiguration):
    """base class for cubicweb server and web configurations"""

    if CubicWebNoAppConfiguration.mode == 'user':
        _INSTANCES_DIR = expanduser('~/etc/cubicweb.d/')
    #mode == system'
    elif _USR_INSTALL:
        _INSTANCES_DIR = '/etc/cubicweb.d/'
    else:
        _INSTANCES_DIR = join(_INSTALL_PREFIX, 'etc', 'cubicweb.d')

    # set to true during repair (shell, migration) to allow some things which
    # wouldn't be possible otherwise
    repairing = False

    # set by upgrade command
    verbosity = 0
    cmdline_options = None
    options = CubicWebNoAppConfiguration.options + (
        ('log-file',
         {'type' : 'string',
          'default': Method('default_log_file'),
          'help': 'file where output logs should be written',
          'group': 'main', 'level': 2,
          }),
        ('statsd-endpoint',
         {'type' : 'string',
          'default': '',
          'help': 'UDP address of the statsd endpoint; it must be formatted'
                  'like <ip>:<port>; disabled is unset.',
          'group': 'main', 'level': 2,
          }),
        # email configuration
        ('smtp-host',
         {'type' : 'string',
          'default': 'mail',
          'help': 'hostname of the SMTP mail server',
          'group': 'email', 'level': 1,
          }),
        ('smtp-port',
         {'type' : 'int',
          'default': 25,
          'help': 'listening port of the SMTP mail server',
          'group': 'email', 'level': 1,
          }),
        ('sender-name',
         {'type' : 'string',
          'default': Method('default_instance_id'),
          'help': 'name used as HELO name for outgoing emails from the \
repository.',
          'group': 'email', 'level': 2,
          }),
        ('sender-addr',
         {'type' : 'string',
          'default': 'cubicweb@mydomain.com',
          'help': 'email address used as HELO address for outgoing emails from \
the repository',
          'group': 'email', 'level': 1,
          }),
        ('logstat-interval',
         {'type' : 'int',
          'default': 0,
          'help': 'interval (in seconds) at which stats are dumped in the logstat file; set 0 to disable',
          'group': 'main', 'level': 2,
          }),
        ('logstat-file',
         {'type' : 'string',
          'default': Method('default_stats_file'),
          'help': 'file where stats for the instance should be written',
          'group': 'main', 'level': 2,
          }),
        )

    @classmethod
    def instances_dir(cls):
        """return the control directory"""
        return abspath(os.environ.get('CW_INSTANCES_DIR', cls._INSTANCES_DIR))

    @classmethod
    def migration_scripts_dir(cls):
        """cubicweb migration scripts directory"""
        if CWDEV:
            return join(CW_SOFTWARE_ROOT, 'misc', 'migration')
        mdir = join(_INSTALL_PREFIX, 'share', 'cubicweb', 'migration')
        if not exists(mdir):
            raise ConfigurationError('migration path %s doesn\'t exist' % mdir)
        return mdir

    @classmethod
    def config_for(cls, appid, config=None, debugmode=False, creating=False):
        """return a configuration instance for the given instance identifier
        """
        cls.load_available_configs()
        config = config or guess_configuration(cls.instance_home(appid))
        configcls = configuration_cls(config)
        return configcls(appid, debugmode, creating)

    @classmethod
    def possible_configurations(cls, appid):
        """return the name of possible configurations for the given
        instance id
        """
        home = cls.instance_home(appid)
        return possible_configurations(home)

    @classmethod
    def instance_home(cls, appid):
        """return the home directory of the instance with the given
        instance id
        """
        home = join(cls.instances_dir(), appid)
        if not exists(home):
            raise ConfigurationError('no such instance %s (check it exists with'
                                     ' "cubicweb-ctl list")' % appid)
        return home

    MODES = ('common', 'repository', 'Any')
    MCOMPAT = {'all-in-one': MODES,
               'repository': ('common', 'repository', 'Any')}
    @classmethod
    def accept_mode(cls, mode):
        #assert mode in cls.MODES, mode
        return mode in cls.MCOMPAT[cls.name]

    # default configuration methods ###########################################

    def default_instance_id(self):
        """return the instance identifier, useful for option which need this
        as default value
        """
        return self.appid

    def default_log_file(self):
        """return default path to the log file of the instance'server"""
        if self.mode == 'user':
            import tempfile
            basepath = join(tempfile.gettempdir(), '%s-%s' % (
                basename(self.appid), self.name))
            path = basepath + '.log'
            i = 1
            while exists(path) and i < 100: # arbitrary limit to avoid infinite loop
                try:
                    open(path, 'a')
                    break
                except IOError:
                    path = '%s-%s.log' % (basepath, i)
                    i += 1
            return path
        if _USR_INSTALL:
            return '/var/log/cubicweb/%s-%s.log' % (self.appid, self.name)
        else:
            log_path = os.path.join(_INSTALL_PREFIX, 'var', 'log', 'cubicweb', '%s-%s.log')
            return log_path % (self.appid, self.name)

    def default_stats_file(self):
        """return default path to the stats file of the instance'server"""
        logfile = self.default_log_file()
        if logfile.endswith('.log'):
            logfile = logfile[:-4]
        return logfile + '.stats'

    def default_pid_file(self):
        """return default path to the pid file of the instance'server"""
        if self.mode == 'system':
            if _USR_INSTALL:
                default = '/var/run/cubicweb/'
            else:
                default = os.path.join(_INSTALL_PREFIX, 'var', 'run', 'cubicweb')
        else:
            import tempfile
            default = tempfile.gettempdir()
        # runtime directory created on startup if necessary, don't check it
        # exists
        rtdir = abspath(os.environ.get('CW_RUNTIME_DIR', default))
        return join(rtdir, '%s-%s.pid' % (self.appid, self.name))

    # config -> repository

    def repository(self, vreg=None):
        from cubicweb.server.repository import Repository
        from cubicweb.server.utils import TasksManager
        return Repository(self, TasksManager(), vreg=vreg)

    # instance methods used to get instance specific resources #############

    def __init__(self, appid, debugmode=False, creating=False):
        self.appid = appid
        # set to true while creating an instance
        self.creating = creating
        super(CubicWebConfiguration, self).__init__(debugmode)
        fake_gettext = (text_type, lambda ctx, msgid: text_type(msgid))
        for lang in self.available_languages():
            self.translations[lang] = fake_gettext
        self._cubes = None
        self.load_file_configuration(self.main_config_file())

    def adjust_sys_path(self):
        super(CubicWebConfiguration, self).adjust_sys_path()
        # adding apphome to python path is not usually necessary in production
        # environments, but necessary for tests
        if self.apphome and self.apphome not in sys.path:
            sys.path.insert(0, self.apphome)

    @property
    def apphome(self):
        return join(self.instances_dir(), self.appid)

    @property
    def appdatahome(self):
        if self.mode == 'system':
            if _USR_INSTALL:
                iddir = os.path.join('/var','lib', 'cubicweb', 'instances')
            else:
                iddir = os.path.join(_INSTALL_PREFIX, 'var', 'lib', 'cubicweb', 'instances')
        else:
            iddir = self.instances_dir()
        iddir = abspath(os.environ.get('CW_INSTANCES_DATA_DIR', iddir))
        return join(iddir, self.appid)

    def init_cubes(self, cubes):
        super(CubicWebConfiguration, self).init_cubes(cubes)
        # reload config file in cases options are defined in cubes __init__
        # or site_cubicweb files
        self.load_file_configuration(self.main_config_file())
        # configuration initialization hook
        self.load_configuration(**(self.cmdline_options or {}))

    def add_cubes(self, cubes):
        """add given cubes to the list of used cubes"""
        if not isinstance(cubes, list):
            cubes = list(cubes)
        self._cubes = self.reorder_cubes(list(self._cubes) + cubes)
        self.load_site_cubicweb(cubes)

    def main_config_file(self):
        """return instance's control configuration file"""
        return join(self.apphome, '%s.conf' % self.name)

    def save(self):
        """write down current configuration"""
        with open(self.main_config_file(), 'w') as fobj:
            self.generate_config(fobj)

    def check_writeable_uid_directory(self, path):
        """check given directory path exists, belongs to the user running the
        server process and is writeable.

        If not, try to fix this, letting exception propagate when not possible.
        """
        if not exists(path):
            self.info('creating %s directory', path)
            try:
                os.makedirs(path)
            except OSError as ex:
                self.warning('error while creating %s directory: %s', path, ex)
                return
        self.ensure_uid(path)

    def get_uid(self):
        if self['uid']:
            try:
                uid = int(self['uid'])
            except ValueError:
                from pwd import getpwnam
                uid = getpwnam(self['uid']).pw_uid
        else:
            try:
                uid = os.getuid()
            except AttributeError: # we are on windows
                return
        return uid

    def ensure_uid(self, path, enforce_write=False):
        if not exists(path):
            return
        uid = self.get_uid()
        if uid is None:
            return
        fstat = os.stat(path)
        if fstat.st_uid != uid:
            self.info('giving ownership of %s to %s', path, self['uid'])
            try:
                os.chown(path, uid, os.getgid())
            except OSError as ex:
                self.warning('error while giving ownership of %s to %s: %s',
                             path, self['uid'], ex)

        if enforce_write and not (fstat.st_mode & stat.S_IWUSR):
            self.info('forcing write permission on %s', path)
            try:
                os.chmod(path, fstat.st_mode | stat.S_IWUSR)
            except OSError as ex:
                self.warning('error while forcing write permission on %s: %s',
                             path, ex)

    def ensure_uid_directory(self, path, enforce_write=False):
        self.check_writeable_uid_directory(path)
        for dirpath, dirnames, filenames in os.walk(path):
            for name in filenames:
                self.ensure_uid(join(dirpath, name), enforce_write)
        return path

    @cached
    def instance_md5_version(self):
        from hashlib import md5 # pylint: disable=E0611
        infos = []
        for pkg in sorted(self.cubes()):
            version = self.cube_version(pkg)
            infos.append('%s-%s' % (pkg, version))
        infos.append('cubicweb-%s' % str(self.cubicweb_version()))
        return md5((';'.join(infos)).encode('ascii')).hexdigest()

    def load_configuration(self, **kw):
        """load instance's configuration files"""
        super(CubicWebConfiguration, self).load_configuration(**kw)
        if self.apphome and not self.creating:
            # init gettext
            self._gettext_init()

    def _load_site_cubicweb(self, cube):
        # overridden to register cube specific options
        mod = super(CubicWebConfiguration, self)._load_site_cubicweb(cube)
        if getattr(mod, 'options', None):
            self.register_options(mod.options)
            self.load_defaults()

    def init_log(self, logthreshold=None, force=False):
        """init the log service"""
        if not force and hasattr(self, '_logging_initialized'):
            return
        self._logging_initialized = True
        super_self = super(CubicWebConfiguration, self)
        super_self.init_log(logthreshold, logfile=self.get('log-file'))
        # read a config file if it exists
        logconfig = join(self.apphome, 'logging.conf')
        if exists(logconfig):
            logging.config.fileConfig(logconfig)
        # set the statsd address, if any
        if self.get('statsd-endpoint'):
            try:
                address, port = self.get('statsd-endpoint').split(':')
                port = int(port)
            except:
                self.error('statsd-endpoint: invalid address format ({}); '
                           'it should be "ip:port"'.format(self.get('statsd-endpoint')))
            else:
                import statsd_logger
                statsd_logger.setup('cubicweb.%s' % self.appid, (address, port))

    def available_languages(self, *args):
        """return available translation for an instance, by looking for
        compiled catalog

        take \*args to be usable as a vocabulary method
        """
        from glob import glob
        yield 'en' # ensure 'en' is yielded even if no .mo found
        for path in glob(join(self.apphome, 'i18n',
                              '*', 'LC_MESSAGES')):
            lang = path.split(os.sep)[-2]
            if lang != 'en':
                yield lang

    def _gettext_init(self):
        """set language for gettext"""
        from cubicweb.cwgettext import translation
        path = join(self.apphome, 'i18n')
        for language in self.available_languages():
            self.info("loading language %s", language)
            try:
                tr = translation('cubicweb', path, languages=[language])
                self.translations[language] = (tr.ugettext, tr.upgettext)
            except (ImportError, AttributeError, IOError):
                if self.mode != 'test':
                    # in test contexts, data/i18n does not exist, hence
                    # logging will only pollute the logs
                    self.exception('localisation support error for language %s',
                                   language)

    def appobjects_path(self):
        """return a list of files or directories where the registry will look
        for application objects
        """
        templpath = list(reversed(self.cubes_path()))
        if self.apphome: # may be unset in tests
            templpath.append(self.apphome)
        return self.build_appobjects_path(templpath)

    def set_sources_mode(self, sources):
        if not 'all' in sources:
            print('warning: ignoring specified sources, requires a repository '
                  'configuration')

    def i18ncompile(self, langs=None):
        from cubicweb import i18n
        if langs is None:
            langs = self.available_languages()
        i18ndir = join(self.apphome, 'i18n')
        if not exists(i18ndir):
            create_dir(i18ndir)
        sourcedirs = [join(path, 'i18n') for path in self.cubes_path()]
        sourcedirs.append(self.i18n_lib_dir())
        return i18n.compile_i18n_catalogs(sourcedirs, i18ndir, langs)

    def sendmails(self, msgs, fromaddr=None):
        """msgs: list of 2-uple (message object, recipients). Return False
        if connection to the smtp server failed, else True.
        """
        server, port = self['smtp-host'], self['smtp-port']
        if fromaddr is None:
            fromaddr = '%s <%s>' % (self['sender-name'], self['sender-addr'])
        SMTP_LOCK.acquire()
        try:
            try:
                smtp = SMTP(server, port)
            except Exception as ex:
                self.exception("can't connect to smtp server %s:%s (%s)",
                               server, port, ex)
                return False
            for msg, recipients in msgs:
                try:
                    smtp.sendmail(fromaddr, recipients, msg.as_string())
                except Exception as ex:
                    self.exception("error sending mail to %s (%s)",
                                   recipients, ex)
            smtp.close()
        finally:
            SMTP_LOCK.release()
        return True

set_log_methods(CubicWebNoAppConfiguration,
                logging.getLogger('cubicweb.configuration'))

# alias to get a configuration instance from an instance id
instance_configuration = CubicWebConfiguration.config_for
application_configuration = deprecated('use instance_configuration')(instance_configuration)


_EXT_REGISTERED = False
def register_stored_procedures():
    from logilab.database import FunctionDescr
    from rql.utils import register_function, iter_funcnode_variables
    from rql.nodes import SortTerm, Constant, VariableRef

    global _EXT_REGISTERED
    if _EXT_REGISTERED:
        return
    _EXT_REGISTERED = True

    class COMMA_JOIN(FunctionDescr):
        supported_backends = ('postgres', 'sqlite',)
        rtype = 'String'

        def st_description(self, funcnode, mainindex, tr):
            return ', '.join(sorted(term.get_description(mainindex, tr)
                                    for term in iter_funcnode_variables(funcnode)))

    register_function(COMMA_JOIN)  # XXX do not expose?


    class CONCAT_STRINGS(COMMA_JOIN):
        aggregat = True

    register_function(CONCAT_STRINGS) # XXX bw compat


    class GROUP_CONCAT(CONCAT_STRINGS):
        supported_backends = ('mysql', 'postgres', 'sqlite',)

    register_function(GROUP_CONCAT)


    class LIMIT_SIZE(FunctionDescr):
        supported_backends = ('postgres', 'sqlite',)
        minargs = maxargs = 3
        rtype = 'String'

        def st_description(self, funcnode, mainindex, tr):
            return funcnode.children[0].get_description(mainindex, tr)

    register_function(LIMIT_SIZE)


    class TEXT_LIMIT_SIZE(LIMIT_SIZE):
        supported_backends = ('mysql', 'postgres', 'sqlite',)
        minargs = maxargs = 2

    register_function(TEXT_LIMIT_SIZE)


    class FTIRANK(FunctionDescr):
        """return ranking of a variable that must be used as some has_text
        relation subject in the query's restriction. Usually used to sort result
        of full-text search by ranking.
        """
        supported_backends = ('postgres',)
        rtype = 'Float'

        def st_check_backend(self, backend, funcnode):
            """overriden so that on backend not supporting fti ranking, the
            function is removed when in an orderby clause, or replaced by a 1.0
            constant.
            """
            if not self.supports(backend):
                parent = funcnode.parent
                while parent is not None and not isinstance(parent, SortTerm):
                    parent = parent.parent
                if isinstance(parent, SortTerm):
                    parent.parent.remove(parent)
                else:
                    funcnode.parent.replace(funcnode, Constant(1.0, 'Float'))
                    parent = funcnode
                for vref in parent.iget_nodes(VariableRef):
                    vref.unregister_reference()

    register_function(FTIRANK)


    class FSPATH(FunctionDescr):
        """return path of some bytes attribute stored using the Bytes
        File-System Storage (bfss)
        """
        rtype = 'Bytes' # XXX return a String? potential pb with fs encoding

        def update_cb_stack(self, stack):
            assert len(stack) == 1
            stack[0] = self.source_execute

        def as_sql(self, backend, args):
            raise NotImplementedError(
                'This callback is only available for BytesFileSystemStorage '
                'managed attribute. Is FSPATH() argument BFSS managed?')

        def source_execute(self, source, session, value):
            fpath = source.binary_to_str(value)
            try:
                return Binary(fpath)
            except OSError as ex:
                source.critical("can't open %s: %s", fpath, ex)
                return None

    register_function(FSPATH)
