"""generate list of modules for sphinx doc"""

import sys

EXCLUDE_DIRS = ('test', 'tests', 'examples', 'data', 'doc', '.hg', 'migration')
if __name__ == '__main__':

    from logilab.common.sphinxutils import generate_modules_file

    gen = generate_modules_file(sys.argv[1:])
    gen.set_docdir("cubicweb/doc/book/en")
    gen.make(['cubicweb', '/indexer', '/logilab', '/rql', '/yams'], EXCLUDE_DIRS)
