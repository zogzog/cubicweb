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
"""CubicWeb web client core. You'll need a apache-modpython or twisted
publisher to get a full CubicWeb web application
"""

__docformat__ = "restructuredtext en"
from cubicweb import _

from six.moves.urllib.parse import quote as urlquote
from logilab.common.deprecation import deprecated

from cubicweb.web._exceptions import *
from cubicweb.utils import json_dumps
from cubicweb.uilib import eid_param

assert json_dumps is not None, 'no json module installed'

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
