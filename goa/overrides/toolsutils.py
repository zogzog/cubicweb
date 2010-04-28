# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
