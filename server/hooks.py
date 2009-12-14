"""Core hooks: check schema validity, unsure we are not deleting necessary
entities...

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from datetime import datetime

from cubicweb import UnknownProperty, ValidationError, BadConnectionId
from cubicweb.schema import RQLConstraint, RQLUniqueConstraint
from cubicweb.server.pool import Operation, LateOperation, PreCommitOperation
from cubicweb.server.hookhelper import (check_internal_entity,
                                        get_user_sessions, rproperty)
from cubicweb.server.repository import FTIndexEntityOp

# special relations that don't have to be checked for integrity, usually
# because they are handled internally by hooks (so we trust ourselves)
DONT_CHECK_RTYPES_ON_ADD = set(('owned_by', 'created_by',
                                'is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))
DONT_CHECK_RTYPES_ON_DEL = set(('is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))


def relation_deleted(session, eidfrom, rtype, eidto):
    session.transaction_data.setdefault('pendingrelations', []).append(
        (eidfrom, rtype, eidto))

def eschema_type_eid(session, etype):
    """get eid of the CWEType entity for the given yams type"""
    eschema = session.repo.schema.eschema(etype)
    # eschema.eid is None if schema has been readen from the filesystem, not
    # from the database (eg during tests)
    if eschema.eid is None:
        eschema.eid = session.unsafe_execute(
            'Any X WHERE X is CWEType, X name %(name)s',
            {'name': str(etype)})[0][0]
    return eschema.eid


# base meta-data handling ######################################################

def setctime_before_add_entity(session, entity):
    """before create a new entity -> set creation and modification date

    this is a conveniency hook, you shouldn't have to disable it
    """
    timestamp = datetime.now()
    entity.setdefault('creation_date', timestamp)
    entity.setdefault('modification_date', timestamp)
    if not session.get_shared_data('do-not-insert-cwuri'):
        entity.setdefault('cwuri', u'%seid/%s' % (session.base_url(), entity.eid))


def setmtime_before_update_entity(session, entity):
    """update an entity -> set modification date"""
    entity.setdefault('modification_date', datetime.now())


class SetCreatorOp(PreCommitOperation):

    def precommit_event(self):
        session = self.session
        if self.entity.eid in session.transaction_data.get('pendingeids', ()):
            # entity have been created and deleted in the same transaction
            return
        if not self.entity.created_by:
            session.add_relation(self.entity.eid, 'created_by', session.user.eid)


def setowner_after_add_entity(session, entity):
    """create a new entity -> set owner and creator metadata"""
    asession = session.actual_session()
    if not asession.is_internal_session:
        session.add_relation(entity.eid, 'owned_by', asession.user.eid)
        SetCreatorOp(asession, entity=entity)


def setis_after_add_entity(session, entity):
    """create a new entity -> set is relation"""
    if hasattr(entity, '_cw_recreating'):
        return
    try:
        #session.add_relation(entity.eid, 'is',
        #                     eschema_type_eid(session, entity.id))
        session.system_sql('INSERT INTO is_relation(eid_from,eid_to) VALUES (%s,%s)'
                           % (entity.eid, eschema_type_eid(session, entity.id)))
    except IndexError:
        # during schema serialization, skip
        return
    for etype in entity.e_schema.ancestors() + [entity.e_schema]:
        #session.add_relation(entity.eid, 'is_instance_of',
        #                     eschema_type_eid(session, etype))
        session.system_sql('INSERT INTO is_instance_of_relation(eid_from,eid_to) VALUES (%s,%s)'
                           % (entity.eid, eschema_type_eid(session, etype)))


def setowner_after_add_user(session, entity):
    """when a user has been created, add owned_by relation on itself"""
    session.add_relation(entity.eid, 'owned_by', entity.eid)


def fti_update_after_add_relation(session, eidfrom, rtype, eidto):
    """sync fulltext index when relevant relation is added. Reindexing the
    contained entity is enough since it will implicitly reindex the container
    entity.
    """
    ftcontainer = session.repo.schema.rschema(rtype).fulltext_container
    if ftcontainer == 'subject':
        FTIndexEntityOp(session, entity=session.entity_from_eid(eidto))
    elif ftcontainer == 'object':
        FTIndexEntityOp(session, entity=session.entity_from_eid(eidfrom))


def fti_update_after_delete_relation(session, eidfrom, rtype, eidto):
    """sync fulltext index when relevant relation is deleted. Reindexing both
    entities is necessary.
    """
    if session.repo.schema.rschema(rtype).fulltext_container:
        FTIndexEntityOp(session, entity=session.entity_from_eid(eidto))
        FTIndexEntityOp(session, entity=session.entity_from_eid(eidfrom))


class SyncOwnersOp(PreCommitOperation):

    def precommit_event(self):
        self.session.unsafe_execute('SET X owned_by U WHERE C owned_by U, C eid %(c)s,'
                                    'NOT EXISTS(X owned_by U, X eid %(x)s)',
                                    {'c': self.compositeeid, 'x': self.composedeid},
                                    ('c', 'x'))


def sync_owner_after_add_composite_relation(session, eidfrom, rtype, eidto):
    """when adding composite relation, the composed should have the same owners
    has the composite
    """
    if rtype == 'wf_info_for':
        # skip this special composite relation # XXX (syt) why?
        return
    composite = rproperty(session, rtype, eidfrom, eidto, 'composite')
    if composite == 'subject':
        SyncOwnersOp(session, compositeeid=eidfrom, composedeid=eidto)
    elif composite == 'object':
        SyncOwnersOp(session, compositeeid=eidto, composedeid=eidfrom)


def _register_metadata_hooks(hm):
    """register meta-data related hooks on the hooks manager"""
    hm.register_hook(setctime_before_add_entity, 'before_add_entity', '')
    hm.register_hook(setmtime_before_update_entity, 'before_update_entity', '')
    hm.register_hook(setowner_after_add_entity, 'after_add_entity', '')
    hm.register_hook(sync_owner_after_add_composite_relation, 'after_add_relation', '')
    hm.register_hook(fti_update_after_add_relation, 'after_add_relation', '')
    hm.register_hook(fti_update_after_delete_relation, 'after_delete_relation', '')
    if 'is' in hm.schema:
        hm.register_hook(setis_after_add_entity, 'after_add_entity', '')
    if 'CWUser' in hm.schema:
        hm.register_hook(setowner_after_add_user, 'after_add_entity', 'CWUser')


# core hooks ##################################################################

class DelayedDeleteOp(PreCommitOperation):
    """delete the object of composite relation except if the relation
    has actually been redirected to another composite
    """

    def precommit_event(self):
        session = self.session
        # don't do anything if the entity is being created or deleted
        if not (self.eid in session.transaction_data.get('pendingeids', ()) or
                self.eid in session.transaction_data.get('neweids', ())):
            etype = session.describe(self.eid)[0]
            if self.role == 'subject':
                rql = 'DELETE %s X WHERE X eid %%(x)s, NOT X %s Y'
            else: # self.role == 'object':
                rql = 'DELETE %s X WHERE X eid %%(x)s, NOT Y %s X'
            session.unsafe_execute(rql % (etype, self.rtype), {'x': self.eid}, 'x')


def handle_composite_before_del_relation(session, eidfrom, rtype, eidto):
    """delete the object of composite relation"""
    # if the relation is being delete, don't delete composite's components
    # automatically
    pendingrdefs = session.transaction_data.get('pendingrdefs', ())
    if (session.describe(eidfrom)[0], rtype, session.describe(eidto)[0]) in pendingrdefs:
        return
    composite = rproperty(session, rtype, eidfrom, eidto, 'composite')
    if composite == 'subject':
        DelayedDeleteOp(session, eid=eidto, rtype=rtype, role='object')
    elif composite == 'object':
        DelayedDeleteOp(session, eid=eidfrom, rtype=rtype, role='subject')


def before_del_group(session, eid):
    """check that we don't remove the owners group"""
    check_internal_entity(session, eid, ('owners',))


