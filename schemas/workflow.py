"""workflow related schemas

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from yams.buildobjs import (EntityType, RelationType, SubjectRelation,
                            ObjectRelation, RichString, String)
from cubicweb.schema import RQLConstraint
from cubicweb.schemas import META_ETYPE_PERMS, META_RTYPE_PERMS, HOOKS_RTYPE_PERMS

class State(EntityType):
    """used to associate simple states to an entity type and/or to define
    workflows
    """
    permissions = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description = RichString(fulltextindexed=True, default_format='text/rest',
                             description=_('semantic description of this state'))

    state_of = SubjectRelation('CWEType', cardinality='+*',
                    description=_('entity types which may use this state'),
                    constraints=[RQLConstraint('O final FALSE')])
    allowed_transition = SubjectRelation('Transition', cardinality='**',
                                         constraints=[RQLConstraint('S state_of ET, O transition_of ET')],
                                         description=_('allowed transitions from this state'))

    initial_state = ObjectRelation('CWEType', cardinality='?*',
                                   # S initial_state O, O state_of S
                                   constraints=[RQLConstraint('O state_of S')],
                                   description=_('initial state for entities of this type'))


class Transition(EntityType):
    """use to define a transition from one or multiple states to a destination
    states in workflow's definitions.
    """
    permissions = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description = RichString(fulltextindexed=True,
                         description=_('semantic description of this transition'))
    condition = SubjectRelation('RQLExpression', cardinality='*?', composite='subject',
                                description=_('a RQL expression which should return some results, '
                                              'else the transition won\'t be available. '
                                              'This query may use X and U variables '
                                              'that will respectivly represents '
                                              'the current entity and the current user'))

    require_group = SubjectRelation('CWGroup', cardinality='**',
                                    description=_('group in which a user should be to be '
                                                  'allowed to pass this transition'))
    transition_of = SubjectRelation('CWEType', cardinality='+*',
                                    description=_('entity types which may use this transition'),
                                    constraints=[RQLConstraint('O final FALSE')])
    destination_state = SubjectRelation('State', cardinality='1*',
                                        constraints=[RQLConstraint('S transition_of ET, O state_of ET')],
                                        description=_('destination state for this transition'))


class TrInfo(EntityType):
    permissions = META_ETYPE_PERMS

    from_state = SubjectRelation('State', cardinality='?*')
    to_state = SubjectRelation('State', cardinality='1*')
    comment = RichString(fulltextindexed=True)
    # get actor and date time using owned_by and creation_date


class from_state(RelationType):
    permissions = HOOKS_RTYPE_PERMS
    inlined = True
class to_state(RelationType):
    permissions = HOOKS_RTYPE_PERMS
    inlined = True

class wf_info_for(RelationType):
    """link a transition information to its object"""
    permissions = {
        'read':   ('managers', 'users', 'guests',),# RRQLExpression('U has_read_permission O')),
        'add':    (), # handled automatically, no one should add one explicitly
        'delete': ('managers',), # RRQLExpression('U has_delete_permission O')
        }
    inlined = True
    composite = 'object'
    fulltext_container = composite

class state_of(RelationType):
    """link a state to one or more entity type"""
    permissions = META_RTYPE_PERMS
class transition_of(RelationType):
    """link a transition to one or more entity type"""
    permissions = META_RTYPE_PERMS

class initial_state(RelationType):
    """indicate which state should be used by default when an entity using
    states is created
    """
    permissions = META_RTYPE_PERMS
    inlined = True

class destination_state(RelationType):
    """destination state of a transition"""
    permissions = META_RTYPE_PERMS
    inlined = True

class allowed_transition(RelationType):
    """allowed transition from this state"""
    permissions = META_RTYPE_PERMS

class in_state(RelationType):
    """indicate the current state of an entity"""
    # not inlined intentionnaly since when using ldap sources, user'state
    # has to be stored outside the CWUser table

    # add/delete perms given to managers/users, after what most of the job
    # is done by workflow enforcment
    permissions = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users',), # XXX has_update_perm
        'delete': ('managers', 'users',),
        }

