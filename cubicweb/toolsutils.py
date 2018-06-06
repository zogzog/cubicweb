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
"""some utilities for cubicweb command line tools"""
from __future__ import print_function


# XXX move most of this in logilab.common (shellutils ?)

import io
import os
import sys
import subprocess
from os import listdir, makedirs, chmod, walk, remove
from os.path import exists, join, normpath
import re
from rlcompleter import Completer
try:
    import readline
except ImportError:  # readline not available, no completion
    pass
try:
    from os import symlink
except ImportError:
    def symlink(*args):
        raise NotImplementedError

from six import add_metaclass

from logilab.common.clcommands import Command as BaseCommand
from logilab.common.shellutils import ASK

from cubicweb import warning  # pylint: disable=E0611
from cubicweb import ConfigurationError, ExecutionError


def underline_title(title, car='-'):
    return title + '\n' + (car * len(title))


def iter_dir(directory, condition_file=None, ignore=()):
    """iterate on a directory"""
    for sub in listdir(directory):
        if sub in ('CVS', '.svn', '.hg'):
            continue
        if condition_file is not None and \
                not exists(join(directory, sub, condition_file)):
            continue
        if sub in ignore:
            continue
        yield sub


def create_dir(directory):
    """create a directory if it doesn't exist yet"""
    try:
        makedirs(directory)
        print('-> created directory %s' % directory)
    except OSError as ex:
        import errno
        if ex.errno != errno.EEXIST:
            raise
        print('-> no need to create existing directory %s' % directory)


def create_symlink(source, target):
    """create a symbolic link"""
    if exists(target):
        remove(target)
    symlink(source, target)
    print('[symlink] %s <-- %s' % (target, source))


def create_copy(source, target):
    import shutil
    print('[copy] %s <-- %s' % (target, source))
    shutil.copy2(source, target)


def rm(whatever):
    import shutil
    shutil.rmtree(whatever)
    print('-> removed %s' % whatever)


def show_diffs(appl_file, ref_file, askconfirm=True):
    """interactivly replace the old file with the new file according to
    user decision
    """
    import shutil
    pipe = subprocess.Popen(['diff', '-u', appl_file, ref_file], stdout=subprocess.PIPE)
    diffs = pipe.stdout.read().decode('utf-8')
    if diffs:
        if askconfirm:
            print()
            print(diffs)
            action = ASK.ask('Replace ?', ('Y', 'n', 'q'), 'Y').lower()
        else:
            action = 'y'
        if action == 'y':
            try:
                shutil.copyfile(ref_file, appl_file)
            except IOError:
                os.system('chmod a+w %s' % appl_file)
                shutil.copyfile(ref_file, appl_file)
            print('replaced')
        elif action == 'q':
            sys.exit(0)
        else:
            copy_file = appl_file + '.default'
            copy = open(copy_file, 'w')
            copy.write(open(ref_file).read())
            copy.close()
            print('keep current version, the new file has been written to', copy_file)
    else:
        print('no diff between %s and %s' % (appl_file, ref_file))


SKEL_EXCLUDE = ('*.py[co]', '*.orig', '*~', '*_flymake.py')


def copy_skeleton(skeldir, targetdir, context,
                  exclude=SKEL_EXCLUDE, askconfirm=False):
    import shutil
    from fnmatch import fnmatch
    skeldir = normpath(skeldir)
    targetdir = normpath(targetdir)
    for dirpath, dirnames, filenames in walk(skeldir):
        tdirpath = dirpath.replace(skeldir, targetdir)
        if 'cubicweb_CUBENAME' in tdirpath:
            tdirpath = tdirpath.replace('cubicweb_CUBENAME',
                                        'cubicweb_' + context['cubename'])
        create_dir(tdirpath)
        for fname in filenames:
            if any(fnmatch(fname, pat) for pat in exclude):
                continue
            fpath = join(dirpath, fname)
            if 'CUBENAME' in fname:
                tfpath = join(tdirpath, fname.replace('CUBENAME', context['cubename']))
            elif 'DISTNAME' in fname:
                tfpath = join(tdirpath, fname.replace('DISTNAME', context['distname']))
            else:
                tfpath = join(tdirpath, fname)
            if fname.endswith('.tmpl'):
                tfpath = tfpath[:-5]
                if not askconfirm or not exists(tfpath) or \
                        ASK.confirm('%s exists, overwrite?' % tfpath):
                    fill_templated_file(fpath, tfpath, context)
                    print('[generate] %s <-- %s' % (tfpath, fpath))
            elif exists(tfpath):
                show_diffs(tfpath, fpath, askconfirm)
            else:
                shutil.copyfile(fpath, tfpath)
                shutil.copymode(fpath, tfpath)


