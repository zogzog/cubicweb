"""CubicWeb web client core. You'll need a apache-modpython or twisted
publisher to get a full CubicWeb web application


:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

import sys
if sys.version_info < (2,6):
    import simplejson as json
else:
    import json

dumps = json.dumps

from urllib import quote as urlquote

from logilab.common.deprecation import deprecated

from cubicweb.web._exceptions import *
from cubicweb.utils import CubicWebJsonEncoder

INTERNAL_FIELD_VALUE = '__cubicweb_internal_field__'


class stdmsgs(object):
    """standard ui message (in a class for bw compat)"""
    BUTTON_OK     = (_('button_ok'), 'OK_ICON')
    BUTTON_APPLY  = (_('button_apply'), 'APPLY_ICON')
    BUTTON_CANCEL = (_('button_cancel'), 'CANCEL_ICON')
    BUTTON_DELETE = (_('button_delete'), 'TRASH_ICON')
    YES = (_('yes'), None)
    NO  = (_('no'), None)


def eid_param(name, eid):
    assert eid is not None
    if eid is None:
        eid = ''
    return '%s:%s' % (name, eid)


from logging import getLogger
LOGGER = getLogger('cubicweb.web')

# XXX deprecated
FACETTES = set()


def json_dumps(value):
    return dumps(value, cls=CubicWebJsonEncoder)

def jsonize(function):
    def newfunc(*args, **kwargs):
        value = function(*args, **kwargs)
        try:
            return json_dumps(value)
        except TypeError:
            return json_dumps(repr(value))
    return newfunc

@deprecated('[3.4] use req.build_ajax_replace_url() instead')
def ajax_replace_url(nodeid, rql, vid=None, swap=False, **extraparams):
    """builds a replacePageChunk-like url
    >>> ajax_replace_url('foo', 'Person P')
    "javascript: replacePageChunk('foo', 'Person%20P');"
    >>> ajax_replace_url('foo', 'Person P', 'oneline')
    "javascript: replacePageChunk('foo', 'Person%20P', 'oneline');"
    >>> ajax_replace_url('foo', 'Person P', 'oneline', name='bar', age=12)
    "javascript: replacePageChunk('foo', 'Person%20P', 'oneline', {'age':12, 'name':'bar'});"
    >>> ajax_replace_url('foo', 'Person P', name='bar', age=12)
    "javascript: replacePageChunk('foo', 'Person%20P', 'null', {'age':12, 'name':'bar'});"
    """
    params = [repr(nodeid), repr(urlquote(rql))]
    if extraparams and not vid:
        params.append("'null'")
    elif vid:
        params.append(repr(vid))
    if extraparams:
        params.append(json_dumps(extraparams))
    if swap:
        params.append('true')
    return "javascript: replacePageChunk(%s);" % ', '.join(params)
