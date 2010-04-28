# -*- coding: utf-8 -*-
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
"""
.. _ResourceMode:

Resource mode
-------------

A resource *mode* is a predifined set of settings for various resources
directories, such as cubes, instances, etc. to ease development with the
framework. There are two running modes with *CubicWeb*:

* 'user', resources are searched / created in the user home directory:

  - instances are stored in :file:`~/etc/cubicweb.d`
  - temporary files (such as pid file) in :file:`/tmp`

* 'system', resources are searched / created in the system directories (eg
  usually requiring root access):

  - instances are stored in :file:`<INSTALL_PREFIX>/etc/cubicweb.d`
  - temporary files (such as pid file) in :file:`/var/run/cubicweb`

  where `<INSTALL_PREFIX>` is the detected installation prefix ('/usr/local' for
  instance).


Notice that each resource path may be explicitly set using an environment
variable if the default doesn't suit your needs. Here are the default resource
directories that are affected according to mode:

* 'system': ::

        CW_INSTANCES_DIR = <INSTALL_PREFIX>/etc/cubicweb.d/
        CW_INSTANCES_DATA_DIR = /var/lib/cubicweb/instances/
        CW_RUNTIME_DIR = /var/run/cubicweb/

 * 'user': ::

        CW_INSTANCES_DIR = ~/etc/cubicweb.d/
        CW_INSTANCES_DATA_DIR = ~/etc/cubicweb.d/
        CW_RUNTIME_DIR = /tmp

Cubes search path is also affected, see the :ref:Cube section.

By default, the mode automatically set to 'user' if a :file:`.hg` directory is found
in the cubicweb package, else it's set to 'system'. You can force this by setting
the :envvar:`CW_MODE` environment variable to either 'user' or 'system' so you can
easily:

* use system wide installation but user specific instances and all, without root
  privileges on the system (`export CW_MODE=user`)

* use local checkout of cubicweb on system wide instances (requires root
  privileges on the system (`export CW_MODE=system`)

If you've a doubt about the mode you're currently running, check the first line
outputed by the :command:`cubicweb-ctl list` command.

Also, if cubicweb is a mercurial checkout located in `<CW_SOFTWARE_ROOT>`:

* main cubes directory is `<CW_SOFTWARE_ROOT>/../cubes`. You can specify
  another one with :envvar:`CW_INSTANCES_DIR` environment variable or simply
  add some other directories by using :envvar:`CW_CUBES_PATH`

* cubicweb migration files are searched in `<CW_SOFTWARE_ROOT>/misc/migration`
  instead of `<INSTALL_PREFIX>/share/cubicweb/migration/`.


.. _ConfigurationEnv:

Environment configuration
-------------------------

Python
``````

If you installed *CubicWeb* by cloning the Mercurial forest or from source
distribution, then you will need to update the environment variable PYTHONPATH by
adding the path to the forest `cubicweb`:

Add the following lines to either :file:`.bashrc` or :file:`.bash_profile` to
configure your development environment ::

    export PYTHONPATH=/full/path/to/cubicweb-forest

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
__docformat__ = "restructuredtext en"
_ = unicode

import sys
import os
import logging
from smtplib import SMTP
from threading import Lock
from os.path import (exists, join, expanduser, abspath, normpath,
                     basename, isdir, dirname)
from warnings import warn
from logilab.common.decorators import cached, classproperty
from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods, init_log
from logilab.common.configuration import (Configuration, Method,
                                          ConfigurationMixIn, merge_options)

from cubicweb import (CW_SOFTWARE_ROOT, CW_MIGRATION_MAP,
                      ConfigurationError, Binary)
from cubicweb.toolsutils import env_path, create_dir

CONFIGURATIONS = []

SMTP_LOCK = Lock()


class metaconfiguration(type):
    """metaclass to automaticaly register configuration"""
    def __new__(mcs, name, bases, classdict):
        cls = super(metaconfiguration, mcs).__new__(mcs, name, bases, classdict)
        if classdict.get('name'):
            CONFIGURATIONS.append(cls)
        return cls

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
    return [name for name in ('repository', 'twisted', 'all-in-one')
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

def _find_prefix(start_path=CW_SOFTWARE_ROOT):
    """Runs along the parent directories of *start_path* (default to cubicweb source directory)
    looking for one containing a 'share/cubicweb' directory.
    The first matching directory is assumed as the prefix installation of cubicweb

    Returns the matching prefix or None.
    """
    prefix = start_path
    old_prefix = None
    if not isdir(start_path):
        prefix = dirname(start_path)
    while not isdir(join(prefix, 'share', 'cubicweb')) and prefix != old_prefix:
        old_prefix = prefix
        prefix = dirname(prefix)
    if isdir(join(prefix, 'share', 'cubicweb')):
        return prefix
    return sys.prefix

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
      'help': _('how to format date in the ui ("man strftime" for format description)'),
      'group': 'ui',
      }),
    ('datetime-format',
     {'type' : 'string',
      'default': '%Y/%m/%d %H:%M',
      'help': _('how to format date and time in the ui ("man strftime" for format description)'),
      'group': 'ui',
      }),
    ('time-format',
     {'type' : 'string',
      'default': '%H:%M',
      'help': _('how to format time in the ui ("man strftime" for format description)'),
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
      'choices': ('text/plain', 'text/rest', 'text/html'),
      'default': 'text/html', # use fckeditor in the web ui
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

CWDEV = exists(join(CW_SOFTWARE_ROOT, '.hg'))

try:
    _INSTALL_PREFIX = os.environ['CW_INSTALL_PREFIX']
except KeyError:
    _INSTALL_PREFIX = _find_prefix()

class CubicWebNoAppConfiguration(ConfigurationMixIn):
    """base class for cubicweb configuration without a specific instance directory
    """
    __metaclass__ = metaconfiguration
    # to set in concrete configuration
    name = None
    # log messages format (see logging module documentation for available keys)
    log_format = '%(asctime)s - (%(name)s) %(levelname)s: %(message)s'
    # nor remove appobjects based on unused interface
    cleanup_interface_sobjects = True
    # debug mode
    debugmode = False


    if (CWDEV and _forced_mode != 'system'):
        mode = 'user'
        _CUBES_DIR = join(CW_SOFTWARE_ROOT, '../cubes')
    else:
        mode = _forced_mode or 'system'
        _CUBES_DIR = join(_INSTALL_PREFIX, 'share', 'cubicweb', 'cubes')

    CUBES_DIR = env_path('CW_CUBES_DIR', _CUBES_DIR, 'cubes', checkexists=False)
    CUBES_PATH = os.environ.get('CW_CUBES_PATH', '').split(os.pathsep)

    options = (
       ('log-threshold',
         {'type' : 'string', # XXX use a dedicated type?
          'default': 'WARNING',
          'help': 'server\'s log level',
          'group': 'main', 'level': 1,
          }),
        # pyro options
        ('pyro-instance-id',
         {'type' : 'string',
          'default': Method('default_instance_id'),
          'help': 'identifier of the CubicWeb instance in the Pyro name server',
          'group': 'pyro', 'level': 1,
          }),
        ('pyro-ns-host',
         {'type' : 'string',
          'default': '',
          'help': 'Pyro name server\'s host. If not set, will be detected by a \
broadcast query. It may contains port information using <host>:<port> notation.',
          'group': 'pyro', 'level': 1,
          }),
        ('pyro-ns-group',
         {'type' : 'string',
          'default': 'cubicweb',
          'help': 'Pyro name server\'s group where the repository will be \
registered.',
          'group': 'pyro', 'level': 1,
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
        ('use-request-subdomain',
         {'type' : 'yn',
          'default': None,
          'help': ('if set, base-url subdomain is replaced by the request\'s '
                   'host, to help managing sites with several subdomains in a '
                   'single cubicweb instance'),
          'group': 'main', 'level': 1,
          }),
        ('mangle-emails',
         {'type' : 'yn',
          'default': False,
          'help': "don't display actual email addresses but mangle them if \
this option is set to yes",
          'group': 'email', 'level': 2,
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
        """return the cube directory for the given cube id,
        raise `ConfigurationError` if it doesn't exists
        """
        for directory in cls.cubes_search_path():
            cubedir = join(directory, cube)
            if exists(cubedir):
                return cubedir
        raise ConfigurationError('no cube %s in %s' % (cube, cls.cubes_search_path()))

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
        except Exception, ex:
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
                # bw compat
                if hasattr(pkginfo, oldkey):
                    warn('[3.8] cube %s: %s is deprecated, use %s dict'
                         % (cube, oldkey, key), DeprecationWarning)
                    deps = getattr(pkginfo, oldkey)
                else:
                    deps = {}
            else:
                deps = dict( (x[len('cubicweb-'):], v)
                             for x, v in gendeps.iteritems()
                             if x.startswith('cubicweb-'))
        if not isinstance(deps, dict):
            deps = dict((key, None) for key in deps)
            warn('[3.8] cube %s should define %s as a dict' % (cube, key),
                 DeprecationWarning)
        return deps

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
        while todo:
            cube = todo.pop(0)
            for depcube in cls.cube_dependencies(cube):
                if depcube not in cubes:
                    depcube = CW_MIGRATION_MAP.get(depcube, depcube)
                    cubes.append(depcube)
                    todo.append(depcube)
            if with_recommends:
                for depcube in cls.cube_recommends(cube):
                    if depcube not in cubes:
                        depcube = CW_MIGRATION_MAP.get(depcube, depcube)
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
        except UnorderableGraph, ex:
            raise ConfigurationError('cycles in cubes dependencies: %s'
                                     % ex.cycles)

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
    def load_cwctl_plugins(cls):
        from logilab.common.modutils import load_module_from_file
        cls.cls_adjust_sys_path()
        for ctlfile in ('web/webctl.py',  'etwist/twctl.py',
                        'server/serverctl.py',
                        'devtools/devctl.py', 'goa/goactl.py'):
            if exists(join(CW_SOFTWARE_ROOT, ctlfile)):
                try:
                    load_module_from_file(join(CW_SOFTWARE_ROOT, ctlfile))
                except ImportError, err:
                    cls.info('could not import the command provider %s (cause : %s)' %
                                (ctlfile, err))
                cls.info('loaded cubicweb-ctl plugin %s', ctlfile)
        for cube in cls.available_cubes():
            oldpluginfile = join(cls.cube_dir(cube), 'ecplugin.py')
            pluginfile = join(cls.cube_dir(cube), 'ccplugin.py')
            initfile = join(cls.cube_dir(cube), '__init__.py')
            if exists(pluginfile):
                try:
                    __import__('cubes.%s.ccplugin' % cube)
                    cls.info('loaded cubicweb-ctl plugin from %s', cube)
                except:
                    cls.exception('while loading plugin %s', pluginfile)
            elif exists(oldpluginfile):
                warn('[3.6] %s: ecplugin module should be renamed to ccplugin' % cube,
                     DeprecationWarning)
                try:
                    __import__('cubes.%s.ecplugin' % cube)
                    cls.info('loaded cubicweb-ctl plugin from %s', cube)
                except:
                    cls.exception('while loading plugin %s', oldpluginfile)
            elif exists(initfile):
                try:
                    __import__('cubes.%s' % cube)
                except:
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
            except Exception, ex:
                cls.warning("can't init cube %s: %s", cube, ex)

    cubicweb_appobject_path = set(['entities'])
    cube_appobject_path = set(['entities'])

    @classmethod
    def build_vregistry_path(cls, templpath, evobjpath=None, tvobjpath=None):
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
        vregpath = cls.build_vregistry_cubicweb_path(evobjpath)
        vregpath += cls.build_vregistry_cube_path(templpath, tvobjpath)
        return vregpath

    @classmethod
    def build_vregistry_cubicweb_path(cls, evobjpath=None):
        vregpath = []
        if evobjpath is None:
            evobjpath = cls.cubicweb_appobject_path
        for subdir in evobjpath:
            path = join(CW_SOFTWARE_ROOT, subdir)
            if exists(path):
                vregpath.append(path)
        return vregpath

    @classmethod
    def build_vregistry_cube_path(cls, templpath, tvobjpath=None):
        vregpath = []
        if tvobjpath is None:
            tvobjpath = cls.cube_appobject_path
        for directory in templpath:
            for subdir in tvobjpath:
                path = join(directory, subdir)
                if exists(path):
                    vregpath.append(path)
                elif exists(path + '.py'):
                    vregpath.append(path + '.py')
        return vregpath

    def __init__(self):
        register_stored_procedures()
        ConfigurationMixIn.__init__(self)
        self.adjust_sys_path()
        self.load_defaults()
        self.translations = {}
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

    def init_log(self, logthreshold=None, debug=False,
                 logfile=None, syslog=False):
        """init the log service"""
        if logthreshold is None:
            if debug:
                logthreshold = 'DEBUG'
            else:
                logthreshold = self['log-threshold']
        self.debugmode = debug
        init_log(debug, syslog, logthreshold, logfile, self.log_format)
        # configure simpleTal logger
        logging.getLogger('simpleTAL').setLevel(logging.ERROR)

    def vregistry_path(self):
        """return a list of files or directories where the registry will look
        for application objects. By default return nothing in NoApp config.
        """
        return []

    def eproperty_definitions(self):
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


class CubicWebConfiguration(CubicWebNoAppConfiguration):
    """base class for cubicweb server and web configurations"""

    if CubicWebNoAppConfiguration.mode == 'user':
        _INSTANCES_DIR = expanduser('~/etc/cubicweb.d/')
    else: #mode = 'system'
        if _INSTALL_PREFIX == '/usr':
            _INSTANCES_DIR = '/etc/cubicweb.d/'
        else:
            _INSTANCES_DIR = join(_INSTALL_PREFIX, 'etc', 'cubicweb.d')

    if os.environ.get('APYCOT_ROOT'):
        _cubes_init = join(CubicWebNoAppConfiguration.CUBES_DIR, '__init__.py')
        if not exists(_cubes_init):
            file(join(_cubes_init), 'w').close()
        if not exists(_INSTANCES_DIR):
            os.makedirs(_INSTANCES_DIR)

    # for some commands (creation...) we don't want to initialize gettext
    set_language = True
    # set this to true to allow somethings which would'nt be possible
    repairing = False

    options = CubicWebNoAppConfiguration.options + (
        ('log-file',
         {'type' : 'string',
          'default': Method('default_log_file'),
          'help': 'file where output logs should be written',
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
        )

    @classmethod
    def instances_dir(cls):
        """return the control directory"""
        return env_path('CW_INSTANCES_DIR', cls._INSTANCES_DIR, 'registry')

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
    def config_for(cls, appid, config=None):
        """return a configuration instance for the given instance identifier
        """
        config = config or guess_configuration(cls.instance_home(appid))
        configcls = configuration_cls(config)
        return configcls(appid)

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

    MODES = ('common', 'repository', 'Any', 'web')
    MCOMPAT = {'all-in-one': MODES,
               'repository': ('common', 'repository', 'Any'),
               'twisted'   : ('common', 'web'),}
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
                    file(path, 'a')
                    break
                except IOError:
                    path = '%s-%s.log' % (basepath, i)
                    i += 1
            return path
        return '/var/log/cubicweb/%s-%s.log' % (self.appid, self.name)

    def default_pid_file(self):
        """return default path to the pid file of the instance'server"""
        if self.mode == 'system':
            # XXX not under _INSTALL_PREFIX, right?
            rtdir = env_path('CW_RUNTIME_DIR', '/var/run/cubicweb/', 'run time')
        else:
            import tempfile
            rtdir = env_path('CW_RUNTIME_DIR', tempfile.gettempdir(), 'run time')
        return join(rtdir, '%s-%s.pid' % (self.appid, self.name))

    # instance methods used to get instance specific resources #############

    def __init__(self, appid):
        self.appid = appid
        CubicWebNoAppConfiguration.__init__(self)
        self._cubes = None
        self._site_loaded = set()
        self.load_file_configuration(self.main_config_file())

    def adjust_sys_path(self):
        CubicWebNoAppConfiguration.adjust_sys_path(self)
        # adding apphome to python path is not usually necessary in production
        # environments, but necessary for tests
        if self.apphome and not self.apphome in sys.path:
            sys.path.insert(0, self.apphome)

    @property
    def apphome(self):
        return join(self.instances_dir(), self.appid)

    @property
    def appdatahome(self):
        if self.mode == 'system':
            # XXX not under _INSTALL_PREFIX, right?
            iddir = '/var/lib/cubicweb/instances/'
        else:
            iddir = self.instances_dir()
        iddir = env_path('CW_INSTANCES_DATA_DIR', iddir, 'additional data')
        return join(iddir, self.appid)

    def init_cubes(self, cubes):
        assert self._cubes is None, self._cubes
        self._cubes = self.reorder_cubes(cubes)
        # load cubes'__init__.py file first
        for cube in cubes:
            __import__('cubes.%s' % cube)
        self.load_site_cubicweb()
        # reload config file in cases options are defined in cubes __init__
        # or site_cubicweb files
        self.load_file_configuration(self.main_config_file())
        # configuration initialization hook
        self.load_configuration()

    def cubes(self):
        """return the list of cubes used by this instance

        result is ordered from the top level cubes to inner dependencies
        cubes
        """
        assert self._cubes is not None
        return self._cubes

    def cubes_path(self):
        """return the list of path to cubes used by this instance, from outer
        most to inner most cubes
        """
        return [self.cube_dir(p) for p in self.cubes()]

    def add_cubes(self, cubes):
        """add given cubes to the list of used cubes"""
        if not isinstance(cubes, list):
            cubes = list(cubes)
        self._cubes = self.reorder_cubes(list(self._cubes) + cubes)

    def main_config_file(self):
        """return instance's control configuration file"""
        return join(self.apphome, '%s.conf' % self.name)

    def save(self):
        """write down current configuration"""
        self.generate_config(open(self.main_config_file(), 'w'))

    @cached
    def instance_md5_version(self):
        import md5
        infos = []
        for pkg in self.cubes():
            version = self.cube_version(pkg)
            infos.append('%s-%s' % (pkg, version))
        return md5.new(';'.join(infos)).hexdigest()

    def load_site_cubicweb(self):
        """load instance's specific site_cubicweb file"""
        for path in reversed([self.apphome] + self.cubes_path()):
            sitefile = join(path, 'site_cubicweb.py')
            if exists(sitefile) and not sitefile in self._site_loaded:
                self._load_site_cubicweb(sitefile)
                self._site_loaded.add(sitefile)
            else:
                sitefile = join(path, 'site_erudi.py')
                if exists(sitefile) and not sitefile in self._site_loaded:
                    self._load_site_cubicweb(sitefile)
                    self._site_loaded.add(sitefile)
                    self.warning('[3.5] site_erudi.py is deprecated, should be '
                                 'renamed to site_cubicweb.py')

    def _load_site_cubicweb(self, sitefile):
        # XXX extrapath argument to load_module_from_file only in lgc > 0.46
        from logilab.common.modutils import load_module_from_modpath, modpath_from_file
        def load_module_from_file(filepath, path=None, use_sys=1, extrapath=None):
            return load_module_from_modpath(modpath_from_file(filepath, extrapath),
                                            path, use_sys)
        module = load_module_from_file(sitefile, extrapath=self.extrapath)
        self.info('%s loaded', sitefile)
        # cube specific options
        if getattr(module, 'options', None):
            self.register_options(module.options)
            self.load_defaults()

    def load_configuration(self):
        """load instance's configuration files"""
        super(CubicWebConfiguration, self).load_configuration()
        if self.apphome and self.set_language:
            # init gettext
            self._set_language()

    def init_log(self, logthreshold=None, debug=False, force=False):
        """init the log service"""
        if not force and hasattr(self, '_logging_initialized'):
            return
        self._logging_initialized = True
        CubicWebNoAppConfiguration.init_log(self, logthreshold, debug,
                                            logfile=self.get('log-file'))
        # read a config file if it exists
        logconfig = join(self.apphome, 'logging.conf')
        if exists(logconfig):
            logging.fileConfig(logconfig)

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

    def _set_language(self):
        """set language for gettext"""
        from gettext import translation
        path = join(self.apphome, 'i18n')
        for language in self.available_languages():
            self.info("loading language %s", language)
            try:
                tr = translation('cubicweb', path, languages=[language])
                self.translations[language] = (tr.ugettext, tr.upgettext)
            except (ImportError, AttributeError, IOError):
                self.exception('localisation support error for language %s',
                               language)

    def vregistry_path(self):
        """return a list of files or directories where the registry will look
        for application objects
        """
        templpath = list(reversed(self.cubes_path()))
        if self.apphome: # may be unset in tests
            templpath.append(self.apphome)
        return self.build_vregistry_path(templpath)

    def set_sources_mode(self, sources):
        if not 'all' in sources:
            print 'warning: ignoring specified sources, requires a repository '\
                  'configuration'

    def migration_handler(self):
        """return a migration handler instance"""
        from cubicweb.migration import MigrationHelper
        return MigrationHelper(self, verbosity=self.verbosity)

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

    def sendmails(self, msgs):
        """msgs: list of 2-uple (message object, recipients). Return False
        if connection to the smtp server failed, else True.
        """
        server, port = self['smtp-host'], self['smtp-port']
        SMTP_LOCK.acquire()
        try:
            try:
                smtp = SMTP(server, port)
            except Exception, ex:
                self.exception("can't connect to smtp server %s:%s (%s)",
                               server, port, ex)
                return False
            heloaddr = '%s <%s>' % (self['sender-name'], self['sender-addr'])
            for msg, recipients in msgs:
                try:
                    smtp.sendmail(heloaddr, recipients, msg.as_string())
                except Exception, ex:
                    self.exception("error sending mail to %s (%s)",
                                   recipients, ex)
            smtp.close()
        finally:
            SMTP_LOCK.release()
        return True

