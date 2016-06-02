"""
Provides a 'pyramid' command as a replacement to the 'start' command.

The reloading strategy is heavily inspired by (and partially copied from)
the pyramid script 'pserve'.
"""
from __future__ import print_function

import atexit
import errno
import os
import signal
import sys
import tempfile
import time
import threading
import subprocess

from cubicweb import BadCommandUsage, ExecutionError
from cubicweb.__pkginfo__ import numversion as cwversion
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from cubicweb.cwctl import CWCTL, InstanceCommand, init_cmdline_log_threshold
from cubicweb.server import set_debug

from pyramid_cubicweb import wsgi_application_from_cwconfig
import waitress

MAXFD = 1024

DBG_FLAGS = ('RQL', 'SQL', 'REPO', 'HOOKS', 'OPS', 'SEC', 'MORE')
LOG_LEVELS = ('debug', 'info', 'warning', 'error')


class PyramidStartHandler(InstanceCommand):
    """Start an interactive pyramid server.

    This command requires http://hg.logilab.org/review/pyramid_cubicweb/

    <instance>
      identifier of the instance to configure.
    """
    name = 'pyramid'

    options = (
        ('no-daemon',
         {'action': 'store_true',
          'help': 'Run the server in the foreground.'}),
        ('debug-mode',
         {'action': 'store_true',
          'help': 'Activate the repository debug mode ('
                  'logs in the console and the debug toolbar).'
                  ' Implies --no-daemon'}),
        ('debug',
         {'short': 'D', 'action': 'store_true',
          'help': 'Equals to "--debug-mode --no-daemon --reload"'}),
        ('reload',
         {'action': 'store_true',
          'help': 'Restart the server if any source file is changed'}),
        ('reload-interval',
         {'type': 'int', 'default': 1,
          'help': 'Interval, in seconds, between file modifications checks'}),
        ('loglevel',
         {'short': 'l', 'type': 'choice', 'metavar': '<log level>',
          'default': None, 'choices': LOG_LEVELS,
          'help': 'debug if -D is set, error otherwise; '
                  'one of %s' % (LOG_LEVELS,),
          }),
        ('dbglevel',
         {'type': 'multiple_choice', 'metavar': '<dbg level>',
          'default': None,
          'choices': DBG_FLAGS,
          'help': ('Set the server debugging flags; you may choose several '
                   'values in %s; imply "debug" loglevel' % (DBG_FLAGS,)),
          }),
        ('profile',
         {'action': 'store_true',
          'default': False,
          'help': 'Enable profiling'}),
        ('profile-output',
         {'type': 'string',
          'default': None,
          'help': 'Profiling output file (default: "program.prof")'}),
        ('profile-dump-every',
         {'type': 'int',
          'default': None,
          'metavar': 'N',
          'help': 'Dump profile stats to ouput every N requests '
                  '(default: 100)'}),
    )
    if cwversion >= (3, 21, 0):
        options = options + (
            ('param',
             {'short': 'p',
              'type': 'named',
              'metavar': 'key1:value1,key2:value2',
              'default': {},
              'help': 'override <key> configuration file option with <value>.',
              }),
        )

    _reloader_environ_key = 'CW_RELOADER_SHOULD_RUN'
    _reloader_filelist_environ_key = 'CW_RELOADER_FILELIST'

    def debug(self, msg):
        print('DEBUG - %s' % msg)

    def info(self, msg):
        print('INFO - %s' % msg)

    def ordered_instances(self):
        instances = super(PyramidStartHandler, self).ordered_instances()
        if (self['debug-mode'] or self['debug'] or self['reload']) \
                and len(instances) > 1:
            raise BadCommandUsage(
                '--debug-mode, --debug and --reload can be used on a single '
                'instance only')
        return instances

    def quote_first_command_arg(self, arg):
        """
        There's a bug in Windows when running an executable that's
        located inside a path with a space in it.  This method handles
        that case, or on non-Windows systems or an executable with no
        spaces, it just leaves well enough alone.
        """
        if (sys.platform != 'win32' or ' ' not in arg):
            # Problem does not apply:
            return arg
        try:
            import win32api
        except ImportError:
            raise ValueError(
                "The executable %r contains a space, and in order to "
                "handle this issue you must have the win32api module "
                "installed" % arg)
        arg = win32api.GetShortPathName(arg)
        return arg

    def _remove_pid_file(self, written_pid, filename):
        current_pid = os.getpid()
        if written_pid != current_pid:
            # A forked process must be exiting, not the process that
            # wrote the PID file
            return
        if not os.path.exists(filename):
            return
        with open(filename) as f:
            content = f.read().strip()
        try:
            pid_in_file = int(content)
        except ValueError:
            pass
        else:
            if pid_in_file != current_pid:
                msg = "PID file %s contains %s, not expected PID %s"
                self.out(msg % (filename, pid_in_file, current_pid))
                return
        self.info("Removing PID file %s" % filename)
        try:
            os.unlink(filename)
            return
        except OSError as e:
            # Record, but don't give traceback
            self.out("Cannot remove PID file: (%s)" % e)
        # well, at least lets not leave the invalid PID around...
        try:
            with open(filename, 'w') as f:
                f.write('')
        except OSError as e:
            self.out('Stale PID left in file: %s (%s)' % (filename, e))
        else:
            self.out('Stale PID removed')

    def record_pid(self, pid_file):
        pid = os.getpid()
        self.debug('Writing PID %s to %s' % (pid, pid_file))
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        atexit.register(
            self._remove_pid_file, pid, pid_file)

    def daemonize(self, pid_file):
        pid = live_pidfile(pid_file)
        if pid:
            raise ExecutionError(
                "Daemon is already running (PID: %s from PID file %s)"
                % (pid, pid_file))

        self.debug('Entering daemon mode')
        pid = os.fork()
        if pid:
            # The forked process also has a handle on resources, so we
            # *don't* want proper termination of the process, we just
            # want to exit quick (which os._exit() does)
            os._exit(0)
        # Make this the session leader
        os.setsid()
        # Fork again for good measure!
        pid = os.fork()
        if pid:
            os._exit(0)

        # @@: Should we set the umask and cwd now?

        import resource  # Resource usage information.
        maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        if (maxfd == resource.RLIM_INFINITY):
            maxfd = MAXFD
        # Iterate through and close all file descriptors.
        for fd in range(0, maxfd):
            try:
                os.close(fd)
            except OSError:  # ERROR, fd wasn't open to begin with (ignored)
                pass

        if (hasattr(os, "devnull")):
            REDIRECT_TO = os.devnull
        else:
            REDIRECT_TO = "/dev/null"
        os.open(REDIRECT_TO, os.O_RDWR)  # standard input (0)
        # Duplicate standard input to standard output and standard error.
        os.dup2(0, 1)  # standard output (1)
        os.dup2(0, 2)  # standard error (2)

    def restart_with_reloader(self):
        self.debug('Starting subprocess with file monitor')

        with tempfile.NamedTemporaryFile(delete=False) as f:
            filelist_path = f.name

        while True:
            args = [self.quote_first_command_arg(sys.executable)] + sys.argv
            new_environ = os.environ.copy()
            new_environ[self._reloader_environ_key] = 'true'
            new_environ[self._reloader_filelist_environ_key] = filelist_path
            proc = None
            try:
                try:
                    proc = subprocess.Popen(args, env=new_environ)
                    exit_code = proc.wait()
                    proc = None
                    print("Process exited with", exit_code)
                except KeyboardInterrupt:
                    self.info('^C caught in monitor process')
                    return 1
            finally:
                if proc is not None:
                    proc.terminate()
                    self.info(
                        'Waiting for the server to stop. Hit CTRL-C to exit')
                    exit_code = proc.wait()

            if exit_code != 3:
                with open(filelist_path) as f:
                    filelist = [line.strip() for line in f]
                if filelist:
                    self.info("Reloading failed. Waiting for a file to change")
                    mon = Monitor(extra_files=filelist, nomodules=True)
                    while mon.check_reload():
                        time.sleep(1)
                else:
                    return exit_code

            self.info('%s %s %s' % ('-' * 20, 'Restarting', '-' * 20))

    def set_needreload(self):
        self._needreload = True

    def install_reloader(self, poll_interval, extra_files, filelist_path):
        mon = Monitor(
            poll_interval=poll_interval, extra_files=extra_files,
            atexit=self.set_needreload, filelist_path=filelist_path)
        mon_thread = threading.Thread(target=mon.periodic_reload)
        mon_thread.daemon = True
        mon_thread.start()

    def configfiles(self, cwconfig):
        """Generate instance configuration filenames"""
        yield cwconfig.main_config_file()
        for f in (
                'sources', 'logging.conf', 'pyramid.ini', 'pyramid-debug.ini'):
            f = os.path.join(cwconfig.apphome, f)
            if os.path.exists(f):
                yield f

    def i18nfiles(self, cwconfig):
        """Generate instance i18n files"""
        i18ndir = os.path.join(cwconfig.apphome, 'i18n')
        if os.path.exists(i18ndir):
            for lang in cwconfig.available_languages():
                f = os.path.join(i18ndir, lang, 'LC_MESSAGES', 'cubicweb.mo')
                if os.path.exists(f):
                    yield f

    def pyramid_instance(self, appid):
        self._needreload = False

        debugmode = self['debug-mode'] or self['debug']
        autoreload = self['reload'] or self['debug']
        daemonize = not (self['no-daemon'] or debugmode or autoreload)

        if autoreload and not os.environ.get(self._reloader_environ_key):
            return self.restart_with_reloader()

        cwconfig = cwcfg.config_for(appid, debugmode=debugmode)
        if cwversion >= (3, 21, 0):
            cwconfig.cmdline_options = self.config.param
        if autoreload:
            _turn_sigterm_into_systemexit()
            self.debug('Running reloading file monitor')
            extra_files = [sys.argv[0]]
            extra_files.extend(self.configfiles(cwconfig))
            extra_files.extend(self.i18nfiles(cwconfig))
            self.install_reloader(
                self['reload-interval'], extra_files,
                filelist_path=os.environ.get(
                    self._reloader_filelist_environ_key))

        if daemonize:
            self.daemonize(cwconfig['pid-file'])
            self.record_pid(cwconfig['pid-file'])

        if self['dbglevel']:
            self['loglevel'] = 'debug'
            set_debug('|'.join('DBG_' + x.upper() for x in self['dbglevel']))
        init_cmdline_log_threshold(cwconfig, self['loglevel'])

        app = wsgi_application_from_cwconfig(
            cwconfig, profile=self['profile'],
            profile_output=self['profile-output'],
            profile_dump_every=self['profile-dump-every']
        )

        host = cwconfig['interface']
        port = cwconfig['port'] or 8080
        repo = app.application.registry['cubicweb.repository']
        try:
            repo.start_looping_tasks()
            waitress.serve(app, host=host, port=port)
        finally:
            repo.shutdown()
        if self._needreload:
            return 3
        return 0

