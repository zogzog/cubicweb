"""Exceptions shared by different cubicweb packages.


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from yams import ValidationError

# abstract exceptions #########################################################

class CubicWebException(Exception):
    """base class for cubicweb server exception"""
    msg = ""
    def __str__(self):
        if self.msg:
            if self.args:
                return self.msg % tuple(self.args)
            return self.msg
        return ' '.join(str(arg) for arg in self.args)


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
    a connection failed"""

class AuthenticationError(ConnectionError):
    """raised when a bad connection id is given or when an attempt to establish
    a connection failed"""

class BadConnectionId(ConnectionError):
    """raised when a bad connection id is given or when an attempt to establish
    a connection failed"""

BadSessionId = BadConnectionId # XXX bw compat for pyro connections

class UnknownEid(RepositoryError):
    """the eid is not defined in the system tables"""
    msg = 'No entity with eid %s in the repository'

class ETypeNotSupportedBySources(RepositoryError, InternalError):
    """no source support an entity type"""
    msg = 'No source supports %r entity\'s type'

class MultiSourcesError(RepositoryError, InternalError):
    """usually due to bad multisources configuration or rql query"""


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
        except Exception, ex:
            return str(ex)

# source exceptions ###########################################################

class EidNotInSource(SourceException):
    """trying to access an object with a particular eid from a particular
    source has failed
    """
    msg = 'No entity with eid %s in %s'


# registry exceptions #########################################################

class RegistryException(CubicWebException):
    """raised when an unregistered view is called"""

class RegistryNotFound(RegistryException):
    """raised when an unknown registry is requested

    this is usually a programming/typo error...
    """

class ObjectNotFound(RegistryException):
    """raised when an unregistered object is requested

    this may be a programming/typo or a misconfiguration error
    """

class NoSelectableObject(RegistryException):
    """some views with the given vid have been found but no
    one is applicable to the result set
    """

class UnknownProperty(RegistryException):
    """property found in database but unknown in registry"""

class RegistryOutOfDate(RegistryException):
    """raised when a source file modification is detected"""

# query exception #############################################################

class QueryError(CubicWebRuntimeError):
    """a query try to do something it shouldn't"""

class NotAnEntity(CubicWebRuntimeError):
    """raised when get_entity is called for a column which doesn't contain
    a non final entity
    """

# tools exceptions ############################################################

class ExecutionError(Exception):
    """server execution control error (already started, not running...)"""

# pylint: disable-msg=W0611
from logilab.common.clcommands import BadCommandUsage
