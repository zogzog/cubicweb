"""utility to ease migration of application version to newly installed
version

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
import os
import logging
from tempfile import mktemp
from os.path import exists, join, basename, splitext

from logilab.common.decorators import cached
from logilab.common.configuration import REQUIRED, read_old_config


def migration_files(config, toupgrade):
    """return an orderer list of path of scripts to execute to upgrade
    an installed application according to installed cube and cubicweb versions
    """
    merged = []
    for cube, fromversion, toversion in toupgrade:
        if cube == 'cubicweb':
            migrdir = config.migration_scripts_dir()
        else:
            migrdir = config.cube_migration_scripts_dir(cube)
        scripts = filter_scripts(config, migrdir, fromversion, toversion)
        merged += [s[1] for s in scripts]
    if config.accept_mode('Any'):
        migrdir = config.migration_scripts_dir()
        merged.insert(0, join(migrdir, 'bootstrapmigration_repository.py'))
    return merged


def filter_scripts(config, directory, fromversion, toversion, quiet=True):
    """return a list of paths of migration files to consider to upgrade
    from a version to a greater one
    """
    from logilab.common.changelog import Version # doesn't work with appengine
    assert fromversion
    assert toversion
    assert isinstance(fromversion, tuple), fromversion.__class__
    assert isinstance(toversion, tuple), toversion.__class__
    assert fromversion <= toversion, (fromversion, toversion)
    if not exists(directory):
        if not quiet:
            print directory, "doesn't exists, no migration path"
        return []
    if fromversion == toversion:
        return []
    result = []
    for fname in os.listdir(directory):
        if fname.endswith('.pyc') or fname.endswith('.pyo') \
               or fname.endswith('~'):
            continue
        fpath = join(directory, fname)
        try:
            tver, mode = fname.split('_', 1)
        except ValueError:
            continue
        mode = mode.split('.', 1)[0]
        if not config.accept_mode(mode):
            continue
        try:
            tver = Version(tver)
        except ValueError:
            continue
        if tver <= fromversion:
            continue
        if tver > toversion:
            continue
        result.append((tver, fpath))
    # be sure scripts are executed in order
    return sorted(result)


IGNORED_EXTENSIONS = ('.swp', '~')


def execscript_confirm(scriptpath):
    """asks for confirmation before executing a script and provides the
    ability to show the script's content
    """
    while True:
        confirm = raw_input('** execute %r (Y/n/s[how]) ?' % scriptpath)
        confirm = confirm.strip().lower()
        if confirm in ('n', 'no'):
            return False
        elif confirm in ('s', 'show'):
            stream = open(scriptpath)
            scriptcontent = stream.read()
            stream.close()
            print
            print scriptcontent
            print
        else:
            return True

def yes(*args, **kwargs):
    return True


class MigrationHelper(object):
    """class holding CubicWeb Migration Actions used by migration scripts"""

    def __init__(self, config, interactive=True, verbosity=1):
        self.config = config
        self.config.init_log(logthreshold=logging.ERROR, debug=True)
        # 0: no confirmation, 1: only main commands confirmed, 2 ask for everything
        self.verbosity = verbosity
        self.need_wrap = True
        if not interactive or not verbosity:
            self.confirm = yes
            self.execscript_confirm = yes
        else:
            self.execscript_confirm = execscript_confirm
        self._option_changes = []
        self.__context = {'confirm': self.confirm,
                          'config': self.config,
                          'interactive_mode': interactive,
                          }

    def repo_connect(self):
        return self.config.repository()

    def migrate(self, vcconf, toupgrade, options):
        """upgrade the given set of cubes

        `cubes` is an ordered list of 3-uple:
        (cube, fromversion, toversion)
        """
        if options.fs_only:
            # monkey path configuration.accept_mode so database mode (e.g. Any)
            # won't be accepted
            orig_accept_mode = self.config.accept_mode
            def accept_mode(mode):
                if mode == 'Any':
                    return False
                return orig_accept_mode(mode)
            self.config.accept_mode = accept_mode
        scripts = migration_files(self.config, toupgrade)
        if scripts:
            vmap = dict( (pname, (fromver, tover)) for pname, fromver, tover in toupgrade)
            self.__context.update({'applcubicwebversion': vcconf['cubicweb'],
                                   'cubicwebversion': self.config.cubicweb_version(),
                                   'versions_map': vmap})
            self.scripts_session(scripts)
        else:
            print 'no migration script to execute'

    def shutdown(self):
        pass

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            cmd = 'cmd_%s' % name
            if hasattr(self, cmd):
                meth = getattr(self, cmd)
                return lambda *args, **kwargs: self.interact(args, kwargs,
                                                             meth=meth)
            raise
        raise AttributeError(name)

    def interact(self, args, kwargs, meth):
        """execute the given method according to user's confirmation"""
        msg = 'execute command: %s(%s) ?' % (
            meth.__name__[4:],
            ', '.join([repr(arg) for arg in args] +
                      ['%s=%r' % (n,v) for n,v in kwargs.items()]))
        if 'ask_confirm' in kwargs:
            ask_confirm = kwargs.pop('ask_confirm')
        else:
            ask_confirm = True
        if not ask_confirm or self.confirm(msg):
            return meth(*args, **kwargs)

    def confirm(self, question, shell=True, abort=True, retry=False):
        """ask for confirmation and return true on positive answer

        if `retry` is true the r[etry] answer may return 2
        """
        print question,
        possibleanswers = 'Y/n'
        if abort:
            possibleanswers += '/a[bort]'
        if shell:
            possibleanswers += '/s[hell]'
        if retry:
            possibleanswers += '/r[etry]'
        try:
            confirm = raw_input('(%s): ' % ( possibleanswers, ))
            answer = confirm.strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = 'abort'
        if answer in ('n', 'no'):
            return False
        if answer in ('r', 'retry'):
            return 2
        if answer in ('a', 'abort'):
            self.rollback()
            raise SystemExit(1)
        if shell and answer in ('s', 'shell'):
            self.interactive_shell()
            return self.confirm(question)
        return True

    def interactive_shell(self):
        self.confirm = yes
        self.need_wrap = False
        # avoid '_' to be added to builtins by sys.display_hook
        def do_not_add___to_builtins(obj):
            if obj is not None:
                print repr(obj)
        sys.displayhook = do_not_add___to_builtins
        local_ctx = self._create_context()
        try:
            import readline
            from rlcompleter import Completer
        except ImportError:
            # readline not available
            pass
        else:
            readline.set_completer(Completer(local_ctx).complete)
            readline.parse_and_bind('tab: complete')
            histfile = os.path.join(os.environ["HOME"], ".eshellhist")
            try:
                readline.read_history_file(histfile)
            except IOError:
                pass
        from code import interact
        banner = """entering the migration python shell
just type migration commands or arbitrary python code and type ENTER to execute it
type "exit" or Ctrl-D to quit the shell and resume operation"""
        # give custom readfunc to avoid http://bugs.python.org/issue1288615
        def unicode_raw_input(prompt):
            return unicode(raw_input(prompt), sys.stdin.encoding)
        interact(banner, readfunc=unicode_raw_input, local=local_ctx)
        readline.write_history_file(histfile)
        # delete instance's confirm attribute to avoid questions
        del self.confirm
        self.need_wrap = True

    @cached
    def _create_context(self):
        """return a dictionary to use as migration script execution context"""
        context = self.__context
        for attr in dir(self):
            if attr.startswith('cmd_'):
                if self.need_wrap:
                    context[attr[4:]] = getattr(self, attr[4:])
                else:
                    context[attr[4:]] = getattr(self, attr)
        return context

    def process_script(self, migrscript, funcname=None, *args, **kwargs):
        """execute a migration script
        in interactive mode,  display the migration script path, ask for
        confirmation and execute it if confirmed
        """
        assert migrscript.endswith('.py'), migrscript
        if self.execscript_confirm(migrscript):
            scriptlocals = self._create_context().copy()
            if funcname is None:
                pyname = '__main__'
            else:
                pyname = splitext(basename(migrscript))[0]
            scriptlocals.update({'__file__': migrscript, '__name__': pyname})
            execfile(migrscript, scriptlocals)
            if funcname is not None:
                try:
                    func = scriptlocals[funcname]
                    self.info('found %s in locals', funcname)
                    assert callable(func), '%s (%s) is not callable' % (func, funcname)
                except KeyError:
                    self.critical('no %s in script %s', funcname, migrscript)
                    return None
                return func(*args, **kwargs)

    def scripts_session(self, migrscripts):
        """execute some scripts in a transaction"""
        try:
            for migrscript in migrscripts:
                self.process_script(migrscript)
            self.commit()
        except:
            self.rollback()
            raise

    def cmd_option_renamed(self, oldname, newname):
        """a configuration option has been renamed"""
        self._option_changes.append(('renamed', oldname, newname))

    def cmd_option_group_change(self, option, oldgroup, newgroup):
        """a configuration option has been moved in another group"""
        self._option_changes.append(('moved', option, oldgroup, newgroup))

    def cmd_option_added(self, optname):
        """a configuration option has been added"""
        self._option_changes.append(('added', optname))

    def cmd_option_removed(self, optname):
        """a configuration option has been removed"""
        # can safely be ignored
        #self._option_changes.append(('removed', optname))

    def cmd_option_type_changed(self, optname, oldtype, newvalue):
        """a configuration option's type has changed"""
        self._option_changes.append(('typechanged', optname, oldtype, newvalue))

    def cmd_add_cubes(self, cubes):
        """modify the list of used cubes in the in-memory config
        returns newly inserted cubes, including dependencies
        """
        if isinstance(cubes, basestring):
            cubes = (cubes,)
        origcubes = self.config.cubes()
        newcubes = [p for p in self.config.expand_cubes(cubes)
                       if not p in origcubes]
        if newcubes:
            for cube in cubes:
                assert cube in newcubes
            self.config.add_cubes(newcubes)
        return newcubes

    def cmd_remove_cube(self, cube):
        origcubes = self.config._cubes
        basecubes = list(origcubes)
        for pkg in self.config.expand_cubes([cube]):
            try:
                basecubes.remove(pkg)
            except ValueError:
                continue
        self.config._cubes = tuple(self.config.expand_cubes(basecubes))
        removed = [p for p in origcubes if not p in self.config._cubes]
        assert cube in removed, \
               "can't remove cube %s, used as a dependancy" % cube
        return removed

    def rewrite_configuration(self):
        # import locally, show_diffs unavailable in gae environment
        from cubicweb.toolsutils import show_diffs
        configfile = self.config.main_config_file()
        if self._option_changes:
            read_old_config(self.config, self._option_changes, configfile)
        newconfig = mktemp()
        for optdescr in self._option_changes:
            if optdescr[0] == 'added':
                optdict = self.config.get_option_def(optdescr[1])
                if optdict.get('default') is REQUIRED:
                    self.config.input_option(optdescr[1], optdict)
        self.config.generate_config(open(newconfig, 'w'))
        show_diffs(configfile, newconfig)
        if exists(newconfig):
            os.unlink(newconfig)


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(MigrationHelper, getLogger('cubicweb.migration'))
