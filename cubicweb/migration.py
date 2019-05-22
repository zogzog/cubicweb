# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""utilities for instances migration"""

import sys
import os
import string
import logging
import tempfile
import itertools
import traceback
from os.path import exists, join, basename, splitext
from itertools import chain

from logilab.common import IGNORED_EXTENSIONS
from logilab.common.decorators import cached
from logilab.common.configuration import REQUIRED, read_old_config
from logilab.common.shellutils import ASK
from logilab.common.changelog import Version

from cubicweb import ConfigurationError, ExecutionError, utils
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from cubicweb.toolsutils import show_diffs

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
            print(directory, "doesn't exists, no migration path")
        return []
    if fromversion == toversion:
        return []
    result = []
    for fname in os.listdir(directory):
        if fname.endswith(IGNORED_EXTENSIONS):
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


def execscript_confirm(scriptpath):
    """asks for confirmation before executing a script and provides the
    ability to show the script's content
    """
    while True:
        answer = ASK.ask('Execute %r ?' % scriptpath,
                         ('Y','n','show','abort'), 'Y')
        if answer == 'abort':
            raise SystemExit(1)
        elif answer == 'n':
            return False
        elif answer == 'show':
            stream = open(scriptpath)
            scriptcontent = stream.read()
            stream.close()
            print()
            print(scriptcontent)
            print()
        else:
            return True

def yes(*args, **kwargs):
    return True


