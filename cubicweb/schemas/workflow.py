# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""workflow related schemas

"""

from cubicweb import _

from yams.buildobjs import (EntityType, RelationType, RelationDefinition,
                            SubjectRelation,
                            RichString, String, Int)
from cubicweb.schema import RQLConstraint
from cubicweb.schemas import (PUB_SYSTEM_ENTITY_PERMS, PUB_SYSTEM_REL_PERMS,
                              RO_REL_PERMS)

class Workflow(EntityType):
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS

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
    __permissions__ = PUB_SYSTEM_REL_PERMS

    subject = 'CWEType'
    object = 'Workflow'
    cardinality = '?*'
    constraints = [RQLConstraint('S final FALSE, O workflow_of S',
                                 msg=_('workflow isn\'t a workflow for this type'))]


class State(EntityType):
    """used to associate simple states to an entity type and/or to define
    workflows
    """
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    __unique_together__ = [('name', 'state_of')]
    name = String(required=True, indexed=True, internationalizable=True, maxsize=256)
    description = RichString(default_format='text/rest',
                             description=_('semantic description of this state'))

    # XXX should be on BaseTransition w/ AND/OR selectors when we will
    # implements #345274
    allowed_transition = SubjectRelation('BaseTransition', cardinality='**',
                                         constraints=[RQLConstraint('S state_of WF, O transition_of WF',
                                                                    msg=_('state and transition don\'t belong the the same workflow'))],
                                         description=_('allowed transitions from this state'))
    state_of = SubjectRelation('Workflow', cardinality='1*', composite='object', inlined=True,
                               description=_('workflow to which this state belongs'))


class BaseTransition(EntityType):
    """abstract base class for transitions"""
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    __unique_together__ = [('name', 'transition_of')]

    name = String(required=True, indexed=True, internationalizable=True, maxsize=256)
    type = String(vocabulary=(_('normal'), _('auto')), default='normal')
    description = RichString(description=_('semantic description of this transition'))

    transition_of = SubjectRelation('Workflow', cardinality='1*', composite='object', inlined=True,
                                    description=_('workflow to which this transition belongs'))


class require_group(RelationDefinition):
    """group in which a user should be to be allowed to pass this transition"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    subject = 'BaseTransition'
    object = 'CWGroup'


class condition(RelationDefinition):
    """a RQL expression which should return some results, else the transition
    won't be available.

    This query may use X and U variables that will respectivly represents the
    current entity and the current user.
    """
    __permissions__ = PUB_SYSTEM_REL_PERMS
    subject = 'BaseTransition'
    object = 'RQLExpression'
    cardinality = '*?'
    composite = 'subject'


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
                                   msg=_('exit state must be a subworkflow state'))],
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
    # The unique_together constraint ensures that 2 repositories
    # sharing the db won't be able to fire a transition simultaneously
    # on the same entity tr_count is filled in the FireTransitionHook
    # to the number of TrInfo attached to the entity on which we
    # attempt to fire a transition. In other word, it contains the
    # rank of the TrInfo for that entity, and the constraint says we
    # cannot have 2 TrInfo with the same rank.
    __unique_together__ = [('tr_count', 'wf_info_for')]
    from_state = SubjectRelation('State', cardinality='1*', inlined=True)
    to_state = SubjectRelation('State', cardinality='1*', inlined=True)
    # make by_transition optional because we want to allow managers to set
    # entity into an arbitrary state without having to respect wf transition
    by_transition = SubjectRelation('BaseTransition', cardinality='?*')
    comment = RichString(fulltextindexed=True, default_format='text/plain')
    tr_count = Int(description='autocomputed attribute used to ensure transition coherency')
    # get actor and date time using owned_by and creation_date

class from_state(RelationType):
    __permissions__ = RO_REL_PERMS.copy()
    inlined = True

class to_state(RelationType):
    __permissions__ = RO_REL_PERMS.copy()
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
    __permissions__ = PUB_SYSTEM_REL_PERMS

class state_of(RelationType):
    """link a state to one or more workflow"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True

class transition_of(RelationType):
    """link a transition to one or more workflow"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True

class destination_state(RelationType):
    """destination state of a transition"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True

class allowed_transition(RelationType):
    """allowed transitions from this state"""
    __permissions__ = PUB_SYSTEM_REL_PERMS

class initial_state(RelationType):
    """indicate which state should be used by default when an entity using
    states is created
    """
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True


class subworkflow(RelationType):
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True

class exit_point(RelationType):
    __permissions__ = PUB_SYSTEM_REL_PERMS

class subworkflow_state(RelationType):
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True


# "abstract" relations, set by WorkflowableEntityType ##########################

class custom_workflow(RelationType):
    """allow to set a specific workflow for an entity"""
    __permissions__ = PUB_SYSTEM_REL_PERMS

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
    __permissions__ = RO_REL_PERMS

    # not inlined intentionnally since when using ldap sources, user'state
    # has to be stored outside the CWUser table
    inlined = False

    cardinality = '1*'
    constraints = [RQLConstraint('S is ET, O state_of WF, WF workflow_of ET',
                                 msg=_('state doesn\'t apply to this entity\'s type'))]
    object = 'State'
