# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""This package contains all WSGI specific code for cubicweb

NOTE: this package borrows a lot of code to Django
      (http://www.djangoproject.com) and to the wsgiref module
      of the python2.5's stdlib.

WSGI corresponding PEP: http://www.python.org/dev/peps/pep-0333/

"""


from email import message, message_from_string
from pprint import pformat as _pformat

from six.moves.http_cookies import SimpleCookie

def pformat(obj):
    """pretty prints `obj` if possible"""
    try:
        return _pformat(obj)
    except Exception:
        return u'<could not parse>'

def normalize_header(header):
    """returns a normalized header name

    >>> normalize_header('User_Agent')
    'User-agent'
    """
    return header.replace('_', '-').capitalize()

def safe_copyfileobj(fsrc, fdst, length=16*1024, size=0):
    """
    THIS COMES FROM DJANGO
    A version of shutil.copyfileobj that will not read more than 'size' bytes.
    This makes it safe from clients sending more than CONTENT_LENGTH bytes of
    data in the body.
    """
    if not size:
        return
    while size > 0:
        buf = fsrc.read(min(length, size))
        if not buf:
            break
        fdst.write(buf)
        size -= len(buf)
