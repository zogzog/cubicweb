"""generate list of modules for sphinx doc

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import sys

EXCLUDE_DIRS = ('test', 'tests', 'examples', 'data', 'doc', 'dist',
                '.hg', 'migration')
if __name__ == '__main__':

    from logilab.common.sphinxutils import ModuleGenerator
    cw_gen = ModuleGenerator('cubicweb', '../..')
    cw_gen.generate("../book/en/annexes/api_cubicweb.rst",
                    EXCLUDE_DIRS + ('cwdesklets', 'misc', 'skel', 'skeleton'))
    for modname in ('indexer', 'logilab', 'rql', 'yams'):
        cw_gen = ModuleGenerator(modname, '../../../' + modname)
        cw_gen.generate("../book/en/annexes/api_%s.rst" % modname,
                        EXCLUDE_DIRS + ('tools',))
