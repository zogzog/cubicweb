"""%%prog %s [options] %s

CubicWeb main instances controller.
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
%s"""

import sys
from os import remove, listdir, system, kill, getpgid, pathsep
from os.path import exists, join, isfile, isdir

from logilab.common.clcommands import register_commands, pop_arg
from logilab.common.shellutils import ASK

from cubicweb import ConfigurationError, ExecutionError, BadCommandUsage, underline_title
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg, CONFIGURATIONS
from cubicweb.toolsutils import Command, main_run,  rm, create_dir

def wait_process_end(pid, maxtry=10, waittime=1):
    """wait for a process to actually die"""
    import signal
    from time import sleep
    nbtry = 0
    while nbtry < maxtry:
        try:
            kill(pid, signal.SIGUSR1)
        except OSError:
            break
        nbtry += 1
        sleep(waittime)
    else:
        raise ExecutionError('can\'t kill process %s' % pid)

def list_instances(regdir):
    return sorted(idir for idir in listdir(regdir) if isdir(join(regdir, idir)))

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
        some instances depends on another as external source
        """
        regdir = cwcfg.registry_dir()
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
        for appid in args:
            if askconfirm:
                print '*'*72
                if not confirm('%s instance %r ?' % (self.name, appid)):
                    continue
            self.run_arg(appid)

    def run_arg(self, appid):
        cmdmeth = getattr(self, '%s_instance' % self.name)
        try:
            cmdmeth(appid)
        except (KeyboardInterrupt, SystemExit):
            print >> sys.stderr, '%s aborted' % self.name
            sys.exit(2) # specific error code
        except (ExecutionError, ConfigurationError), ex:
            print >> sys.stderr, 'instance %s not %s: %s' % (
                appid, self.actionverb, ex)
        except Exception, ex:
            import traceback
            traceback.print_exc()
            print >> sys.stderr, 'instance %s not %s: %s' % (
                appid, self.actionverb, ex)


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
                if not confirm('%s instance %r ?' % (self.name, appid)):
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

    list available configurations, installed cubes, and registered instances
    """
    name = 'list'
    options = (
        ('verbose',
         {'short': 'v', 'action' : 'store_true',
          'help': "display more information."}),
        )

    def run(self, args):
        """run the command with its specific arguments"""
        if args:
            raise BadCommandUsage('Too much arguments')
        print 'CubicWeb version:', cwcfg.cubicweb_version()
        print 'Detected mode:', cwcfg.mode
        print
        print 'Available configurations:'
        for config in CONFIGURATIONS:
            print '*', config.name
            for line in config.__doc__.splitlines():
                line = line.strip()
                if not line:
                    continue
                print '   ', line
        print
        try:
            cubesdir = pathsep.join(cwcfg.cubes_search_path())
            namesize = max(len(x) for x in cwcfg.available_cubes())
        except ConfigurationError, ex:
            print 'No cubes available:', ex
        except ValueError:
            print 'No cubes available in %s' % cubesdir
        else:
            print 'Available cubes (%s):' % cubesdir
            for cube in cwcfg.available_cubes():
                if cube in ('CVS', '.svn', 'shared', '.hg'):
                    continue
                try:
                    tinfo = cwcfg.cube_pkginfo(cube)
                    tversion = tinfo.version
                except ConfigurationError:
                    tinfo = None
                    tversion = '[missing cube information]'
                print '* %s %s' % (cube.ljust(namesize), tversion)
                if self.config.verbose:
                    shortdesc = tinfo and (getattr(tinfo, 'short_desc', '')
                                           or tinfo.__doc__)
                    if shortdesc:
                        print '    '+ '    \n'.join(shortdesc.splitlines())
                    modes = detect_available_modes(cwcfg.cube_dir(cube))
                    print '    available modes: %s' % ', '.join(modes)
        print
        try:
            regdir = cwcfg.registry_dir()
        except ConfigurationError, ex:
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
                except Exception, exc:
                    print '    (BROKEN instance, %s)' % exc
                    continue
        else:
            print 'No instance available in %s' % regdir
        print