# schema validation hooks #####################################################

class CheckConstraintsOperation(LateOperation):
    """check a new relation satisfy its constraints
    """
    def precommit_event(self):
        eidfrom, rtype, eidto = self.rdef
        # first check related entities have not been deleted in the same
        # transaction
        pending = self.session.transaction_data.get('pendingeids', ())
        if eidfrom in pending:
            return
        if eidto in pending:
            return
        for constraint in self.constraints:
            try:
                constraint.repo_check(self.session, eidfrom, rtype, eidto)
            except NotImplementedError:
                self.critical('can\'t check constraint %s, not supported',
                              constraint)

    def commit_event(self):
        pass


def cstrcheck_after_add_relation(session, eidfrom, rtype, eidto):
    """check the relation satisfy its constraints

    this is delayed to a precommit time operation since other relation which
    will make constraint satisfied may be added later.
    """
    if session.is_super_session:
        return
    constraints = rproperty(session, rtype, eidfrom, eidto, 'constraints')
    if constraints:
        # XXX get only RQL[Unique]Constraints?
        CheckConstraintsOperation(session, constraints=constraints,
                                  rdef=(eidfrom, rtype, eidto))

def uniquecstrcheck_before_modification(session, entity):
    if session.is_super_session:
        return
    eschema = entity.e_schema
    for attr in entity.edited_attributes:
        val = entity[attr]
        if val is None:
            continue
        if eschema.subjrels[attr].final and \
               eschema.has_unique_values(attr):
            rql = '%s X WHERE X %s %%(val)s' % (entity.e_schema, attr)
            rset = session.unsafe_execute(rql, {'val': val})
            if rset and rset[0][0] != entity.eid:
                msg = session._('the value "%s" is already used, use another one')
                raise ValidationError(entity.eid, {attr: msg % val})


