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
from cubicweb.schema import RQLConstraint, RQLUniqueConstraint
from cubicweb.schemas import (META_ETYPE_PERMS, META_RTYPE_PERMS,
                              HOOKS_RTYPE_PERMS)

class Workflow(EntityType):
    permissions = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description = RichString(fulltextindexed=True, default_format='text/rest',
                             description=_('semantic description of this workflow'))

    workflow_of = SubjectRelation('CWEType', cardinality='+*',
                                  description=_('entity types which may use this workflow'),
                                  constraints=[RQLConstraint('O final FALSE')])

    initial_state = SubjectRelation('State', cardinality='?*',
                                   # S initial_state O, O state_of S
                                   constraints=[RQLConstraint('O state_of S')],
                                   description=_('initial state for this workflow'))


class default_workflow(RelationType):
    """default workflow for this entity types"""
    permissions = META_RTYPE_PERMS

    subject = 'CWEType'
    object = 'Workflow'
    cardinality = '?*'
    constraints = [RQLConstraint('S final FALSE, O workflow_of S')]


class State(EntityType):
    """used to associate simple states to an entity type and/or to define
    workflows
    """
    permissions = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description = RichString(fulltextindexed=True, default_format='text/rest',
                             description=_('semantic description of this state'))

    # XXX should be on BaseTransition w/ AND/OR selectors when we will
    # implements #345274
    allowed_transition = SubjectRelation('BaseTransition', cardinality='**',
                                         constraints=[RQLConstraint('S state_of WF, O transition_of WF')],
                                         description=_('allowed transitions from this state'))
    state_of = SubjectRelation('Workflow', cardinality='+*',
                               description=_('workflow to which this state belongs'),
                               constraints=[RQLUniqueConstraint('S name N, Y state_of O, Y name N')])


class BaseTransition(EntityType):
    """abstract base class for transitions"""
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
    transition_of = SubjectRelation('Workflow', cardinality='+*',
                                    description=_('workflow to which this transition belongs'),
                                    constraints=[RQLUniqueConstraint('S name N, Y transition_of O, Y name N')])


class Transition(BaseTransition):
    """use to define a transition from one or multiple states to a destination
    states in workflow's definitions.
    """
    __specializes_schema__ = True

    destination_state = SubjectRelation('State', cardinality='1*',
                                        constraints=[RQLConstraint('S transition_of WF, O state_of WF')],
                                        description=_('destination state for this transition'))


class WorkflowTransition(BaseTransition):
    """special transition allowing to go through a sub-workflow"""
    __specializes_schema__ = True

    subworkflow = SubjectRelation('Workflow', cardinality='1*',
                                  constraints=[RQLConstraint('S transition_of WF, WF workflow_of ET, O workflow_of ET')])
    subworkflow_exit = SubjectRelation('SubWorkflowExitPoint', cardinality='+1',
                                       composite='subject')


class SubWorkflowExitPoint(EntityType):
    """define how we get out from a sub-workflow"""
    subworkflow_state = SubjectRelation('State', cardinality='1*',
                                        constraints=[RQLConstraint('T subworkflow_exit S, T subworkflow WF, O state_of WF')],
                                        description=_('subworkflow state'))
    destination_state = SubjectRelation('State', cardinality='1*',
                                        constraints=[RQLConstraint('T subworkflow_exit S, T transition_of WF, O state_of WF')],
                                        description=_('destination state'))


# XXX should we allow managers to delete TrInfo?

class TrInfo(EntityType):
    """workflow history item"""
    # 'add' security actually done by hooks
    permissions = {
        'read':   ('managers', 'users', 'guests',), # XXX U has_read_permission O ?
        'add':    ('managers', 'users', 'guests',),
        'delete': (),
        'update': ('managers', 'owners',),
    }

    from_state = SubjectRelation('State', cardinality='1*')
    to_state = SubjectRelation('State', cardinality='1*')
    # make by_transition optional because we want to allow managers to set
    # entity into an arbitrary state without having to respect wf transition
    by_transition = SubjectRelation('BaseTransition', cardinality='?*')
    comment = RichString(fulltextindexed=True)
    # get actor and date time using owned_by and creation_date

class from_state(RelationType):
    permissions = HOOKS_RTYPE_PERMS.copy()
    inlined = True

class to_state(RelationType):
    permissions = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers',),
        'delete': (),
    }
    inlined = True

class by_transition(RelationType):
    # 'add' security actually done by hooks
    permissions = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users', 'guests',),
        'delete': (),
    }
    inlined = True

class workflow_of(RelationType):
    """link a workflow to one or more entity type"""
    permissions = META_RTYPE_PERMS

class state_of(RelationType):
    """link a state to one or more workflow"""
    permissions = META_RTYPE_PERMS

class transition_of(RelationType):
    """link a transition to one or more workflow"""
    permissions = META_RTYPE_PERMS

class subworkflow(RelationType):
    """link a transition to one or more workflow"""
    permissions = META_RTYPE_PERMS
    inlined = True

class exit_point(RelationType):
    """link a transition to one or more workflow"""
    permissions = META_RTYPE_PERMS

class subworkflow_state(RelationType):
    """link a transition to one or more workflow"""
    permissions = META_RTYPE_PERMS
    inlined = True

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


# "abstract" relations, set by WorkflowableEntityType ##########################

class custom_workflow(RelationType):
    """allow to set a specific workflow for an entity"""
    permissions = META_RTYPE_PERMS

    cardinality = '?*'
    constraints = [RQLConstraint('S is ET, O workflow_of ET')]
    object = 'Workflow'


class wf_info_for(RelationType):
    """link a transition information to its object"""
    # 'add' security actually done by hooks
    permissions = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users', 'guests',),
        'delete': (),
    }
    inlined = True

    cardinality='1*'
    composite = 'object'
    fulltext_container = composite
    subject = 'TrInfo'


class in_state(RelationType):
    """indicate the current state of an entity"""
    permissions = HOOKS_RTYPE_PERMS

    # not inlined intentionnaly since when using ldap sources, user'state
    # has to be stored outside the CWUser table
    inlined = False

    cardinality = '1*'
    constraints = [RQLConstraint('S is ET, O state_of WF, WF workflow_of ET')]
    object = 'State'