CWCTL.register(PyramidStartHandler)


def live_pidfile(pidfile):  # pragma: no cover
    """(pidfile:str) -> int | None
    Returns an int found in the named file, if there is one,
    and if there is a running process with that process id.
    Return None if no such process exists.
    """
    pid = read_pidfile(pidfile)
    if pid:
        try:
            os.kill(int(pid), 0)
            return pid
        except OSError as e:
            if e.errno == errno.EPERM:
                return pid
    return None


def read_pidfile(filename):
    if os.path.exists(filename):
        try:
            with open(filename) as f:
                content = f.read()
            return int(content.strip())
        except (ValueError, IOError):
            return None
    else:
        return None


def _turn_sigterm_into_systemexit():
    """Attempts to turn a SIGTERM exception into a SystemExit exception."""
    try:
        import signal
    except ImportError:
        return

    def handle_term(signo, frame):
        raise SystemExit
    signal.signal(signal.SIGTERM, handle_term)


class Monitor(object):
    """A file monitor and server stopper.

    It is a simplified version of pyramid pserve.Monitor, with little changes:

    -   The constructor takes extra_files, atexit, nomodules and filelist_path
    -   The process is stopped by auto-kill with signal SIGTERM
    """

    def __init__(self, poll_interval=1, extra_files=[], atexit=None,
                 nomodules=False, filelist_path=None):
        self.module_mtimes = {}
        self.keep_running = True
        self.poll_interval = poll_interval
        self.extra_files = extra_files
        self.atexit = atexit
        self.nomodules = nomodules
        self.filelist_path = filelist_path

    def _exit(self):
        if self.atexit:
            self.atexit()
        os.kill(os.getpid(), signal.SIGTERM)

    def periodic_reload(self):
        while True:
            if not self.check_reload():
                self._exit()
                break
            time.sleep(self.poll_interval)

    def check_reload(self):
        filenames = list(self.extra_files)

        if not self.nomodules:
            for module in list(sys.modules.values()):
                try:
                    filename = module.__file__
                except (AttributeError, ImportError):
                    continue
                if filename is not None:
                    filenames.append(filename)

        for filename in filenames:
            try:
                stat = os.stat(filename)
                if stat:
                    mtime = stat.st_mtime
                else:
                    mtime = 0
            except (OSError, IOError):
                continue
            if filename.endswith('.pyc') and os.path.exists(filename[:-1]):
                mtime = max(os.stat(filename[:-1]).st_mtime, mtime)
            if filename not in self.module_mtimes:
                self.module_mtimes[filename] = mtime
            elif self.module_mtimes[filename] < mtime:
                print('%s changed; reloading...' % filename)
                return False

        if self.filelist_path:
            with open(self.filelist_path) as f:
                filelist = set((line.strip() for line in f))

            filelist.update(filenames)

            with open(self.filelist_path, 'w') as f:
                for filename in filelist:
                    f.write('%s\n' % filename)

        return True
