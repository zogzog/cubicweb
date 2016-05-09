# pylint: disable=W0622,C0103
# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

numversion = (3, 20, 15)
version = '.'.join(str(num) for num in numversion)

description = "a repository of entities / relations for knowledge management"
author = "Logilab"
author_email = "contact@logilab.fr"
web = 'http://www.cubicweb.org'
license = 'LGPL'

classifiers = [
           'Environment :: Web Environment',
           'Framework :: CubicWeb',
           'Programming Language :: Python',
           'Programming Language :: JavaScript',
]

__depends__ = {
    'logilab-common': '>= 0.63.1',
    'logilab-mtconverter': '>= 0.8.0',
    'rql': '>= 0.31.2, < 0.34',
    'yams': '>= 0.40.0, < 0.42',
    #gettext                    # for xgettext, msgcat, etc...
    # web dependencies
    'lxml': '',
    # XXX graphviz
    # server dependencies
    'logilab-database': '>= 1.13.0, < 1.15',
    'passlib': '',
    'Markdown': ''
    }

__recommends__ = {
    'docutils': '>= 0.6',
    'Pyro': '>= 3.9.1, < 4.0.0',
    'Pillow': '',               # for captcha
    'pycrypto': '',             # for crypto extensions
    'fyzz': '>= 0.1.0',         # for sparql
    'vobject': '>= 0.6.0',      # for ical view
    'rdflib': None,             #
    'pyzmq': None,
    'Twisted': '',
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
                join('devtools', 'data'),
                join('devtools', 'test', 'data'),
                'schemas', 'skeleton']


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

# data files that shall be copied into the main package directory
package_data = {
    'cubicweb.web.views':['*.pt'],
    }

try:
    # data files that shall be copied outside the main package directory
    data_files = [
        # server data
        [join('share', 'cubicweb', 'schemas'),
         glob.glob(join('schemas', '*.sql'))],
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
        [join('share', 'cubicweb', 'cubes', 'shared', 'data', 'jquery-treeview'),
         [join(_data_dir, 'jquery-treeview', fname) for fname in listdir(join(_data_dir, 'jquery-treeview'))
          if not isdir(join(_data_dir, 'jquery-treeview', fname))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'data', 'jquery-treeview', 'images'),
         [join(_data_dir, 'jquery-treeview', 'images', fname)
          for fname in listdir(join(_data_dir, 'jquery-treeview', 'images'))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'wdoc'),
         [join(_wdoc_dir, fname) for fname in listdir(_wdoc_dir)
          if not isdir(join(_wdoc_dir, fname))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'wdoc', 'images'),
         [join(_wdocimages_dir, fname) for fname in listdir(_wdocimages_dir)]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'i18n'),
         glob.glob(join(_i18n_dir, '*.po'))],
        # skeleton
        ]
except OSError:
    # we are in an installed directory, don't care about this
    pass
