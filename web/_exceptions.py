# pylint: disable=W0401,W0614
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
"""exceptions used in the core of the CubicWeb web application"""

__docformat__ = "restructuredtext en"

import httplib

from cubicweb._exceptions import *
from cubicweb.utils import json_dumps


class DirectResponse(Exception):
    """Used to supply a twitted HTTP Response directly"""
    def __init__(self, response):
        self.response = response

class InvalidSession(CubicWebException):
    """raised when a session id is found but associated session is not found or
    invalid"""

# Publish related exception

class PublishException(CubicWebException):
    """base class for publishing related exception"""

    def __init__(self, *args, **kwargs):
        self.status = kwargs.pop('status', httplib.OK)
        super(PublishException, self).__init__(*args, **kwargs)

class LogOut(PublishException):
    """raised to ask for deauthentication of a logged in user"""
    def __init__(self, url=None):
        super(LogOut, self).__init__()
        self.url = url

class Redirect(PublishException):
    """raised to redirect the http request"""
    def __init__(self, location, status=httplib.SEE_OTHER):
        super(Redirect, self).__init__(status=status)
        self.location = location

class StatusResponse(PublishException):

    def __init__(self, status, content=''):
        super(StatusResponse, self).__init__(status=status)
        self.content = content

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.status, self.content)

# Publish related error

class RequestError(PublishException):
    """raised when a request can't be served because of a bad input"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('status', httplib.BAD_REQUEST)
        super(RequestError, self).__init__(*args, **kwargs)


class NothingToEdit(RequestError):
    """raised when an edit request doesn't specify any eid to edit"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('status', httplib.BAD_REQUEST)
        super(NothingToEdit, self).__init__(*args, **kwargs)

class ProcessFormError(RequestError):
    """raised when posted data can't be processed by the corresponding field
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('status', httplib.BAD_REQUEST)
        super(ProcessFormError, self).__init__(*args, **kwargs)

class NotFound(RequestError):
    """raised when something was not found. In most case,
       a 404 error should be returned"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('status', httplib.NOT_FOUND)
        super(NotFound, self).__init__(*args, **kwargs)

class RemoteCallFailed(RequestError):
    """raised when a json remote call fails
    """
    def __init__(self, reason='', status=httplib.INTERNAL_SERVER_ERROR):
        super(RemoteCallFailed, self).__init__(reason, status=status)
        self.reason = reason

    def dumps(self):
        return json_dumps({'reason': self.reason})
