"""helper functions for application hooks

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.deprecation import deprecated, class_moved

from cubicweb import RepositoryError
from cubicweb.server import hook

@deprecated('[3.6] entity_oldnewvalue should be imported from cw.server.hook')
def entity_oldnewvalue(entity, attr):
    """return the "name" attribute of the entity with the given eid"""
    return hook.entity_oldnewvalue(entity, attr)

@deprecated('[3.6] entity_name is deprecated, use entity.name')
def entity_name(session, eid):
    """return the "name" attribute of the entity with the given eid"""
    return session.entity_from_eid(eid).name

@deprecated('[3.6] rproperty is deprecated, use session.schema_rproperty')
def rproperty(session, rtype, eidfrom, eidto, rprop):
    return session.rproperty(rtype, eidfrom, eidto, rprop)

SendMailOp = class_moved(hook.SendMailOp)
