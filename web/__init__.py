"""CubicWeb web client core. You'll need a apache-modpython or twisted
publisher to get a full CubicWeb web application


:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.web._exceptions import *    

_ = unicode

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

FACETTES = set()


## FACETTES = set( (
##     # (relation, role, target's attribute)
##     ('created_by', 'subject', 'login'),
##     ('in_group', 'subject', 'name'),
##     ('in_state', 'subject', 'name'),
##     ))
