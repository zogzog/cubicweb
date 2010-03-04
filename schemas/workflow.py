"""workflow related schemas

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from yams.buildobjs import (EntityType, RelationType, SubjectRelation,
                            RichString, String)
from cubicweb.schema import RQLConstraint, RQLUniqueConstraint
from cubicweb.schemas import (META_ETYPE_PERMS, META_RTYPE_PERMS,
                              HOOKS_RTYPE_PERMS)

class Workflow(EntityType):
    __permissions__ = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description = RichString(default_format='text/rest',
                             description=_('semantic description of this workflow'))

    workflow_of = SubjectRelation('CWEType', cardinality='+*',
                                  description=_('entity types which may use this workflow'),
                                  constraints=[RQLConstraint('O final FALSE')])

    initial_state = SubjectRelation('State', cardinality='?*',
                                   constraints=[RQLConstraint('O state_of S',
                                                              msg=_('state doesn\'t belong to this workflow'))],
                                   description=_('initial state for this workflow'))


class default_workflow(RelationType):
    """default workflow for an entity type"""
    __permissions__ = META_RTYPE_PERMS

    subject = 'CWEType'
    object = 'Workflow'
    cardinality = '?*'
    constraints = [RQLConstraint('S final FALSE, O workflow_of S',
                                 msg=_('workflow isn\'t a workflow for this type'))]


class State(EntityType):
    """used to associate simple states to an entity type and/or to define
    workflows
    """
    __permissions__ = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256,
                  constraints=[RQLUniqueConstraint('S name N, S state_of WF, Y state_of WF, Y name N', 'Y',
                                                   _('workflow already have a state of that name'))])
    description = RichString(default_format='text/rest',
                             description=_('semantic description of this state'))

    # XXX should be on BaseTransition w/ AND/OR selectors when we will
    # implements #345274
    allowed_transition = SubjectRelation('BaseTransition', cardinality='**',
                                         constraints=[RQLConstraint('S state_of WF, O transition_of WF',
                                                                    msg=_('state and transition don\'t belong the the same workflow'))],
                                         description=_('allowed transitions from this state'))
    state_of = SubjectRelation('Workflow', cardinality='1*', composite='object',
                               description=_('workflow to which this state belongs'),
                               constraints=[RQLUniqueConstraint('S name N, Y state_of O, Y name N', 'Y',
                                                                _('workflow already have a state of that name'))])


class BaseTransition(EntityType):
    """abstract base class for transitions"""
    __permissions__ = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256,
                  constraints=[RQLUniqueConstraint('S name N, S transition_of WF, Y transition_of WF, Y name N', 'Y',
                                                   _('workflow already have a transition of that name'))])
    type = String(vocabulary=(_('normal'), _('auto')), default='normal')
    description = RichString(description=_('semantic description of this transition'))
    condition = SubjectRelation('RQLExpression', cardinality='*?', composite='subject',
                                description=_('a RQL expression which should return some results, '
                                              'else the transition won\'t be available. '
                                              'This query may use X and U variables '
                                              'that will respectivly represents '
                                              'the current entity and the current user'))

    require_group = SubjectRelation('CWGroup', cardinality='**',
                                    description=_('group in which a user should be to be '
                                                  'allowed to pass this transition'))
    transition_of = SubjectRelation('Workflow', cardinality='1*', composite='object',
                                    description=_('workflow to which this transition belongs'),
                                    constraints=[RQLUniqueConstraint('S name N, Y transition_of O, Y name N', 'Y',
                                                                     _('workflow already have a transition of that name'))])


class Transition(BaseTransition):
    """use to define a transition from one or multiple states to a destination
    states in workflow's definitions. Transition without destination state will
    go back to the state from which we arrived to the current state.
    """
    __specializes_schema__ = True

    destination_state = SubjectRelation(
        'State', cardinality='?*',
        constraints=[RQLConstraint('S transition_of WF, O state_of WF',
                                   msg=_('state and transition don\'t belong the the same workflow'))],
        description=_('destination state for this transition'))


class WorkflowTransition(BaseTransition):
    """special transition allowing to go through a sub-workflow"""
    __specializes_schema__ = True

    subworkflow = SubjectRelation('Workflow', cardinality='1*',
                                  constraints=[RQLConstraint('S transition_of WF, WF workflow_of ET, O workflow_of ET',
                                                             msg=_('subworkflow isn\'t a workflow for the same types as the transition\'s workflow'))]
                                  )
    # XXX use exit_of and inline it
    subworkflow_exit = SubjectRelation('SubWorkflowExitPoint', cardinality='*1',
                                       composite='subject')


class SubWorkflowExitPoint(EntityType):
    """define how we get out from a sub-workflow"""
    subworkflow_state = SubjectRelation(
        'State', cardinality='1*',
        constraints=[RQLConstraint('T subworkflow_exit S, T subworkflow WF, O state_of WF',
                                   msg=_('exit state must a subworkflow state'))],
        description=_('subworkflow state'))
    destination_state = SubjectRelation(
        'State', cardinality='?*',
        constraints=[RQLConstraint('T subworkflow_exit S, T transition_of WF, O state_of WF',
                                   msg=_('destination state must be in the same workflow as our parent transition'))],
        description=_('destination state. No destination state means that transition '
                      'should go back to the state from which we\'ve entered the '
                      'subworkflow.'))


class TrInfo(EntityType):
    """workflow history item"""
    # 'add' security actually done by hooks
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',), # XXX U has_read_permission O ?
        'add':    ('managers', 'users', 'guests',),
        'delete': (), # XXX should we allow managers to delete TrInfo?
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
    __permissions__ = HOOKS_RTYPE_PERMS.copy()
    inlined = True

class to_state(RelationType):
    __permissions__ = HOOKS_RTYPE_PERMS.copy()
    inlined = True

class by_transition(RelationType):
    # 'add' security actually done by hooks
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users', 'guests',),
        'delete': (),
    }
    inlined = True


class workflow_of(RelationType):
    """link a workflow to one or more entity type"""
    __permissions__ = META_RTYPE_PERMS

class state_of(RelationType):
    """link a state to one or more workflow"""
    __permissions__ = META_RTYPE_PERMS
    inlined = True

class transition_of(RelationType):
    """link a transition to one or more workflow"""
    __permissions__ = META_RTYPE_PERMS
    inlined = True

class destination_state(RelationType):
    """destination state of a transition"""
    __permissions__ = META_RTYPE_PERMS
    inlined = True

class allowed_transition(RelationType):
    """allowed transitions from this state"""
    __permissions__ = META_RTYPE_PERMS

class initial_state(RelationType):
    """indicate which state should be used by default when an entity using
    states is created
    """
    __permissions__ = META_RTYPE_PERMS
    inlined = True


class subworkflow(RelationType):
    __permissions__ = META_RTYPE_PERMS
    inlined = True

class exit_point(RelationType):
    __permissions__ = META_RTYPE_PERMS

class subworkflow_state(RelationType):
    __permissions__ = META_RTYPE_PERMS
    inlined = True


class condition(RelationType):
    __permissions__ = META_RTYPE_PERMS

# already defined in base.py
# class require_group(RelationType):
#     __permissions__ = META_RTYPE_PERMS


# "abstract" relations, set by WorkflowableEntityType ##########################

class custom_workflow(RelationType):
    """allow to set a specific workflow for an entity"""
    __permissions__ = META_RTYPE_PERMS

    cardinality = '?*'
    constraints = [RQLConstraint('S is ET, O workflow_of ET',
                                 msg=_('workflow isn\'t a workflow for this type'))]
    object = 'Workflow'


class wf_info_for(RelationType):
    """link a transition information to its object"""
    # 'add' security actually done by hooks
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users', 'guests',),
        'delete': (),
    }
    inlined = True

    cardinality = '1*'
    composite = 'object'
    fulltext_container = composite
    subject = 'TrInfo'


class in_state(RelationType):
    """indicate the current state of an entity"""
    __permissions__ = HOOKS_RTYPE_PERMS

    # not inlined intentionnaly since when using ldap sources, user'state
    # has to be stored outside the CWUser table
    inlined = False

    cardinality = '1*'
    constraints = [RQLConstraint('S is ET, O state_of WF, WF workflow_of ET',
                                 msg=_('state doesn\'t apply to this entity\'s type'))]
    object = 'State'
