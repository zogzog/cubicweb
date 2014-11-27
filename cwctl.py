# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

__docformat__ = "restructuredtext en"

# *ctl module should limit the number of import to be imported as quickly as
# possible (for cubicweb-ctl reactivity, necessary for instance for usable bash
# completion). So import locally in command helpers.
import sys
from warnings import warn
from os import remove, listdir, system, pathsep
from os.path import exists, join, isfile, isdir, dirname, abspath
from urlparse import urlparse

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

from cubicweb import ConfigurationError, ExecutionError, BadCommandUsage
from cubicweb.utils import support_args
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg, CWDEV, CONFIGURATIONS
from cubicweb.toolsutils import Command, rm, create_dir, underline_title
from cubicweb.__pkginfo__ import version

# don't check duplicated commands, it occurs when reloading site_cubicweb
CWCTL = CommandLine('cubicweb-ctl', 'The CubicWeb swiss-knife.',
                    version=version, check_duplicated_command=False)

def wait_process_end(pid, maxtry=10, waittime=1):
    """wait for a process to actually die"""
    import signal
    from time import sleep
    nbtry = 0
    while nbtry < maxtry:
        try:
            kill(pid, signal.SIGUSR1)
        except (OSError, AttributeError): # XXX win32
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


class InstanceCommand(Command):
    """base class for command taking 0 to n instance id as arguments
    (0 meaning all registered instances)
    """
    arguments = '[<instance>...]'
    options = (
        ("force",
         {'short': 'f', 'action' : 'store_true',
          'default': False,
          'help': 'force command without asking confirmation',
          }
         ),
        )
    actionverb = None

    def ordered_instances(self):
        """return instances in the order in which they should be started,
        considering $REGISTRY_DIR/startorder file if it exists (useful when
        some instances depends on another as external source).

        Instance used by another one should appears first in the file (one
        instance per line)
        """
        regdir = cwcfg.instances_dir()
        _allinstances = list_instances(regdir)
        if isfile(join(regdir, 'startorder')):
            allinstances = []
            for line in file(join(regdir, 'startorder')):
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        _allinstances.remove(line)
                        allinstances.append(line)
                    except ValueError:
                        print ('ERROR: startorder file contains unexistant '
                               'instance %s' % line)
            allinstances += _allinstances
        else:
            allinstances = _allinstances
        return allinstances

    def run(self, args):
        """run the <command>_method on each argument (a list of instance
        identifiers)
        """
        if not args:
            args = self.ordered_instances()
            try:
                askconfirm = not self.config.force
            except AttributeError:
                # no force option
                askconfirm = False
        else:
            askconfirm = False
        self.run_args(args, askconfirm)

    def run_args(self, args, askconfirm):
        status = 0
        for appid in args:
            if askconfirm:
                print '*'*72
                if not ASK.confirm('%s instance %r ?' % (self.name, appid)):
                    continue
            try:
                status = max(status, self.run_arg(appid))
            except (KeyboardInterrupt, SystemExit):
                sys.stderr.write('%s aborted\n' % self.name)
                return 2 # specific error code
        sys.exit(status)

    def run_arg(self, appid):
        cmdmeth = getattr(self, '%s_instance' % self.name)
        try:
            status = cmdmeth(appid)
        except (ExecutionError, ConfigurationError) as ex:
            sys.stderr.write('instance %s not %s: %s\n' % (
                    appid, self.actionverb, ex))
            status = 4
        except Exception as ex:
            import traceback
            traceback.print_exc()
            sys.stderr.write('instance %s not %s: %s\n' % (
                    appid, self.actionverb, ex))
            status = 8
        return status