def fill_templated_file(fpath, tfpath, context):
    with io.open(fpath, encoding='ascii') as fobj:
        template = fobj.read()
    with io.open(tfpath, 'w', encoding='ascii') as fobj:
        fobj.write(template % context)


def restrict_perms_to_user(filepath, log=None):
    """set -rw------- permission on the given file"""
    if log:
        log('set permissions to 0600 for %s', filepath)
    else:
        print('-> set permissions to 0600 for %s' % filepath)
    chmod(filepath, 0o600)


def option_value_from_env(option, default=None):
    """Return the value of configuration `option` from cannonical environment
    variable.
    """
    envvar = ('CW_' + '_'.join(option.split('-'))).upper()
    return os.environ.get(envvar, default)


def read_config(config_file, raise_if_unreadable=False):
    """read some simple configuration from `config_file` and return it as a
    dictionary. If `raise_if_unreadable` is false (the default), an empty
    dictionary will be returned if the file is inexistant or unreadable, else
    :exc:`ExecutionError` will be raised.
    """
    from logilab.common.fileutils import lines
    config = current = {}
    try:
        for line in lines(config_file, comments='#'):
            try:
                option, value = line.split('=', 1)
            except ValueError:
                option = line.strip().lower()
                if option[0] == '[':
                    # start a section
                    section = option[1:-1]
                    assert section not in config, \
                        'Section %s is defined more than once' % section
                    config[section] = current = {}
                    continue
                sys.stderr.write('ignoring malformed line\n%r\n' % line)
                continue
            option = option.strip().replace(' ', '_')
            value = option_value_from_env(option, value.strip())
            current[option] = value or None
    except IOError as ex:
        if raise_if_unreadable:
            raise ExecutionError('%s. Are you logged with the correct user '
                                 'to use this instance?' % ex)
        else:
            warning('missing or non readable configuration file %s (%s)',
                    config_file, ex)
    return config


_HDLRS = {}


class metacmdhandler(type):
    def __new__(mcs, name, bases, classdict):
        cls = super(metacmdhandler, mcs).__new__(mcs, name, bases, classdict)
        if getattr(cls, 'cfgname', None) and getattr(cls, 'cmdname', None):
            _HDLRS.setdefault(cls.cmdname, []).append(cls)
        return cls


@add_metaclass(metacmdhandler)
class CommandHandler(object):
    """configuration specific helper for cubicweb-ctl commands"""

    def __init__(self, config):
        self.config = config


class Command(BaseCommand):
    """base class for cubicweb-ctl commands"""

    def config_helper(self, config, required=True, cmdname=None):
        if cmdname is None:
            cmdname = self.name
        for helpercls in _HDLRS.get(cmdname, ()):
            if helpercls.cfgname == config.name:
                return helpercls(config)
        if config.name == 'all-in-one':
            for helpercls in _HDLRS.get(cmdname, ()):
                if helpercls.cfgname == 'repository':
                    return helpercls(config)
        if required:
            msg = 'No helper for command %s using %s configuration' % (
                cmdname, config.name)
            raise ConfigurationError(msg)

    def fail(self, reason):
        print("command failed:", reason)
        sys.exit(1)


CONNECT_OPTIONS = (
    ("user",
     {'short': 'u', 'type': 'string', 'metavar': '<user>',
      'help': 'connect as <user> instead of being prompted to give it.',
      }
     ),
    ("password",
     {'short': 'p', 'type': 'password', 'metavar': '<password>',
      'help': 'automatically give <password> for authentication instead of \
being prompted to give it.',
      }),
    ("host",
     {'short': 'H', 'type': 'string', 'metavar': '<hostname>',
      'default': None,
      'help': 'specify the name server\'s host name. Will be detected by \
broadcast if not provided.',
      }),
)

# cwshell helpers #############################################################