def cstrcheck_after_update_attributes(session, entity):
    if session.is_super_session:
        return
    eschema = entity.e_schema
    for attr in entity.edited_attributes:
        if eschema.subjrels[attr].final:
            constraints = [c for c in entity.e_schema.constraints(attr)
                           if isinstance(c, (RQLConstraint, RQLUniqueConstraint))]
            if constraints:
                CheckConstraintsOperation(session, rdef=(entity.eid, attr, None),
                                          constraints=constraints)


class CheckRequiredRelationOperation(LateOperation):
    """checking relation cardinality has to be done after commit in
    case the relation is being replaced
    """
    eid, rtype = None, None

    def precommit_event(self):
        # recheck pending eids
        if self.eid in self.session.transaction_data.get('pendingeids', ()):
            return
        if self.rtype in self.session.transaction_data.get('pendingrtypes', ()):
            return
        if self.session.unsafe_execute(*self._rql()).rowcount < 1:
            etype = self.session.describe(self.eid)[0]
            _ = self.session._
            msg = _('at least one relation %(rtype)s is required on %(etype)s (%(eid)s)')
            msg %= {'rtype': _(self.rtype), 'etype': _(etype), 'eid': self.eid}
            raise ValidationError(self.eid, {self.rtype: msg})

    def commit_event(self):
        pass

    def _rql(self):
        raise NotImplementedError()


class CheckSRelationOp(CheckRequiredRelationOperation):
    """check required subject relation"""
    def _rql(self):
        return 'Any O WHERE S eid %%(x)s, S %s O' % self.rtype, {'x': self.eid}, 'x'


class CheckORelationOp(CheckRequiredRelationOperation):
    """check required object relation"""
    def _rql(self):
        return 'Any S WHERE O eid %%(x)s, S %s O' % self.rtype, {'x': self.eid}, 'x'


