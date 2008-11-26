"""%%prog %s [options] %s

CubicWeb main applications controller. 
%s"""

import sys
from os import remove, listdir, system, kill, getpgid
from os.path import exists, join, isfile, isdir

from cubicweb import ConfigurationError, ExecutionError, BadCommandUsage
from cubicweb.cwconfig import CubicWebConfiguration, CONFIGURATIONS
from cubicweb.toolsutils import (Command, register_commands, main_run, 
                                 rm, create_dir, pop_arg, confirm)
    
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
    
    
class ApplicationCommand(Command):
    """base class for command taking 0 to n application id as arguments
    (0 meaning all registered applications)
    """
    arguments = '[<application>...]'    
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
        regdir = CubicWebConfiguration.registry_dir()
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
                        print 'ERROR: startorder file contains unexistant instance %s' % line
            allinstances += _allinstances
        else:
            allinstances = _allinstances
        return allinstances
    
    def run(self, args):
        """run the <command>_method on each argument (a list of application
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
                if not confirm('%s application %r ?' % (self.name, appid)):
                    continue
            self.run_arg(appid)
            
    def run_arg(self, appid):
        cmdmeth = getattr(self, '%s_application' % self.name)
        try:
            cmdmeth(appid)
        except (KeyboardInterrupt, SystemExit):
            print >> sys.stderr, '%s aborted' % self.name
            sys.exit(2) # specific error code
        except (ExecutionError, ConfigurationError), ex:
            print >> sys.stderr, 'application %s not %s: %s' % (
                appid, self.actionverb, ex)
        except Exception, ex:
            import traceback
            traceback.print_exc()
            print >> sys.stderr, 'application %s not %s: %s' % (
                appid, self.actionverb, ex)


class ApplicationCommandFork(ApplicationCommand):
    """Same as `ApplicationCommand`, but command is forked in a new environment
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
                if not confirm('%s application %r ?' % (self.name, appid)):
                    continue
            if forkcmd:
                status = system('%s %s' % (forkcmd, appid))
                if status:
                    sys.exit(status)
            else:
                self.run_arg(appid)
    
# base commands ###############################################################