class AbstractMatcher(object):
    """Abstract class for CWShellCompleter's matchers.

    A matcher should implement a ``possible_matches`` method. This
    method has to return the list of possible completions for user's input.
    Because of the python / readline interaction, each completion should
    be a superset of the user's input.

    NOTE: readline tokenizes user's input and only passes last token to
    completers.
    """

    def possible_matches(self, text):
        """return possible completions for user's input.

        Parameters:
            text: the user's input

        Return:
            a list of completions. Each completion includes the original input.
        """
        raise NotImplementedError()


class RQLExecuteMatcher(AbstractMatcher):
    """Custom matcher for rql queries.

    If user's input starts with ``rql(`` or ``session.execute(`` and
    the corresponding rql query is incomplete, suggest some valid completions.
    """
    query_match_rgx = re.compile(
        r'(?P<func_prefix>\s*(?:rql)'  # match rql, possibly indented
        r'|'                           # or
        r'\s*(?:\w+\.execute))'        # match .execute, possibly indented
        # end of <func_prefix>
        r'\('                          # followed by a parenthesis
        r'(?P<quote_delim>["\'])'      # a quote or double quote
        r'(?P<parameters>.*)')         # and some content

    def __init__(self, local_ctx, req):
        self.local_ctx = local_ctx
        self.req = req
        self.schema = req.vreg.schema
        self.rsb = req.vreg['components'].select('rql.suggestions', req)

    @staticmethod
    def match(text):
        """check if ``text`` looks like a call to ``rql`` or ``session.execute``

        Parameters:
            text: the user's input

        Returns:
            None if it doesn't match, the query structure otherwise.
        """
        query_match = RQLExecuteMatcher.query_match_rgx.match(text)
        if query_match is None:
            return None
        parameters_text = query_match.group('parameters')
        quote_delim = query_match.group('quote_delim')
        # first parameter is fully specified, no completion needed
        if re.match(r"(.*?)%s" % quote_delim, parameters_text) is not None:
            return None
        func_prefix = query_match.group('func_prefix')
        return {
            # user's input
            'text': text,
            # rql( or session.execute(
            'func_prefix': func_prefix,
            # offset of rql query
            'rql_offset': len(func_prefix) + 2,
            # incomplete rql query
            'rql_query': parameters_text,
        }

    def possible_matches(self, text):
        """call ``rql.suggestions`` component to complete user's input.
        """
        # readline will only send last token, but we need the entire user's input
        user_input = readline.get_line_buffer()
        query_struct = self.match(user_input)
        if query_struct is None:
            return []
        else:
            # we must only send completions of the last token => compute where it
            # starts relatively to the rql query itself.
            completion_offset = readline.get_begidx() - query_struct['rql_offset']
            rql_query = query_struct['rql_query']
            return [suggestion[completion_offset:]
                    for suggestion in self.rsb.build_suggestions(rql_query)]


class DefaultMatcher(AbstractMatcher):
    """Default matcher: delegate to standard's `rlcompleter.Completer`` class
    """

    def __init__(self, local_ctx):
        self.completer = Completer(local_ctx)

    def possible_matches(self, text):
        if "." in text:
            return self.completer.attr_matches(text)
        else:
            return self.completer.global_matches(text)


class CWShellCompleter(object):
    """Custom auto-completion helper for cubicweb-ctl shell.

    ``CWShellCompleter`` provides a ``complete`` method suitable for
    ``readline.set_completer``.

    Attributes:
        matchers: the list of ``AbstractMatcher`` instances that will suggest
                  possible completions

    The completion process is the following:

    - readline calls the ``complete`` method with user's input,
    - the ``complete`` method asks for each known matchers if
      it can suggest completions for user's input.
    """

    def __init__(self, local_ctx):
        # list of matchers to ask for possible matches on completion
        self.matchers = [DefaultMatcher(local_ctx)]
        self.matchers.insert(0, RQLExecuteMatcher(local_ctx, local_ctx['session']))

    def complete(self, text, state):
        """readline's completer method

        cf http://docs.python.org/2/library/readline.html#readline.set_completer
        for more details.

        Implementation inspired by `rlcompleter.Completer`
        """
        if state == 0:
            # reset self.matches
            self.matches = []
            for matcher in self.matchers:
                matches = matcher.possible_matches(text)
                if matches:
                    self.matches = matches
                    break
            else:
                return None  # no matcher able to handle `text`
        try:
            return self.matches[state]
        except IndexError:
            return None
