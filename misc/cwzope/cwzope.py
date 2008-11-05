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

