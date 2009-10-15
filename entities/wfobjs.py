"""workflow definition and history related entities

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.decorators import cached, clear_cache
from logilab.common.deprecation import deprecated

from cubicweb.entities import AnyEntity, fetch_config
from cubicweb.interfaces import IWorkflowable
from cubicweb.common.mixins import MI_REL_TRIGGERS

class WorkflowException(Exception): pass

class Workflow(AnyEntity):
    id = 'Workflow'

    @property
    def initial(self):
        """return the initial state for this workflow"""
        return self.initial_state and self.initial_state[0] or None

    def is_default_workflow_of(self, etype):
        """return True if this workflow is the default workflow for the given
        entity type
        """
        return any(et for et in self.reverse_default_workflow
                   if et.name == etype)

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.workflow_of:
            return self.workflow_of[0].rest_path(), {'vid': 'workflow'}
        return super(Workflow, self).after_deletion_path()

    def iter_workflows(self, _done=None):
        """return an iterator on actual workflows, eg this workflow and its
        subworkflows
        """
        # infinite loop safety belt
        if _done is None:
            _done = set()
        yield self
        _done.add(self.eid)
        for tr in self.req.execute('Any T WHERE T is WorkflowTransition, '
                                   'T transition_of WF, WF eid %(wf)s',
                                   {'wf': self.eid}).entities():
            if tr.subwf.eid in _done:
                continue
            for subwf in tr.subwf.iter_workflows(_done):
                yield subwf

    # state / transitions accessors ############################################

    def state_by_name(self, statename):
        rset = self.req.execute('Any S, SN WHERE S name SN, S name %(n)s, '
                                'S state_of WF, WF eid %(wf)s',
                                {'n': statename, 'wf': self.eid}, 'wf')
        if rset:
            return rset.get_entity(0, 0)
        return None

    def state_by_eid(self, eid):
        rset = self.req.execute('Any S, SN WHERE S name SN, S eid %(s)s, '
                                'S state_of WF, WF eid %(wf)s',
                                {'s': eid, 'wf': self.eid}, ('wf', 's'))
        if rset:
            return rset.get_entity(0, 0)
        return None

    def transition_by_name(self, trname):
        rset = self.req.execute('Any T, TN WHERE T name TN, T name %(n)s, '
                                'T transition_of WF, WF eid %(wf)s',
                                {'n': trname, 'wf': self.eid}, 'wf')
        if rset:
            return rset.get_entity(0, 0)
        return None

    def transition_by_eid(self, eid):
        rset = self.req.execute('Any T, TN WHERE T name TN, T eid %(t)s, '
                                'T transition_of WF, WF eid %(wf)s',
                                {'t': eid, 'wf': self.eid}, ('wf', 't'))
        if rset:
            return rset.get_entity(0, 0)
        return None

    # wf construction methods ##################################################

    def add_state(self, name, initial=False, **kwargs):
        """add a state to this workflow"""
        state = self.req.create_entity('State', name=unicode(name), **kwargs)
        self.req.execute('SET S state_of WF WHERE S eid %(s)s, WF eid %(wf)s',
                         {'s': state.eid, 'wf': self.eid}, ('s', 'wf'))
        if initial:
            assert not self.initial
            self.req.execute('SET WF initial_state S '
                             'WHERE S eid %(s)s, WF eid %(wf)s',
                             {'s': state.eid, 'wf': self.eid}, ('s', 'wf'))
        return state

    def _add_transition(self, trtype, name, fromstates,
                        requiredgroups=(), conditions=(), **kwargs):
        tr = self.req.create_entity(trtype, name=unicode(name), **kwargs)
        self.req.execute('SET T transition_of WF '
                         'WHERE T eid %(t)s, WF eid %(wf)s',
                         {'t': tr.eid, 'wf': self.eid}, ('t', 'wf'))
        assert fromstates, fromstates
        if not isinstance(fromstates, (tuple, list)):
            fromstates = (fromstates,)
        for state in fromstates:
            if hasattr(state, 'eid'):
                state = state.eid
            self.req.execute('SET S allowed_transition T '
                             'WHERE S eid %(s)s, T eid %(t)s',
                             {'s': state, 't': tr.eid}, ('s', 't'))
        tr.set_transition_permissions(requiredgroups, conditions, reset=False)
        return tr

    def add_transition(self, name, fromstates, tostate=None,
                       requiredgroups=(), conditions=(), **kwargs):
        """add a transition to this workflow from some state(s) to another"""
        tr = self._add_transition('Transition', name, fromstates,
                                  requiredgroups, conditions, **kwargs)
        if tostate is not None:
            if hasattr(tostate, 'eid'):
                tostate = tostate.eid
            self.req.execute('SET T destination_state S '
                             'WHERE S eid %(s)s, T eid %(t)s',
                             {'t': tr.eid, 's': tostate}, ('s', 't'))
        return tr

    def add_wftransition(self, name, subworkflow, fromstates, exitpoints=(),
                         requiredgroups=(), conditions=(), **kwargs):
        """add a workflow transition to this workflow"""
        tr = self._add_transition('WorkflowTransition', name, fromstates,
                                  requiredgroups, conditions, **kwargs)
        if hasattr(subworkflow, 'eid'):
            subworkflow = subworkflow.eid
        assert self.req.execute('SET T subworkflow WF WHERE WF eid %(wf)s,T eid %(t)s',
                                {'t': tr.eid, 'wf': subworkflow}, ('wf', 't'))
        for fromstate, tostate in exitpoints:
            tr.add_exit_point(fromstate, tostate)
        return tr


class BaseTransition(AnyEntity):
    """customized class for abstract transition

    provides a specific may_be_fired method to check if the relation may be
    fired by the logged user
    """
    id = 'BaseTransition'
    fetch_attrs, fetch_order = fetch_config(['name'])

    def __init__(self, *args, **kwargs):
        if self.id == 'BaseTransition':
            raise WorkflowException('should not be instantiated')
        super(BaseTransition, self).__init__(*args, **kwargs)

    @property
    def workflow(self):
        return self.transition_of[0]

    def has_input_state(self, state):
        if hasattr(state, 'eid'):
            state = state.eid
        return any(s for s in self.reverse_allowed_transition if s.eid == state)

    def may_be_fired(self, eid):
        """return true if the logged user may fire this transition

        `eid` is the eid of the object on which we may fire the transition
        """
        user = self.req.user
        # check user is at least in one of the required groups if any
        groups = frozenset(g.name for g in self.require_group)
        if groups:
            matches = user.matching_groups(groups)
            if matches:
                return matches
            if 'owners' in groups and user.owns(eid):
                return True
        # check one of the rql expression conditions matches if any
        if self.condition:
            for rqlexpr in self.condition:
                if rqlexpr.check_expression(self.req, eid):
                    return True
        if self.condition or groups:
            return False
        return True

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.transition_of:
            return self.transition_of[0].rest_path(), {}
        return super(Transition, self).after_deletion_path()

    def set_transition_permissions(self, requiredgroups=(), conditions=(),
                                   reset=True):
        """set or add (if `reset` is False) groups and conditions for this
        transition
        """
        if reset:
            self.req.execute('DELETE T require_group G WHERE T eid %(x)s',
                             {'x': self.eid}, 'x')
            self.req.execute('DELETE T condition R WHERE T eid %(x)s',
                             {'x': self.eid}, 'x')
        for gname in requiredgroups:
            rset = self.req.execute('SET T require_group G '
                                    'WHERE T eid %(x)s, G name %(gn)s',
                                    {'x': self.eid, 'gn': gname}, 'x')
            assert rset, '%s is not a known group' % gname
        if isinstance(conditions, basestring):
            conditions = (conditions,)
        for expr in conditions:
            if isinstance(expr, basestring):
                kwargs = {'expr': unicode(expr)}
            else:
                assert isinstance(expr, dict)
                kwargs = expr
            kwargs['x'] = self.eid
            kwargs.setdefault('mainvars', u'X')
            self.req.execute('INSERT RQLExpression X: X exprtype "ERQLExpression", '
                             'X expression %(expr)s, X mainvars %(mainvars)s, '
                             'T condition X WHERE T eid %(x)s', kwargs, 'x')
        # XXX clear caches?


class Transition(BaseTransition):
    """customized class for Transition entities"""
    id = 'Transition'

    def destination(self):
        return self.destination_state[0]


class WorkflowTransition(BaseTransition):
    """customized class for WorkflowTransition entities"""
    id = 'WorkflowTransition'

    @property
    def subwf(self):
        return self.subworkflow[0]

    def destination(self):
        return self.subwf.initial

    def add_exit_point(self, fromstate, tostate):
        if hasattr(fromstate, 'eid'):
            fromstate = fromstate.eid
        if tostate is None:
            self.req.execute('INSERT SubWorkflowExitPoint X: T subworkflow_exit X, '
                             'X subworkflow_state FS WHERE T eid %(t)s, FS eid %(fs)s',
                             {'t': self.eid, 'fs': fromstate}, ('t', 'fs'))
        else:
            if hasattr(tostate, 'eid'):
                tostate = tostate.eid
            self.req.execute('INSERT SubWorkflowExitPoint X: T subworkflow_exit X, '
                             'X subworkflow_state FS, X destination_state TS '
                             'WHERE T eid %(t)s, FS eid %(fs)s, TS eid %(ts)s',
                             {'t': self.eid, 'fs': fromstate, 'ts': tostate},
                             ('t', 'fs', 'ts'))

    def get_exit_point(self, entity, stateeid):
        """if state is an exit point, return its associated destination state"""
        if hasattr(stateeid, 'eid'):
            stateeid = stateeid.eid
        try:
            tostateeid = self.exit_points()[stateeid]
        except KeyError:
            return None
        if tostateeid is None:
            # go back to state from which we've entered the subworkflow
            return entity.subworkflow_input_trinfo().previous_state
        return self.req.entity_from_eid(tostateeid)

    @cached
    def exit_points(self):
        result = {}
        for ep in self.subworkflow_exit:
            result[ep.subwf_state.eid] = ep.destination and ep.destination.eid
        return result

    def clear_all_caches(self):
        super(WorkflowableMixIn, self).clear_all_caches()
        clear_cache(self, 'exit_points')


class SubWorkflowExitPoint(AnyEntity):
    """customized class for SubWorkflowExitPoint entities"""
    id = 'SubWorkflowExitPoint'

    @property
    def subwf_state(self):
        return self.subworkflow_state[0]

    @property
    def destination(self):
        return self.destination_state and self.destination_state[0] or None


class State(AnyEntity):
    """customized class for State entities"""
    id = 'State'
    fetch_attrs, fetch_order = fetch_config(['name'])
    rest_attr = 'eid'

    @property
    def workflow(self):
        # take care, may be missing in multi-sources configuration
        return self.state_of and self.state_of[0]

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.state_of:
            return self.state_of[0].rest_path(), {}
        return super(State, self).after_deletion_path()


class TrInfo(AnyEntity):
    """customized class for Transition information entities
    """
    id = 'TrInfo'
    fetch_attrs, fetch_order = fetch_config(['creation_date', 'comment'],
                                            pclass=None) # don't want modification_date
    @property
    def for_entity(self):
        return self.wf_info_for[0]

    @property
    def previous_state(self):
        return self.from_state[0]

    @property
    def new_state(self):
        return self.to_state[0]

    @property
    def transition(self):
        return self.by_transition and self.by_transition[0] or None

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.for_entity:
            return self.for_entity.rest_path(), {}
        return 'view', {}


class WorkflowableMixIn(object):
    """base mixin providing workflow helper methods for workflowable entities.
    This mixin will be automatically set on class supporting the 'in_state'
    relation (which implies supporting 'wf_info_for' as well)
    """
    __implements__ = (IWorkflowable,)

    @property
    def main_workflow(self):
        """return current workflow applied to this entity"""
        if self.custom_workflow:
            return self.custom_workflow[0]
        return self.cwetype_workflow()

    @property
    def current_workflow(self):
        """return current workflow applied to this entity"""
        return self.current_state and self.current_state.workflow or self.main_workflow

    @property
    def current_state(self):
        """return current state entity"""
        return self.in_state and self.in_state[0] or None

    @property
    def state(self):
        """return current state name"""
        try:
            return self.in_state[0].name
        except IndexError:
            self.warning('entity %s has no state', self)
            return None

    @property
    def printable_state(self):
        """return current state name translated to context's language"""
        state = self.current_state
        if state:
            return self.req._(state.name)
        return u''

    @property
    def workflow_history(self):
        """return the workflow history for this entity (eg ordered list of
        TrInfo entities)
        """
        return self.reverse_wf_info_for

    def latest_trinfo(self):
        """return the latest transition information for this entity"""
        return self.reverse_wf_info_for[-1]

    @cached
    def cwetype_workflow(self):
        """return the default workflow for entities of this type"""
        wfrset = self.req.execute('Any WF WHERE ET default_workflow WF, '
                                  'ET name %(et)s', {'et': self.id})
        if wfrset:
            return wfrset.get_entity(0, 0)
        self.warning("can't find any workflow for %s", self.id)
        return None

    def possible_transitions(self, type='normal'):
        """generates transition that MAY be fired for the given entity,
        expected to be in this state
        """
        if self.current_state is None or self.current_workflow is None:
            return
        rset = self.req.execute(
            'Any T,TT, TN WHERE S allowed_transition T, S eid %(x)s, '
            'T type TT, T type %(type)s, '
            'T name TN, T transition_of WF, WF eid %(wfeid)s',
            {'x': self.current_state.eid, 'type': type,
             'wfeid': self.current_workflow.eid}, 'x')
        for tr in rset.entities():
            if tr.may_be_fired(self.eid):
                yield tr

    def _add_trinfo(self, comment, commentformat, treid=None, tseid=None):
        kwargs = {}
        if comment is not None:
            kwargs['comment'] = comment
            if commentformat is not None:
                kwargs['comment_format'] = commentformat
        kwargs['wf_info_for'] = self
        if treid is not None:
            kwargs['by_transition'] = self.req.entity_from_eid(treid)
        if tseid is not None:
            kwargs['to_state'] = self.req.entity_from_eid(tseid)
        return self.req.create_entity('TrInfo', *args, **kwargs)

    def fire_transition(self, tr, comment=None, commentformat=None):
        """change the entity's state by firing transition of the given name in
        entity's workflow
        """
        assert self.current_workflow
        if isinstance(tr, basestring):
            _tr = self.current_workflow.transition_by_name(tr)
            assert _tr is not None, 'not a %s transition: %s' % (self.id, tr)
            tr = _tr
        return self._add_trinfo(comment, commentformat, tr.eid)

    def change_state(self, statename, comment=None, commentformat=None, tr=None):
        """change the entity's state to the given state (name or entity) in
        entity's workflow. This method should only by used by manager to fix an
        entity's state when their is no matching transition, otherwise
        fire_transition should be used.
        """
        assert self.current_workflow
        if hasattr(statename, 'eid'):
            stateeid = statename.eid
        else:
            if not isinstance(statename, basestring):
                warn('give a state name')
                state = self.current_workflow.state_by_eid(statename)
            else:
                state = self.current_workflow.state_by_name(statename)
            if state is None:
                raise WorkflowException('not a %s state: %s' % (self.id,
                                                                statename))
            stateeid = state.eid
        # XXX try to find matching transition?
        return self._add_trinfo(comment, commentformat, tr and tr.eid, stateeid)

    def subworkflow_input_trinfo(self):
        """return the TrInfo which has be recorded when this entity went into
        the current sub-workflow
        """
        if self.main_workflow.eid == self.current_workflow.eid:
            return # doesn't make sense
        subwfentries = []
        for trinfo in self.workflow_history:
            if (trinfo.transition and
                trinfo.previous_state.workflow.eid != trinfo.new_state.workflow.eid):
                # entering or leaving a subworkflow
                if (subwfentries and
                    subwfentries[-1].new_state.workflow.eid == trinfo.previous_state.workflow.eid and
                    subwfentries[-1].previous_state.workflow.eid == trinfo.new_state.workflow.eid):
                    # leave
                    del subwfentries[-1]
                else:
                    # enter
                    subwfentries.append(trinfo)
        if not subwfentries:
            return None
        return subwfentries[-1]

    def subworkflow_input_transition(self):
        """return the transition which has went through the current sub-workflow
        """
        return getattr(self.subworkflow_input_trinfo(), 'transition', None)

    def clear_all_caches(self):
        super(WorkflowableMixIn, self).clear_all_caches()
        clear_cache(self, 'cwetype_workflow')

    @deprecated('get transition from current workflow and use its may_be_fired method')
    def can_pass_transition(self, trname):
        """return the Transition instance if the current user can fire the
        transition with the given name, else None
        """
        tr = self.current_workflow and self.current_workflow.transition_by_name(trname)
        if tr and tr.may_be_fired(self.eid):
            return tr

    @property
    @deprecated('use printable_state')
    def displayable_state(self):
        return self.req._(self.state)

MI_REL_TRIGGERS[('in_state', 'subject')] = WorkflowableMixIn
