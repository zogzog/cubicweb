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
"""helper functions for application hooks

"""
__docformat__ = "restructuredtext en"

from logilab.common.deprecation import deprecated, class_moved

from cubicweb.server import hook

@deprecated('[3.6] entity_oldnewvalue should be imported from cw.server.hook')
def entity_oldnewvalue(entity, attr):
    return hook.entity_oldnewvalue(entity, attr)

@deprecated('[3.6] entity_name is deprecated, use entity.name')
def entity_name(session, eid):
    """return the "name" attribute of the entity with the given eid"""
    return session.entity_from_eid(eid).name

@deprecated('[3.6] rproperty is deprecated, use session.schema_rproperty')
def rproperty(session, rtype, eidfrom, eidto, rprop):
    return session.rproperty(rtype, eidfrom, eidto, rprop)

SendMailOp = class_moved(hook.SendMailOp)