def checkrel_if_necessary(session, opcls, rtype, eid):
    """check an equivalent operation has not already been added"""
    for op in session.pending_operations:
        if isinstance(op, opcls) and op.rtype == rtype and op.eid == eid:
            break
    else:
        opcls(session, rtype=rtype, eid=eid)


def cardinalitycheck_after_add_entity(session, entity):
    """check cardinalities are satisfied"""
    if session.is_super_session:
        return
    eid = entity.eid
    for rschema, targetschemas, x in entity.e_schema.relation_definitions():
        # skip automatically handled relations
        if rschema.type in DONT_CHECK_RTYPES_ON_ADD:
            continue
        if x == 'subject':
            subjtype = entity.e_schema
            objtype = targetschemas[0].type
            cardindex = 0
            opcls = CheckSRelationOp
        else:
            subjtype = targetschemas[0].type
            objtype = entity.e_schema
            cardindex = 1
            opcls = CheckORelationOp
        card = rschema.rproperty(subjtype, objtype, 'cardinality')
        if card[cardindex] in '1+':
            checkrel_if_necessary(session, opcls, rschema.type, eid)

def cardinalitycheck_before_del_relation(session, eidfrom, rtype, eidto):
    """check cardinalities are satisfied"""
    if session.is_super_session:
        return
    if rtype in DONT_CHECK_RTYPES_ON_DEL:
        return
    card = rproperty(session, rtype, eidfrom, eidto, 'cardinality')
    pendingrdefs = session.transaction_data.get('pendingrdefs', ())
    if (session.describe(eidfrom)[0], rtype, session.describe(eidto)[0]) in pendingrdefs:
        return
    pendingeids = session.transaction_data.get('pendingeids', ())
    if card[0] in '1+' and not eidfrom in pendingeids:
        checkrel_if_necessary(session, CheckSRelationOp, rtype, eidfrom)
    if card[1] in '1+' and not eidto in pendingeids:
        checkrel_if_necessary(session, CheckORelationOp, rtype, eidto)


def _register_core_hooks(hm):
    hm.register_hook(handle_composite_before_del_relation, 'before_delete_relation', '')
    hm.register_hook(before_del_group, 'before_delete_entity', 'CWGroup')

    #hm.register_hook(cstrcheck_before_update_entity, 'before_update_entity', '')
    hm.register_hook(cardinalitycheck_after_add_entity, 'after_add_entity', '')
    hm.register_hook(cardinalitycheck_before_del_relation, 'before_delete_relation', '')
    hm.register_hook(cstrcheck_after_add_relation, 'after_add_relation', '')
    hm.register_hook(uniquecstrcheck_before_modification, 'before_add_entity', '')
    hm.register_hook(uniquecstrcheck_before_modification, 'before_update_entity', '')
    hm.register_hook(cstrcheck_after_update_attributes, 'after_add_entity', '')
    hm.register_hook(cstrcheck_after_update_attributes, 'after_update_entity', '')

# user/groups synchronisation #################################################

class GroupOperation(Operation):
    """base class for group operation"""
    geid = None
    def __init__(self, session, *args, **kwargs):
        """override to get the group name before actual groups manipulation:

        we may temporarily loose right access during a commit event, so
        no query should be emitted while comitting
        """
        rql = 'Any N WHERE G eid %(x)s, G name N'
        result = session.execute(rql, {'x': kwargs['geid']}, 'x', build_descr=False)
        Operation.__init__(self, session, *args, **kwargs)
        self.group = result[0][0]


class DeleteGroupOp(GroupOperation):
    """synchronize user when a in_group relation has been deleted"""
    def commit_event(self):
        """the observed connections pool has been commited"""
        groups = self.cnxuser.groups
        try:
            groups.remove(self.group)
        except KeyError:
            self.error('user %s not in group %s',  self.cnxuser, self.group)
            return


