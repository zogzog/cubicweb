# pylint: disable-msg=W0401,W0614
"""exceptions used in the core of the CubicWeb web application

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb._exceptions import *

class PublishException(CubicWebException):
    """base class for publishing related exception"""

class RequestError(PublishException):
    """raised when a request can't be served because of a bad input"""

class NothingToEdit(RequestError):
    """raised when an edit request doesn't specify any eid to edit"""

class ProcessFormError(RequestError):
    """raised when posted data can't be processed by the corresponding field
    """

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

class InvalidSession(CubicWebException):
    """raised when a session id is found but associated session is not found or
    invalid
    """

class RemoteCallFailed(RequestError):
    """raised when a json remote call fails
    """
    def __init__(self, reason=''):
        super(RequestError, self).__init__()
        self.reason = reason

    def dumps(self):
        import simplejson
        return simplejson.dumps({'reason': self.reason})

class LogOut(PublishException):
    """raised to ask for deauthentication of a logged in user"""
    def __init__(self, url):
        super(LogOut, self).__init__()
        self.url = url
