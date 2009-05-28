"""generate list of modules for sphinx doc

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import sys

EXCLUDE_DIRS = ('test', 'tests', 'examples', 'data', 'doc', '.hg', 'migration')
if __name__ == '__main__':

    from logilab.common.sphinxutils import generate_modules_file

    gen = generate_modules_file(sys.argv[1:])
    gen.set_docdir("cubicweb/doc/book/en")
    gen.make(['cubicweb', '/indexer', '/logilab', '/rql', '/yams'], EXCLUDE_DIRS)
