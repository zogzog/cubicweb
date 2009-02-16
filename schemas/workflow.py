"""workflow related schemas

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

class State(MetaEntityType):
    """used to associate simple states to an entity type and/or to define
    workflows
    """
    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description = RichString(fulltextindexed=True, default='text/rest',
                             description=_('semantic description of this state'))
    
    state_of = SubjectRelation('EEType', cardinality='+*',
                    description=_('entity types which may use this state'),
                    constraints=[RQLConstraint('O final FALSE')])
    allowed_transition = SubjectRelation('Transition', cardinality='**',
                                         constraints=[RQLConstraint('S state_of ET, O transition_of ET')],
                                         description=_('allowed transitions from this state'))
    
    initial_state = ObjectRelation('EEType', cardinality='?*',
                                   # S initial_state O, O state_of S
                                   constraints=[RQLConstraint('O state_of S')],
                                   description=_('initial state for entities of this type'))


class Transition(MetaEntityType):
    """use to define a transition from one or multiple states to a destination
    states in workflow's definitions.
    """
    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description_format = String(meta=True, internationalizable=True, maxsize=50,
                                default='text/rest', constraints=[format_constraint])
    description = String(fulltextindexed=True,
                         description=_('semantic description of this transition'))
    condition = SubjectRelation('RQLExpression', cardinality='*?', composite='subject',
                                description=_('a RQL expression which should return some results, '
                                              'else the transition won\'t be available. '
                                              'This query may use X and U variables '
                                              'that will respectivly represents '
                                              'the current entity and the current user'))
    
    require_group = SubjectRelation('EGroup', cardinality='**',
                                    description=_('group in which a user should be to be '
                                                  'allowed to pass this transition'))
    transition_of = SubjectRelation('EEType', cardinality='+*',
                                    description=_('entity types which may use this transition'),
                                    constraints=[RQLConstraint('O final FALSE')])
    destination_state = SubjectRelation('State', cardinality='?*',
                                        constraints=[RQLConstraint('S transition_of ET, O state_of ET')],
                                        description=_('destination state for this transition'))


class TrInfo(MetaEntityType):
    from_state = SubjectRelation('State', cardinality='?*')
    to_state = SubjectRelation('State', cardinality='1*')
    comment_format = String(meta=True, internationalizable=True, maxsize=50,
                            default='text/rest', constraints=[format_constraint])
    comment = String(fulltextindexed=True)
    # get actor and date time using owned_by and creation_date


class from_state(MetaRelationType):
    inlined = True
class to_state(MetaRelationType):
    inlined = True
class wf_info_for(MetaRelationType):
    """link a transition information to its object"""
    permissions = {
        'read':   ('managers', 'users', 'guests',),# RRQLExpression('U has_read_permission O')),
        'add':    (), # handled automatically, no one should add one explicitly
        'delete': ('managers',), # RRQLExpression('U has_delete_permission O')
        }
    inlined = True
    composite = 'object'
    fulltext_container = composite
    
class state_of(MetaRelationType):
    """link a state to one or more entity type"""
class transition_of(MetaRelationType):
    """link a transition to one or more entity type"""
    
class initial_state(MetaRelationType):
    """indicate which state should be used by default when an entity using
    states is created
    """
    inlined = True

class destination_state(MetaRelationType):
    """destination state of a transition"""
    inlined = True
    
class allowed_transition(MetaRelationType):
    """allowed transition from this state"""

class in_state(UserRelationType):
    """indicate the current state of an entity"""
    meta = True
    # not inlined intentionnaly since when using ldap sources, user'state
    # has to be stored outside the EUser table
    
    # add/delete perms given to managers/users, after what most of the job
    # is done by workflow enforcment
    