class CreateInstanceCommand(Command):
    """Create an instance from a cube. This is an unified
    command which can handle web / server / all-in-one installation
    according to available parts of the software library and of the
    desired cube.

    <cube>
      the name of cube to use (list available cube names using
      the "list" command). You can use several cubes by separating
      them using comma (e.g. 'jpl,eemail')
    <instance>
      an identifier for the instance to create
    """
    name = 'create'
    arguments = '<cube> <instance>'
    options = (
        ("config-level",
         {'short': 'l', 'type' : 'int', 'metavar': '<level>',
          'default': 0,
          'help': 'configuration level (0..2): 0 will ask for essential \
configuration parameters only while 2 will ask for all parameters',
          }
         ),
        ("config",
         {'short': 'c', 'type' : 'choice', 'metavar': '<install type>',
          'choices': ('all-in-one', 'repository', 'twisted'),
          'default': 'all-in-one',
          'help': 'installation type, telling which part of an instance \
should be installed. You can list available configurations using the "list" \
command. Default to "all-in-one", e.g. an installation embedding both the RQL \
repository and the web server.',
          }
         ),
        )

    def run(self, args):
        """run the command with its specific arguments"""
        from logilab.common.textutils import get_csv
        configname = self.config.config
        cubes = get_csv(pop_arg(args, 1))
        appid = pop_arg(args)
        # get the configuration and helper
        cwcfg.creating = True
        config = cwcfg.config_for(appid, configname)
        config.set_language = False
        cubes = config.expand_cubes(cubes)
        config.init_cubes(cubes)
        helper = self.config_helper(config)
        # check the cube exists
        try:
            templdirs = [cwcfg.cube_dir(cube)
                         for cube in cubes]
        except ConfigurationError, ex:
            print ex
            print '\navailable cubes:',
            print ', '.join(cwcfg.available_cubes())
            return
        # create the registry directory for this instance
        print '\n'+underline_title('Creating the instance %s' % appid)
        create_dir(config.apphome)
        # load site_cubicweb from the cubes dir (if any)
        config.load_site_cubicweb()
        # cubicweb-ctl configuration
        print '\n'+underline_title('Configuring the instance (%s.conf)' % configname)
        config.input_config('main', self.config.config_level)
        # configuration'specific stuff
        print
        helper.bootstrap(cubes, self.config.config_level)
        # write down configuration
        config.save()
        print '-> generated %s' % config.main_config_file()
        # handle i18n files structure
        # in the first cube given
        print '-> preparing i18n catalogs'
        from cubicweb.common import i18n
        langs = [lang for lang, _ in i18n.available_catalogs(join(templdirs[0], 'i18n'))]
        errors = config.i18ncompile(langs)
        if errors:
            print '\n'.join(errors)
            if not confirm('error while compiling message catalogs, '
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
        print '\n-> creation done for %r.\n' % config.apphome
        helper.postcreate()


class DeleteInstanceCommand(Command):
    """Delete an instance. Will remove instance's files and
    unregister it.
    """
    name = 'delete'
    arguments = '<instance>'

    options = ()

    def run(self, args):
        """run the command with its specific arguments"""
        appid = pop_arg(args, msg="No instance specified !")
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
        except OSError, ex:
            import errno
            if ex.errno != errno.ENOENT:
                raise
        confignames = ', '.join([config.name for config in configs])
        print '-> instance %s (%s) deleted.' % (appid, confignames)


# instance commands ########################################################

class StartInstanceCommand(InstanceCommand):
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
        )

    def start_instance(self, appid):
        """start the instance's server"""
        # use get() since start may be used from other commands (eg upgrade)
        # without all options defined
        debug = self.get('debug')
        force = self.get('force')
        config = cwcfg.config_for(appid)
        if self.get('profile'):
            config.global_set_option('profile', self.config.profile)
        helper = self.config_helper(config, cmdname='start')
        pidf = config['pid-file']
        if exists(pidf) and not force:
            msg = "%s seems to be running. Remove %s by hand if necessary or use \
the --force option."
            raise ExecutionError(msg % (appid, pidf))
        command = helper.start_command(config, debug)
        if debug:
            print "starting server with command :"
            print command
        if system(command):
            print 'an error occured while starting the instance, not started'
            print
            return False
        if not debug:
            print '-> instance %s started.' % appid
        return True


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
            print >> sys.stderr, "%s doesn't exist." % pidf
            return
        import signal
        pid = int(open(pidf).read().strip())
        try:
            kill(pid, signal.SIGTERM)
        except:
            print >> sys.stderr, "process %s seems already dead." % pid
        else:
            try:
                wait_process_end(pid)
            except ExecutionError, ex:
                print >> sys.stderr, ex
                print >> sys.stderr, 'trying SIGKILL'
                try:
                    kill(pid, signal.SIGKILL)
                except:
                    # probably dead now
                    pass
                wait_process_end(pid)
        try:
            remove(pidf)
        except OSError:
            # already removed by twistd
            pass
        print 'instance %s stopped' % appid


