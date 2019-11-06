# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""the cubicweb-ctl tool, based on logilab.common.clcommands to
provide a pluggable commands system.
"""
# *ctl module should limit the number of import to be imported as quickly as
# possible (for cubicweb-ctl reactivity, necessary for instance for usable bash
# completion). So import locally in command helpers.
import os
import sys
import traceback
from warnings import filterwarnings
from os import listdir
from os.path import exists, join, isdir

try:
    from os import kill, getpgid
except ImportError:
    def kill(*args):
        """win32 kill implementation"""
    def getpgid():
        """win32 getpgid implementation"""

from logilab.common.clcommands import CommandLine
from logilab.common.shellutils import ASK
from logilab.common.configuration import merge_options
from logilab.common.decorators import clear_cache

from cubicweb import ConfigurationError, ExecutionError, BadCommandUsage, utils
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg, CONFIGURATIONS
from cubicweb.server import set_debug
from cubicweb.toolsutils import Command, rm, create_dir, underline_title
from cubicweb.__pkginfo__ import version as cw_version

LOG_LEVELS = ('debug', 'info', 'warning', 'error')
DBG_FLAGS = ('RQL', 'SQL', 'REPO', 'HOOKS', 'OPS', 'SEC', 'MORE', 'ALL')

# don't check duplicated commands, it occurs when reloading site_cubicweb
CWCTL = CommandLine('cubicweb-ctl', 'The CubicWeb swiss-knife.',
                    version=cw_version, check_duplicated_command=False)


def wait_process_end(pid, maxtry=10, waittime=1):
    """wait for a process to actually die"""
    import signal
    from time import sleep
    nbtry = 0
    while nbtry < maxtry:
        try:
            kill(pid, signal.SIGUSR1)
        except (OSError, AttributeError):  # XXX win32
            break
        nbtry += 1
        sleep(waittime)
    else:
        raise ExecutionError('can\'t kill process %s' % pid)


def list_instances(regdir):
    if isdir(regdir):
        return sorted(idir for idir in listdir(regdir) if isdir(join(regdir, idir)))
    else:
        return []


def detect_available_modes(templdir):
    modes = []
    for fname in ('schema', 'schema.py'):
        if exists(join(templdir, fname)):
            modes.append('repository')
            break
    for fname in ('data', 'views', 'views.py'):
        if exists(join(templdir, fname)):
            modes.append('web ui')
            break
    return modes


def available_cube_names(cwcfg):
    """Return a list of available cube names, with 'cubicweb_' prefix dropped.
    """
    def drop_prefix(cube):
        prefix = 'cubicweb_'
        if cube.startswith(prefix):
            cube = cube[len(prefix):]
        return cube

    return [drop_prefix(cube) for cube in cwcfg.available_cubes()]


class InstanceCommand(Command):
    """base class for command taking one instance id as arguments"""
    arguments = '<instance>'

    # enforce having one instance
    min_args = 0
    max_args = 1

    options = (
        ("force",
         {'short': 'f', 'action': 'store_true',
          'default': False,
          'help': 'force command without asking confirmation',
          }
         ),
        ("pdb",
         {'action': 'store_true', 'default': False,
          'help': 'launch pdb on exception',
          }
         ),
        ("loglevel",
         {'type': 'choice', 'default': None, 'metavar': '<log level>',
          'choices': LOG_LEVELS, 'short': 'l',
          'help': 'allow to specify log level for debugging (choices: %s)'
                  % (', '.join(LOG_LEVELS)),
          }
         ),
        ('dbglevel',
         {'type': 'multiple_choice', 'metavar': '<debug level>',
          'default': None,
          'choices': DBG_FLAGS,
          'help': ('Set the server debugging flags; you may choose several '
                   'values in %s; imply "debug" loglevel if loglevel is not set' % (DBG_FLAGS,)),
          }),
    )
    actionverb = None

    def run(self, args):
        """run the <command>_method on each argument (a list of instance
        identifiers)
        """
        if not args:
            if "CW_INSTANCE" in os.environ:
                appid = os.environ["CW_INSTANCE"]
            else:
                raise BadCommandUsage("Error: instance id is missing")
        else:
            appid = args[0]

        cmdmeth = getattr(self, '%s_instance' % self.name)

        traceback_ = None

        # debugmode=True is to force to have a StreamHandler used instead of
        # writting the logs into a file in /tmp
        self.cwconfig = cwcfg.config_for(appid, debugmode=True)

        # by default loglevel is 'error' but we keep the default value to None
        # because some subcommands (e.g: pyramid) can override the loglevel in
        # certain situations if it's not explicitly set by the user and we want
        # to detect that (the "None" case)
        if self['loglevel'] is None:
            # if no loglevel is set but dbglevel is here we want to set level to debug
            if self['dbglevel']:
                init_cmdline_log_threshold(self.cwconfig, 'debug')
            else:
                init_cmdline_log_threshold(self.cwconfig, 'error')
        else:
            init_cmdline_log_threshold(self.cwconfig, self['loglevel'])

        if self['dbglevel']:
            set_debug('|'.join('DBG_' + x.upper() for x in self['dbglevel']))

        try:
            status = cmdmeth(appid) or 0
        except (ExecutionError, ConfigurationError) as ex:
            # we need to do extract this information here for pdb since it is
            # now lost in python 3 once we exit the try/catch statement
            exception_type, exception, traceback_ = sys.exc_info()

            sys.stderr.write('instance %s not %s: %s\n' % (
                appid, self.actionverb, ex))
            status = 4
        except Exception as ex:
            # idem
            exception_type, exception, traceback_ = sys.exc_info()

            traceback.print_exc()

            sys.stderr.write('instance %s not %s: %s\n' % (
                appid, self.actionverb, ex))
            status = 8

        except (KeyboardInterrupt, SystemExit) as ex:
            # idem
            exception_type, exception, traceback_ = sys.exc_info()

            sys.stderr.write('%s aborted\n' % self.name)
            if isinstance(ex, KeyboardInterrupt):
                status = 2  # specific error code
            else:
                status = ex.code

        if status != 0 and self.config.pdb:
            pdb = utils.get_pdb()

            if traceback_ is not None:
                pdb.post_mortem(traceback_)
            else:
                print("WARNING: Could not access to the traceback because the command return "
                      "code is different than 0 but the command didn't raised an exception.")
                # we can't use "header=" of set_trace because ipdb doesn't supports it
                pdb.set_trace()

        sys.exit(status)


# base commands ###############################################################

class ListCommand(Command):
    """List configurations, cubes and instances.

    List available configurations, installed cubes, and registered instances.

    If given, the optional argument allows to restrict listing only a category of items.
    """
    name = 'list'
    arguments = '[all|cubes|configurations|instances]'
    options = (
        ('verbose',
         {'short': 'v', 'action': 'store_true',
          'help': "display more information."}),
    )

    def run(self, args):
        """run the command with its specific arguments"""
        if not args:
            mode = 'all'
        elif len(args) == 1:
            mode = args[0]
        else:
            raise BadCommandUsage('Too many arguments')

        from cubicweb.migration import ConfigurationProblem

        if mode == 'all':
            print('CubicWeb %s (%s mode)' % (cwcfg.cubicweb_version(), cwcfg.mode))
            print()

        if mode in ('all', 'config', 'configurations'):
            cwcfg.load_available_configs()
            print('Available configurations:')
            for config in CONFIGURATIONS:
                print('*', config.name)
                for line in config.__doc__.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    print('   ', line)
            print()

        if mode in ('all', 'cubes'):
            cfgpb = ConfigurationProblem(cwcfg)
            try:
                cube_names = available_cube_names(cwcfg)
                namesize = max(len(x) for x in cube_names)
            except ConfigurationError as ex:
                print('No cubes available:', ex)
            except ValueError:
                print('No cubes available')
            else:
                print('Available cubes:')
                for cube in cube_names:
                    try:
                        tinfo = cwcfg.cube_pkginfo(cube)
                        tversion = tinfo.version
                        cfgpb.add_cube(cube, tversion)
                    except (ConfigurationError, AttributeError) as ex:
                        tinfo = None
                        tversion = '[missing cube information: %s]' % ex
                    print('* %s %s' % (cube.ljust(namesize), tversion))
                    if self.config.verbose:
                        if tinfo:
                            descr = getattr(tinfo, 'description', '')
                            if not descr:
                                descr = tinfo.__doc__
                            if descr:
                                print('    ' + '    \n'.join(descr.splitlines()))
                        modes = detect_available_modes(cwcfg.cube_dir(cube))
                        print('    available modes: %s' % ', '.join(modes))
            print()

        if mode in ('all', 'instances'):
            try:
                regdir = cwcfg.instances_dir()
            except ConfigurationError as ex:
                print('No instance available:', ex)
                print()
                return
            instances = list_instances(regdir)
            if instances:
                print('Available instances (%s):' % regdir)
                for appid in instances:
                    modes = cwcfg.possible_configurations(appid)
                    if not modes:
                        print('* %s (BROKEN instance, no configuration found)' % appid)
                        continue
                    print('* %s (%s)' % (appid, ', '.join(modes)))
                    try:
                        config = cwcfg.config_for(appid, modes[0])
                    except Exception as exc:
                        print('    (BROKEN instance, %s)' % exc)
                        continue
            else:
                print('No instance available in %s' % regdir)
            print()

        if mode == 'all':
            # configuration management problem solving
            cfgpb.solve()
            if cfgpb.warnings:
                print('Warnings:\n', '\n'.join('* ' + txt for txt in cfgpb.warnings))
            if cfgpb.errors:
                print('Errors:')
                for op, cube, version, src in cfgpb.errors:
                    if op == 'add':
                        print('* cube', cube, end=' ')
                        if version:
                            print(' version', version, end=' ')
                        print('is not installed, but required by %s' % src)
                    else:
                        print(
                            '* cube %s version %s is installed, but version %s is required by %s'
                            % (cube, cfgpb.cubes[cube], version, src)
                        )


def check_options_consistency(config):
    if config.automatic and config.config_level > 0:
        raise BadCommandUsage('--automatic and --config-level should not be '
                              'used together')


class CreateInstanceCommand(Command):
    """Create an instance from a cube. This is a unified
    command which can handle web / server / all-in-one installation
    according to available parts of the software library and of the
    desired cube.

    <cube>
      the name of cube to use (list available cube names using
      the "list" command). You can use several cubes by separating
      them using comma (e.g. 'jpl,email')
    <instance>
      an identifier for the instance to create
    """
    name = 'create'
    arguments = '<cube> <instance>'
    min_args = max_args = 2
    options = (
        ('automatic',
         {'short': 'a', 'action': 'store_true',
          'default': False,
          'help': 'automatic mode: never ask and use default answer to every '
          'question. this may require that your login match a database super '
          'user (allowed to create database & all).',
          }),
        ('config-level',
         {'short': 'l', 'type': 'int', 'metavar': '<level>',
          'default': 0,
          'help': 'configuration level (0..2): 0 will ask for essential '
          'configuration parameters only while 2 will ask for all parameters',
          }),
        ('config',
         {'short': 'c', 'type': 'choice', 'metavar': '<install type>',
          'choices': ('all-in-one', 'repository', 'pyramid'),
          'default': 'all-in-one',
          'help': 'installation type, telling which part of an instance '
          'should be installed. You can list available configurations using the'
          ' "list" command. Default to "all-in-one", e.g. an installation '
          'embedding both the RQL repository and the web server.',
          }),
        ('no-db-create',
         {'short': 'S',
          'action': 'store_true',
          'default': False,
          'help': 'stop after creation and do not continue with db-create',
          }),
    )

    def run(self, args):
        """run the command with its specific arguments"""
        from logilab.common.textutils import splitstrip
        check_options_consistency(self.config)
        configname = self.config.config
        cubes, appid = args
        cubes = splitstrip(cubes)
        # get the configuration and helper
        config = cwcfg.config_for(appid, configname, creating=True)
        cubes = config.expand_cubes(cubes)
        config.init_cubes(cubes)
        helper = self.config_helper(config)
        # check the cube exists
        try:
            templdirs = [cwcfg.cube_dir(cube)
                         for cube in cubes]
        except ConfigurationError as ex:
            print(ex)
            print('\navailable cubes:', end=' ')
            print(', '.join(available_cube_names(cwcfg)))
            return
        # create the registry directory for this instance
        print('\n' + underline_title('Creating the instance %s' % appid))
        create_dir(config.apphome)
        # cubicweb-ctl configuration
        if not self.config.automatic:
            print('\n' + underline_title('Configuring the instance (%s.conf)'
                                         % configname))
            config.input_config('main', self.config.config_level)
        # configuration'specific stuff
        print()
        helper.bootstrap(cubes, self.config.automatic, self.config.config_level)
        # input for cubes specific options
        if not self.config.automatic:
            sections = set(sect.lower() for sect, opt, odict in config.all_options()
                           if 'type' in odict
                           and odict.get('level', 0) <= self.config.config_level)
            for section in sections:
                if section not in ('main', 'email', 'web'):
                    print('\n' + underline_title('%s options' % section))
                    config.input_config(section, self.config.config_level)
        # write down configuration
        config.save()
        print('-> generated config %s' % config.main_config_file())
        # handle i18n files structure
        # in the first cube given
        from cubicweb import i18n
        langs = [lang for lang, _ in i18n.available_catalogs(join(templdirs[0], 'i18n'))]
        errors = config.i18ncompile(langs)
        if errors:
            print('\n'.join(errors))
            if self.config.automatic \
                or not ASK.confirm('error while compiling message catalogs, '
                                   'continue anyway ?'):
                print('creation not completed')
                return
        # create the additional data directory for this instance
        if config.appdatahome != config.apphome:  # true in dev mode
            create_dir(config.appdatahome)
        create_dir(join(config.appdatahome, 'backup'))
        if config['uid']:
            from logilab.common.shellutils import chown
            # this directory should be owned by the uid of the server process
            print('set %s as owner of the data directory' % config['uid'])
            chown(config.appdatahome, config['uid'])
        print('\n-> creation done for %s\n' % repr(config.apphome)[1:-1])
        if not self.config.no_db_create:
            helper.postcreate(self.config.automatic, self.config.config_level)


class DeleteInstanceCommand(Command):
    """Delete an instance. Will remove instance's files and
    unregister it.
    """
    name = 'delete'
    arguments = '<instance>'
    min_args = max_args = 1

    def run(self, args):
        """run the command with its specific arguments"""
        appid = args[0]
        configs = [cwcfg.config_for(appid, configname)
                   for configname in cwcfg.possible_configurations(appid)]
        if not configs:
            raise ExecutionError('unable to guess configuration for %s' % appid)
        for config in configs:
            helper = self.config_helper(config, required=False)
            if helper:
                helper.cleanup()
        # remove home
        rm(config.apphome)
        # remove instance data directory
        try:
            rm(config.appdatahome)
        except OSError as ex:
            import errno
            if ex.errno != errno.ENOENT:
                raise
        confignames = ', '.join([config.name for config in configs])
        print('-> instance %s (%s) deleted.' % (appid, confignames))


# instance commands ########################################################

def init_cmdline_log_threshold(config, loglevel):
    if loglevel is not None:
        config.global_set_option('log-threshold', loglevel.upper())
        config.init_log(config['log-threshold'], force=True)


class UpgradeInstanceCommand(InstanceCommand):
    """Upgrade an instance after cubicweb and/or component(s) upgrade.

    For repository update, you will be prompted for a login / password to use
    to connect to the system database.  For some upgrades, the given user
    should have create or alter table permissions.

    <instance>
      identifier of the instance to upgrade.
    """
    name = 'upgrade'
    actionverb = 'upgraded'
    options = InstanceCommand.options + (
        ('force-cube-version',
         {'short': 't', 'type': 'named', 'metavar': 'cube1:X.Y.Z,cube2:X.Y.Z',
          'default': None,
          'help': 'force migration from the indicated version for the specified cube(s).'}),

        ('force-cubicweb-version',
         {'short': 'e', 'type': 'string', 'metavar': 'X.Y.Z',
          'default': None,
          'help': 'force migration from the indicated cubicweb version.'}),

        ('fs-only',
         {'short': 's', 'action': 'store_true',
          'default': False,
          'help': 'only upgrade files on the file system, not the database.'}),

        ('no-config-update',
         {'short': 'C', 'action': 'store_true',
          'default': False,
          'help': 'do NOT update config file if set.'}),

        ('verbosity',
         {'short': 'v', 'type': 'int', 'metavar': '<0..2>',
          'default': 1,
          'help': "0: no confirmation, 1: only main commands confirmed, 2 ask \
for everything."}),

        ('backup-db',
         {'short': 'b', 'type': 'yn', 'metavar': '<y or n>',
          'default': None,
          'help': "Backup the instance database before upgrade.\n"
          "If the option is ommitted, confirmation will be ask.",
          }),

        ('ext-sources',
         {'short': 'E', 'type': 'csv', 'metavar': '<sources>',
          'default': None,
          'help': "For multisources instances, specify to which sources the \
repository should connect to for upgrading. When unspecified or 'migration' is \
given, appropriate sources for migration will be automatically selected \
(recommended). If 'all' is given, will connect to all defined sources.",
          }),
    )

    def upgrade_instance(self, appid):
        print('\n' + underline_title('Upgrading the instance %s' % appid))
        from logilab.common.changelog import Version
        config = cwcfg.config_for(appid)
        config.repairing = True  # notice we're not starting the server
        config.verbosity = self.config.verbosity
        set_sources_mode = getattr(config, 'set_sources_mode', None)
        if set_sources_mode is not None:
            set_sources_mode(self.config.ext_sources or ('migration',))
        # get instance and installed versions for the server and the componants
        mih = config.migration_handler()
        repo = mih.repo
        vcconf = repo.get_versions()
        helper = self.config_helper(config, required=False)
        if self.config.force_cube_version:
            for cube, version in self.config.force_cube_version.items():
                vcconf[cube] = Version(version)
        toupgrade = []
        for cube in config.cubes():
            installedversion = config.cube_version(cube)
            try:
                applversion = vcconf[cube]
            except KeyError:
                config.error('no version information for %s' % cube)
                continue
            if installedversion > applversion:
                toupgrade.append((cube, applversion, installedversion))
        cubicwebversion = config.cubicweb_version()
        if self.config.force_cubicweb_version:
            applcubicwebversion = Version(self.config.force_cubicweb_version)
            vcconf['cubicweb'] = applcubicwebversion
        else:
            applcubicwebversion = vcconf.get('cubicweb')
        if cubicwebversion > applcubicwebversion:
            toupgrade.append(('cubicweb', applcubicwebversion, cubicwebversion))
        # run cubicweb/componants migration scripts
        if self.config.fs_only or toupgrade:
            for cube, fromversion, toversion in toupgrade:
                print('-> migration needed from %s to %s for %s' % (fromversion, toversion, cube))
            with mih.cnx:
                with mih.cnx.security_enabled(False, False):
                    mih.migrate(vcconf, reversed(toupgrade), self.config)
            clear_cache(config, 'instance_md5_version')
        else:
            print('-> no data migration needed for instance %s.' % appid)
        # rewrite main configuration file
        if not self.config.no_config_update:
            mih.rewrite_configuration()
        mih.shutdown()
        # handle i18n upgrade
        if not self.i18nupgrade(config):
            return
        print()
        if helper:
            helper.postupgrade(repo)
        print('-> instance migrated.')
        print()

    def i18nupgrade(self, config):
        # handle i18n upgrade:
        # * install new languages
        # * recompile catalogs
        # XXX search available language in the first cube given
        from cubicweb import i18n
        templdir = cwcfg.cube_dir(config.cubes()[0])
        langs = [lang for lang, _ in i18n.available_catalogs(join(templdir, 'i18n'))]
        errors = config.i18ncompile(langs)
        if errors:
            print('\n'.join(errors))
            if not ASK.confirm('Error while compiling message catalogs, '
                               'continue anyway?'):
                print('-> migration not completed.')
                return False
        return True


class ListVersionsInstanceCommand(InstanceCommand):
    """List versions used by an instance.

    <instance>...
      identifiers of the instances to list versions for.
    """
    name = 'versions'

    def versions_instance(self, appid):
        config = self.cwconfig
        # should not raise error if db versions don't match fs versions
        config.repairing = True
        # no need to load all appobjects and schema
        config.quick_start = True
        if hasattr(config, 'set_sources_mode'):
            config.set_sources_mode(('migration',))
        vcconf = config.repository().get_versions()
        for key in sorted(vcconf):
            print(key + ': %s.%s.%s' % vcconf[key])


class ShellCommand(Command):
    """Run an interactive migration shell on an instance. This is a python shell
    with enhanced migration commands predefined in the namespace. An additional
    argument may be given corresponding to a file containing commands to execute
    in batch mode.

    By default it will connect to a local instance using an in memory
    connection, unless a URL to a running instance is specified.

    Arguments after bare "--" string will not be processed by the shell command
    You can use it to pass extra arguments to your script and expect for
    them in '__args__' afterwards.

    <instance>
      the identifier of the instance to connect.
    """
    name = 'shell'
    arguments = '<instance> [batch command file(s)] [-- <script arguments>]'
    min_args = 1
    max_args = None
    options = merge_options((
        ('system-only',
         {'short': 'S', 'action': 'store_true',
          'help': 'only connect to the system source when the instance is '
          'using multiple sources. You can\'t use this option and the '
          '--ext-sources option at the same time.',
          'group': 'local'
          }),

        ('ext-sources',
         {'short': 'E', 'type': 'csv', 'metavar': '<sources>',
          'help': "For multisources instances, specify to which sources the \
repository should connect to for upgrading. When unspecified or 'all' given, \
will connect to all defined sources. If 'migration' is given, appropriate \
sources for migration will be automatically selected.",
          'group': 'local'
          }),

        ('force',
         {'short': 'f', 'action': 'store_true',
          'help': 'don\'t check instance is up to date.',
          'group': 'local'
          }),

    ) + InstanceCommand.options)

    def _get_mih(self, appid):
        """ returns migration context handler & shutdown function """
        config = cwcfg.config_for(appid)
        if self.config.ext_sources:
            assert not self.config.system_only
            sources = self.config.ext_sources
        elif self.config.system_only:
            sources = ('system',)
        else:
            sources = ('all',)
        config.set_sources_mode(sources)
        config.repairing = self.config.force
        mih = config.migration_handler()
        return mih, lambda: mih.shutdown()

    def run(self, args):
        appuri = args.pop(0)
        mih, shutdown_callback = self._get_mih(appuri)
        try:
            with mih.cnx:
                with mih.cnx.security_enabled(False, False):
                    if args:
                        # use cmdline parser to access left/right attributes only
                        # remember that usage requires instance appid as first argument
                        scripts, args = self.cmdline_parser.largs[1:], self.cmdline_parser.rargs
                        for script in scripts:
                            mih.cmd_process_script(script, scriptargs=args)
                            mih.commit()
                    else:
                        mih.interactive_shell()
        finally:
            shutdown_callback()


class RecompileInstanceCatalogsCommand(InstanceCommand):
    """Recompile i18n catalogs for instances.

    <instance>
      identifier of the instance to consider.
    """
    name = 'i18ninstance'

    def i18ninstance_instance(self, appid):
        """recompile instance's messages catalogs"""
        config = self.cwconfig
        config.quick_start = True  # notify this is not a regular start
        repo = config.repository()
        if config._cubes is None:
            # web only config
            config.init_cubes(repo.get_cubes())
        errors = config.i18ncompile()
        if errors:
            print('\n'.join(errors))