class MigrationHelper(object):
    """class holding CubicWeb Migration Actions used by migration scripts"""

    def __init__(self, config, interactive=True, verbosity=1):
        self.config = config
        if config:
            # no config on shell to a remote instance
            self.config.init_log(logthreshold=logging.ERROR)
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
        self._context_stack = []

    def __getattribute__(self, name):
        try:
            return object.__getattribute__(self, name)
        except AttributeError:
            cmd = 'cmd_%s' % name
            # search self.__class__ to avoid infinite recursion
            if hasattr(self.__class__, cmd):
                meth = getattr(self, cmd)
                try:
                    return lambda *args, **kwargs: self.interact(args, kwargs,
                                                                 meth=meth)
                except:
                    _, ex, traceback_ = sys.exc_info()
                    traceback.print_exc()
                    if self.confirm('abort?', pdb=True, traceback=traceback_):
                        raise
            raise
        raise AttributeError(name)

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
        # may be an iterator
        toupgrade = tuple(toupgrade)
        vmap = dict( (cube, (fromver, tover)) for cube, fromver, tover in toupgrade)
        ctx = self.__context
        ctx['versions_map'] = vmap
        if self.config.accept_mode('Any') and 'cubicweb' in vmap:
            migrdir = self.config.migration_scripts_dir()
            self.cmd_process_script(join(migrdir, 'bootstrapmigration_repository.py'))
        for cube, fromversion, toversion in toupgrade:
            if cube == 'cubicweb':
                migrdir = self.config.migration_scripts_dir()
            else:
                migrdir = self.config.cube_migration_scripts_dir(cube)
            scripts = filter_scripts(self.config, migrdir, fromversion, toversion)
            if scripts:
                prevversion = None
                for version, script in scripts:
                    # take care to X.Y.Z_Any.py / X.Y.Z_common.py: we've to call
                    # cube_upgraded once all script of X.Y.Z have been executed
                    if prevversion is not None and version != prevversion:
                        self.cube_upgraded(cube, prevversion)
                    prevversion = version
                    self.cmd_process_script(script)
                self.cube_upgraded(cube, toversion)
            else:
                self.cube_upgraded(cube, toversion)

    def cube_upgraded(self, cube, version):
        pass

    def shutdown(self):
        pass

    def interact(self, args, kwargs, meth):
        """execute the given method according to user's confirmation"""
        msg = 'Execute command: %s(%s) ?' % (
            meth.__name__[4:],
            ', '.join([repr(arg) for arg in args] +
                      ['%s=%r' % (n,v) for n,v in kwargs.items()]))
        if 'ask_confirm' in kwargs:
            ask_confirm = kwargs.pop('ask_confirm')
        else:
            ask_confirm = True
        if not ask_confirm or self.confirm(msg):
            return meth(*args, **kwargs)

    def confirm(self, question, # pylint: disable=E0202
                shell=True, abort=True, retry=False, pdb=False, default='y', traceback=None):
        """ask for confirmation and return true on positive answer

        if `retry` is true the r[etry] answer may return 2
        """
        possibleanswers = ['y', 'n']
        if abort:
            possibleanswers.append('abort')
        if pdb:
            possibleanswers.append('pdb')
        if shell:
            possibleanswers.append('shell')
        if retry:
            possibleanswers.append('retry')
        try:
            answer = ASK.ask(question, possibleanswers, default)
        except (EOFError, KeyboardInterrupt):
            answer = 'abort'
        if answer == 'n':
            return False
        if answer == 'retry':
            return 2
        if answer == 'abort':
            raise SystemExit(1)
        if answer == 'shell':
            self.interactive_shell()
            return self.confirm(question, shell, abort, retry, pdb, default, traceback)
        if answer == 'pdb':
            pdb = utils.get_pdb()
            if traceback:
                pdb.post_mortem(traceback)
            else:
                pdb.set_trace()
            return self.confirm(question, shell, abort, retry, pdb, default, traceback)
        return True

    def interactive_shell(self):
        self.confirm = yes
        self.need_wrap = False
        # avoid '_' to be added to builtins by sys.display_hook
        def do_not_add___to_builtins(obj):
            if obj is not None:
                print(repr(obj))
        sys.displayhook = do_not_add___to_builtins
        local_ctx = self._create_context()
        try:
            import readline
            from cubicweb.toolsutils import CWShellCompleter
        except ImportError:
            # readline not available
            pass
        else:
            rql_completer = CWShellCompleter(local_ctx)
            readline.set_completer(rql_completer.complete)
            readline.parse_and_bind('tab: complete')
            home_key = 'HOME'
            if sys.platform == 'win32':
                home_key = 'USERPROFILE'
            histfile = os.path.join(os.environ[home_key], ".cwshell_history")
            try:
                readline.read_history_file(histfile)
            except IOError:
                pass
        from code import interact
        banner = """entering the migration python shell
just type migration commands or arbitrary python code and type ENTER to execute it
type "exit" or Ctrl-D to quit the shell and resume operation"""

        # use ipython if available
        try:
            from IPython import start_ipython
            print(banner)
            start_ipython(argv=[], user_ns=local_ctx)
        except ImportError:
            interact(banner, local=local_ctx)

            try:
                readline.write_history_file(histfile)
            except IOError:
                pass

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

    def update_context(self, key, value):
        for context in self._context_stack:
            context[key] = value
        self.__context[key] = value

    def cmd_process_script(self, migrscript, funcname=None, *args, **kwargs):
        """execute a migration script in interactive mode

        Display the migration script path, ask for confirmation and execute it
        if confirmed

        Allowed input file formats for migration scripts:
        - `python` (.py)
        - `sql` (.sql)
        - `doctest` (.txt or .rst)

        .. warning:: sql migration scripts are not available in web-only instance

        You can pass script parameters with using double dash (--) in the
        command line

        Context environment can have these variables defined:
        - __name__ : will be determine by funcname parameter
        - __file__ : is the name of the script if it exists
        - __args__ : script arguments coming from command-line

        :param migrscript: name of the script
        :param funcname: defines __name__ inside the shell (or use __main__)
        :params args: optional arguments for funcname
        :keyword scriptargs: optional arguments of the script
        """
        ftypes = {'python':  ('.py',),
                  'doctest': ('.txt', '.rst'),
                  'sql':     ('.sql',)}
        # sql migration scripts are not available in web-only instance
        if not hasattr(self, "session"):
            ftypes.pop('sql')
        migrscript = os.path.normpath(migrscript)
        for (script_mode, ftype) in ftypes.items():
            if migrscript.endswith(ftype):
                break
        else:
            ftypes = ', '.join(chain(*ftypes.values()))
            msg = 'ignoring %s, not a valid script extension (%s)'
            raise ExecutionError(msg % (migrscript, ftypes))
        if not self.execscript_confirm(migrscript):
            return
        scriptlocals = self._create_context().copy()
        scriptlocals.update({'__file__': migrscript,
                             '__args__': kwargs.pop("scriptargs", [])})
        self._context_stack.append(scriptlocals)
        if script_mode == 'python':
            if funcname is None:
                pyname = '__main__'
            else:
                pyname = splitext(basename(migrscript))[0]
            scriptlocals['__name__'] = pyname
            with open(migrscript, 'rb') as fobj:
                fcontent = fobj.read()
            code = compile(fcontent, migrscript, 'exec')
            exec(code, scriptlocals)
            if funcname is not None:
                try:
                    func = scriptlocals[funcname]
                    self.info('found %s in locals', funcname)
                    assert callable(func), '%s (%s) is not callable' % (func, funcname)
                except KeyError:
                    self.critical('no %s in script %s', funcname, migrscript)
                    return None
                return func(*args, **kwargs)
        elif script_mode == 'sql':
            from cubicweb.server.sqlutils import sqlexec
            sqlexec(open(migrscript).read(), self.session.system_sql)
            self.commit()
        else: # script_mode == 'doctest'
            import doctest
            return doctest.testfile(migrscript, module_relative=False,
                                    optionflags=doctest.ELLIPSIS,
                                    # verbose mode when user input is expected
                                    verbose=self.verbosity==2,
                                    report=True,
                                    encoding='utf-8',
                                    globs=scriptlocals)
        self._context_stack.pop()

    def cmd_option_renamed(self, oldname, newname):
        """a configuration option has been renamed"""
        self._option_changes.append(('renamed', oldname, newname))

    def cmd_option_group_changed(self, option, oldgroup, newgroup):
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
        if isinstance(cubes, str):
            cubes = (cubes,)
        origcubes = self.config.cubes()
        newcubes = [p for p in self.config.expand_cubes(cubes)
                    if not p in origcubes]
        if newcubes:
            self.config.add_cubes(newcubes)
        return newcubes

    def cmd_drop_cube(self, cube, removedeps=False):
        if removedeps:
            toremove = self.config.expand_cubes([cube])
        else:
            toremove = (cube,)
        origcubes = self.config._cubes
        basecubes = [c for c in origcubes if not c in toremove]
        # don't fake-add any new ones, or we won't be able to really-add them later
        self.config._cubes = tuple(cube for cube in self.config.expand_cubes(basecubes)
                                   if cube in origcubes)
        removed = [p for p in origcubes if not p in self.config._cubes]
        if not cube in removed and cube in origcubes:
            raise ConfigurationError("can't remove cube %s, "
                                     "used as a dependency" % cube)
        return removed

    def rewrite_configuration(self):
        configfile = self.config.main_config_file()
        if self._option_changes:
            read_old_config(self.config, self._option_changes, configfile)
        fd, newconfig = tempfile.mkstemp()
        for optdescr in self._option_changes:
            if optdescr[0] == 'added':
                optdict = self.config.get_option_def(optdescr[1])
                if optdict.get('default') is REQUIRED:
                    self.config.input_option(optdescr[1], optdict)
        self.config.generate_config(open(newconfig, 'w'))
        show_diffs(configfile, newconfig, askconfirm=self.confirm is not yes)
        os.close(fd)
        if exists(newconfig):
            os.unlink(newconfig)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(MigrationHelper, getLogger('cubicweb.migration'))