class RestartInstanceCommand(StartInstanceCommand,
                                StopInstanceCommand):
    """Restart the given instances.

    <instance>...
      identifiers of the instances to restart. If no instance is
      given, restart them all.
    """
    name = 'restart'
    actionverb = 'restarted'

    def run_args(self, args, askconfirm):
        regdir = cwcfg.registry_dir()
        if not isfile(join(regdir, 'startorder')) or len(args) <= 1:
            # no specific startorder
            super(RestartInstanceCommand, self).run_args(args, askconfirm)
            return
        print ('some specific start order is specified, will first stop all '
               'instances then restart them.')
        # get instances in startorder
        stopped = []
        for appid in args:
            if askconfirm:
                print '*'*72
                if not confirm('%s instance %r ?' % (self.name, appid)):
                    continue
            self.stop_instance(appid)
            stopped.append(appid)
        forkcmd = [w for w in sys.argv if not w in args]
        forkcmd[1] = 'start'
        forkcmd = ' '.join(forkcmd)
        for appid in reversed(args):
            status = system('%s %s' % (forkcmd, appid))
            if status:
                sys.exit(status)

    def restart_instance(self, appid):
        self.stop_instance(appid)
        if self.start_instance(appid):
            print 'instance %s %s' % (appid, self.actionverb)


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
                continue
            pid = int(open(pidf).read().strip())
            # trick to guess whether or not the process is running
            try:
                getpgid(pid)
            except OSError:
                print "should be running with pid %s but the process can not be found" % pid
                continue
            print "running with pid %s" % (pid)


class UpgradeInstanceCommand(InstanceCommandFork,
                                StartInstanceCommand,
                                StopInstanceCommand):
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
        ('force-componant-version',
         {'short': 't', 'type' : 'csv', 'metavar': 'cube1=X.Y.Z,cube2=X.Y.Z',
          'default': None,
          'help': 'force migration from the indicated  version for the specified cube.'}),
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

    def ordered_instances(self):
        # need this since mro return StopInstanceCommand implementation
        return InstanceCommand.ordered_instances(self)

    def upgrade_instance(self, appid):
        print '\n' + underline_title('Upgrading the instance %s' % appid)
        from logilab.common.changelog import Version
        config = cwcfg.config_for(appid)
        config.repairing = True # notice we're not starting the server
        config.verbosity = self.config.verbosity
        try:
            config.set_sources_mode(self.config.ext_sources or ('migration',))
        except AttributeError:
            # not a server config
            pass
        # get instance and installed versions for the server and the componants
        mih = config.migration_handler()
        repo = mih.repo_connect()
        vcconf = repo.get_versions()
        if self.config.force_componant_version:
            packversions = {}
            for vdef in self.config.force_componant_version:
                componant, version = vdef.split('=')
                packversions[componant] = Version(version)
            vcconf.update(packversions)
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
        if not self.config.fs_only and not toupgrade:
            print '-> no software migration needed for instance %s.' % appid
            return
        for cube, fromversion, toversion in toupgrade:
            print '-> migration needed from %s to %s for %s' % (fromversion, toversion, cube)
        # only stop once we're sure we have something to do
        if not (cwcfg.mode == 'dev' or self.config.nostartstop):
            self.stop_instance(appid)
        # run cubicweb/componants migration scripts
        mih.migrate(vcconf, reversed(toupgrade), self.config)
        # rewrite main configuration file
        mih.rewrite_configuration()
        # handle i18n upgrade:
        # * install new languages
        # * recompile catalogs
        # in the first componant given
        from cubicweb.common import i18n
        templdir = cwcfg.cube_dir(config.cubes()[0])
        langs = [lang for lang, _ in i18n.available_catalogs(join(templdir, 'i18n'))]
        errors = config.i18ncompile(langs)
        if errors:
            print '\n'.join(errors)
            if not confirm('Error while compiling message catalogs, '
                           'continue anyway ?'):
                print '-> migration not completed.'
                return
        mih.shutdown()
        print
        print '-> instance migrated.'
        if not (cwcfg.mode == 'dev' or self.config.nostartstop):
            self.start_instance(appid)
        print