class ListCommand(Command):
    """List configurations, componants and applications.

    list available configurations, installed web and server componants, and
    registered applications
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
        print 'CubicWeb version:', CubicWebConfiguration.cubicweb_version()
        print 'Detected mode:', CubicWebConfiguration.mode
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
            cubesdir = CubicWebConfiguration.cubes_dir()
            namesize = max(len(x) for x in CubicWebConfiguration.available_cubes())
        except ConfigurationError, ex:
            print 'No cubes available:', ex
        except ValueError:
            print 'No cubes available in %s' % cubesdir
        else:
            print 'Available cubes (%s):' % cubesdir
            for cube in CubicWebConfiguration.available_cubes():
                if cube in ('CVS', '.svn', 'shared', '.hg'):
                    continue
                templdir = join(cubesdir, cube)
                try:
                    tinfo = CubicWebConfiguration.cube_pkginfo(cube)
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
                    modes = detect_available_modes(templdir)
                    print '    available modes: %s' % ', '.join(modes)
        print
        try:
            regdir = CubicWebConfiguration.registry_dir()
        except ConfigurationError, ex:
            print 'No application available:', ex
            print
            return
        instances = list_instances(regdir)
        if instances:
            print 'Available applications (%s):' % regdir
            for appid in instances:
                modes = CubicWebConfiguration.possible_configurations(appid)
                if not modes:
                    print '* %s (BROKEN application, no configuration found)' % appid
                    continue
                print '* %s (%s)' % (appid, ', '.join(modes))
                try:
                    config = CubicWebConfiguration.config_for(appid, modes[0])
                except Exception, exc: 
                    print '    (BROKEN application, %s)' % exc
                    continue
        else:
            print 'No application available in %s' % regdir
        print


class CreateApplicationCommand(Command):
    """Create an application from a cube. This is an unified
    command which can handle web / server / all-in-one installation
    according to available parts of the software library and of the
    desired cube.

    <cube>
      the name of cube to use (list available cube names using
      the "list" command). You can use several cubes by separating
      them using comma (e.g. 'jpl,eemail')
    <application>
      an identifier for the application to create
    """
    name = 'create'
    arguments = '<cube> <application>'
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
          'help': 'installation type, telling which part of an application \
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
        CubicWebConfiguration.creating = True
        config = CubicWebConfiguration.config_for(appid, configname)
        config.set_language = False
        config.init_cubes(config.expand_cubes(cubes))
        helper = self.config_helper(config)
        # check the cube exists
        try:
            templdirs = [CubicWebConfiguration.cube_dir(cube)
                         for cube in cubes]
        except ConfigurationError, ex:
            print ex
            print '\navailable cubes:',
            print ', '.join(CubicWebConfiguration.available_cubes())
            return
        # create the registry directory for this application
        create_dir(config.apphome)
        # load site_cubicweb from the cubes dir (if any)
        config.load_site_cubicweb()
        # cubicweb-ctl configuration
        print '** application\'s %s configuration' % configname
        print '-' * 72
        config.input_config('main', self.config.config_level)
        # configuration'specific stuff
        print
        helper.bootstrap(cubes, self.config.config_level)
        # write down configuration
        config.save()
        # handle i18n files structure
        # XXX currently available languages are guessed from translations found
        # in the first cube given
        from cubicweb.common import i18n
        langs = [lang for lang, _ in i18n.available_catalogs(join(templdirs[0], 'i18n'))]
        errors = config.i18ncompile(langs)
        if errors:
            print '\n'.join(errors)
            if not confirm('error while compiling message catalogs, '
                           'continue anyway ?'):
                print 'creation not completed'
                return
        # create the additional data directory for this application
        if config.appdatahome != config.apphome: # true in dev mode
            create_dir(config.appdatahome)
        if config['uid']:
            from logilab.common.shellutils import chown
            # this directory should be owned by the uid of the server process
            print 'set %s as owner of the data directory' % config['uid']
            chown(config.appdatahome, config['uid'])
        print
        print
        print '*' * 72
        print 'application %s (%s) created in %r' % (appid, configname,
                                                     config.apphome)
        print
        helper.postcreate()

    
class DeleteApplicationCommand(Command):
    """Delete an application. Will remove application's files and
    unregister it.
    """
    name = 'delete'
    arguments = '<application>'
    
    options = ()

    def run(self, args):
        """run the command with its specific arguments"""
        appid = pop_arg(args, msg="No application specified !")
        configs = [CubicWebConfiguration.config_for(appid, configname)
                   for configname in CubicWebConfiguration.possible_configurations(appid)]
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
        print 'application %s (%s) deleted' % (appid, confignames)


# application commands ########################################################

class StartApplicationCommand(ApplicationCommand):
    """Start the given applications. If no application is given, start them all.
    
    <application>...
      identifiers of the applications to start. If no application is
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
          'help': 'start the application even if it seems to be already \
running.'}),
        ('profile',
         {'short': 'P', 'type' : 'string', 'metavar': '<stat file>',
          'default': None,
          'help': 'profile code and use the specified file to store stats',
          }),
        )

    def start_application(self, appid):
        """start the application's server"""
        # use get() since start may be used from other commands (eg upgrade)
        # without all options defined
        debug = self.get('debug')
        force = self.get('force')
        config = CubicWebConfiguration.config_for(appid)
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
            print 'an error occured while starting the application, not started'
            print
            return False
        if not debug:
            print 'application %s started' % appid
        return True


