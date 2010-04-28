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

from logilab.database import FunctionDescr
from logilab.database.sqlite import register_sqlite_pyfunc
from rql.utils import register_function

try:
    class DUMB_SORT(FunctionDescr):
        supported_backends = ('sqlite',)

    register_function(DUMB_SORT)
    def dumb_sort(something):
        return something
    register_sqlite_pyfunc(dumb_sort)
except:
    # already registered
    pass
