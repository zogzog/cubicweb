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
"""Core hooks: workflow related hooks"""


from cubicweb import _

from datetime import datetime


from cubicweb import RepositoryError, validation_error
from cubicweb.predicates import is_instance, adaptable
from cubicweb.server import hook


def _change_state(cnx, x, oldstate, newstate):
    nocheck = cnx.transaction_data.setdefault('skip-security', set())
    nocheck.add((x, 'in_state', oldstate))
    nocheck.add((x, 'in_state', newstate))
    # delete previous state first
    cnx.delete_relation(x, 'in_state', oldstate)
    cnx.add_relation(x, 'in_state', newstate)


# operations ###################################################################

class _SetInitialStateOp(hook.Operation):
    """make initial state be a default state"""
    eid = None # make pylint happy

    def precommit_event(self):
        cnx = self.cnx
        entity = cnx.entity_from_eid(self.eid)
        iworkflowable = entity.cw_adapt_to('IWorkflowable')
        # if there is an initial state and the entity's state is not set,
        # use the initial state as a default state
        if not (cnx.deleted_in_transaction(entity.eid) or entity.in_state) \
               and iworkflowable.current_workflow:
            state = iworkflowable.current_workflow.initial
            if state:
                cnx.add_relation(self.eid, 'in_state', state.eid)
                _FireAutotransitionOp(cnx, eid=self.eid)

class _FireAutotransitionOp(hook.Operation):
    """try to fire auto transition after state changes"""
    eid = None # make pylint happy

    def precommit_event(self):
        entity = self.cnx.entity_from_eid(self.eid)
        iworkflowable = entity.cw_adapt_to('IWorkflowable')
        autotrs = list(iworkflowable.possible_transitions('auto'))
        if autotrs:
            assert len(autotrs) == 1
            iworkflowable.fire_transition(autotrs[0])


class _WorkflowChangedOp(hook.Operation):
    """fix entity current state when changing its workflow"""
    eid = wfeid = None # make pylint happy

    def precommit_event(self):
        # notice that enforcement that new workflow apply to the entity's type is
        # done by schema rule, no need to check it here
        cnx = self.cnx
        pendingeids = cnx.transaction_data.get('pendingeids', ())
        if self.eid in pendingeids:
            return
        entity = cnx.entity_from_eid(self.eid)
        iworkflowable = entity.cw_adapt_to('IWorkflowable')
        # check custom workflow has not been rechanged to another one in the same
        # transaction
        mainwf = iworkflowable.main_workflow
        if mainwf.eid == self.wfeid:
            deststate = mainwf.initial
            if not deststate:
                msg = _('workflow has no initial state')
                raise validation_error(entity, {('custom_workflow', 'subject'): msg})
            if mainwf.state_by_eid(iworkflowable.current_state.eid):
                # nothing to do
                return
            # if there are no history, simply go to new workflow's initial state
            if not iworkflowable.workflow_history:
                if iworkflowable.current_state.eid != deststate.eid:
                    _change_state(cnx, entity.eid,
                                  iworkflowable.current_state.eid, deststate.eid)
                    _FireAutotransitionOp(cnx, eid=entity.eid)
                return
            msg = cnx._('workflow changed to "%s"')
            msg %= cnx._(mainwf.name)
            cnx.transaction_data[(entity.eid, 'customwf')] = self.wfeid
            iworkflowable.change_state(deststate, msg, u'text/plain')


class _CheckTrExitPoint(hook.Operation):
    treid = None # make pylint happy

    def precommit_event(self):
        tr = self.cnx.entity_from_eid(self.treid)
        outputs = set()
        for ep in tr.subworkflow_exit:
            if ep.subwf_state.eid in outputs:
                msg = _("can't have multiple exits on the same state")
                raise validation_error(self.treid, {('subworkflow_exit', 'subject'): msg})
            outputs.add(ep.subwf_state.eid)


class _SubWorkflowExitOp(hook.Operation):
    foreid = trinfo = None # make pylint happy

    def precommit_event(self):
        cnx = self.cnx
        forentity = cnx.entity_from_eid(self.foreid)
        iworkflowable = forentity.cw_adapt_to('IWorkflowable')
        trinfo = self.trinfo
        # we're in a subworkflow, check if we've reached an exit point
        wftr = iworkflowable.subworkflow_input_transition()
        if wftr is None:
            # inconsistency detected
            msg = _("state doesn't belong to entity's current workflow")
            raise validation_error(self.trinfo, {('to_state', 'subject'): msg})
        tostate = wftr.get_exit_point(forentity, trinfo.cw_attr_cache['to_state'])
        if tostate is not None:
            # reached an exit point
            msg = _('exiting from subworkflow %s')
            msg %= cnx._(iworkflowable.current_workflow.name)
            cnx.transaction_data[(forentity.eid, 'subwfentrytr')] = True
            iworkflowable.change_state(tostate, msg, u'text/plain', tr=wftr)


