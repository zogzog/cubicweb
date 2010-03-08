"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.db import FunctionDescr
from logilab.db.sqlite import register_sqlite_pyfunc
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
