# pylint: disable-msg=W0622,C0103
"""cubicweb global packaging information for the cubicweb knowledge management
software
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

distname = "cubicweb"
modname = "cubicweb"

numversion = (3, 2, 3)
version = '.'.join(str(num) for num in numversion)

license = 'LGPL v2'
copyright = '''Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
http://www.logilab.fr/ -- mailto:contact@logilab.fr'''

author = "Logilab"
author_email = "contact@logilab.fr"

short_desc = "a repository of entities / relations for knowledge management"
long_desc = """CubicWeb is a entities / relations based knowledge management system
developped at Logilab.

This package contains:
* a repository server
* a RQL command line client to the repository
* an adaptative modpython interface to the server
* a bunch of other management tools
"""

web = 'http://www.cubicweb.org'
ftp = 'ftp://ftp.logilab.org/pub/cubicweb'
pyversions = ['2.4', '2.5']


import sys
from os import listdir, environ
from os.path import join, isdir
import glob

scripts = [s for s in glob.glob(join('bin', 'cubicweb-*'))
           if not s.endswith('.bat')]
include_dirs = [join('test', 'data'),
                join('common', 'test', 'data'),
                join('server', 'test', 'data'),
                join('web', 'test', 'data'),
                join('devtools', 'test', 'data'),
                'skeleton']


entities_dir = 'entities'
schema_dir = 'schemas'
sobjects_dir = 'sobjects'
server_migration_dir = join('misc', 'migration')
data_dir = join('web', 'data')
wdoc_dir = join('web', 'wdoc')
wdocimages_dir = join(wdoc_dir, 'images')
views_dir = join('web', 'views')
i18n_dir = 'i18n'

if environ.get('APYCOT_ROOT'):
    # --home install
    pydir = 'python'
else:
    python_version = '.'.join(str(num) for num in sys.version_info[0:2])
    pydir = join('python' + python_version, 'site-packages')

try:
    data_files = [
        # common data
        #[join('share', 'cubicweb', 'entities'),
        # [join(entities_dir, filename) for filename in listdir(entities_dir)]],
        # server data
        [join('share', 'cubicweb', 'schemas'),
         [join(schema_dir, filename) for filename in listdir(schema_dir)]],
        #[join('share', 'cubicweb', 'sobjects'),
        # [join(sobjects_dir, filename) for filename in listdir(sobjects_dir)]],
        [join('share', 'cubicweb', 'migration'),
         [join(server_migration_dir, filename)
          for filename in listdir(server_migration_dir)]],
        # web data
        [join('share', 'cubicweb', 'cubes', 'shared', 'data'),
         [join(data_dir, fname) for fname in listdir(data_dir) if not isdir(join(data_dir, fname))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'data', 'timeline'),
         [join(data_dir, 'timeline', fname) for fname in listdir(join(data_dir, 'timeline'))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'wdoc'),
         [join(wdoc_dir, fname) for fname in listdir(wdoc_dir) if not isdir(join(wdoc_dir, fname))]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'wdoc', 'images'),
         [join(wdocimages_dir, fname) for fname in listdir(wdocimages_dir)]],
        # XXX: .pt install should be handled properly in a near future version
        [join('lib', pydir, 'cubicweb', 'web', 'views'),
         [join(views_dir, fname) for fname in listdir(views_dir) if fname.endswith('.pt')]],
        [join('share', 'cubicweb', 'cubes', 'shared', 'i18n'),
         [join(i18n_dir, fname) for fname in listdir(i18n_dir)]],
        # skeleton
        ]
except OSError:
    # we are in an installed directory, don't care about this
    pass