# hooks ########################################################################

class WorkflowHook(hook.Hook):
    __abstract__ = True
    category = 'metadata'


class SetInitialStateHook(WorkflowHook):
    __regid__ = 'wfsetinitial'
    __select__ = WorkflowHook.__select__ & adaptable('IWorkflowable')
    events = ('after_add_entity',)

    def __call__(self):
        _SetInitialStateOp(self._cw, eid=self.entity.eid)


class FireTransitionHook(WorkflowHook):
    """check the transition is allowed and add missing information into the
    TrInfo entity.

    Expect that:
    * wf_info_for inlined relation is set
    * by_transition or to_state (managers only) inlined relation is set

    Check for automatic transition to be fired at the end
    """
    __regid__ = 'wffiretransition'
    __select__ = WorkflowHook.__select__ & is_instance('TrInfo')
    events = ('before_add_entity',)

    def __call__(self):
        cnx = self._cw
        entity = self.entity
        # first retreive entity to which the state change apply
        try:
            foreid = entity.cw_attr_cache['wf_info_for']
        except KeyError:
            msg = _('mandatory relation')
            raise validation_error(entity, {('wf_info_for', 'subject'): msg})
        forentity = cnx.entity_from_eid(foreid)
        # see comment in the TrInfo entity definition
        entity.cw_edited['tr_count']=len(forentity.reverse_wf_info_for)
        iworkflowable = forentity.cw_adapt_to('IWorkflowable')
        # then check it has a workflow set, unless we're in the process of changing
        # entity's workflow
        if cnx.transaction_data.get((forentity.eid, 'customwf')):
            wfeid = cnx.transaction_data[(forentity.eid, 'customwf')]
            wf = cnx.entity_from_eid(wfeid)
        else:
            wf = iworkflowable.current_workflow
        if wf is None:
            msg = _('related entity has no workflow set')
            raise validation_error(entity, {None: msg})
        # then check it has a state set
        fromstate = iworkflowable.current_state
        if fromstate is None:
            msg = _('related entity has no state')
            raise validation_error(entity, {None: msg})
        # True if we are coming back from subworkflow
        swtr = cnx.transaction_data.pop((forentity.eid, 'subwfentrytr'), None)
        cowpowers = (cnx.user.is_in_group('managers')
                     or not cnx.write_security)
        # no investigate the requested state change...
        try:
            treid = entity.cw_attr_cache['by_transition']
        except KeyError:
            # no transition set, check user is a manager and destination state
            # is specified (and valid)
            if not cowpowers:
                msg = _('mandatory relation')
                raise validation_error(entity, {('by_transition', 'subject'): msg})
            deststateeid = entity.cw_attr_cache.get('to_state')
            if not deststateeid:
                msg = _('mandatory relation')
                raise validation_error(entity, {('by_transition', 'subject'): msg})
            deststate = wf.state_by_eid(deststateeid)
            if deststate is None:
                msg = _("state doesn't belong to entity's workflow")
                raise validation_error(entity, {('to_state', 'subject'): msg})
        else:
            # check transition is valid and allowed, unless we're coming back
            # from subworkflow
            tr = cnx.entity_from_eid(treid)
            if swtr is None:
                qname = ('by_transition', 'subject')
                if tr is None:
                    msg = _("transition doesn't belong to entity's workflow")
                    raise validation_error(entity, {qname: msg})
                if not tr.has_input_state(fromstate):
                    msg = _("transition %(tr)s isn't allowed from %(st)s")
                    raise validation_error(entity, {qname: msg}, {
                            'tr': tr.name, 'st': fromstate.name}, ['tr', 'st'])
                if not tr.may_be_fired(foreid):
                    msg = _("transition may not be fired")
                    raise validation_error(entity, {qname: msg})
            deststateeid = entity.cw_attr_cache.get('to_state')
            if deststateeid is not None:
                if not cowpowers and deststateeid != tr.destination(forentity).eid:
                    msg = _("transition isn't allowed")
                    raise validation_error(entity, {('by_transition', 'subject'): msg})
                if swtr is None:
                    deststate = cnx.entity_from_eid(deststateeid)
                    if not cowpowers and deststate is None:
                        msg = _("state doesn't belong to entity's workflow")
                        raise validation_error(entity, {('to_state', 'subject'): msg})
            else:
                deststateeid = tr.destination(forentity).eid
        # everything is ok, add missing information on the trinfo entity
        entity.cw_edited['from_state'] = fromstate.eid
        entity.cw_edited['to_state'] = deststateeid
        nocheck = cnx.transaction_data.setdefault('skip-security', set())
        nocheck.add((entity.eid, 'from_state', fromstate.eid))
        nocheck.add((entity.eid, 'to_state', deststateeid))
        _FireAutotransitionOp(cnx, eid=forentity.eid)


