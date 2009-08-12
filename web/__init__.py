"""CubicWeb web client core. You'll need a apache-modpython or twisted
publisher to get a full CubicWeb web application


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from decimal import Decimal
from datetime import datetime, date, timedelta
from simplejson import dumps

from logilab.common.deprecation import deprecated

from cubicweb.common.uilib import urlquote
from cubicweb.web._exceptions import *


INTERNAL_FIELD_VALUE = '__cubicweb_internal_field__'


class stdmsgs(object):
    """standard ui message (in a class for bw compat)"""
    BUTTON_OK     = _('button_ok')
    BUTTON_APPLY  = _('button_apply')
    BUTTON_CANCEL = _('button_cancel')
    BUTTON_DELETE = _('button_delete')
    YES = _('yes')
    NO  = _('no')


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
    if isinstance(value, Decimal):
        value = float(value)
    elif isinstance(value, (date, datetime)):
        value = value.strftime('%Y-%m-%d %H:%M')
    elif isinstance(value, timedelta):
        value = (value.days * 24*60*60) + value.seconds
    try:
        return dumps(value)
    except TypeError:
        return dumps(repr(value))

def jsonize(function):
    def newfunc(*args, **kwargs):
        return json_dumps(function(*args, **kwargs))
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
