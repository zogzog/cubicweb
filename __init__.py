"""CubicWeb is a generic framework to quickly build applications which describes
relations between entitites.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: Library General Public License version 2 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import __builtin__
# '_' is available in builtins to mark internationalized string but should
# not be used to do the actual translation
if not hasattr(__builtin__, '_'):
    __builtin__._ = unicode

CW_SOFTWARE_ROOT = __path__[0]

import sys, os, logging
from StringIO import StringIO

from logilab.common.logging_ext import set_log_methods

if os.environ.get('APYCOT_ROOT'):
    logging.basicConfig(level=logging.CRITICAL)
else:
    logging.basicConfig()

from cubicweb.__pkginfo__ import version as __version__


set_log_methods(sys.modules[__name__], logging.getLogger('cubicweb'))

# make all exceptions accessible from the package
from cubicweb._exceptions import *

# convert eid to the right type, raise ValueError if it's not a valid eid
typed_eid = int


#def log_thread(f, w, a):
#    print f.f_code.co_filename, f.f_code.co_name
#import threading
#threading.settrace(log_thread)

class Binary(StringIO):
    """customize StringIO to make sure we don't use unicode"""
    def __init__(self, buf=''):
        assert isinstance(buf, (str, buffer)), \
               "Binary objects must use raw strings, not %s" % buf.__class__
        StringIO.__init__(self, buf)

    def write(self, data):
        assert isinstance(data, (str, buffer)), \
               "Binary objects must use raw strings, not %s" % data.__class__
        StringIO.write(self, data)

# use this dictionary for renaming of entity types while keeping bw compath
ETYPE_NAME_MAP = {# 3.2 migration
                  'ECache': 'CWCache',
                  'EUser': 'CWUser',
                  'EGroup': 'CWGroup',
                  'EProperty': 'CWProperty',
                  'EFRDef': 'CWAttribute',
                  'ENFRDef': 'CWRelation',
                  'ERType': 'CWRType',
                  'EEType': 'CWEType',
                  'EConstraintType': 'CWConstraintType',
                  'EConstraint': 'CWConstraint',
                  'EPermission': 'CWPermission',
                  }



# XXX cubic web cube migration map
CW_MIGRATION_MAP = {'erudi': 'cubicweb',
                    'eaddressbook': 'addressbook',
                    'ebasket': 'basket',
                    'eblog': 'blog',
                    'ebook': 'book',
                    'eclassschemes': 'keyword',
                    'eclassfolders': 'folder',
                    'eclasstags': 'tag',
                    'ecomment': 'comment',
                    'ecompany': 'company',
                    'econference':  'conference',
                    'eemail': 'email',
                    'eevent': 'event',
                    'eexpense': 'expense',
                    'efile': 'file',
                    'einvoice': 'invoice',
                    'elink': 'link',
                    'emailinglist': 'mailinglist',
                    'eperson': 'person',
                    'eshopcart': 'shopcart',
                    'eskillmat': 'skillmat',
                    'etask': 'task',
                    'eworkcase': 'workcase',
                    'eworkorder': 'workorder',
                    'ezone': 'zone',
                    'i18ncontent': 'i18ncontent',
                    'svnfile': 'vcsfile',
                    }

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

def onevent(event):
    """decorator to ease event / callback binding

    >>> from cubicweb import onevent
    >>> @onevent('before-registry-reload')
    ... def mycallback():
    ...     print 'hello'
    ...
    >>>
    """
    def _decorator(func):
        CW_EVENT_MANAGER.bind(event, func)
        return func
    return _decorator
