# copyright 2004-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of yams.
#
# yams is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# yams is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with yams. If not, see <http://www.gnu.org/licenses/>.
from yams.buildobjs import (EntityType, RelationType, RelationDefinition,
                            SubjectRelation, Int, String,  Boolean)
from yams.constraints import SizeConstraint, UniqueConstraint

from . import RESTRICTED_RTYPE_PERMS

class State(EntityType):
    """used to associate simple states to an entity
    type and/or to define workflows
    """
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users',),
        'delete': ('managers', 'owners',),
        'update': ('managers', 'owners',),
        }

    # attributes
    eid = Int(required=True, uid=True)
    name = String(required=True,
                  indexed=True, internationalizable=True,
                  constraints=[SizeConstraint(256)])
    description = String(fulltextindexed=True)
    # relations
    state_of = SubjectRelation('Eetype', cardinality='+*')
    next_state = SubjectRelation('State', cardinality='**')


class state_of(RelationType):
    """link a state to one or more entity type"""
    __permissions__ = RESTRICTED_RTYPE_PERMS

class next_state(RelationType):
    """define a workflow by associating a state to possible following states
    """
    __permissions__ = RESTRICTED_RTYPE_PERMS

class initial_state(RelationType):
    """indicate which state should be used by default when an entity using states
    is created
    """
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users',),
        'delete': ('managers', 'users',),
        }
    subject = 'Eetype'
    object = 'State'
    cardinality = '?*'
    inlined = True

class Eetype(EntityType):
    """define an entity type, used to build the application schema"""
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers',),
        'delete': ('managers',),
        'update': ('managers', 'owners',),
        }
    name = String(required=True, indexed=True, internationalizable=True,
                  constraints=[UniqueConstraint(), SizeConstraint(64)])
    description = String(fulltextindexed=True)
    meta = Boolean()
    final = Boolean()