class ShellCommand(Command):
    """Run an interactive migration shell. This is a python shell with
    enhanced migration commands predefined in the namespace. An additional
    argument may be given corresponding to a file containing commands to
    execute in batch mode.

    <instance>
      the identifier of the instance to connect.
    """
    name = 'shell'
    arguments = '<instance> [batch command file]'
    options = (
        ('system-only',
         {'short': 'S', 'action' : 'store_true',
          'default': False,
          'help': 'only connect to the system source when the instance is '
          'using multiple sources. You can\'t use this option and the '
          '--ext-sources option at the same time.'}),

        ('ext-sources',
         {'short': 'E', 'type' : 'csv', 'metavar': '<sources>',
          'default': None,
          'help': "For multisources instances, specify to which sources the \
repository should connect to for upgrading. When unspecified or 'all' given, \
will connect to all defined sources. If 'migration' is given, appropriate \
sources for migration will be automatically selected.",
          }),

        )
    def run(self, args):
        appid = pop_arg(args, 99, msg="No instance specified !")
        config = cwcfg.config_for(appid)
        if self.config.ext_sources:
            assert not self.config.system_only
            sources = self.config.ext_sources
        elif self.config.system_only:
            sources = ('system',)
        else:
            sources = ('all',)
        config.set_sources_mode(sources)
        mih = config.migration_handler()
        if args:
            for arg in args:
                mih.process_script(arg)
        else:
            mih.interactive_shell()
        mih.shutdown()


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
        try:
            config.bootstrap_cubes()
        except IOError, ex:
            import errno
            if ex.errno != errno.ENOENT:
                raise
            # bootstrap_cubes files doesn't exist
            # notify this is not a regular start
            config.repairing = True
            # create an in-memory repository, will call config.init_cubes()
            config.repository()
        except AttributeError:
            # web only config
            config.init_cubes(config.repository().get_cubes())
        errors = config.i18ncompile()
        if errors:
            print '\n'.join(errors)


class ListInstancesCommand(Command):
    """list available instances, useful for bash completion."""
    name = 'listinstances'
    hidden = True

    def run(self, args):
        """run the command with its specific arguments"""
        regdir = cwcfg.registry_dir()
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

register_commands((ListCommand,
                   CreateInstanceCommand,
                   DeleteInstanceCommand,
                   StartInstanceCommand,
                   StopInstanceCommand,
                   RestartInstanceCommand,
                   ReloadConfigurationCommand,
                   StatusCommand,
                   UpgradeInstanceCommand,
                   ShellCommand,
                   RecompileInstanceCatalogsCommand,
                   ListInstancesCommand, ListCubesCommand,
                   ))


def run(args):
    """command line tool"""
    cwcfg.load_cwctl_plugins()
    main_run(args, __doc__)

if __name__ == '__main__':
    run(sys.argv[1:])