def after_del_in_group(session, fromeid, rtype, toeid):
    """modify user permission, need to update users"""
    for session_ in get_user_sessions(session.repo, fromeid):
        DeleteGroupOp(session, cnxuser=session_.user, geid=toeid)


class AddGroupOp(GroupOperation):
    """synchronize user when a in_group relation has been added"""
    def commit_event(self):
        """the observed connections pool has been commited"""
        groups = self.cnxuser.groups
        if self.group in groups:
            self.warning('user %s already in group %s', self.cnxuser,
                         self.group)
            return
        groups.add(self.group)


def after_add_in_group(session, fromeid, rtype, toeid):
    """modify user permission, need to update users"""
    for session_ in get_user_sessions(session.repo, fromeid):
        AddGroupOp(session, cnxuser=session_.user, geid=toeid)


class DelUserOp(Operation):
    """synchronize user when a in_group relation has been added"""
    def __init__(self, session, cnxid):
        self.cnxid = cnxid
        Operation.__init__(self, session)

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            self.repo.close(self.cnxid)
        except BadConnectionId:
            pass # already closed


def after_del_user(session, eid):
    """modify user permission, need to update users"""
    for session_ in get_user_sessions(session.repo, eid):
        DelUserOp(session, session_.id)


def _register_usergroup_hooks(hm):
    """register user/group related hooks on the hooks manager"""
    hm.register_hook(after_del_user, 'after_delete_entity', 'CWUser')
    hm.register_hook(after_add_in_group, 'after_add_relation', 'in_group')
    hm.register_hook(after_del_in_group, 'after_delete_relation', 'in_group')


# workflow handling ###########################################################

from cubicweb.entities.wfobjs import WorkflowTransition, WorkflowException

def _change_state(session, x, oldstate, newstate):
    nocheck = session.transaction_data.setdefault('skip-security', set())
    nocheck.add((x, 'in_state', oldstate))
    nocheck.add((x, 'in_state', newstate))
    # delete previous state first in case we're using a super session
    fromsource = session.describe(x)[1]
    # don't try to remove previous state if in_state isn't stored in the system
    # source
    if fromsource == 'system' or \
       not session.repo.sources_by_uri[fromsource].support_relation('in_state'):
        session.delete_relation(x, 'in_state', oldstate)
    session.add_relation(x, 'in_state', newstate)


class FireAutotransitionOp(PreCommitOperation):
    """try to fire auto transition after state changes"""

    def precommit_event(self):
        session = self.session
        entity = self.entity
        autotrs = list(entity.possible_transitions('auto'))
        if autotrs:
            assert len(autotrs) == 1
            entity.fire_transition(autotrs[0])


def before_add_trinfo(session, entity):
    """check the transition is allowed, add missing information. Expect that:
    * wf_info_for inlined relation is set
    * by_transition or to_state (managers only) inlined relation is set
    """
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
        if deststate is None:
            msg = entity.req._("state doesn't belong to entity's current workflow")
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
                _ = session._
                msg = _("transition %(tr)s isn't allowed from %(st)s") % {'tr': _(tr.name),
                                                                          'st': _(fromstate.name),
                                                                          }
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
                    msg = entity.req._("state doesn't belong to entity's workflow")
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


def after_add_trinfo(session, entity):
    """change related entity state"""
    _change_state(session, entity['wf_info_for'],
                  entity['from_state'], entity['to_state'])
    forentity = session.entity_from_eid(entity['wf_info_for'])
    assert forentity.current_state.eid == entity['to_state'], (
        forentity.eid, forentity.current_state.name)
    if forentity.main_workflow.eid != forentity.current_workflow.eid:
        SubWorkflowExitOp(session, forentity=forentity, trinfo=entity)

class SubWorkflowExitOp(PreCommitOperation):
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


