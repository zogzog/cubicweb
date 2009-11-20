"""helper functions for application hooks

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.deprecation import deprecated, class_moved

from cubicweb import RepositoryError

def entity_oldnewvalue(entity, attr):
    """returns the couple (old attr value, new attr value)
    NOTE: will only work in a before_update_entity hook
    """
    # get new value and remove from local dict to force a db query to
    # fetch old value
    newvalue = entity.pop(attr, None)
    oldvalue = getattr(entity, attr)
    if newvalue is not None:
        entity[attr] = newvalue
    return oldvalue, newvalue

@deprecated('[3.6] entity_name is deprecated, use entity.name')
def entity_name(session, eid):
    """return the "name" attribute of the entity with the given eid"""
    return session.entity_from_eid(eid).name

@deprecated('[3.6] rproperty is deprecated, use session.schema_rproperty')
def rproperty(session, rtype, eidfrom, eidto, rprop):
    return session.rproperty(rtype, eidfrom, eidto, rprop)

from cubicweb.server.hook import SendMailOp
SendMailOp = class_moved(SendMailOp)
