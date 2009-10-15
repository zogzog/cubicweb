"""Core hooks: workflow related hooks

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from datetime import datetime

from cubicweb import RepositoryError, ValidationError
from cubicweb.interfaces import IWorkflowable
from cubicweb.selectors import entity_implements
from cubicweb.server import hook
from cubicweb.entities.wfobjs import WorkflowTransition


def _change_state(session, x, oldstate, newstate):
    nocheck = session.transaction_data.setdefault('skip-security', set())
    nocheck.add((x, 'in_state', oldstate))
    nocheck.add((x, 'in_state', newstate))
    # delete previous state first in case we're using a super session,
    # unless in_state isn't stored in the system source
    fromsource = session.describe(x)[1]
    if fromsource == 'system' or \
           not session.repo.sources_by_uri[fromsource].support_relation('in_state'):
        session.delete_relation(x, 'in_state', oldstate)
    session.add_relation(x, 'in_state', newstate)


# operations ###################################################################

class _SetInitialStateOp(hook.Operation):
    """make initial state be a default state"""

    def precommit_event(self):
        session = self.session
        entity = self.entity
        # if there is an initial state and the entity's state is not set,
        # use the initial state as a default state
        if not (session.deleted_in_transaction(entity.eid) or entity.in_state) \
               and entity.current_workflow:
            state = entity.current_workflow.initial
            if state:
                # use super session to by-pass security checks
                session.super_session.add_relation(entity.eid, 'in_state',
                                                   state.eid)


class _FireAutotransitionOp(hook.Operation):
    """try to fire auto transition after state changes"""

    def precommit_event(self):
        session = self.session
        entity = self.entity
        autotrs = list(entity.possible_transitions('auto'))
        if autotrs:
            assert len(autotrs) == 1
            entity.fire_transition(autotrs[0])


class _WorkflowChangedOp(hook.Operation):
    """fix entity current state when changing its workflow"""

    def precommit_event(self):
        # notice that enforcement that new workflow apply to the entity's type is
        # done by schema rule, no need to check it here
        session = self.session
        pendingeids = session.transaction_data.get('pendingeids', ())
        if self.eid in pendingeids:
            return
        entity = session.entity_from_eid(self.eid)
        # check custom workflow has not been rechanged to another one in the same
        # transaction
        mainwf = entity.main_workflow
        if mainwf.eid == self.wfeid:
            deststate = mainwf.initial
            if not deststate:
                msg = session._('workflow has no initial state')
                raise ValidationError(entity.eid, {'custom_workflow': msg})
            if mainwf.state_by_eid(entity.current_state.eid):
                # nothing to do
                return
            # if there are no history, simply go to new workflow's initial state
            if not entity.workflow_history:
                if entity.current_state.eid != deststate.eid:
                    _change_state(session, entity.eid,
                                  entity.current_state.eid, deststate.eid)
                return
            msg = session._('workflow changed to "%s"')
            msg %= session._(mainwf.name)
            session.transaction_data[(entity.eid, 'customwf')] = self.wfeid
            entity.change_state(deststate, msg, u'text/plain')


class _CheckTrExitPoint(hook.Operation):

    def precommit_event(self):
        tr = self.session.entity_from_eid(self.treid)
        outputs = set()
        for ep in tr.subworkflow_exit:
            if ep.subwf_state.eid in outputs:
                msg = self.session._("can't have multiple exits on the same state")
                raise ValidationError(self.treid, {'subworkflow_exit': msg})
            outputs.add(ep.subwf_state.eid)


class _SubWorkflowExitOp(PreCommitOperation):

    def precommit_event(self):
        session = self.session
        forentity = self.forentity
        trinfo = self.trinfo
        # we're in a subworkflow, check if we've reached an exit point
        wftr = forentity.subworkflow_input_transition()
        if wftr is None:
            # inconsistency detected
            msg = session._("state doesn't belong to entity's current workflow")
            raise ValidationError(self.trinfo.eid, {'to_state': msg})
        tostate = wftr.get_exit_point(forentity, trinfo['to_state'])
        if tostate is not None:
            # reached an exit point
            msg = session._('exiting from subworkflow %s')
            msg %= session._(forentity.current_workflow.name)
            session.transaction_data[(forentity.eid, 'subwfentrytr')] = True
            # XXX iirk
            req = forentity.req
            forentity.req = session.super_session
            try:
                trinfo = forentity.change_state(tostate, msg, u'text/plain',
                                                tr=wftr)
            finally:
                forentity.req = req


# hooks ########################################################################

class WorkflowHook(hook.Hook):
    __abstract__ = True
    category = 'worfklow'


class SetInitialStateHook(WorkflowHook):
    __regid__ = 'wfsetinitial'
    __select__ = WorkflowHook.__select__ & entity_implements(IWorkflowable)
    events = ('after_add_entity',)

    def __call__(self):
        _SetInitialStateOp(self._cw, entity=self.entity)


class PrepareStateChangeHook(WorkflowHook):
    """record previous state information"""
    __regid__ = 'cwdelstate'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('in_state')
    events = ('before_delete_relation',)

    def __call__(self):
        self._cw.transaction_data.setdefault('pendingrelations', []).append(
            (self.eidfrom, self.rtype, self.eidto))


class FireTransitionHook(WorkflowHook):
    """check the transition is allowed, add missing information. Expect that:
    * wf_info_for inlined relation is set
    * by_transition or to_state (managers only) inlined relation is set
    """
    __regid__ = 'wffiretransition'
    __select__ = WorkflowHook.__select__ & entity_implements('TrInfo')
    events = ('before_add_entity',)

    def __call__(self):
        session = self._cw
        entity = self.entity
        # first retreive entity to which the state change apply
        try:
            foreid = entity['wf_info_for']
        except KeyError:
            msg = session._('mandatory relation')
            raise ValidationError(entity.eid, {'wf_info_for': msg})
        forentity = session.entity_from_eid(foreid)
        # then check it has a workflow set, unless we're in the process of changing
        # entity's workflow
        if session.transaction_data.get((forentity.eid, 'customwf')):
            wfeid = session.transaction_data[(forentity.eid, 'customwf')]
            wf = session.entity_from_eid(wfeid)
        else:
            wf = forentity.current_workflow
        if wf is None:
            msg = session._('related entity has no workflow set')
            raise ValidationError(entity.eid, {None: msg})
        # then check it has a state set
        fromstate = forentity.current_state
        if fromstate is None:
            msg = session._('related entity has no state')
            raise ValidationError(entity.eid, {None: msg})
        # True if we are coming back from subworkflow
        swtr = session.transaction_data.pop((forentity.eid, 'subwfentrytr'), None)
        cowpowers = session.is_super_session or 'managers' in session.user.groups
        # no investigate the requested state change...
        try:
            treid = entity['by_transition']
        except KeyError:
            # no transition set, check user is a manager and destination state is
            # specified (and valid)
            if not cowpowers:
                msg = session._('mandatory relation')
                raise ValidationError(entity.eid, {'by_transition': msg})
            deststateeid = entity.get('to_state')
            if not deststateeid:
                msg = session._('mandatory relation')
                raise ValidationError(entity.eid, {'by_transition': msg})
            deststate = wf.state_by_eid(deststateeid)
            if not cowpowers and deststate is None:
                msg = session._("state doesn't belong to entity's workflow")
                raise ValidationError(entity.eid, {'to_state': msg})
        else:
            # check transition is valid and allowed, unless we're coming back from
            # subworkflow
            tr = session.entity_from_eid(treid)
            if swtr is None:
                if tr is None:
                    msg = session._("transition doesn't belong to entity's workflow")
                    raise ValidationError(entity.eid, {'by_transition': msg})
                if not tr.has_input_state(fromstate):
                    msg = session._("transition isn't allowed")
                    raise ValidationError(entity.eid, {'by_transition': msg})
                if not tr.may_be_fired(foreid):
                    msg = session._("transition may not be fired")
                    raise ValidationError(entity.eid, {'by_transition': msg})
            if entity.get('to_state'):
                deststateeid = entity['to_state']
                if not cowpowers and deststateeid != tr.destination().eid:
                    msg = session._("transition isn't allowed")
                    raise ValidationError(entity.eid, {'by_transition': msg})
                if swtr is None:
                    deststate = session.entity_from_eid(deststateeid)
                    if not cowpowers and deststate is None:
                        msg = session._("state doesn't belong to entity's workflow")
                        raise ValidationError(entity.eid, {'to_state': msg})
            else:
                deststateeid = tr.destination().eid
        # everything is ok, add missing information on the trinfo entity
        entity['from_state'] = fromstate.eid
        entity['to_state'] = deststateeid
        nocheck = session.transaction_data.setdefault('skip-security', set())
        nocheck.add((entity.eid, 'from_state', fromstate.eid))
        nocheck.add((entity.eid, 'to_state', deststateeid))
        FireAutotransitionOp(session, entity=forentity)


class FiredTransitionHook(WorkflowHook):
    """change related entity state"""
    __regid__ = 'wffiretransition'
    __select__ = WorkflowHook.__select__ & entity_implements('TrInfo')
    events = ('after_add_entity',)

    def __call__(self):
        trinfo = self.entity
        _change_state(self._cw, trinfo['wf_info_for'],
                      trinfo['from_state'], trinfo['to_state'])
        forentity = self._cw.entity_from_eid(trinfo['wf_info_for'])
        assert forentity.current_state.eid == trinfo['to_state']
        if forentity.main_workflow.eid != forentity.current_workflow.eid:
            _SubWorkflowExitOp(self._cw, forentity=forentity, trinfo=trinfo)


class CheckInStateChangeAllowed(WorkflowHook):
    """check state apply, in case of direct in_state change using unsafe_execute
    """
    __regid__ = 'wfcheckinstate'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('in_state')
    events = ('before_add_relation',)

    def __call__(self):
        session = self._cw
        nocheck = session.transaction_data.setdefault('skip-security', ())
        if (self.eidfrom, 'in_state', self.eidto) in nocheck:
            # state changed through TrInfo insertion, so we already know it's ok
            return
        entity = session.entity_from_eid(self.eidfrom)
        mainwf = entity.main_workflow
        if mainwf is None:
            msg = session._('entity has no workflow set')
            raise ValidationError(entity.eid, {None: msg})
        for wf in mainwf.iter_workflows():
            if wf.state_by_eid(self.eidto):
                break
        else:
            msg = session._("state doesn't belong to entity's workflow. You may "
                            "want to set a custom workflow for this entity first.")
            raise ValidationError(self.eidfrom, {'in_state': msg})
        if entity.current_workflow and wf.eid != entity.current_workflow.eid:
            msg = session._("state doesn't belong to entity's current workflow")
            raise ValidationError(self.eidfrom, {'in_state': msg})


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
            entity.set_attributes(modification_date=datetime.now(),
                                  _cw_unsafe=True)
        except RepositoryError, ex:
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
        typewf = entity.cwetype_workflow()
        if typewf is not None:
            _WorkflowChangedOp(self._cw, eid=self.eidfrom, wfeid=typewf.eid)

