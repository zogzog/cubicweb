# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""workflow handling:

* entity types defining workflow (Workflow, State, Transition...)
* workflow history (TrInfo)
* adapter for workflowable entities (IWorkflowableAdapter)
"""
from __future__ import print_function



from six import text_type, string_types

from logilab.common.decorators import cached, clear_cache
from logilab.common.deprecation import deprecated

from cubicweb.entities import AnyEntity, fetch_config
from cubicweb.view import EntityAdapter
from cubicweb.predicates import relation_possible


try:
    from cubicweb import server
except ImportError:
    # We need to lookup DEBUG from there,
    # however a pure dbapi client may not have it.
    class server(object): pass
    server.DEBUG = False


class WorkflowException(Exception): pass

class Workflow(AnyEntity):
    __regid__ = 'Workflow'

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

    def iter_workflows(self, _done=None):
        """return an iterator on actual workflows, eg this workflow and its
        subworkflows
        """
        # infinite loop safety belt
        if _done is None:
            _done = set()
        yield self
        _done.add(self.eid)
        for tr in self._cw.execute('Any T WHERE T is WorkflowTransition, '
                                   'T transition_of WF, WF eid %(wf)s',
                                   {'wf': self.eid}).entities():
            if tr.subwf.eid in _done:
                continue
            for subwf in tr.subwf.iter_workflows(_done):
                yield subwf

    # state / transitions accessors ############################################

    def state_by_name(self, statename):
        rset = self._cw.execute('Any S, SN WHERE S name SN, S name %(n)s, '
                                'S state_of WF, WF eid %(wf)s',
                                {'n': statename, 'wf': self.eid})
        if rset:
            return rset.get_entity(0, 0)
        return None

    def state_by_eid(self, eid):
        rset = self._cw.execute('Any S, SN WHERE S name SN, S eid %(s)s, '
                                'S state_of WF, WF eid %(wf)s',
                                {'s': eid, 'wf': self.eid})
        if rset:
            return rset.get_entity(0, 0)
        return None

    def transition_by_name(self, trname):
        rset = self._cw.execute('Any T, TN WHERE T name TN, T name %(n)s, '
                                'T transition_of WF, WF eid %(wf)s',
                                {'n': text_type(trname), 'wf': self.eid})
        if rset:
            return rset.get_entity(0, 0)
        return None

    def transition_by_eid(self, eid):
        rset = self._cw.execute('Any T, TN WHERE T name TN, T eid %(t)s, '
                                'T transition_of WF, WF eid %(wf)s',
                                {'t': eid, 'wf': self.eid})
        if rset:
            return rset.get_entity(0, 0)
        return None

    # wf construction methods ##################################################

    def add_state(self, name, initial=False, **kwargs):
        """add a state to this workflow"""
        state = self._cw.create_entity('State', name=text_type(name), **kwargs)
        self._cw.execute('SET S state_of WF WHERE S eid %(s)s, WF eid %(wf)s',
                         {'s': state.eid, 'wf': self.eid})
        if initial:
            assert not self.initial, "Initial state already defined as %s" % self.initial
            self._cw.execute('SET WF initial_state S '
                             'WHERE S eid %(s)s, WF eid %(wf)s',
                             {'s': state.eid, 'wf': self.eid})
        return state

    def _add_transition(self, trtype, name, fromstates,
                        requiredgroups=(), conditions=(), **kwargs):
        tr = self._cw.create_entity(trtype, name=text_type(name), **kwargs)
        self._cw.execute('SET T transition_of WF '
                         'WHERE T eid %(t)s, WF eid %(wf)s',
                         {'t': tr.eid, 'wf': self.eid})
        assert fromstates, fromstates
        if not isinstance(fromstates, (tuple, list)):
            fromstates = (fromstates,)
        for state in fromstates:
            if hasattr(state, 'eid'):
                state = state.eid
            self._cw.execute('SET S allowed_transition T '
                             'WHERE S eid %(s)s, T eid %(t)s',
                             {'s': state, 't': tr.eid})
        tr.set_permissions(requiredgroups, conditions, reset=False)
        return tr

    def add_transition(self, name, fromstates, tostate=None,
                       requiredgroups=(), conditions=(), **kwargs):
        """add a transition to this workflow from some state(s) to another"""
        tr = self._add_transition('Transition', name, fromstates,
                                  requiredgroups, conditions, **kwargs)
        if tostate is not None:
            if hasattr(tostate, 'eid'):
                tostate = tostate.eid
            self._cw.execute('SET T destination_state S '
                             'WHERE S eid %(s)s, T eid %(t)s',
                             {'t': tr.eid, 's': tostate})
        return tr

    def add_wftransition(self, name, subworkflow, fromstates, exitpoints=(),
                         requiredgroups=(), conditions=(), **kwargs):
        """add a workflow transition to this workflow"""
        tr = self._add_transition('WorkflowTransition', name, fromstates,
                                  requiredgroups, conditions, **kwargs)
        if hasattr(subworkflow, 'eid'):
            subworkflow = subworkflow.eid
        assert self._cw.execute('SET T subworkflow WF WHERE WF eid %(wf)s,T eid %(t)s',
                                {'t': tr.eid, 'wf': subworkflow})
        for fromstate, tostate in exitpoints:
            tr.add_exit_point(fromstate, tostate)
        return tr

    def replace_state(self, todelstate, replacement):
        """migration convenience method"""
        if not hasattr(todelstate, 'eid'):
            todelstate = self.state_by_name(todelstate)
        if not hasattr(replacement, 'eid'):
            replacement = self.state_by_name(replacement)
        args = {'os': todelstate.eid, 'ns': replacement.eid}
        execute = self._cw.execute
        execute('SET X in_state NS WHERE X in_state OS, '
                'NS eid %(ns)s, OS eid %(os)s', args)
        execute('SET X from_state NS WHERE X from_state OS, '
                'OS eid %(os)s, NS eid %(ns)s', args)
        execute('SET X to_state NS WHERE X to_state OS, '
                'OS eid %(os)s, NS eid %(ns)s', args)
        todelstate.cw_delete()


class BaseTransition(AnyEntity):
    """customized class for abstract transition

    provides a specific may_be_fired method to check if the relation may be
    fired by the logged user
    """
    __regid__ = 'BaseTransition'
    fetch_attrs, cw_fetch_order = fetch_config(['name', 'type'])

    def __init__(self, *args, **kwargs):
        if self.cw_etype == 'BaseTransition':
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
        DBG = False
        if server.DEBUG & server.DBG_SEC:
            if 'transition' in server._SECURITY_CAPS:
                DBG = True
        user = self._cw.user
        # check user is at least in one of the required groups if any
        groups = frozenset(g.name for g in self.require_group)
        if groups:
            matches = user.matching_groups(groups)
            if matches:
                if DBG:
                    print('may_be_fired: %r may fire: user matches %s' % (self.name, groups))
                return matches
            if 'owners' in groups and user.owns(eid):
                if DBG:
                    print('may_be_fired: %r may fire: user is owner' % self.name)
                return True
        # check one of the rql expression conditions matches if any
        if self.condition:
            if DBG:
                print('may_be_fired: %r: %s' %
                      (self.name, [(rqlexpr.expression,
                                    rqlexpr.check_expression(self._cw, eid))
                                    for rqlexpr in self.condition]))
            for rqlexpr in self.condition:
                if rqlexpr.check_expression(self._cw, eid):
                    return True
        if self.condition or groups:
            return False
        return True

    def set_permissions(self, requiredgroups=(), conditions=(), reset=True):
        """set or add (if `reset` is False) groups and conditions for this
        transition
        """
        if reset:
            self._cw.execute('DELETE T require_group G WHERE T eid %(x)s',
                             {'x': self.eid})
            self._cw.execute('DELETE T condition R WHERE T eid %(x)s',
                             {'x': self.eid})
        for gname in requiredgroups:
            rset = self._cw.execute('SET T require_group G '
                                    'WHERE T eid %(x)s, G name %(gn)s',
                                    {'x': self.eid, 'gn': text_type(gname)})
            assert rset, '%s is not a known group' % gname
        if isinstance(conditions, string_types):
            conditions = (conditions,)
        for expr in conditions:
            if isinstance(expr, string_types):
                kwargs = {'expr': text_type(expr)}
            else:
                assert isinstance(expr, dict)
                kwargs = expr
            kwargs['x'] = self.eid
            kwargs.setdefault('mainvars', u'X')
            self._cw.execute('INSERT RQLExpression X: X exprtype "ERQLExpression", '
                             'X expression %(expr)s, X mainvars %(mainvars)s, '
                             'T condition X WHERE T eid %(x)s', kwargs)
        # XXX clear caches?


class Transition(BaseTransition):
    """customized class for Transition entities"""
    __regid__ = 'Transition'

    def dc_long_title(self):
        return '%s (%s)' % (self.name, self._cw._(self.name))

    def destination(self, entity):
        try:
            return self.destination_state[0]
        except IndexError:
            return entity.cw_adapt_to('IWorkflowable').latest_trinfo().previous_state

    def potential_destinations(self):
        try:
            yield self.destination_state[0]
        except IndexError:
            for incomingstate in self.reverse_allowed_transition:
                for tr in incomingstate.reverse_destination_state:
                    for previousstate in tr.reverse_allowed_transition:
                        yield previousstate


class WorkflowTransition(BaseTransition):
    """customized class for WorkflowTransition entities"""
    __regid__ = 'WorkflowTransition'

    @property
    def subwf(self):
        return self.subworkflow[0]

    def destination(self, entity):
        return self.subwf.initial

    def potential_destinations(self):
        yield self.subwf.initial

    def add_exit_point(self, fromstate, tostate):
        if hasattr(fromstate, 'eid'):
            fromstate = fromstate.eid
        if tostate is None:
            self._cw.execute('INSERT SubWorkflowExitPoint X: T subworkflow_exit X, '
                             'X subworkflow_state FS WHERE T eid %(t)s, FS eid %(fs)s',
                             {'t': self.eid, 'fs': fromstate})
        else:
            if hasattr(tostate, 'eid'):
                tostate = tostate.eid
            self._cw.execute('INSERT SubWorkflowExitPoint X: T subworkflow_exit X, '
                             'X subworkflow_state FS, X destination_state TS '
                             'WHERE T eid %(t)s, FS eid %(fs)s, TS eid %(ts)s',
                             {'t': self.eid, 'fs': fromstate, 'ts': tostate})

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
            return entity.cw_adapt_to('IWorkflowable').subworkflow_input_trinfo().previous_state
        return self._cw.entity_from_eid(tostateeid)

    @cached
    def exit_points(self):
        result = {}
        for ep in self.subworkflow_exit:
            result[ep.subwf_state.eid] = ep.destination and ep.destination.eid
        return result

    def cw_clear_all_caches(self):
        super(WorkflowTransition, self).cw_clear_all_caches()
        clear_cache(self, 'exit_points')


class SubWorkflowExitPoint(AnyEntity):
    """customized class for SubWorkflowExitPoint entities"""
    __regid__ = 'SubWorkflowExitPoint'

    @property
    def subwf_state(self):
        return self.subworkflow_state[0]

    @property
    def destination(self):
        return self.destination_state and self.destination_state[0] or None


class State(AnyEntity):
    """customized class for State entities"""
    __regid__ = 'State'
    fetch_attrs, cw_fetch_order = fetch_config(['name'])
    rest_attr = 'eid'

    def dc_long_title(self):
        return '%s (%s)' % (self.name, self._cw._(self.name))

    @property
    def workflow(self):
        # take care, may be missing in multi-sources configuration
        return self.state_of and self.state_of[0] or None


class TrInfo(AnyEntity):
    """customized class for Transition information entities
    """
    __regid__ = 'TrInfo'
    fetch_attrs, cw_fetch_order = fetch_config(['creation_date', 'comment'],
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



class IWorkflowableAdapter(EntityAdapter):
    """base adapter providing workflow helper methods for workflowable entities.
    """
    __regid__ = 'IWorkflowable'
    __select__ = relation_possible('in_state')

    @cached
    def cwetype_workflow(self):
        """return the default workflow for entities of this type"""
        # XXX CWEType method
        wfrset = self._cw.execute('Any WF WHERE ET default_workflow WF, '
                                  'ET name %(et)s', {'et': text_type(self.entity.cw_etype)})
        if wfrset:
            return wfrset.get_entity(0, 0)
        self.warning("can't find any workflow for %s", self.entity.cw_etype)
        return None

    @property
    def main_workflow(self):
        """return current workflow applied to this entity"""
        if self.entity.custom_workflow:
            return self.entity.custom_workflow[0]
        return self.cwetype_workflow()

    @property
    def current_workflow(self):
        """return current workflow applied to this entity"""
        return self.current_state and self.current_state.workflow or self.main_workflow

    @property
    def current_state(self):
        """return current state entity"""
        return self.entity.in_state and self.entity.in_state[0] or None

    @property
    def state(self):
        """return current state name"""
        try:
            return self.current_state.name
        except AttributeError:
            self.warning('entity %s has no state', self.entity)
            return None

    @property
    def printable_state(self):
        """return current state name translated to context's language"""
        state = self.current_state
        if state:
            return self._cw._(state.name)
        return u''

    @property
    def workflow_history(self):
        """return the workflow history for this entity (eg ordered list of
        TrInfo entities)
        """
        return self.entity.reverse_wf_info_for

    def latest_trinfo(self):
        """return the latest transition information for this entity"""
        try:
            return self.workflow_history[-1]
        except IndexError:
            return None

    def possible_transitions(self, type='normal'):
        """generates transition that MAY be fired for the given entity,
        expected to be in this state
        used only by the UI
        """
        if self.current_state is None or self.current_workflow is None:
            return
        rset = self._cw.execute(
            'Any T,TT, TN WHERE S allowed_transition T, S eid %(x)s, '
            'T type TT, T type %(type)s, '
            'T name TN, T transition_of WF, WF eid %(wfeid)s',
            {'x': self.current_state.eid, 'type': text_type(type),
             'wfeid': self.current_workflow.eid})
        for tr in rset.entities():
            if tr.may_be_fired(self.entity.eid):
                yield tr

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

    def _add_trinfo(self, comment, commentformat, treid=None, tseid=None):
        kwargs = {}
        if comment is not None:
            kwargs['comment'] = comment
            if commentformat is not None:
                kwargs['comment_format'] = commentformat
        kwargs['wf_info_for'] = self.entity
        if treid is not None:
            kwargs['by_transition'] = self._cw.entity_from_eid(treid)
        if tseid is not None:
            kwargs['to_state'] = self._cw.entity_from_eid(tseid)
        return self._cw.create_entity('TrInfo', **kwargs)

    def _get_transition(self, tr):
        assert self.current_workflow
        if isinstance(tr, string_types):
            _tr = self.current_workflow.transition_by_name(tr)
            assert _tr is not None, 'not a %s transition: %s' % (
                self.__regid__, tr)
            tr = _tr
        return tr

    def fire_transition(self, tr, comment=None, commentformat=None):
        """change the entity's state by firing given transition (name or entity)
        in entity's workflow
        """
        tr = self._get_transition(tr)
        return self._add_trinfo(comment, commentformat, tr.eid)

    def fire_transition_if_possible(self, tr, comment=None, commentformat=None):
        """change the entity's state by firing given transition (name or entity)
        in entity's workflow if this transition is possible
        """
        tr = self._get_transition(tr)
        if any(tr_ for tr_ in self.possible_transitions()
               if tr_.eid == tr.eid):
            self.fire_transition(tr, comment, commentformat)

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
            state = self.current_workflow.state_by_name(statename)
            if state is None:
                raise WorkflowException('not a %s state: %s' % (self.__regid__,
                                                                statename))
            stateeid = state.eid
        # XXX try to find matching transition?
        return self._add_trinfo(comment, commentformat, tr and tr.eid, stateeid)

    def set_initial_state(self, statename):
        """set a newly created entity's state to the given state (name or entity)
        in entity's workflow. This is useful if you don't want it to be the
        workflow's initial state.
        """
        assert self.current_workflow
        if hasattr(statename, 'eid'):
            stateeid = statename.eid
        else:
            state = self.current_workflow.state_by_name(statename)
            if state is None:
                raise WorkflowException('not a %s state: %s' % (self.__regid__,
                                                                statename))
            stateeid = state.eid
        self._cw.execute('SET X in_state S WHERE X eid %(x)s, S eid %(s)s',
                         {'x': self.entity.eid, 's': stateeid})
