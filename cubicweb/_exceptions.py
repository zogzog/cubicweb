# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Exceptions shared by different cubicweb packages."""


from logilab.common.decorators import cachedproperty
from logilab.common.registry import RegistryException

from yams import ValidationError  # noqa: F401

# abstract exceptions #########################################################


class CubicWebException(Exception):
    """base class for cubicweb server exception"""
    msg = ""

    def __str__(self):
        if self.msg:
            if self.args:
                return self.msg % tuple(self.args)
            else:
                return self.msg
        else:
            return u' '.join(str(arg) for arg in self.args)


class ConfigurationError(CubicWebException):
    """a misconfiguration error"""


class InternalError(CubicWebException):
    """base class for exceptions which should not occur"""


class SecurityError(CubicWebException):
    """base class for cubicweb server security exceptions"""


class RepositoryError(CubicWebException):
    """base class for repository exceptions"""


class SourceException(CubicWebException):
    """base class for source exceptions"""


class CubicWebRuntimeError(CubicWebException):
    """base class for runtime exceptions"""

# repository exceptions #######################################################


class ConnectionError(RepositoryError):
    """raised when a bad connection id is given or when an attempt to establish
    a connection failed
    """


class AuthenticationError(ConnectionError):
    """raised when an attempt to establish a connection failed due to wrong
    connection information (login / password or other authentication token)
    """


class BadConnectionId(ConnectionError):
    """raised when a bad connection id is given"""


class UnknownEid(RepositoryError):
    """the eid is not defined in the system tables"""
    msg = 'No entity with eid %s in the repository'


class UniqueTogetherError(RepositoryError):
    """raised when a unique_together constraint caused an IntegrityError"""

    def __init__(self, session, **kwargs):
        self.session = session
        assert 'rtypes' in kwargs or 'cstrname' in kwargs
        self.kwargs = kwargs
        # fill cache while the session is open
        self.rtypes

    @cachedproperty
    def rtypes(self):
        if 'rtypes' in self.kwargs:
            return self.kwargs['rtypes']
        cstrname = str(self.kwargs['cstrname'])
        cstr = self.session.find('CWUniqueTogetherConstraint', name=cstrname).one()
        return sorted(rtype.name for rtype in cstr.relations)


class ViolatedConstraint(RepositoryError):
    def __init__(self, cnx, cstrname, query):
        self.cnx = cnx
        self.cstrname = cstrname
        message = (
            "constraint '%s' is being violated by the query '%s'. "
            "You can run the inverted constraint on the database to list the problematic rows."
        ) % (cstrname, query)
        super(ViolatedConstraint, self).__init__(message)


# security exceptions #########################################################

class Unauthorized(SecurityError):
    """raised when a user tries to perform an action without sufficient
    credentials
    """
    msg = u'You are not allowed to perform this operation'
    msg1 = u'You are not allowed to perform %s operation on %s'
    var = None

    def __str__(self):
        try:
            if self.args and len(self.args) == 2:
                return self.msg1 % self.args
            if self.args:
                return u' '.join(self.args)
            return self.msg
        except Exception as ex:
            return str(ex)


class Forbidden(SecurityError):
    """raised when a user tries to perform a forbidden action
    """

# source exceptions ###########################################################


class EidNotInSource(SourceException):
    """trying to access an object with a particular eid from a particular
    source has failed
    """
    msg = 'No entity with eid %s in %s'


# registry exceptions #########################################################

class UnknownProperty(RegistryException):
    """property found in database but unknown in registry"""

# query exception #############################################################


class QueryError(CubicWebRuntimeError):
    """a query try to do something it shouldn't"""


class NotAnEntity(CubicWebRuntimeError):
    """raised when get_entity is called for a column which doesn't contain
    a non final entity
    """


class MultipleResultsError(CubicWebRuntimeError):
    """raised when ResultSet.one() is called on a resultset with multiple rows
    of multiple columns.
    """


class NoResultError(CubicWebRuntimeError):
    """raised when no result is found but at least one is expected.
    """


class UndoTransactionException(QueryError):
    """Raised when undoing a transaction could not be performed completely.

    Note that :
      1) the partial undo operation might be acceptable
         depending upon the final application

      2) the undo operation can also fail with a `ValidationError` in
         cases where the undoing breaks integrity constraints checked
         immediately.

      3) It might be that neither of those exception is raised but a
         subsequent `commit` might raise a `ValidationError` in cases
         where the undoing breaks integrity constraints checked at
         commit time.

    :type txuuix: int
    :param txuuid: Unique identifier of the partially undone transaction

    :type errors: list
    :param errors: List of errors occurred during undoing
    """
    msg = u"The following error(s) occurred while undoing transaction #%d : %s"

    def __init__(self, txuuid, errors):
        super(UndoTransactionException, self).__init__(txuuid, errors)
        self.txuuid = txuuid
        self.errors = errors

# tools exceptions ############################################################


class ExecutionError(Exception):
    """server execution control error (already started, not running...)"""


# pylint: disable=W0611
from logilab.common.clcommands import BadCommandUsage  # noqa: E402, F401