class SetInitialStateOp(PreCommitOperation):
    """make initial state be a default state"""

    def precommit_event(self):
        session = self.session
        entity = self.entity
        # if there is an initial state and the entity's state is not set,
        # use the initial state as a default state
        pendingeids = session.transaction_data.get('pendingeids', ())
        if not entity.eid in pendingeids and not entity.in_state and \
               entity.main_workflow:
            state = entity.main_workflow.initial
            if state:
                # use super session to by-pass security checks
                session.super_session.add_relation(entity.eid, 'in_state',
                                                   state.eid)


def set_initial_state_after_add(session, entity):
    SetInitialStateOp(session, entity=entity)


def before_add_in_state(session, eidfrom, rtype, eidto):
    """check state apply, in case of direct in_state change using unsafe_execute
    """
    nocheck = session.transaction_data.setdefault('skip-security', set())
    if (eidfrom, 'in_state', eidto) in nocheck:
        # state changed through TrInfo insertion, so we already know it's ok
        return
    entity = session.entity_from_eid(eidfrom)
    mainwf = entity.main_workflow
    if mainwf is None:
        msg = session._('entity has no workflow set')
        raise ValidationError(entity.eid, {None: msg})
    for wf in mainwf.iter_workflows():
        if wf.state_by_eid(eidto):
            break
    else:
        msg = session._("state doesn't belong to entity's workflow. You may "
                        "want to set a custom workflow for this entity first.")
        raise ValidationError(eidfrom, {'in_state': msg})
    if entity.current_workflow and wf.eid != entity.current_workflow.eid:
        msg = session._("state doesn't belong to entity's current workflow")
        raise ValidationError(eidfrom, {'in_state': msg})


class CheckTrExitPoint(PreCommitOperation):

    def precommit_event(self):
        tr = self.session.entity_from_eid(self.treid)
        outputs = set()
        for ep in tr.subworkflow_exit:
            if ep.subwf_state.eid in outputs:
                msg = self.session._("can't have multiple exits on the same state")
                raise ValidationError(self.treid, {'subworkflow_exit': msg})
            outputs.add(ep.subwf_state.eid)


def after_add_subworkflow_exit(session, eidfrom, rtype, eidto):
    CheckTrExitPoint(session, treid=eidfrom)


class WorkflowChangedOp(PreCommitOperation):
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


def set_custom_workflow(session, eidfrom, rtype, eidto):
    WorkflowChangedOp(session, eid=eidfrom, wfeid=eidto)


def del_custom_workflow(session, eidfrom, rtype, eidto):
    entity = session.entity_from_eid(eidfrom)
    typewf = entity.cwetype_workflow()
    if typewf is not None:
        WorkflowChangedOp(session, eid=eidfrom, wfeid=typewf.eid)


def after_del_workflow(session, eid):
    # workflow cleanup
    session.execute('DELETE State X WHERE NOT X state_of Y')
    session.execute('DELETE Transition X WHERE NOT X transition_of Y')


def _register_wf_hooks(hm):
    """register workflow related hooks on the hooks manager"""
    if 'in_state' in hm.schema:
        hm.register_hook(before_add_trinfo, 'before_add_entity', 'TrInfo')
        hm.register_hook(after_add_trinfo, 'after_add_entity', 'TrInfo')
        #hm.register_hook(relation_deleted, 'before_delete_relation', 'in_state')
        for eschema in hm.schema.entities():
            if 'in_state' in eschema.subject_relations():
                hm.register_hook(set_initial_state_after_add, 'after_add_entity',
                                 str(eschema))
        hm.register_hook(set_custom_workflow, 'after_add_relation', 'custom_workflow')
        hm.register_hook(del_custom_workflow, 'after_delete_relation', 'custom_workflow')
        hm.register_hook(after_del_workflow, 'after_delete_entity', 'Workflow')
        hm.register_hook(before_add_in_state, 'before_add_relation', 'in_state')
        hm.register_hook(after_add_subworkflow_exit, 'after_add_relation', 'subworkflow_exit')


# CWProperty hooks #############################################################


class DelCWPropertyOp(Operation):
    """a user's custom properties has been deleted"""

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            del self.epropdict[self.key]
        except KeyError:
            self.error('%s has no associated value', self.key)