def version_strictly_lower(a, b):
    if a is None:
        return True
    if b is None:
        return False
    if a:
        a = Version(a)
    if b:
        b = Version(b)
    return a < b

def max_version(a, b):
    return str(max(Version(a), Version(b)))


def split_constraint(constraint):
    oper = itertools.takewhile(lambda x: x in "<>=", constraint)
    version = itertools.dropwhile(lambda x: x not in string.digits + ".", constraint)

    return "".join(oper), "".join(version)


class ConfigurationProblem(object):
    """Each cube has its own list of dependencies on other cubes/versions.

    The ConfigurationProblem is used to record the loaded cubes, then to detect
    inconsistencies in their dependencies.

    See configuration management on wikipedia for litterature.
    """

    def __init__(self, config):
        self.config = config
        self.cubes = {'cubicweb': cwcfg.cubicweb_version()}

    def add_cube(self, name, version):
        self.cubes[name] = version

    def solve(self):
        self.warnings = []
        self.errors = []
        self.dependencies = {}
        self.reverse_dependencies = {}
        self.constraints = {}
        # read dependencies
        for cube in self.cubes:
            if cube == 'cubicweb': continue
            self.dependencies[cube] = dict(self.config.cube_dependencies(cube))
            self.dependencies[cube]['cubicweb'] = self.config.cube_depends_cubicweb_version(cube)
        # compute reverse dependencies
        for cube, dependencies in self.dependencies.items():
            for name, constraint in dependencies.items():
                self.reverse_dependencies.setdefault(name,set())
                if constraint:
                    try:
                        oper, version = split_constraint(constraint)
                        self.reverse_dependencies[name].add( (oper, version, cube) )
                    except Exception:
                        self.warnings.append(
                            'cube %s depends on %s but constraint badly '
                            'formatted: %s' % (cube, name, constraint))
                else:
                    self.reverse_dependencies[name].add( (None, None, cube) )
        # check consistency
        for cube, versions in sorted(self.reverse_dependencies.items()):
            oper, version, source = None, None, None
            # simplify constraints
            if versions:
                for constraint in versions:
                    op, ver, src = constraint
                    if oper is None:
                        oper = op
                        version = ver
                        source = src
                    elif op == '>=' and oper == '>=':
                        if version_strictly_lower(version, ver):
                            version = ver
                            source = src
                    elif op == None:
                        continue
                    else:
                        print('unable to handle %s in %s, set to `%s %s` '
                              'but currently up to `%s %s`' %
                              (cube, source, oper, version, op, ver))
            # "solve" constraint satisfaction problem
            if cube not in self.cubes:
                self.errors.append( ('add', cube, version, source) )
            elif versions:
                lower_strict = version_strictly_lower(self.cubes[cube], version)
                if oper in ('>=','=','=='):
                    if lower_strict:
                        self.errors.append( ('update', cube, version, source) )
                elif oper is None:
                    pass # no constraint on version
                else:
                    print('unknown operator', oper)
