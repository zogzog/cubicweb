"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.adbh import FunctionDescr
from rql.utils import register_function

try:
    class DUMB_SORT(FunctionDescr):
        supported_backends = ('sqlite',)

    register_function(DUMB_SORT)


    def init_sqlite_connexion(cnx):
        def dumb_sort(something):
            return something
        cnx.create_function("DUMB_SORT", 1, dumb_sort)

    from cubicweb.server import sqlutils
    sqlutils.SQL_CONNECT_HOOKS['sqlite'].append(init_sqlite_connexion)
except:
    # already registered
    pass