class ChangeCWPropertyOp(Operation):
    """a user's custom properties has been added/changed"""

    def commit_event(self):
        """the observed connections pool has been commited"""
        self.epropdict[self.key] = self.value


class AddCWPropertyOp(Operation):
    """a user's custom properties has been added/changed"""

    def commit_event(self):
        """the observed connections pool has been commited"""
        eprop = self.eprop
        if not eprop.for_user:
            self.repo.vreg.eprop_values[eprop.pkey] = eprop.value
        # if for_user is set, update is handled by a ChangeCWPropertyOp operation


def after_add_eproperty(session, entity):
    key, value = entity.pkey, entity.value
    try:
        value = session.vreg.typed_value(key, value)
    except UnknownProperty:
        raise ValidationError(entity.eid, {'pkey': session._('unknown property key')})
    except ValueError, ex:
        raise ValidationError(entity.eid, {'value': session._(str(ex))})
    if not session.user.matching_groups('managers'):
        session.add_relation(entity.eid, 'for_user', session.user.eid)
    else:
        AddCWPropertyOp(session, eprop=entity)


def after_update_eproperty(session, entity):
    if not ('pkey' in entity.edited_attributes or
            'value' in entity.edited_attributes):
        return
    key, value = entity.pkey, entity.value
    try:
        value = session.vreg.typed_value(key, value)
    except UnknownProperty:
        return
    except ValueError, ex:
        raise ValidationError(entity.eid, {'value': session._(str(ex))})
    if entity.for_user:
        for session_ in get_user_sessions(session.repo, entity.for_user[0].eid):
            ChangeCWPropertyOp(session, epropdict=session_.user.properties,
                              key=key, value=value)
    else:
        # site wide properties
        ChangeCWPropertyOp(session, epropdict=session.vreg.eprop_values,
                          key=key, value=value)


def before_del_eproperty(session, eid):
    for eidfrom, rtype, eidto in session.transaction_data.get('pendingrelations', ()):
        if rtype == 'for_user' and eidfrom == eid:
            # if for_user was set, delete has already been handled
            break
    else:
        key = session.execute('Any K WHERE P eid %(x)s, P pkey K',
                              {'x': eid}, 'x')[0][0]
        DelCWPropertyOp(session, epropdict=session.vreg.eprop_values, key=key)


def after_add_for_user(session, fromeid, rtype, toeid):
    if not session.describe(fromeid)[0] == 'CWProperty':
        return
    key, value = session.execute('Any K,V WHERE P eid %(x)s,P pkey K,P value V',
                                 {'x': fromeid}, 'x')[0]
    if session.vreg.property_info(key)['sitewide']:
        raise ValidationError(fromeid,
                              {'for_user': session._("site-wide property can't be set for user")})
    for session_ in get_user_sessions(session.repo, toeid):
        ChangeCWPropertyOp(session, epropdict=session_.user.properties,
                          key=key, value=value)


def before_del_for_user(session, fromeid, rtype, toeid):
    key = session.execute('Any K WHERE P eid %(x)s, P pkey K',
                          {'x': fromeid}, 'x')[0][0]
    relation_deleted(session, fromeid, rtype, toeid)
    for session_ in get_user_sessions(session.repo, toeid):
        DelCWPropertyOp(session, epropdict=session_.user.properties, key=key)


def _register_eproperty_hooks(hm):
    """register workflow related hooks on the hooks manager"""
    hm.register_hook(after_add_eproperty, 'after_add_entity', 'CWProperty')
    hm.register_hook(after_update_eproperty, 'after_update_entity', 'CWProperty')
    hm.register_hook(before_del_eproperty, 'before_delete_entity', 'CWProperty')
    hm.register_hook(after_add_for_user, 'after_add_relation', 'for_user')
    hm.register_hook(before_del_for_user, 'before_delete_relation', 'for_user')
