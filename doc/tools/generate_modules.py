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
"""generate list of modules for sphinx doc

"""

import sys

EXCLUDE_DIRS = ('test', 'tests', 'examples', 'data', 'doc', 'dist',
                '.hg', 'migration')
if __name__ == '__main__':

    from logilab.common.sphinxutils import ModuleGenerator
    cw_gen = ModuleGenerator('cubicweb', '../..')
    cw_gen.generate("../book/en/annexes/api_cubicweb.rst",
                    EXCLUDE_DIRS + ('cwdesklets', 'misc', 'skel', 'skeleton'))
    for modname in ('logilab', 'rql', 'yams'):
        cw_gen = ModuleGenerator(modname, '../../../' + modname)
        cw_gen.generate("../book/en/annexes/api_%s.rst" % modname,
                        EXCLUDE_DIRS + ('tools',))