class StopApplicationCommand(ApplicationCommand):
    """Stop the given applications.
    
    <application>...
      identifiers of the applications to stop. If no application is
      given, stop them all.
    """
    name = 'stop'
    actionverb = 'stopped'
    
    def ordered_instances(self):
        instances = super(StopApplicationCommand, self).ordered_instances()
        instances.reverse()
        return instances
    
    def stop_application(self, appid):
        """stop the application's server"""
        config = CubicWebConfiguration.config_for(appid)
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
        print 'application %s stopped' % appid
    

class RestartApplicationCommand(StartApplicationCommand,
                                StopApplicationCommand):
    """Restart the given applications.
    
    <application>...
      identifiers of the applications to restart. If no application is
      given, restart them all.
    """
    name = 'restart'
    actionverb = 'restarted'

    def run_args(self, args, askconfirm):
        regdir = CubicWebConfiguration.registry_dir()
        if not isfile(join(regdir, 'startorder')) or len(args) <= 1:
            # no specific startorder
            super(RestartApplicationCommand, self).run_args(args, askconfirm)
            return
        print ('some specific start order is specified, will first stop all '
               'applications then restart them.')
        # get instances in startorder
        stopped = []
        for appid in args:
            if askconfirm:
                print '*'*72
                if not confirm('%s application %r ?' % (self.name, appid)):
                    continue
            self.stop_application(appid)
            stopped.append(appid)
        forkcmd = [w for w in sys.argv if not w in args]
        forkcmd[1] = 'start'
        forkcmd = ' '.join(forkcmd)
        for appid in reversed(args):
            status = system('%s %s' % (forkcmd, appid))
            if status:
                sys.exit(status)
    
    def restart_application(self, appid):
        self.stop_application(appid)
        if self.start_application(appid):
            print 'application %s %s' % (appid, self.actionverb)

        
class ReloadConfigurationCommand(RestartApplicationCommand):
    """Reload the given applications. This command is equivalent to a
    restart for now.
    
    <application>...
      identifiers of the applications to reload. If no application is
      given, reload them all.
    """
    name = 'reload'
    
    def reload_application(self, appid):
        self.restart_application(appid)
    

class StatusCommand(ApplicationCommand):
    """Display status information about the given applications.
    
    <application>...
      identifiers of the applications to status. If no application is
      given, get status information about all registered applications.
    """
    name = 'status'
    options = ()

    def status_application(self, appid):
        """print running status information for an application"""
        for mode in CubicWebConfiguration.possible_configurations(appid):
            config = CubicWebConfiguration.config_for(appid, mode)
            print '[%s-%s]' % (appid, mode),
            try:
                pidf = config['pid-file']
            except KeyError:
                print 'buggy application, pid file not specified'
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


