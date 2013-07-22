# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

__docformat__ = "restructuredtext en"

from yams import ValidationError as ValidationError

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
            return u' '.join(unicode(arg) for arg in self.args)

class ConfigurationError(CubicWebException):
    """a misconfiguration error"""

class InternalError(CubicWebException):
    """base class for exceptions which should not occurs"""

class SecurityError(CubicWebException):
    """base class for cubicweb server security exception"""

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

class ETypeNotSupportedBySources(RepositoryError, InternalError):
    """no source support an entity type"""
    msg = 'No source supports %r entity\'s type'

class MultiSourcesError(RepositoryError, InternalError):
    """usually due to bad multisources configuration or rql query"""

class UniqueTogetherError(RepositoryError):
    """raised when a unique_together constraint caused an IntegrityError"""


# security exceptions #########################################################

class Unauthorized(SecurityError):
    """raised when a user tries to perform an action without sufficient
    credentials
    """
    msg = 'You are not allowed to perform this operation'
    msg1 = 'You are not allowed to perform %s operation on %s'
    var = None

    def __str__(self):
        try:
            if self.args and len(self.args) == 2:
                return self.msg1 % self.args
            if self.args:
                return ' '.join(self.args)
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

# pre 3.15 bw compat
from logilab.common.registry import RegistryException, ObjectNotFound, NoSelectableObject

class UnknownProperty(RegistryException):
    """property found in database but unknown in registry"""

# query exception #############################################################

class QueryError(CubicWebRuntimeError):
    """a query try to do something it shouldn't"""

class NotAnEntity(CubicWebRuntimeError):
    """raised when get_entity is called for a column which doesn't contain
    a non final entity
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
    :param txuuid: Unique identifier of the partialy undone transaction

    :type errors: list
    :param errors: List of errors occured during undoing
    """
    msg = u"The following error(s) occured while undoing transaction #%d : %s"

    def __init__(self, txuuid, errors):
        super(UndoTransactionException, self).__init__(txuuid, errors)
        self.txuuid = txuuid
        self.errors = errors

# tools exceptions ############################################################

class ExecutionError(Exception):
    """server execution control error (already started, not running...)"""

# pylint: disable=W0611
from logilab.common.clcommands import BadCommandUsage

