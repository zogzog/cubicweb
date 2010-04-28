# pylint: disable-msg=W0622,C0103
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
"""cubicweb global packaging information for the cubicweb knowledge management
software
"""

modname = distname = "cubicweb"

numversion = (3, 8, 1)
version = '.'.join(str(num) for num in numversion)

description = "a repository of entities / relations for knowledge management"
author = "Logilab"
author_email = "contact@logilab.fr"
web = 'http://www.cubicweb.org'
ftp = 'ftp://ftp.logilab.org/pub/cubicweb'
license = 'LGPL'

classifiers = [
           'Environment :: Web Environment',
           'Framework :: CubicWeb',
           'Programming Language :: Python',
           'Programming Language :: JavaScript',
]

__depends__ = {
    'logilab-common': '>= 0.50.1',
    'logilab-mtconverter': '>= 0.6.0',
    'rql': '>= 0.26.0',
    'yams': '>= 0.28.1',
    'docutils': '>= 0.6',
    #gettext                    # for xgettext, msgcat, etc...
    # web dependancies
    'simplejson': '>= 2.0.9',
    'lxml': '',
    'Twisted': '',
    # XXX graphviz
    # server dependencies
    'logilab-database': '',
    'pysqlite': '>= 2.5.5', # XXX install pysqlite2
    }

__recommends__ = {
    'Pyro': '>= 3.9.1',
    'PIL': '',                  # for captcha
    'pycrypto': '',             # for crypto extensions
    'fyzz': '>= 0.1.0',         # for sparql
    'vobject': '>= 0.6.0',      # for ical view
    #'Products.FCKeditor':'',
    #'SimpleTAL':'>= 4.1.6',
    }

import sys
from os import listdir, environ
from os.path import join, isdir
import glob

scripts = [s for s in glob.glob(join('bin', 'cubicweb-*'))
           if not s.endswith('.bat')]
include_dirs = [join('test', 'data'),
                join('server', 'test', 'data'),
                join('hooks', 'test', 'data'),
                join('web', 'test', 'data'),
                join('devtools', 'test', 'data'),
                'skeleton']


_server_migration_dir = join('misc', 'migration')
_data_dir = join('web', 'data')
_wdoc_dir = join('web', 'wdoc')
_wdocimages_dir = join(_wdoc_dir, 'images')
_views_dir = join('web', 'views')
_i18n_dir = 'i18n'

_pyversion = '.'.join(str(num) for num in sys.version_info[0:2])
if '--home' in sys.argv:
    # --home install
    pydir = 'python' + _pyversion
else:
    pydir = join('python' + _pyversion, 'site-packages')

try:
    data_files = [
        # server data
        [join('share', 'cubicweb', 'schemas'),
         [join('schemas', filename) for filename in listdir('schemas')]],
        [join('share', 'cubicweb', 'migration'),
         [join(_server_migration_dir, filename)
          for filename in listdir(_server_migration_dir)]],
        # web data
        [join('share', 'cubicweb', 'cubes', 'shared', 'data'),
         [join(_data_dir, fname) for fname in listdir(_data_dir)
          if not isdir(join(_data_dir, fname))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'data', 'timeline'),
         [join(_data_dir, 'timeline', fname) for fname in listdir(join(_data_dir, 'timeline'))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'data', 'images'),
         [join(_data_dir, 'images', fname) for fname in listdir(join(_data_dir, 'images'))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'wdoc'),
         [join(_wdoc_dir, fname) for fname in listdir(_wdoc_dir)
          if not isdir(join(_wdoc_dir, fname))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'wdoc', 'images'),
         [join(_wdocimages_dir, fname) for fname in listdir(_wdocimages_dir)]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'i18n'),
         [join(_i18n_dir, fname) for fname in listdir(_i18n_dir)]],
        # XXX: drop .pt files
        [join('lib', pydir, 'cubicweb', 'web', 'views'),
         [join(_views_dir, fname) for fname in listdir(_views_dir)
          if fname.endswith('.pt')]],
        # skeleton
        ]
except OSError:
    # we are in an installed directory, don't care about this
    pass