class UpgradeApplicationCommand(ApplicationCommandFork,
                                StartApplicationCommand,
                                StopApplicationCommand):
    """Upgrade an application after cubicweb and/or component(s) upgrade.

    For repository update, you will be prompted for a login / password to use
    to connect to the system database.  For some upgrades, the given user
    should have create or alter table permissions.

    <application>...
      identifiers of the applications to upgrade. If no application is
      given, upgrade them all.
    """
    name = 'upgrade'
    actionverb = 'upgraded'
    options = ApplicationCommand.options + (
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
          'help': 'don\'t try to stop application before migration and to restart it after.'}),
        
        ('verbosity',
         {'short': 'v', 'type' : 'int', 'metavar': '<0..2>',
          'default': 1,
          'help': "0: no confirmation, 1: only main commands confirmed, 2 ask \
for everything."}),
        
        ('backup-db',
         {'short': 'b', 'type' : 'yn', 'metavar': '<y or n>',
          'default': None,
          'help': "Backup the application database before upgrade.\n"\
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
        # need this since mro return StopApplicationCommand implementation
        return ApplicationCommand.ordered_instances(self)
    
    def upgrade_application(self, appid):
        from logilab.common.changelog import Version
        if not (CubicWebConfiguration.mode == 'dev' or self.config.nostartstop):
            self.stop_application(appid)
        config = CubicWebConfiguration.config_for(appid)
        config.creating = True # notice we're not starting the server
        config.verbosity = self.config.verbosity
        config.set_sources_mode(self.config.ext_sources or ('migration',))
        # get application and installed versions for the server and the componants
        print 'getting versions configuration from the repository...'
        mih = config.migration_handler()
        repo = mih.repo_connect()
        vcconf = repo.get_versions()
        print 'done'
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
            toupgrade.append( ('cubicweb', applcubicwebversion, cubicwebversion) )
        if not self.config.fs_only and not toupgrade:
            print 'no software migration needed for application %s' % appid
            return
        for cube, fromversion, toversion in toupgrade:
            print '**** %s migration %s -> %s' % (cube, fromversion, toversion)
        # run cubicweb/componants migration scripts
        mih.migrate(vcconf, reversed(toupgrade), self.config)
        # rewrite main configuration file
        mih.rewrite_configuration()
        # handle i18n upgrade:
        # * install new languages
        # * recompile catalogs
        # XXX currently available languages are guessed from translations found
        # in the first componant given
        from cubicweb.common import i18n
        templdir = CubicWebConfiguration.cube_dir(config.cubes()[0])
        langs = [lang for lang, _ in i18n.available_catalogs(join(templdir, 'i18n'))]
        errors = config.i18ncompile(langs)
        if errors:
            print '\n'.join(errors)
            if not confirm('error while compiling message catalogs, '
                           'continue anyway ?'):
                print 'migration not completed'
                return
        mih.rewrite_vcconfiguration()
        mih.shutdown()
        print
        print 'application migrated'
        if not (CubicWebConfiguration.mode == 'dev' or self.config.nostartstop):
            self.start_application(appid)
        print


class ShellCommand(Command):
    """Run an interactive migration shell. This is a python shell with
    enhanced migration commands predefined in the namespace. An additional
    argument may be given corresponding to a file containing commands to
    execute in batch mode.

    <application>
      the identifier of the application to connect.
    """
    name = 'shell'
    arguments = '<application> [batch command file]'
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
        appid = pop_arg(args, 99, msg="No application specified !")
        config = CubicWebConfiguration.config_for(appid)
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
            mih.scripts_session(args)
        else:
            mih.interactive_shell()
        mih.shutdown() 


class RecompileApplicationCatalogsCommand(ApplicationCommand):
    """Recompile i18n catalogs for applications.
    
    <application>...
      identifiers of the applications to consider. If no application is
      given, recompile for all registered applications.
    """
    name = 'i18ncompile'
    
    def i18ncompile_application(self, appid):
        """recompile application's messages catalogs"""
        config = CubicWebConfiguration.config_for(appid)
        try:
            config.bootstrap_cubes()
        except IOError, ex:
            import errno
            if ex.errno != errno.ENOENT:
                raise
            # bootstrap_cubes files doesn't exist
            # set creating to notify this is not a regular start
            config.creating = True
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
        regdir = CubicWebConfiguration.registry_dir()
        for appid in sorted(listdir(regdir)):
            print appid


class ListCubesCommand(Command):
    """list available componants, useful for bash completion."""
    name = 'listcubes'
    hidden = True
    
    def run(self, args):
        """run the command with its specific arguments"""
        for cube in CubicWebConfiguration.available_cubes():
            print cube

register_commands((ListCommand,
                   CreateApplicationCommand,
                   DeleteApplicationCommand,
                   StartApplicationCommand,
                   StopApplicationCommand,
                   RestartApplicationCommand,
                   ReloadConfigurationCommand,
                   StatusCommand,
                   UpgradeApplicationCommand,
                   ShellCommand,
                   RecompileApplicationCatalogsCommand,
                   ListInstancesCommand, ListCubesCommand,
                   ))

                
def run(args):
    """command line tool"""
    CubicWebConfiguration.load_cwctl_plugins()
    main_run(args, __doc__)

if __name__ == '__main__':
    run(sys.argv[1:])
