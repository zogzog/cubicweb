"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import sys
from cubicweb import warning

def lines(path, comments=None):
    result = []
    for line in open(path, 'U'):
        line = line.strip()
        if line and (comments is None or not line.startswith(comments)):
            result.append(line)
    return result

def read_config(config_file):
    """read the instance configuration from a file and return it as a
    dictionnary

    :type config_file: str
    :param config_file: path to the configuration file

    :rtype: dict
    :return: a dictionary with specified values associated to option names
    """
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
    return default

def create_dir(*args):
    raise RuntimeError()
