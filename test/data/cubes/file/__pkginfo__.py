# pylint: disable-msg=W0622
"""cubicweb-file packaging information

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

distname = "cubicweb-file"
modname = distname.split('-', 1)[1]

numversion = (1, 4, 3)
version = '.'.join(str(num) for num in numversion)

license = 'LGPL'
copyright = '''Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
http://www.logilab.fr/ -- mailto:contact@logilab.fr'''

author = "Logilab"
author_email = "contact@logilab.fr"
web = ''

short_desc = "Raw file support for the CubicWeb framework"
long_desc = """CubicWeb is a entities / relations bases knowledge management system
developped at Logilab.
.
This package provides schema and views to store files and images in cubicweb
applications.
.
"""

from os import listdir
from os.path import join

CUBES_DIR = join('share', 'cubicweb', 'cubes')
try:
    data_files = [
        [join(CUBES_DIR, 'file'),
         [fname for fname in listdir('.')
          if fname.endswith('.py') and fname != 'setup.py']],
        [join(CUBES_DIR, 'file', 'data'),
         [join('data', fname) for fname in listdir('data')]],
        [join(CUBES_DIR, 'file', 'wdoc'),
         [join('wdoc', fname) for fname in listdir('wdoc')]],
        [join(CUBES_DIR, 'file', 'views'),
         [join('views', fname) for fname in listdir('views') if fname.endswith('.py')]],
        [join(CUBES_DIR, 'file', 'i18n'),
         [join('i18n', fname) for fname in listdir('i18n')]],
        [join(CUBES_DIR, 'file', 'migration'),
         [join('migration', fname) for fname in listdir('migration')]],
        ]
except OSError:
    # we are in an installed directory
    pass


cube_eid = 20320
# used packages
__use__ = ()
