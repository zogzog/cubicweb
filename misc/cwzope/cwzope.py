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
from AccessControl import getSecurityManager

from cubicweb.dbapi import connect, Connection, Cursor
from cubicweb.common.utils import ResultSet, ResultSetIterator, ResultSetRow, Entity

Connection.__allow_access_to_unprotected_subobjects__ = 1
Cursor.__allow_access_to_unprotected_subobjects__ = 1
ResultSet.__allow_access_to_unprotected_subobjects__ = 1
ResultSetIterator.__allow_access_to_unprotected_subobjects__ = 1
ResultSetRow.__allow_access_to_unprotected_subobjects__ = 1
Entity.__allow_access_to_unprotected_subobjects__ = 1

CNX_CACHE = {}

def get_connection(context, user=None, password=None,
                   host=None, database=None, group='cubicweb'):
    """get a connection on an cubicweb server"""
    request = context.REQUEST
    zope_user = getSecurityManager().getUser()
    if user is None:
        user = zope_user.getId()
    key = (user, host, database)
    try:
        return CNX_CACHE[key]
    except KeyError:
        if password is None:
            password = zope_user._getPassword()
        cnx = connect(user, password, host, database, group)
        CNX_CACHE[key] = cnx
        return cnx