class InstanceCommandFork(InstanceCommand):
    """Same as `InstanceCommand`, but command is forked in a new environment
    for each argument
    """

    def run_args(self, args, askconfirm):
        if len(args) > 1:
            forkcmd = ' '.join(w for w in sys.argv if not w in args)
        else:
            forkcmd = None
        for appid in args:
            if askconfirm:
                print '*'*72
                if not ASK.confirm('%s instance %r ?' % (self.name, appid)):
                    continue
            if forkcmd:
                status = system('%s %s' % (forkcmd, appid))
                if status:
                    print '%s exited with status %s' % (forkcmd, status)
            else:
                self.run_arg(appid)


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
         {'short': 'v', 'action' : 'store_true',
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
            print 'CubicWeb %s (%s mode)' % (cwcfg.cubicweb_version(), cwcfg.mode)
            print

        if mode in ('all', 'config', 'configurations'):
            print 'Available configurations:'
            for config in CONFIGURATIONS:
                print '*', config.name
                for line in config.__doc__.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    print '   ', line
            print

        if mode in ('all', 'cubes'):
            cfgpb = ConfigurationProblem(cwcfg)
            try:
                cubesdir = pathsep.join(cwcfg.cubes_search_path())
                namesize = max(len(x) for x in cwcfg.available_cubes())
            except ConfigurationError as ex:
                print 'No cubes available:', ex
            except ValueError:
                print 'No cubes available in %s' % cubesdir
            else:
                print 'Available cubes (%s):' % cubesdir
                for cube in cwcfg.available_cubes():
                    try:
                        tinfo = cwcfg.cube_pkginfo(cube)
                        tversion = tinfo.version
                        cfgpb.add_cube(cube, tversion)
                    except (ConfigurationError, AttributeError) as ex:
                        tinfo = None
                        tversion = '[missing cube information: %s]' % ex
                    print '* %s %s' % (cube.ljust(namesize), tversion)
                    if self.config.verbose:
                        if tinfo:
                            descr = getattr(tinfo, 'description', '')
                            if not descr:
                                descr = tinfo.__doc__
                            if descr:
                                print '    '+ '    \n'.join(descr.splitlines())
                        modes = detect_available_modes(cwcfg.cube_dir(cube))
                        print '    available modes: %s' % ', '.join(modes)
            print

        if mode in ('all', 'instances'):
            try:
                regdir = cwcfg.instances_dir()
            except ConfigurationError as ex:
                print 'No instance available:', ex
                print
                return
            instances = list_instances(regdir)
            if instances:
                print 'Available instances (%s):' % regdir
                for appid in instances:
                    modes = cwcfg.possible_configurations(appid)
                    if not modes:
                        print '* %s (BROKEN instance, no configuration found)' % appid
                        continue
                    print '* %s (%s)' % (appid, ', '.join(modes))
                    try:
                        config = cwcfg.config_for(appid, modes[0])
                    except Exception as exc:
                        print '    (BROKEN instance, %s)' % exc
                        continue
            else:
                print 'No instance available in %s' % regdir
            print

        if mode == 'all':
            # configuration management problem solving
            cfgpb.solve()
            if cfgpb.warnings:
                print 'Warnings:\n', '\n'.join('* '+txt for txt in cfgpb.warnings)
            if cfgpb.errors:
                print 'Errors:'
                for op, cube, version, src in cfgpb.errors:
                    if op == 'add':
                        print '* cube', cube,
                        if version:
                            print ' version', version,
                        print 'is not installed, but required by %s' % src
                    else:
                        print '* cube %s version %s is installed, but version %s is required by %s' % (
                            cube, cfgpb.cubes[cube], version, src)

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
         {'short': 'a', 'action' : 'store_true',
          'default': False,
          'help': 'automatic mode: never ask and use default answer to every '
          'question. this may require that your login match a database super '
          'user (allowed to create database & all).',
          }),
        ('config-level',
         {'short': 'l', 'type' : 'int', 'metavar': '<level>',
          'default': 0,
          'help': 'configuration level (0..2): 0 will ask for essential '
          'configuration parameters only while 2 will ask for all parameters',
          }),
        ('config',
         {'short': 'c', 'type' : 'choice', 'metavar': '<install type>',
          'choices': ('all-in-one', 'repository'),
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
            print ex
            print '\navailable cubes:',
            print ', '.join(cwcfg.available_cubes())
            return
        # create the registry directory for this instance
        print '\n'+underline_title('Creating the instance %s' % appid)
        create_dir(config.apphome)
        # cubicweb-ctl configuration
        if not self.config.automatic:
            print '\n'+underline_title('Configuring the instance (%s.conf)'
                                       % configname)
            config.input_config('main', self.config.config_level)
        # configuration'specific stuff
        print
        helper.bootstrap(cubes, self.config.automatic, self.config.config_level)
        # input for cubes specific options
        if not self.config.automatic:
            sections = set(sect.lower() for sect, opt, odict in config.all_options()
                           if 'type' in odict
                           and odict.get('level') <= self.config.config_level)
            for section in sections:
                if section not in ('main', 'email', 'pyro', 'web'):
                    print '\n' + underline_title('%s options' % section)
                    config.input_config(section, self.config.config_level)
        # write down configuration
        config.save()
        self._handle_win32(config, appid)
        print '-> generated config %s' % config.main_config_file()
        # handle i18n files structure
        # in the first cube given
        from cubicweb import i18n
        langs = [lang for lang, _ in i18n.available_catalogs(join(templdirs[0], 'i18n'))]
        errors = config.i18ncompile(langs)
        if errors:
            print '\n'.join(errors)
            if self.config.automatic \
                   or not ASK.confirm('error while compiling message catalogs, '
                                      'continue anyway ?'):
                print 'creation not completed'
                return
        # create the additional data directory for this instance
        if config.appdatahome != config.apphome: # true in dev mode
            create_dir(config.appdatahome)
        create_dir(join(config.appdatahome, 'backup'))
        if config['uid']:
            from logilab.common.shellutils import chown
            # this directory should be owned by the uid of the server process
            print 'set %s as owner of the data directory' % config['uid']
            chown(config.appdatahome, config['uid'])
        print '\n-> creation done for %s\n' % repr(config.apphome)[1:-1]
        if not self.config.no_db_create:
            helper.postcreate(self.config.automatic, self.config.config_level)

    def _handle_win32(self, config, appid):
        if sys.platform != 'win32':
            return
        service_template = """
import sys
import win32serviceutil
sys.path.insert(0, r"%(CWPATH)s")

from cubicweb.etwist.service import CWService

classdict = {'_svc_name_': 'cubicweb-%(APPID)s',
             '_svc_display_name_': 'CubicWeb ' + '%(CNAME)s',
             'instance': '%(APPID)s'}
%(CNAME)sService = type('%(CNAME)sService', (CWService,), classdict)

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(%(CNAME)sService)
"""
        open(join(config.apphome, 'win32svc.py'), 'wb').write(
            service_template % {'APPID': appid,
                                'CNAME': appid.capitalize(),
                                'CWPATH': abspath(join(dirname(__file__), '..'))})


class DeleteInstanceCommand(Command):
    """Delete an instance. Will remove instance's files and
    unregister it.
    """
    name = 'delete'
    arguments = '<instance>'
    min_args = max_args = 1
    options = ()

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
        print '-> instance %s (%s) deleted.' % (appid, confignames)


# instance commands ########################################################

class StartInstanceCommand(InstanceCommandFork):
    """Start the given instances. If no instance is given, start them all.

    <instance>...
      identifiers of the instances to start. If no instance is
      given, start them all.
    """
    name = 'start'
    actionverb = 'started'
    options = (
        ("debug",
         {'short': 'D', 'action' : 'store_true',
          'help': 'start server in debug mode.'}),
        ("force",
         {'short': 'f', 'action' : 'store_true',
          'default': False,
          'help': 'start the instance even if it seems to be already \
running.'}),
        ('profile',
         {'short': 'P', 'type' : 'string', 'metavar': '<stat file>',
          'default': None,
          'help': 'profile code and use the specified file to store stats',
          }),
        ('loglevel',
         {'short': 'l', 'type' : 'choice', 'metavar': '<log level>',
          'default': None, 'choices': ('debug', 'info', 'warning', 'error'),
          'help': 'debug if -D is set, error otherwise',
          }),
        )

    def start_instance(self, appid):
        """start the instance's server"""
        try:
            import twisted  # noqa
        except ImportError:
            msg = (
                "Twisted is required by the 'start' command\n"
                "Either install it, or use one of the alternative commands:\n"
                "- '{ctl} wsgi {appid}'\n"
                "- '{ctl} pyramid {appid}' (requires the pyramid cube)\n")
            raise ExecutionError(msg.format(ctl='cubicweb-ctl', appid=appid))
        config = cwcfg.config_for(appid, debugmode=self['debug'])
        init_cmdline_log_threshold(config, self['loglevel'])
        if self['profile']:
            config.global_set_option('profile', self.config.profile)
        helper = self.config_helper(config, cmdname='start')
        pidf = config['pid-file']
        if exists(pidf) and not self['force']:
            msg = "%s seems to be running. Remove %s by hand if necessary or use \
the --force option."
            raise ExecutionError(msg % (appid, pidf))
        if helper.start_server(config) == 1:
            print 'instance %s started' % appid


def init_cmdline_log_threshold(config, loglevel):
    if loglevel is not None:
        config.global_set_option('log-threshold', loglevel.upper())
        config.init_log(config['log-threshold'], force=True)


class StopInstanceCommand(InstanceCommand):
    """Stop the given instances.

    <instance>...
      identifiers of the instances to stop. If no instance is
      given, stop them all.
    """
    name = 'stop'
    actionverb = 'stopped'

    def ordered_instances(self):
        instances = super(StopInstanceCommand, self).ordered_instances()
        instances.reverse()
        return instances

    def stop_instance(self, appid):
        """stop the instance's server"""
        config = cwcfg.config_for(appid)
        helper = self.config_helper(config, cmdname='stop')
        helper.poststop() # do this anyway
        pidf = config['pid-file']
        if not exists(pidf):
            sys.stderr.write("%s doesn't exist.\n" % pidf)
            return
        import signal
        pid = int(open(pidf).read().strip())
        try:
            kill(pid, signal.SIGTERM)
        except Exception:
            sys.stderr.write("process %s seems already dead.\n" % pid)
        else:
            try:
                wait_process_end(pid)
            except ExecutionError as ex:
                sys.stderr.write('%s\ntrying SIGKILL\n' % ex)
                try:
                    kill(pid, signal.SIGKILL)
                except Exception:
                    # probably dead now
                    pass
                wait_process_end(pid)
        try:
            remove(pidf)
        except OSError:
            # already removed by twistd
            pass
        print 'instance %s stopped' % appid


class RestartInstanceCommand(StartInstanceCommand):
    """Restart the given instances.

    <instance>...
      identifiers of the instances to restart. If no instance is
      given, restart them all.
    """
    name = 'restart'
    actionverb = 'restarted'

    def run_args(self, args, askconfirm):
        regdir = cwcfg.instances_dir()
        if not isfile(join(regdir, 'startorder')) or len(args) <= 1:
            # no specific startorder
            super(RestartInstanceCommand, self).run_args(args, askconfirm)
            return
        print ('some specific start order is specified, will first stop all '
               'instances then restart them.')
        # get instances in startorder
        for appid in args:
            if askconfirm:
                print '*'*72
                if not ASK.confirm('%s instance %r ?' % (self.name, appid)):
                    continue
            StopInstanceCommand(self.logger).stop_instance(appid)
        forkcmd = [w for w in sys.argv if not w in args]
        forkcmd[1] = 'start'
        forkcmd = ' '.join(forkcmd)
        for appid in reversed(args):
            status = system('%s %s' % (forkcmd, appid))
            if status:
                sys.exit(status)

    def restart_instance(self, appid):
        StopInstanceCommand(self.logger).stop_instance(appid)
        self.start_instance(appid)


class ReloadConfigurationCommand(RestartInstanceCommand):
    """Reload the given instances. This command is equivalent to a
    restart for now.

    <instance>...
      identifiers of the instances to reload. If no instance is
      given, reload them all.
    """
    name = 'reload'

    def reload_instance(self, appid):
        self.restart_instance(appid)


class StatusCommand(InstanceCommand):
    """Display status information about the given instances.

    <instance>...
      identifiers of the instances to status. If no instance is
      given, get status information about all registered instances.
    """
    name = 'status'
    options = ()

    @staticmethod
    def status_instance(appid):
        """print running status information for an instance"""
        status = 0
        for mode in cwcfg.possible_configurations(appid):
            config = cwcfg.config_for(appid, mode)
            print '[%s-%s]' % (appid, mode),
            try:
                pidf = config['pid-file']
            except KeyError:
                print 'buggy instance, pid file not specified'
                continue
            if not exists(pidf):
                print "doesn't seem to be running"
                status = 1
                continue
            pid = int(open(pidf).read().strip())
            # trick to guess whether or not the process is running
            try:
                getpgid(pid)
            except OSError:
                print "should be running with pid %s but the process can not be found" % pid
                status = 1
                continue
            print "running with pid %s" % (pid)
        return status

class UpgradeInstanceCommand(InstanceCommandFork):
    """Upgrade an instance after cubicweb and/or component(s) upgrade.

    For repository update, you will be prompted for a login / password to use
    to connect to the system database.  For some upgrades, the given user
    should have create or alter table permissions.

    <instance>...
      identifiers of the instances to upgrade. If no instance is
      given, upgrade them all.
    """
    name = 'upgrade'
    actionverb = 'upgraded'
    options = InstanceCommand.options + (
        ('force-cube-version',
         {'short': 't', 'type' : 'named', 'metavar': 'cube1:X.Y.Z,cube2:X.Y.Z',
          'default': None,
          'help': 'force migration from the indicated version for the specified cube(s).'}),

        ('force-cubicweb-version',
         {'short': 'e', 'type' : 'string', 'metavar': 'X.Y.Z',
          'default': None,
          'help': 'force migration from the indicated cubicweb version.'}),

        ('fs-only',
         {'short': 's', 'action' : 'store_true',
          'default': False,
          'help': 'only upgrade files on the file system, not the database.'}),

        ('nostartstop',
         {'short': 'n', 'action' : 'store_true',
          'default': False,
          'help': 'don\'t try to stop instance before migration and to restart it after.'}),

        ('verbosity',
         {'short': 'v', 'type' : 'int', 'metavar': '<0..2>',
          'default': 1,
          'help': "0: no confirmation, 1: only main commands confirmed, 2 ask \
for everything."}),

        ('backup-db',
         {'short': 'b', 'type' : 'yn', 'metavar': '<y or n>',
          'default': None,
          'help': "Backup the instance database before upgrade.\n"\
          "If the option is ommitted, confirmation will be ask.",
          }),

        ('ext-sources',
         {'short': 'E', 'type' : 'csv', 'metavar': '<sources>',
          'default': None,
          'help': "For multisources instances, specify to which sources the \
repository should connect to for upgrading. When unspecified or 'migration' is \
given, appropriate sources for migration will be automatically selected \
(recommended). If 'all' is given, will connect to all defined sources.",
          }),
        )

    def upgrade_instance(self, appid):
        print '\n' + underline_title('Upgrading the instance %s' % appid)
        from logilab.common.changelog import Version
        config = cwcfg.config_for(appid)
        instance_running = exists(config['pid-file'])
        config.repairing = True # notice we're not starting the server
        config.verbosity = self.config.verbosity
        set_sources_mode = getattr(config, 'set_sources_mode', None)
        if set_sources_mode is not None:
            set_sources_mode(self.config.ext_sources or ('migration',))
        # get instance and installed versions for the server and the componants
        mih = config.migration_handler()
        repo = mih.repo_connect()
        vcconf = repo.get_versions()
        helper = self.config_helper(config, required=False)
        if self.config.force_cube_version:
            for cube, version in self.config.force_cube_version.iteritems():
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
                toupgrade.append( (cube, applversion, installedversion) )
        cubicwebversion = config.cubicweb_version()
        if self.config.force_cubicweb_version:
            applcubicwebversion = Version(self.config.force_cubicweb_version)
            vcconf['cubicweb'] = applcubicwebversion
        else:
            applcubicwebversion = vcconf.get('cubicweb')
        if cubicwebversion > applcubicwebversion:
            toupgrade.append(('cubicweb', applcubicwebversion, cubicwebversion))
        # only stop once we're sure we have something to do
        if instance_running and not (CWDEV or self.config.nostartstop):
            StopInstanceCommand(self.logger).stop_instance(appid)
        # run cubicweb/componants migration scripts
        if self.config.fs_only or toupgrade:
            for cube, fromversion, toversion in toupgrade:
                print '-> migration needed from %s to %s for %s' % (fromversion, toversion, cube)
            with mih.cnx:
                with mih.cnx.security_enabled(False, False):
                    mih.migrate(vcconf, reversed(toupgrade), self.config)
        else:
            print '-> no data migration needed for instance %s.' % appid
        # rewrite main configuration file
        mih.rewrite_configuration()
        mih.shutdown()
        # handle i18n upgrade
        if not self.i18nupgrade(config):
            return
        print
        if helper:
            helper.postupgrade(repo)
        print '-> instance migrated.'
        if instance_running and not (CWDEV or self.config.nostartstop):
            # restart instance through fork to get a proper environment, avoid
            # uicfg pb (and probably gettext catalogs, to check...)
            forkcmd = '%s start %s' % (sys.argv[0], appid)
            status = system(forkcmd)
            if status:
                print '%s exited with status %s' % (forkcmd, status)
        print

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
            print '\n'.join(errors)
            if not ASK.confirm('Error while compiling message catalogs, '
                               'continue anyway?'):
                print '-> migration not completed.'
                return False
        return True


class ListVersionsInstanceCommand(InstanceCommand):
    """List versions used by an instance.

    <instance>...
      identifiers of the instances to list versions for.
    """
    name = 'versions'

    def versions_instance(self, appid):
        config = cwcfg.config_for(appid)
        # should not raise error if db versions don't match fs versions
        config.repairing = True
        # no need to load all appobjects and schema
        config.quick_start = True
        if hasattr(config, 'set_sources_mode'):
            config.set_sources_mode(('migration',))
        repo = config.migration_handler().repo_connect()
        vcconf = repo.get_versions()
        for key in sorted(vcconf):
            print key+': %s.%s.%s' % vcconf[key]

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
    options = (
        ('system-only',
         {'short': 'S', 'action' : 'store_true',
          'help': 'only connect to the system source when the instance is '
          'using multiple sources. You can\'t use this option and the '
          '--ext-sources option at the same time.',
          'group': 'local'
         }),

        ('ext-sources',
         {'short': 'E', 'type' : 'csv', 'metavar': '<sources>',
          'help': "For multisources instances, specify to which sources the \
repository should connect to for upgrading. When unspecified or 'all' given, \
will connect to all defined sources. If 'migration' is given, appropriate \
sources for migration will be automatically selected.",
          'group': 'local'
          }),

        ('force',
         {'short': 'f', 'action' : 'store_true',
          'help': 'don\'t check instance is up to date.',
          'group': 'local'
          }),

        ('repo-uri',
         {'short': 'H', 'type' : 'string', 'metavar': '<protocol>://<[host][:port]>',
          'help': 'URI of the CubicWeb repository to connect to. URI can be \
pyro://[host:port] the Pyro name server host; if the pyro nameserver is not set, \
it will be detected by using a broadcast query, a ZMQ URL or \
inmemory:// (default) use an in-memory repository. THIS OPTION IS DEPRECATED, \
directly give URI as instance id instead',
          'group': 'remote'
          }),
        )

    def _handle_inmemory(self, appid):
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

    def _handle_networked(self, appuri):
        """ returns migration context handler & shutdown function """
        from cubicweb import AuthenticationError
        from cubicweb.repoapi import connect, get_repository
        from cubicweb.server.utils import manager_userpasswd
        from cubicweb.server.migractions import ServerMigrationHelper
        while True:
            try:
                login, pwd = manager_userpasswd(msg=None)
                repo = get_repository(appuri)
                cnx = connect(repo, login=login, password=pwd, mulcnx=False)
            except AuthenticationError as ex:
                print ex
            except (KeyboardInterrupt, EOFError):
                print
                sys.exit(0)
            else:
                break
        cnx.load_appobjects()
        repo = cnx._repo
        mih = ServerMigrationHelper(None, repo=repo, cnx=cnx, verbosity=0,
                                    # hack so it don't try to load fs schema
                                    schema=1)
        return mih, lambda: cnx.close()

    def run(self, args):
        appuri = args.pop(0)
        if self.config.repo_uri:
            warn('[3.16] --repo-uri option is deprecated, directly give the URI as instance id',
                 DeprecationWarning)
            if urlparse(self.config.repo_uri).scheme in ('pyro', 'inmemory'):
                appuri = '%s/%s' % (self.config.repo_uri.rstrip('/'), appuri)

        from cubicweb.utils import parse_repo_uri
        protocol, hostport, appid = parse_repo_uri(appuri)
        if protocol == 'inmemory':
            mih, shutdown_callback = self._handle_inmemory(appid)
        else:
            mih, shutdown_callback = self._handle_networked(appuri)
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

    <instance>...
      identifiers of the instances to consider. If no instance is
      given, recompile for all registered instances.
    """
    name = 'i18ninstance'

    @staticmethod
    def i18ninstance_instance(appid):
        """recompile instance's messages catalogs"""
        config = cwcfg.config_for(appid)
        config.quick_start = True # notify this is not a regular start
        repo = config.repository()
        if config._cubes is None:
            # web only config
            config.init_cubes(repo.get_cubes())
        errors = config.i18ncompile()
        if errors:
            print '\n'.join(errors)


class ListInstancesCommand(Command):
    """list available instances, useful for bash completion."""
    name = 'listinstances'
    hidden = True

    def run(self, args):
        """run the command with its specific arguments"""
        regdir = cwcfg.instances_dir()
        for appid in sorted(listdir(regdir)):
            print appid


class ListCubesCommand(Command):
    """list available componants, useful for bash completion."""
    name = 'listcubes'
    hidden = True

    def run(self, args):
        """run the command with its specific arguments"""
        for cube in cwcfg.available_cubes():
            print cube

class ConfigureInstanceCommand(InstanceCommand):
    """Configure instance.

    <instance>...
      identifier of the instance to configure.
    """
    name = 'configure'
    actionverb = 'configured'

    options = merge_options(InstanceCommand.options +
                            (('param',
                              {'short': 'p', 'type' : 'named', 'metavar' : 'key1:value1,key2:value2',
                               'default': None,
                               'help': 'set <key> to <value> in configuration file.',
                               }),
                             ))

    def configure_instance(self, appid):
        if self.config.param is not None:
            appcfg = cwcfg.config_for(appid)
            for key, value in self.config.param.iteritems():
                try:
                    appcfg.global_set_option(key, value)
                except KeyError:
                    raise ConfigurationError('unknown configuration key "%s" for mode %s' % (key, appcfg.name))
            appcfg.save()


# WSGI #########

WSGI_CHOICES = {}
from cubicweb.wsgi import server as stdlib_server
WSGI_CHOICES['stdlib'] = stdlib_server
try:
    from cubicweb.wsgi import wz
except ImportError:
    pass
else:
    WSGI_CHOICES['werkzeug'] = wz
try:
    from cubicweb.wsgi import tnd
except ImportError:
    pass
else:
    WSGI_CHOICES['tornado'] = tnd


def wsgichoices():
    return tuple(WSGI_CHOICES)


class WSGIStartHandler(InstanceCommand):
    """Start an interactive wsgi server """
    name = 'wsgi'
    actionverb = 'started'
    arguments = '<instance>'

    @property
    def options(self):
        return (
        ("debug",
         {'short': 'D', 'action': 'store_true',
          'default': False,
          'help': 'start server in debug mode.'}),
        ('method',
         {'short': 'm',
          'type': 'choice',
          'metavar': '<method>',
          'default': 'stdlib',
          'choices': wsgichoices(),
          'help': 'wsgi utility/method'}),
        ('loglevel',
         {'short': 'l',
          'type': 'choice',
          'metavar': '<log level>',
          'default': None,
          'choices': ('debug', 'info', 'warning', 'error'),
          'help': 'debug if -D is set, error otherwise',
          }),
        )

    def wsgi_instance(self, appid):
        config = cwcfg.config_for(appid, debugmode=self['debug'])
        init_cmdline_log_threshold(config, self['loglevel'])
        assert config.name == 'all-in-one'
        meth = self['method']
        server = WSGI_CHOICES[meth]
        return server.run(config)



for cmdcls in (ListCommand,
               CreateInstanceCommand, DeleteInstanceCommand,
               StartInstanceCommand, StopInstanceCommand, RestartInstanceCommand,
               WSGIStartHandler,
               ReloadConfigurationCommand, StatusCommand,
               UpgradeInstanceCommand,
               ListVersionsInstanceCommand,
               ShellCommand,
               RecompileInstanceCatalogsCommand,
               ListInstancesCommand, ListCubesCommand,
               ConfigureInstanceCommand,
               ):
    CWCTL.register(cmdcls)



def run(args):
    """command line tool"""
    import os
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)
    cwcfg.load_cwctl_plugins()
    try:
        CWCTL.run(args)
    except ConfigurationError as err:
        print 'ERROR: ', err
        sys.exit(1)
    except ExecutionError as err:
        print err
        sys.exit(2)

if __name__ == '__main__':
    run(sys.argv[1:])
