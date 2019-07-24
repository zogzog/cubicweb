# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# copyright 2014-2016 UNLISH S.A.S. (Montpellier, FRANCE), all rights reserved.
#
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
Provides a 'pyramid' command as a replacement to the 'start' command.

The reloading strategy is heavily inspired by (and partially copied from)
the pyramid script 'pserve'.
"""

import os
import signal
import sys
import time
import threading
import subprocess

from logilab.common.configuration import merge_options

from cubicweb.cwctl import CWCTL, InstanceCommand, init_cmdline_log_threshold
from cubicweb.pyramid import wsgi_application_from_cwconfig
from cubicweb.pyramid.config import get_random_secret_key
from cubicweb.view import inject_html_generating_call_on_w
from cubicweb.server import serverctl
from cubicweb.web.webctl import WebCreateHandler
from cubicweb.toolsutils import fill_templated_file

import waitress

MAXFD = 1024


def _generate_pyramid_ini_file(pyramid_ini_path):
    """Write a 'pyramid.ini' file into apphome."""
    template_fpath = os.path.join(os.path.dirname(__file__), 'pyramid.ini.tmpl')
    context = {
        'secret_1': get_random_secret_key(),
        'secret_2': get_random_secret_key(),
        'secret_3': get_random_secret_key(),
    }
    fill_templated_file(template_fpath, pyramid_ini_path, context)


class PyramidCreateHandler(serverctl.RepositoryCreateHandler,
                           WebCreateHandler):
    cfgname = 'pyramid'

    def bootstrap(self, cubes, automatic=False, inputlevel=0):
        serverctl.RepositoryCreateHandler.bootstrap(self, cubes, automatic, inputlevel)
        # Call WebCreateHandler.bootstrap to prompt about get anonymous-user.
        WebCreateHandler.bootstrap(self, cubes, automatic, inputlevel)
        self.config.write_development_ini(cubes)


class AllInOneCreateHandler(serverctl.RepositoryCreateHandler,
                            WebCreateHandler):
    """configuration to get an instance running in a Pyramid web server
    integrating a repository server in the same process
    """
    cfgname = 'all-in-one'

    def bootstrap(self, cubes, automatic=False, inputlevel=0):
        """bootstrap this configuration"""
        serverctl.RepositoryCreateHandler.bootstrap(self, cubes, automatic, inputlevel)
        WebCreateHandler.bootstrap(self, cubes, automatic, inputlevel)
        _generate_pyramid_ini_file(os.path.join(self.config.apphome, "pyramid.ini"))


class PyramidStartHandler(InstanceCommand):
    """Start an interactive pyramid server.

    <instance>
      identifier of the instance to configure.
    """
    name = 'pyramid'
    actionverb = 'started'

    options = merge_options((
        ('debug-mode',
         {'action': 'store_true',
          'help': 'Activate the repository debug mode ('
                  'logs in the console and the debug toolbar).'}),
        ('debug',
         {'short': 'D', 'action': 'store_true',
          'help': 'Equals to "--debug-mode --reload"'}),
        ('toolbar',
         {'short': 't', 'action': 'store_true',
          'help': 'Activate the pyramid debug toolbar'
                  '(the pypi "pyramid_debugtoolbar" package must be installed)'}),
        ('reload',
         {'action': 'store_true',
          'help': 'Restart the server if any source file is changed'}),
        ('reload-interval',
         {'type': 'int', 'default': 1,
          'help': 'Interval, in seconds, between file modifications checks'}),
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
        ('param',
         {'short': 'p',
          'type': 'named',
          'metavar': 'key1:value1,key2:value2',
          'default': {},
          'help': 'override <key> configuration file option with <value>.'}),
    ) + InstanceCommand.options)

    _reloader_environ_key = 'CW_RELOADER_SHOULD_RUN'

    def debug(self, msg):
        print('DEBUG - %s' % msg)

    def info(self, msg):
        print('INFO - %s' % msg)

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

    def restart_with_reloader(self, filelist_path):
        self.debug('Starting subprocess with file monitor')

        # Create or clear monitored files list file.
        with open(filelist_path, 'w') as f:
            pass

        while True:
            args = [self.quote_first_command_arg(sys.executable)] + sys.argv
            new_environ = os.environ.copy()
            new_environ[self._reloader_environ_key] = 'true'
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

        autoreload = self['reload'] or self['debug']

        cwconfig = self.cwconfig
        filelist_path = os.path.join(cwconfig.apphome,
                                     '.pyramid-reload-files.list')

        pyramid_ini_path = os.path.join(cwconfig.apphome, "pyramid.ini")
        if not os.path.exists(pyramid_ini_path):
            _generate_pyramid_ini_file(pyramid_ini_path)

        if autoreload and not os.environ.get(self._reloader_environ_key):
            return self.restart_with_reloader(filelist_path)

        if autoreload:
            _turn_sigterm_into_systemexit()
            self.debug('Running reloading file monitor')
            extra_files = [sys.argv[0]]
            extra_files.extend(self.configfiles(cwconfig))
            extra_files.extend(self.i18nfiles(cwconfig))
            self.install_reloader(
                self['reload-interval'], extra_files,
                filelist_path=filelist_path)

        # if no loglevel is specified and --debug is here, set log level at debug
        if self['loglevel'] is None and self['debug']:
            init_cmdline_log_threshold(self.cwconfig, 'debug')

        # if the debugtoolbar is activated, test if it's importable
        if self['toolbar']:
            try:
                import pyramid_debugtoolbar  # noqa
            except ImportError:
                print("Error: you've tried to activate the pyramid debugtoolbar but it failed to "
                      "import, make sure it's correctly installed by doing a "
                      "'pip install pyramid_debugtoolbar'.\nYou can find more information on the "
                      "official documentation: "
                      "https://docs.pylonsproject.org/projects/pyramid_debugtoolbar/en/latest/")
                sys.exit(1)

        if self['debug']:
            # this is for injecting those into generated html:
            # > cubicweb-generated-by="module.Class" cubicweb-from-source="/path/to/file.py:42"
            inject_html_generating_call_on_w()

        app = wsgi_application_from_cwconfig(
            cwconfig, profile=self['profile'],
            profile_output=self['profile-output'],
            profile_dump_every=self['profile-dump-every'],
            debugtoolbar=self['toolbar']
        )

        host = cwconfig['interface']
        port = cwconfig['port'] or 8080
        url_scheme = ('https' if cwconfig['base-url'].startswith('https')
                      else 'http')
        repo = app.application.registry['cubicweb.repository']
        try:
            waitress.serve(app, host=host, port=port, url_scheme=url_scheme,
                           clear_untrusted_proxy_headers=True)
        finally:
            repo.shutdown()
        if self._needreload:
            return 3
        return 0


CWCTL.register(PyramidStartHandler)


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
