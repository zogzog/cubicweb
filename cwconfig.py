# -*- coding: utf-8 -*-
"""common configuration utilities for cubicweb

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr

.. envvar:: CW_CUBES_PATH

   Augments the default search path for cubes

:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

import sys
import os
import logging
from smtplib import SMTP
from threading import Lock
from os.path import exists, join, expanduser, abspath, normpath, basename, isdir
import tempfile

from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods, init_log
from logilab.common.configuration import (Configuration, Method,
                                          ConfigurationMixIn, merge_options)

from cubicweb import CW_SOFTWARE_ROOT, CW_MIGRATION_MAP, ConfigurationError
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
    according to *-ctl files
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
      'default': 40,
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

    if os.environ.get('APYCOT_ROOT'):
        mode = 'test'
        CUBES_DIR = '%(APYCOT_ROOT)s/local/share/cubicweb/cubes/' % os.environ
        # create __init__ file
        file(join(CUBES_DIR, '__init__.py'), 'w').close()
    elif (exists(join(CW_SOFTWARE_ROOT, '.hg')) and _forced_mode != 'system') or _forced_mode == 'user':
        mode = 'dev'
        CUBES_DIR = abspath(normpath(join(CW_SOFTWARE_ROOT, '../cubes')))
    else:
        mode = 'installed'
        CUBES_DIR = '/usr/share/cubicweb/cubes/'

    options = (
       ('log-threshold',
         {'type' : 'string', # XXX use a dedicated type?
          'default': 'ERROR',
          'help': 'server\'s log level',
          'group': 'main', 'inputlevel': 1,
          }),
        # pyro name server
        ('pyro-ns-host',
         {'type' : 'string',
          'default': '',
          'help': 'Pyro name server\'s host. If not set, will be detected by a \
broadcast query. It may contains port information using <host>:<port> notation.',
          'group': 'pyro-name-server', 'inputlevel': 1,
          }),
        ('pyro-ns-group',
         {'type' : 'string',
          'default': 'cubicweb',
          'help': 'Pyro name server\'s group where the repository will be \
registered.',
          'group': 'pyro-name-server', 'inputlevel': 1,
          }),
        # common configuration options which are potentially required as soon as
        # you're using "base" application objects (ie to really server/web
        # specific)
        ('base-url',
         {'type' : 'string',
          'default': None,
          'help': 'web server root url',
          'group': 'main', 'inputlevel': 1,
          }),
        ('allow-email-login',
         {'type' : 'yn',
          'default': False,
          'help': 'allow users to login with their primary email if set',
          'group': 'main', 'inputlevel': 2,
          }),
        ('use-request-subdomain',
         {'type' : 'yn',
          'default': None,
          'help': ('if set, base-url subdomain is replaced by the request\'s '
                   'host, to help managing sites with several subdomains in a '
                   'single cubicweb instance'),
          'group': 'main', 'inputlevel': 1,
          }),
        ('mangle-emails',
         {'type' : 'yn',
          'default': False,
          'help': "don't display actual email addresses but mangle them if \
this option is set to yes",
          'group': 'email', 'inputlevel': 2,
          }),
        ('disable-appobjects',
         {'type' : 'csv', 'default': (),
          'help': 'comma separated list of identifiers of application objects (<registry>.<oid>) to disable',
          'group': 'appobjects', 'inputlevel': 2,
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
        if cls.mode in ('dev', 'test') and not os.environ.get('APYCOT_ROOT'):
            return join(CW_SOFTWARE_ROOT, 'web')
        return cls.cube_dir('shared')

    @classmethod
    def i18n_lib_dir(cls):
        """return instance's i18n directory"""
        if cls.mode in ('dev', 'test') and not os.environ.get('APYCOT_ROOT'):
            return join(CW_SOFTWARE_ROOT, 'i18n')
        return join(cls.shared_dir(), 'i18n')

    @classmethod
    def available_cubes(cls):
        cubes = set()
        for directory in cls.cubes_search_path():
            for cube in os.listdir(directory):
                if isdir(join(directory, cube)) and not cube in ('CVS', '.svn', 'shared', '.hg'):
                    cubes.add(cube)
        return sorted(cubes)

    @classmethod
    def cubes_search_path(cls):
        """return the path of directories where cubes should be searched"""
        path = []
        try:
            for directory in os.environ['CW_CUBES_PATH'].split(os.pathsep):
                directory = abspath(normpath(directory))
                if exists(directory) and not directory in path:
                    path.append(directory)
        except KeyError:
            pass
        if not cls.CUBES_DIR in path:
            path.append(cls.CUBES_DIR)
        return path

    @classmethod
    def cube_dir(cls, cube):
        """return the cube directory for the given cube id,
        raise ConfigurationError if it doesn't exists
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
            return getattr(__import__('cubes.%s.__pkginfo__' % cube), cube).__pkginfo__
        except Exception, ex:
            raise ConfigurationError('unable to find packaging information for '
                                     'cube %s (%s: %s)' % (cube, ex.__class__.__name__, ex))

    @classmethod
    def cube_version(cls, cube):
        """return the version of the cube located in the given directory
        """
        from logilab.common.changelog import Version
        version = cls.cube_pkginfo(cube).numversion
        assert len(version) == 3, version
        return Version(version)

    @classmethod
    def cube_dependencies(cls, cube):
        """return cubicweb cubes used by the given cube"""
        return getattr(cls.cube_pkginfo(cube), '__use__', ())

    @classmethod
    def cube_recommends(cls, cube):
        """return cubicweb cubes recommended by the given cube"""
        return getattr(cls.cube_pkginfo(cube), '__recommend__', ())

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
        from logilab.common.graph import get_cycles
        graph = {}
        for cube in cubes:
            cube = CW_MIGRATION_MAP.get(cube, cube)
            deps = cls.cube_dependencies(cube) + \
                   cls.cube_recommends(cube)
            graph[cube] = set(dep for dep in deps if dep in cubes)
        cycles = get_cycles(graph)
        if cycles:
            cycles = '\n'.join(' -> '.join(cycle) for cycle in cycles)
            raise ConfigurationError('cycles in cubes dependencies: %s'
                                     % cycles)
        cubes = []
        while graph:
            # sorted to get predictable results
            for cube, deps in sorted(graph.items()):
                if not deps:
                    cubes.append(cube)
                    del graph[cube]
                    for deps in graph.itervalues():
                        try:
                            deps.remove(cube)
                        except KeyError:
                            continue
        return tuple(reversed(cubes))

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
                        'server/serverctl.py', 'hercule.py',
                        'devtools/devctl.py', 'goa/goactl.py'):
            if exists(join(CW_SOFTWARE_ROOT, ctlfile)):
                try:
                    load_module_from_file(join(CW_SOFTWARE_ROOT, ctlfile))
                except ImportError, err:
                    cls.critical('could not import the command provider %s (cause : %s)' %
                                (ctlfile, err))
                cls.info('loaded cubicweb-ctl plugin %s', ctlfile)
        for cube in cls.available_cubes():
            pluginfile = join(cls.cube_dir(cube), 'ecplugin.py')
            initfile = join(cls.cube_dir(cube), '__init__.py')
            if exists(pluginfile):
                try:
                    __import__('cubes.%s.ecplugin' % cube)
                    cls.info('loaded cubicweb-ctl plugin from %s', cube)
                except:
                    cls.exception('while loading plugin %s', pluginfile)
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
        ConfigurationMixIn.__init__(self)
        self.adjust_sys_path()
        self.load_defaults()
        self.translations = {}

    def adjust_sys_path(self):
        self.cls_adjust_sys_path()

    def init_log(self, logthreshold=None, debug=False,
                 logfile=None, syslog=False):
        """init the log service"""
        if logthreshold is None:
            if debug:
                logthreshold = 'DEBUG'
            else:
                logthreshold = self['log-threshold']
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


class CubicWebConfiguration(CubicWebNoAppConfiguration):
    """base class for cubicweb server and web configurations"""

    INSTANCE_DATA_DIR = None
    if CubicWebNoAppConfiguration.mode == 'test':
        root = os.environ['APYCOT_ROOT']
        REGISTRY_DIR = '%s/etc/cubicweb.d/' % root
        RUNTIME_DIR = tempfile.gettempdir()
        MIGRATION_DIR = '%s/local/share/cubicweb/migration/' % root
        if not exists(REGISTRY_DIR):
            os.makedirs(REGISTRY_DIR)
    elif CubicWebNoAppConfiguration.mode == 'dev':
        REGISTRY_DIR = expanduser('~/etc/cubicweb.d/')
        RUNTIME_DIR = tempfile.gettempdir()
        MIGRATION_DIR = join(CW_SOFTWARE_ROOT, 'misc', 'migration')
    else: #mode = 'installed'
        REGISTRY_DIR = '/etc/cubicweb.d/'
        INSTANCE_DATA_DIR = '/var/lib/cubicweb/instances/'
        RUNTIME_DIR = '/var/run/cubicweb/'
        MIGRATION_DIR = '/usr/share/cubicweb/migration/'

    # for some commands (creation...) we don't want to initialize gettext
    set_language = True
    # set this to true to avoid false error message while creating an instance
    creating = False
    # set this to true to allow somethings which would'nt be possible
    repairing = False

    options = CubicWebNoAppConfiguration.options + (
        ('log-file',
         {'type' : 'string',
          'default': Method('default_log_file'),
          'help': 'file where output logs should be written',
          'group': 'main', 'inputlevel': 2,
          }),
        # email configuration
        ('smtp-host',
         {'type' : 'string',
          'default': 'mail',
          'help': 'hostname of the SMTP mail server',
          'group': 'email', 'inputlevel': 1,
          }),
        ('smtp-port',
         {'type' : 'int',
          'default': 25,
          'help': 'listening port of the SMTP mail server',
          'group': 'email', 'inputlevel': 1,
          }),
        ('sender-name',
         {'type' : 'string',
          'default': Method('default_instance_id'),
          'help': 'name used as HELO name for outgoing emails from the \
repository.',
          'group': 'email', 'inputlevel': 2,
          }),
        ('sender-addr',
         {'type' : 'string',
          'default': 'cubicweb@mydomain.com',
          'help': 'email address used as HELO address for outgoing emails from \
the repository',
          'group': 'email', 'inputlevel': 1,
          }),
        )

    @classmethod
    def runtime_dir(cls):
        """run time directory for pid file..."""
        return env_path('CW_RUNTIME_DIR', cls.RUNTIME_DIR, 'run time')

    @classmethod
    def registry_dir(cls):
        """return the control directory"""
        return env_path('CW_INSTANCES_DIR', cls.REGISTRY_DIR, 'registry')

    @classmethod
    def instance_data_dir(cls):
        """return the instance data directory"""
        return env_path('CW_INSTANCES_DATA_DIR',
                        cls.INSTANCE_DATA_DIR or cls.REGISTRY_DIR,
                        'additional data')

    @classmethod
    def migration_scripts_dir(cls):
        """cubicweb migration scripts directory"""
        return env_path('CW_MIGRATION_DIR', cls.MIGRATION_DIR, 'migration')

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
        home = join(cls.registry_dir(), appid)
        if not exists(home):
            raise ConfigurationError('no such instance %s (check it exists with "cubicweb-ctl list")' % appid)
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
        if self.mode == 'dev':
            basepath = join(tempfile.gettempdir(), '%s-%s' % (basename(self.appid), self.name))
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
        return join(self.runtime_dir(), '%s-%s.pid' % (self.appid, self.name))

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
        return join(self.registry_dir(), self.appid)

    @property
    def appdatahome(self):
        return join(self.instance_data_dir(), self.appid)

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
                    self.warning('site_erudi.py is deprecated, should be renamed to site_cubicweb.py')

    def _load_site_cubicweb(self, sitefile):
        context = {'__file__': sitefile}
        execfile(sitefile, context, context)
        self.info('%s loaded', sitefile)
        # cube specific options
        if context.get('options'):
            self.register_options(context['options'])
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

        take *args to be usable as a vocabulary method
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
                self.translations[language] = tr.ugettext
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
        from cubicweb.common.migration import MigrationHelper
        return MigrationHelper(self, verbosity=self.verbosity)

    def i18ncompile(self, langs=None):
        from cubicweb.common import i18n
        if langs is None:
            langs = self.available_languages()
        i18ndir = join(self.apphome, 'i18n')
        if not exists(i18ndir):
            create_dir(i18ndir)
        sourcedirs = [join(path, 'i18n') for path in self.cubes_path()]
        sourcedirs.append(self.i18n_lib_dir())
        return i18n.compile_i18n_catalogs(sourcedirs, i18ndir, langs)

    def sendmails(self, msgs):
        """msgs: list of 2-uple (message object, recipients)"""
        server, port = self['smtp-host'], self['smtp-port']
        SMTP_LOCK.acquire()
        try:
            try:
                smtp = SMTP(server, port)
            except Exception, ex:
                self.exception("can't connect to smtp server %s:%s (%s)",
                               server, port, ex)
                return
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

set_log_methods(CubicWebConfiguration, logging.getLogger('cubicweb.configuration'))

# alias to get a configuration instance from an instance id
instance_configuration = CubicWebConfiguration.config_for
application_configuration = deprecated('use instance_configuration')(instance_configuration)