class ListInstancesCommand(Command):
    """list available instances, useful for bash completion."""
    name = 'listinstances'
    hidden = True

    def run(self, args):
        """run the command with its specific arguments"""
        regdir = cwcfg.instances_dir()
        for appid in sorted(listdir(regdir)):
            print(appid)


class ListCubesCommand(Command):
    """list available componants, useful for bash completion."""
    name = 'listcubes'
    hidden = True

    def run(self, args):
        """run the command with its specific arguments"""
        for cube in cwcfg.available_cubes():
            print(cube)


class ConfigureInstanceCommand(InstanceCommand):
    """Configure instance.

    <instance>
      identifier of the instance to configure.
    """
    name = 'configure'
    actionverb = 'configured'

    options = merge_options(
        InstanceCommand.options + (
            ('param',
             {'short': 'p', 'type': 'named', 'metavar': 'key1:value1,key2:value2',
              'default': None,
              'help': 'set <key> to <value> in configuration file.'}),
        ),
    )

    def configure_instance(self, appid):
        if self.config.param is not None:
            appcfg = self.cwconfig
            for key, value in self.config.param.items():
                try:
                    appcfg.global_set_option(key, value)
                except KeyError:
                    raise ConfigurationError(
                        'unknown configuration key "%s" for mode %s' % (key, appcfg.name))
            appcfg.save()


for cmdcls in (ListCommand,
               CreateInstanceCommand, DeleteInstanceCommand,
               UpgradeInstanceCommand,
               ListVersionsInstanceCommand,
               ShellCommand,
               RecompileInstanceCatalogsCommand,
               ListInstancesCommand, ListCubesCommand,
               ConfigureInstanceCommand,
               ):
    CWCTL.register(cmdcls)


def run(args=sys.argv[1:]):
    """command line tool"""
    filterwarnings('default', category=DeprecationWarning)
    cwcfg.load_cwctl_plugins()
    try:
        CWCTL.run(args)
    except ConfigurationError as err:
        print('ERROR: ', err)
        sys.exit(1)
    except ExecutionError as err:
        print(err)
        sys.exit(2)


if __name__ == '__main__':
    run()
