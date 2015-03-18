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
"""CubicWeb is a generic framework to quickly build applications which describes
relations between entitites.
"""
__docformat__ = "restructuredtext en"

# ignore the pygments UserWarnings
import warnings
import cPickle
import zlib
warnings.filterwarnings('ignore', category=UserWarning,
                        message='.*was already imported',
                        module='.*pygments')


import __builtin__
# '_' is available in builtins to mark internationalized string but should
# not be used to do the actual translation
if not hasattr(__builtin__, '_'):
    __builtin__._ = unicode

CW_SOFTWARE_ROOT = __path__[0]

import sys, os, logging
from StringIO import StringIO

from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods
from yams.constraints import BASE_CONVERTERS, BASE_CHECKERS

# pre python 2.7.2 safety
logging.basicConfig()

from cubicweb.__pkginfo__ import version as __version__


set_log_methods(sys.modules[__name__], logging.getLogger('cubicweb'))

# make all exceptions accessible from the package
from cubicweb._exceptions import *
from logilab.common.registry import ObjectNotFound, NoSelectableObject, RegistryNotFound

# convert eid to the right type, raise ValueError if it's not a valid eid
@deprecated('[3.17] typed_eid() was removed. replace it with int() when needed.')
def typed_eid(eid):
    return int(eid)

#def log_thread(f, w, a):
#    print f.f_code.co_filename, f.f_code.co_name
#import threading
#threading.settrace(log_thread)

class Binary(StringIO):
    """customize StringIO to make sure we don't use unicode"""
    def __init__(self, buf=''):
        assert isinstance(buf, (str, buffer, bytearray)), \
               "Binary objects must use raw strings, not %s" % buf.__class__
        StringIO.__init__(self, buf)

    def write(self, data):
        assert isinstance(data, (str, buffer, bytearray)), \
               "Binary objects must use raw strings, not %s" % data.__class__
        StringIO.write(self, data)

    def to_file(self, fobj):
        """write a binary to disk

        the writing is performed in a safe way for files stored on
        Windows SMB shares
        """
        pos = self.tell()
        self.seek(0)
        if sys.platform == 'win32':
            while True:
                # the 16kB chunksize comes from the shutil module
                # in stdlib
                chunk = self.read(16*1024)
                if not chunk:
                    break
                fobj.write(chunk)
        else:
            fobj.write(self.read())
        self.seek(pos)

    @staticmethod
    def from_file(filename):
        """read a file and returns its contents in a Binary

        the reading is performed in a safe way for files stored on
        Windows SMB shares
        """
        binary = Binary()
        with open(filename, 'rb') as fobj:
            if sys.platform == 'win32':
                while True:
                    # the 16kB chunksize comes from the shutil module
                    # in stdlib
                    chunk = fobj.read(16*1024)
                    if not chunk:
                        break
                    binary.write(chunk)
            else:
                binary.write(fobj.read())
        binary.seek(0)
        return binary

    def __eq__(self, other):
        if not isinstance(other, Binary):
            return False
        return self.getvalue() == other.getvalue()


    # Binary helpers to store/fetch python objects

    @classmethod
    def zpickle(cls, obj):
        """ return a Binary containing a gzipped pickle of obj """
        retval = cls()
        retval.write(zlib.compress(cPickle.dumps(obj, protocol=2)))
        return retval

    def unzpickle(self):
        """ decompress and loads the stream before returning it """
        return cPickle.loads(zlib.decompress(self.getvalue()))


def check_password(eschema, value):
    return isinstance(value, (str, Binary))
BASE_CHECKERS['Password'] = check_password

def str_or_binary(value):
    if isinstance(value, Binary):
        return value
    return str(value)
BASE_CONVERTERS['Password'] = str_or_binary


# use this dictionary to rename entity types while keeping bw compat
ETYPE_NAME_MAP = {}

# XXX cubic web cube migration map. See if it's worth keeping this mecanism
#     to help in cube renaming
CW_MIGRATION_MAP = {}

def neg_role(role):
    if role == 'subject':
        return 'object'
    return 'subject'

def role(obj):
    try:
        return obj.role
    except AttributeError:
        return neg_role(obj.target)

def target(obj):
    try:
        return obj.target
    except AttributeError:
        return neg_role(obj.role)


class CubicWebEventManager(object):
    """simple event / callback manager.

    Typical usage to register a callback::

      >>> from cubicweb import CW_EVENT_MANAGER
      >>> CW_EVENT_MANAGER.bind('after-registry-reload', mycallback)

    Typical usage to emit an event::

      >>> from cubicweb import CW_EVENT_MANAGER
      >>> CW_EVENT_MANAGER.emit('after-registry-reload')

    emit() accepts an additional context parameter that will be passed
    to the callback if specified (and only in that case)
    """
    def __init__(self):
        self.callbacks = {}

    def bind(self, event, callback, *args, **kwargs):
        self.callbacks.setdefault(event, []).append( (callback, args, kwargs) )

    def emit(self, event, context=None):
        for callback, args, kwargs in self.callbacks.get(event, ()):
            if context is None:
                callback(*args, **kwargs)
            else:
                callback(context, *args, **kwargs)

CW_EVENT_MANAGER = CubicWebEventManager()

def onevent(event, *args, **kwargs):
    """decorator to ease event / callback binding

    >>> from cubicweb import onevent
    >>> @onevent('before-registry-reload')
    ... def mycallback():
    ...     print 'hello'
    ...
    >>>
    """
    def _decorator(func):
        CW_EVENT_MANAGER.bind(event, func, *args, **kwargs)
        return func
    return _decorator


from yams.schema import role_name as rname

def validation_error(entity, errors, substitutions=None, i18nvalues=None):
    """easy way to retrieve a :class:`cubicweb.ValidationError` for an entity or eid.

    You may also have 2-tuple as error keys, :func:`yams.role_name` will be
    called automatically for them.

    Messages in errors **should not be translated yet**, though marked for
    internationalization. You may give an additional substition dictionary that
    will be used for interpolation after the translation.
    """
    if substitutions is None:
        # set empty dict else translation won't be done for backward
        # compatibility reason (see ValidationError.translate method)
        substitutions = {}
    for key in list(errors):
        if isinstance(key, tuple):
            errors[rname(*key)] = errors.pop(key)
    return ValidationError(getattr(entity, 'eid', entity), errors,
                           substitutions, i18nvalues)


# exceptions ##################################################################

class ProgrammingError(Exception): #DatabaseError):
    """Exception raised for errors that are related to the database's operation
    and not necessarily under the control of the programmer, e.g. an unexpected
    disconnect occurs, the data source name is not found, a transaction could
    not be processed, a memory allocation error occurred during processing,
    etc.
    """

