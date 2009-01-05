# pylint: disable-msg=W0401,W0614
"""exceptions used in the core of the CubicWeb web application

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb._exceptions import *

class PublishException(CubicWebException):
    """base class for publishing related exception"""
    
class RequestError(PublishException):
    """raised when a request can't be served because of a bad input"""

class NothingToEdit(RequestError):
    """raised when an edit request doesn't specify any eid to edit"""
    
class NotFound(RequestError):
    """raised when a 404 error should be returned"""

class Redirect(PublishException):
    """raised to redirect the http request"""
    def __init__(self, location):
        self.location = location

class DirectResponse(Exception):
    def __init__(self, response):
        self.response = response

class StatusResponse(Exception):
    def __init__(self, status, content=''):
        self.status = int(status)
        self.content = content
    
class ExplicitLogin(AuthenticationError):
    """raised when a bad connection id is given or when an attempt to establish
    a connection failed"""

class InvalidSession(CubicWebException):
    """raised when a session id is found but associated session is not found or
    invalid
    """

class RemoteCallFailed(RequestError):
    """raised when a json remote call fails
    """
    def __init__(self, reason=''):
        #super(RequestError, self).__init__() # XXX require py >= 2.5
        RequestError.__init__(self)
        self.reason = reason

    def dumps(self):
        import simplejson
        return simplejson.dumps({'reason': self.reason})
        
