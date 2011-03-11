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
"""CubicWeb web client core. You'll need a apache-modpython or twisted
publisher to get a full CubicWeb web application
"""

__docformat__ = "restructuredtext en"
_ = unicode

from urllib import quote as urlquote

from logilab.common.deprecation import deprecated

from cubicweb.web._exceptions import *
from cubicweb.utils import json_dumps
from cubicweb.uilib import eid_param

assert json_dumps is not None, 'no json module installed'
dumps = deprecated('[3.9] use cubicweb.utils.json_dumps instead of dumps')(
    json_dumps)

INTERNAL_FIELD_VALUE = '__cubicweb_internal_field__'


class stdmsgs(object):
    """standard ui message (in a class for bw compat)"""
    BUTTON_OK     = (_('button_ok'), 'OK_ICON')
    BUTTON_APPLY  = (_('button_apply'), 'APPLY_ICON')
    BUTTON_CANCEL = (_('button_cancel'), 'CANCEL_ICON')
    BUTTON_DELETE = (_('button_delete'), 'TRASH_ICON')
    YES = (_('yes'), None)
    NO  = (_('no'), None)


from logging import getLogger
LOGGER = getLogger('cubicweb.web')

# XXX deprecated
FACETTES = set()


def jsonize(function):
    def newfunc(*args, **kwargs):
        value = function(*args, **kwargs)
        try:
            return json_dumps(value)
        except TypeError:
            return json_dumps(repr(value))
    return newfunc

@deprecated('[3.4] use req.ajax_replace_url() instead')
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
