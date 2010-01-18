"""some utilities for cubicweb tools

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

# XXX move most of this in logilab.common (shellutils ?)

import os, sys
from os import listdir, makedirs, environ, chmod, walk, remove
from os.path import exists, join, abspath, normpath

try:
    from os import symlink
except ImportError:
    def symlink(*args):
        raise NotImplementedError

from logilab.common.clcommands import Command as BaseCommand, \
     main_run as base_main_run
from logilab.common.compat import any
from logilab.common.shellutils import ASK

from cubicweb import warning
from cubicweb import ConfigurationError, ExecutionError

def underline_title(title, car='-'):
    return title+'\n'+(car*len(title))

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
        print '-> created directory %s.' % directory
    except OSError, ex:
        import errno
        if ex.errno != errno.EEXIST:
            raise
        print '-> directory %s already exists, no need to create it.' % directory

def create_symlink(source, target):
    """create a symbolic link"""
    if exists(target):
        remove(target)
    symlink(source, target)
    print '[symlink] %s <-- %s' % (target, source)

def create_copy(source, target):
    import shutil
    print '[copy] %s <-- %s' % (target, source)
    shutil.copy2(source, target)

def rm(whatever):
    import shutil
    shutil.rmtree(whatever)
    print '-> removed %s' % whatever

def show_diffs(appl_file, ref_file, askconfirm=True):
    """interactivly replace the old file with the new file according to
    user decision
    """
    import shutil
    p_output = os.popen('diff -u %s %s' % (appl_file, ref_file), 'r')
    diffs = p_output.read()
    if diffs:
        if askconfirm:
            print
            print diffs
            action = ASK.ask('Replace ?', ('N','y','q'), 'N')
        else:
            action = 'y'
        if action == 'y':
            try:
                shutil.copyfile(ref_file, appl_file)
            except IOError:
                os.system('chmod a+w %s' % appl_file)
                shutil.copyfile(ref_file, appl_file)
            print 'replaced'
        elif action == 'q':
            sys.exit(0)
        else:
            copy_file = appl_file + '.default'
            copy = file(copy_file, 'w')
            copy.write(open(ref_file).read())
            copy.close()
            print 'keep current version, the new file has been written to', copy_file
    else:
        print 'no diff between %s and %s' % (appl_file, ref_file)


def copy_skeleton(skeldir, targetdir, context,
                  exclude=('*.py[co]', '*.orig', '*~', '*_flymake.py'),
                  askconfirm=False):
    import shutil
    from fnmatch import fnmatch
    skeldir = normpath(skeldir)
    targetdir = normpath(targetdir)
    for dirpath, dirnames, filenames in walk(skeldir):
        tdirpath = dirpath.replace(skeldir, targetdir)
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
                    print '[generate] %s <-- %s' % (tfpath, fpath)
            elif exists(tfpath):
                show_diffs(tfpath, fpath, askconfirm)
            else:
                shutil.copyfile(fpath, tfpath)

def fill_templated_file(fpath, tfpath, context):
    fobj = file(tfpath, 'w')
    templated = file(fpath).read()
    fobj.write(templated % context)
    fobj.close()

def restrict_perms_to_user(filepath, log=None):
    """set -rw------- permission on the given file"""
    if log:
        log('set %s permissions to 0600', filepath)
    else:
        print '-> set %s permissions to 0600' % filepath
    chmod(filepath, 0600)

def read_config(config_file):
    """read the instance configuration from a file and return it as a
    dictionnary

    :type config_file: str
    :param config_file: path to the configuration file

    :rtype: dict
    :return: a dictionary with specified values associated to option names
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
                    assert not config.has_key(section), \
                           'Section %s is defined more than once' % section
                    config[section] = current = {}
                    continue
                print >> sys.stderr, 'ignoring malformed line\n%r' % line
                continue
            option = option.strip().replace(' ', '_')
            value = value.strip()
            current[option] = value or None
    except IOError, ex:
        warning('missing or non readable configuration file %s (%s)',
                config_file, ex)
    return config

def env_path(env_var, default, name):
    """get a path specified in a variable or using the default value and return
    it.

    :type env_var: str
    :param env_var: name of an environment variable

    :type default: str
    :param default: default value if the environment variable is not defined

    :type name: str
    :param name: the informal name of the path, used for error message

    :rtype: str
    :return: the value of the environment variable or the default value

    :raise `ConfigurationError`: if the returned path does not exist
    """
    path = environ.get(env_var, default)
    if not exists(path):
        raise ConfigurationError('%s path %s doesn\'t exist' % (name, path))
    return abspath(path)



_HDLRS = {}

class metacmdhandler(type):
    def __new__(mcs, name, bases, classdict):
        cls = super(metacmdhandler, mcs).__new__(mcs, name, bases, classdict)
        if getattr(cls, 'cfgname', None) and getattr(cls, 'cmdname', None):
            _HDLRS.setdefault(cls.cmdname, []).append(cls)
        return cls


class CommandHandler(object):
    """configuration specific helper for cubicweb-ctl commands"""
    __metaclass__ = metacmdhandler
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
        print "command failed:", reason
        sys.exit(1)


def main_run(args, doc):
    """command line tool"""
    try:
        base_main_run(args, doc)
    except ConfigurationError, err:
        print 'ERROR: ', err
        sys.exit(1)
    except ExecutionError, err:
        print err
        sys.exit(2)

CONNECT_OPTIONS = (
    ("user",
     {'short': 'u', 'type' : 'string', 'metavar': '<user>',
      'help': 'connect as <user> instead of being prompted to give it.',
      }
     ),
    ("password",
     {'short': 'p', 'type' : 'password', 'metavar': '<password>',
      'help': 'automatically give <password> for authentication instead of \
being prompted to give it.',
      }),
    ("host",
     {'short': 'H', 'type' : 'string', 'metavar': '<hostname>',
      'default': None,
      'help': 'specify the name server\'s host name. Will be detected by \
broadcast if not provided.',
      }),
    )

def config_connect(appid, optconfig):
    from cubicweb.dbapi import connect
    from getpass import getpass
    user = optconfig.user
    if not user:
        user = raw_input('login: ')
    password = optconfig.password
    if not password:
        password = getpass('password: ')
    return connect(login=user, password=password, host=optconfig.host, database=appid)