set_log_methods(CubicWebConfiguration, logging.getLogger('cubicweb.configuration'))

# alias to get a configuration instance from an instance id
instance_configuration = CubicWebConfiguration.config_for
application_configuration = deprecated('use instance_configuration')(instance_configuration)


_EXT_REGISTERED = False
def register_stored_procedures():
    from logilab.database import FunctionDescr
    from rql.utils import register_function, iter_funcnode_variables

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
        rtype = 'String'

        def st_description(self, funcnode, mainindex, tr):
            return funcnode.children[0].get_description(mainindex, tr)

    register_function(LIMIT_SIZE)


    class TEXT_LIMIT_SIZE(LIMIT_SIZE):
        supported_backends = ('mysql', 'postgres', 'sqlite',)

    register_function(TEXT_LIMIT_SIZE)


    class FSPATH(FunctionDescr):
        """return path of some bytes attribute stored using the Bytes
        File-System Storage (bfss)
        """
        rtype = 'Bytes' # XXX return a String? potential pb with fs encoding

        def update_cb_stack(self, stack):
            assert len(stack) == 1
            stack[0] = self.source_execute

        def as_sql(self, backend, args):
            raise NotImplementedError('source only callback')

        def source_execute(self, source, value):
            fpath = source.binary_to_str(value)
            try:
                return Binary(fpath)
            except OSError, ex:
                self.critical("can't open %s: %s", fpath, ex)
                return None

    register_function(FSPATH)