class FiredTransitionHook(WorkflowHook):
    """change related entity state and handle exit of subworkflow"""
    __regid__ = 'wffiretransition'
    __select__ = WorkflowHook.__select__ & is_instance('TrInfo')
    events = ('after_add_entity',)

    def __call__(self):
        trinfo = self.entity
        rcache = trinfo.cw_attr_cache
        _change_state(self._cw, rcache['wf_info_for'], rcache['from_state'],
                      rcache['to_state'])
        forentity = self._cw.entity_from_eid(rcache['wf_info_for'])
        iworkflowable = forentity.cw_adapt_to('IWorkflowable')
        assert iworkflowable.current_state.eid == rcache['to_state']
        if iworkflowable.main_workflow.eid != iworkflowable.current_workflow.eid:
            _SubWorkflowExitOp(self._cw, foreid=forentity.eid, trinfo=trinfo)


class CheckInStateChangeAllowed(WorkflowHook):
    """check state apply, in case of direct in_state change using unsafe execute
    """
    __regid__ = 'wfcheckinstate'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('in_state')
    events = ('before_add_relation',)
    category = 'integrity'

    def __call__(self):
        cnx = self._cw
        nocheck = cnx.transaction_data.get('skip-security', ())
        if (self.eidfrom, 'in_state', self.eidto) in nocheck:
            # state changed through TrInfo insertion, so we already know it's ok
            return
        entity = cnx.entity_from_eid(self.eidfrom)
        iworkflowable = entity.cw_adapt_to('IWorkflowable')
        mainwf = iworkflowable.main_workflow
        if mainwf is None:
            msg = _('entity has no workflow set')
            raise validation_error(entity, {None: msg})
        for wf in mainwf.iter_workflows():
            if wf.state_by_eid(self.eidto):
                break
        else:
            msg = _("state doesn't belong to entity's workflow. You may "
                    "want to set a custom workflow for this entity first.")
            raise validation_error(self.eidfrom, {('in_state', 'subject'): msg})
        if iworkflowable.current_workflow and wf.eid != iworkflowable.current_workflow.eid:
            msg = _("state doesn't belong to entity's current workflow")
            raise validation_error(self.eidfrom, {('in_state', 'subject'): msg})


class SetModificationDateOnStateChange(WorkflowHook):
    """update entity's modification date after changing its state"""
    __regid__ = 'wfsyncmdate'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('in_state')
    events = ('after_add_relation',)

    def __call__(self):
        if self._cw.added_in_transaction(self.eidfrom):
            # new entity, not needed
            return
        entity = self._cw.entity_from_eid(self.eidfrom)
        try:
            entity.cw_set(modification_date=datetime.utcnow())
        except RepositoryError as ex:
            # usually occurs if entity is coming from a read-only source
            # (eg ldap user)
            self.warning('cant change modification date for %s: %s', entity, ex)


class CheckWorkflowTransitionExitPoint(WorkflowHook):
    """check that there is no multiple exits from the same state"""
    __regid__ = 'wfcheckwftrexit'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('subworkflow_exit')
    events = ('after_add_relation',)

    def __call__(self):
        _CheckTrExitPoint(self._cw, treid=self.eidfrom)


class SetCustomWorkflow(WorkflowHook):
    __regid__ = 'wfsetcustom'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('custom_workflow')
    events = ('after_add_relation',)

    def __call__(self):
        _WorkflowChangedOp(self._cw, eid=self.eidfrom, wfeid=self.eidto)


class DelCustomWorkflow(SetCustomWorkflow):
    __regid__ = 'wfdelcustom'
    events = ('after_delete_relation',)

    def __call__(self):
        entity = self._cw.entity_from_eid(self.eidfrom)
        typewf = entity.cw_adapt_to('IWorkflowable').cwetype_workflow()
        if typewf is not None:
            _WorkflowChangedOp(self._cw, eid=self.eidfrom, wfeid=typewf.eid)
