"""Core hooks: check schema validity, unsure we are not deleting necessary
entities...

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from datetime import datetime

from cubicweb import UnknownProperty, ValidationError, BadConnectionId

from cubicweb.server.pool import Operation, LateOperation, PreCommitOperation
from cubicweb.server.hookhelper import (check_internal_entity, previous_state,
                                     get_user_sessions, rproperty)
from cubicweb.server.repository import FTIndexEntityOp

def relation_deleted(session, eidfrom, rtype, eidto):
    session.add_query_data('pendingrelations', (eidfrom, rtype, eidto))
    

# base meta-data handling #####################################################

def setctime_before_add_entity(session, entity):
    """before create a new entity -> set creation and modification date
 
    this is a conveniency hook, you shouldn't have to disable it
    """
    if not 'creation_date' in entity:
        entity['creation_date'] = datetime.now()
    if not 'modification_date' in entity:
        entity['modification_date'] = datetime.now()

def setmtime_before_update_entity(session, entity):
    """update an entity -> set modification date"""
    if not 'modification_date' in entity:
        entity['modification_date'] = datetime.now()
        
class SetCreatorOp(PreCommitOperation):
        
    def precommit_event(self):
        if self.eid in self.session.query_data('pendingeids', ()):
            # entity have been created and deleted in the same transaction
            return
        ueid = self.session.user.eid
        execute = self.session.unsafe_execute
        if not execute('Any X WHERE X created_by U, X eid %(x)s',
                       {'x': self.eid}, 'x'): 
            execute('SET X created_by U WHERE X eid %(x)s, U eid %(u)s',
                    {'x': self.eid, 'u': ueid}, 'x')

def setowner_after_add_entity(session, entity):
    """create a new entity -> set owner and creator metadata"""
    asession = session.actual_session()
    if not asession.is_internal_session:
        session.unsafe_execute('SET X owned_by U WHERE X eid %(x)s, U eid %(u)s',
                               {'x': entity.eid, 'u': asession.user.eid}, 'x')
        SetCreatorOp(asession, eid=entity.eid)

def setis_after_add_entity(session, entity):
    """create a new entity -> set is relation"""
    session.unsafe_execute('SET X is E WHERE X eid %(x)s, E name %(name)s',
                           {'x': entity.eid, 'name': entity.id}, 'x')
    # XXX < 2.50 bw compat
    if not session.get_shared_data('do-not-insert-is_instance_of'):
        basetypes = entity.e_schema.ancestors() + [entity.e_schema]
        session.unsafe_execute('SET X is_instance_of E WHERE X eid %%(x)s, E name IN (%s)' %
                               ','.join("'%s'" % str(etype) for etype in basetypes),
                               {'x': entity.eid}, 'x')

def setowner_after_add_user(session, entity):
    """when a user has been created, add owned_by relation on itself"""
    session.unsafe_execute('SET X owned_by X WHERE X eid %(x)s',
                           {'x': entity.eid}, 'x')

def fti_update_after_add_relation(session, eidfrom, rtype, eidto):
    """sync fulltext index when relevant relation is added. Reindexing the
    contained entity is enough since it will implicitly reindex the container
    entity.
    """
    ftcontainer = session.repo.schema.rschema(rtype).fulltext_container
    if ftcontainer == 'subject':
        FTIndexEntityOp(session, entity=session.entity(eidto))
    elif ftcontainer == 'object':
        FTIndexEntityOp(session, entity=session.entity(eidfrom))
def fti_update_after_delete_relation(session, eidfrom, rtype, eidto):
    """sync fulltext index when relevant relation is deleted. Reindexing both
    entities is necessary.
    """
    if session.repo.schema.rschema(rtype).fulltext_container:
        FTIndexEntityOp(session, entity=session.entity(eidto))
        FTIndexEntityOp(session, entity=session.entity(eidfrom))
    
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
        # skip this special composite relation
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
    if 'EUser' in hm.schema:
        hm.register_hook(setowner_after_add_user, 'after_add_entity', 'EUser')
            
# core hooks ##################################################################
    
class DelayedDeleteOp(PreCommitOperation):
    """delete the object of composite relation except if the relation
    has actually been redirected to another composite
    """
        
    def precommit_event(self):
        session = self.session
        if not self.eid in session.query_data('pendingeids', ()):
            etype = session.describe(self.eid)[0]
            session.unsafe_execute('DELETE %s X WHERE X eid %%(x)s, NOT %s'
                                   % (etype, self.relation),
                                   {'x': self.eid}, 'x')
    
def handle_composite_before_del_relation(session, eidfrom, rtype, eidto):
    """delete the object of composite relation"""
    composite = rproperty(session, rtype, eidfrom, eidto, 'composite')
    if composite == 'subject':
        DelayedDeleteOp(session, eid=eidto, relation='Y %s X' % rtype)
    elif composite == 'object':
        DelayedDeleteOp(session, eid=eidfrom, relation='X %s Y' % rtype)

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
        pending = self.session.query_data('pendingeids', ())
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
    constraints = rproperty(session, rtype, eidfrom, eidto, 'constraints')
    if constraints:
        CheckConstraintsOperation(session, constraints=constraints,
                                  rdef=(eidfrom, rtype, eidto))

def uniquecstrcheck_before_modification(session, entity):
    eschema = entity.e_schema
    for attr, val in entity.items():
        if val is None:
            continue
        if eschema.subject_relation(attr).is_final() and \
               eschema.has_unique_values(attr):
            rql = '%s X WHERE X %s %%(val)s' % (entity.e_schema, attr)
            rset = session.unsafe_execute(rql, {'val': val})
            if rset and rset[0][0] != entity.eid:
                msg = session._('the value "%s" is already used, use another one')
                raise ValidationError(entity.eid, {attr: msg % val})





class CheckRequiredRelationOperation(LateOperation):
    """checking relation cardinality has to be done after commit in
    case the relation is being replaced
    """
    eid, rtype = None, None
    
    def precommit_event(self):
        # recheck pending eids
        if self.eid in self.session.query_data('pendingeids', ()):
            return
        if self.session.unsafe_execute(*self._rql()).rowcount < 1:
            etype = self.session.describe(self.eid)[0]
            msg = self.session._('at least one relation %(rtype)s is required on %(etype)s (%(eid)s)')
            raise ValidationError(self.eid, {self.rtype: msg % {'rtype': self.rtype,
                                                                'etype': etype,
                                                                'eid': self.eid}})
    
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
    eid = entity.eid
    for rschema, targetschemas, x in entity.e_schema.relation_definitions():
        # skip automatically handled relations
        if rschema.type in ('owned_by', 'created_by', 'is', 'is_instance_of'):
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
    card = rproperty(session, rtype, eidfrom, eidto, 'cardinality')
    pendingeids = session.query_data('pendingeids', ())
    if card[0] in '1+' and not eidfrom in pendingeids:
        checkrel_if_necessary(session, CheckSRelationOp, rtype, eidfrom)
    if card[1] in '1+' and not eidto in pendingeids:
        checkrel_if_necessary(session, CheckORelationOp, rtype, eidto)


def _register_core_hooks(hm):
    hm.register_hook(handle_composite_before_del_relation, 'before_delete_relation', '')
    hm.register_hook(before_del_group, 'before_delete_entity', 'EGroup')
    
    #hm.register_hook(cstrcheck_before_update_entity, 'before_update_entity', '')
    hm.register_hook(cardinalitycheck_after_add_entity, 'after_add_entity', '')
    hm.register_hook(cardinalitycheck_before_del_relation, 'before_delete_relation', '')
    hm.register_hook(cstrcheck_after_add_relation, 'after_add_relation', '')
    hm.register_hook(uniquecstrcheck_before_modification, 'before_add_entity', '')
    hm.register_hook(uniquecstrcheck_before_modification, 'before_update_entity', '')


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
    hm.register_hook(after_del_user, 'after_delete_entity', 'EUser')
    hm.register_hook(after_add_in_group, 'after_add_relation', 'in_group')
    hm.register_hook(after_del_in_group, 'after_delete_relation', 'in_group')


# workflow handling ###########################################################

def before_add_in_state(session, fromeid, rtype, toeid):
    """check the transition is allowed and record transition information
    """
    assert rtype == 'in_state'
    state = previous_state(session, fromeid)
    etype = session.describe(fromeid)[0]
    if not (session.is_super_session or 'managers' in session.user.groups):
        if not state is None:
            entity = session.entity(fromeid)
            # we should find at least one transition going to this state
            try:
                iter(state.transitions(entity, toeid)).next()
            except StopIteration:
                msg = session._('transition is not allowed')
                raise ValidationError(fromeid, {'in_state': msg})
        else:
            # not a transition
            # check state is initial state if the workflow defines one
            isrset = session.unsafe_execute('Any S WHERE ET initial_state S, ET name %(etype)s',
                                            {'etype': etype})
            if isrset and not toeid == isrset[0][0]:
                msg = session._('not the initial state for this entity')
                raise ValidationError(fromeid, {'in_state': msg})
    eschema = session.repo.schema[etype]
    if not 'wf_info_for' in eschema.object_relations():
        # workflow history not activated for this entity type
        return
    rql = 'INSERT TrInfo T: T wf_info_for E, T to_state DS, T comment %(comment)s'
    args = {'comment': session.get_shared_data('trcomment', None, pop=True),
            'e': fromeid, 'ds': toeid}
    cformat = session.get_shared_data('trcommentformat', None, pop=True)
    if cformat is not None:
        args['comment_format'] = cformat
        rql += ', T comment_format %(comment_format)s'
    restriction = ['DS eid %(ds)s, E eid %(e)s']
    if not state is None: # not a transition
        rql += ', T from_state FS'
        restriction.append('FS eid %(fs)s')
        args['fs'] = state.eid
    rql = '%s WHERE %s' % (rql, ', '.join(restriction))
    session.unsafe_execute(rql, args, 'e')


class SetInitialStateOp(PreCommitOperation):
    """make initial state be a default state"""

    def precommit_event(self):
        session = self.session
        entity = self.entity
        rset = session.execute('Any S WHERE ET initial_state S, ET name %(name)s',
                               {'name': str(entity.e_schema)})
        # if there is an initial state and the entity's state is not set,
        # use the initial state as a default state
        pendingeids = session.query_data('pendingeids', ())
        if rset and not entity.eid in pendingeids and not entity.in_state:
            session.unsafe_execute('SET X in_state S WHERE X eid %(x)s, S eid %(s)s',
                                   {'x' : entity.eid, 's' : rset[0][0]}, 'x')


def set_initial_state_after_add(session, entity):
    SetInitialStateOp(session, entity=entity)
    
def _register_wf_hooks(hm):
    """register workflow related hooks on the hooks manager"""
    if 'in_state' in hm.schema:
        hm.register_hook(before_add_in_state, 'before_add_relation', 'in_state')
        hm.register_hook(relation_deleted, 'before_delete_relation', 'in_state')
        for eschema in hm.schema.entities():
            if 'in_state' in eschema.subject_relations():
                hm.register_hook(set_initial_state_after_add, 'after_add_entity',
                                 str(eschema))


# EProperty hooks #############################################################


class DelEPropertyOp(Operation):
    """a user's custom properties has been deleted"""
    
    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            del self.epropdict[self.key]
        except KeyError:
            self.error('%s has no associated value', self.key)

class ChangeEPropertyOp(Operation):
    """a user's custom properties has been added/changed"""
        
    def commit_event(self):
        """the observed connections pool has been commited"""
        self.epropdict[self.key] = self.value

class AddEPropertyOp(Operation):
    """a user's custom properties has been added/changed"""
        
    def commit_event(self):
        """the observed connections pool has been commited"""
        eprop = self.eprop
        if not eprop.for_user:
            self.repo.vreg.eprop_values[eprop.pkey] = eprop.value
        # if for_user is set, update is handled by a ChangeEPropertyOp operation

def after_add_eproperty(session, entity):
    key, value = entity.pkey, entity.value
    try:
        value = session.vreg.typed_value(key, value)
    except UnknownProperty:
        raise ValidationError(entity.eid, {'pkey': session._('unknown property key')})
    except ValueError, ex:
        raise ValidationError(entity.eid, {'value': session._(str(ex))})
    if not session.user.matching_groups('managers'):
        session.unsafe_execute('SET P for_user U WHERE P eid %(x)s,U eid %(u)s',
                               {'x': entity.eid, 'u': session.user.eid}, 'x')
    else:
        AddEPropertyOp(session, eprop=entity)
        
def after_update_eproperty(session, entity):
    key, value = entity.pkey, entity.value
    try:
        value = session.vreg.typed_value(key, value)
    except UnknownProperty:
        return
    except ValueError, ex:
        raise ValidationError(entity.eid, {'value': session._(str(ex))})
    if entity.for_user:
        for session_ in get_user_sessions(session.repo, entity.for_user[0].eid):
            ChangeEPropertyOp(session, epropdict=session_.user.properties,
                              key=key, value=value)
    else:
        # site wide properties
        ChangeEPropertyOp(session, epropdict=session.vreg.eprop_values,
                          key=key, value=value)
        
def before_del_eproperty(session, eid):
    for eidfrom, rtype, eidto in session.query_data('pendingrelations', ()):
        if rtype == 'for_user' and eidfrom == eid:
            # if for_user was set, delete has already been handled
            break
    else:
        key = session.execute('Any K WHERE P eid %(x)s, P pkey K',
                              {'x': eid}, 'x')[0][0]
        DelEPropertyOp(session, epropdict=session.vreg.eprop_values, key=key)

def after_add_for_user(session, fromeid, rtype, toeid):
    if not session.describe(fromeid)[0] == 'EProperty':
        return
    key, value = session.execute('Any K,V WHERE P eid %(x)s,P pkey K,P value V',
                                 {'x': fromeid}, 'x')[0]
    if session.vreg.property_info(key)['sitewide']:
        raise ValidationError(fromeid,
                              {'for_user': session._("site-wide property can't be set for user")})
    for session_ in get_user_sessions(session.repo, toeid):
        ChangeEPropertyOp(session, epropdict=session_.user.properties,
                          key=key, value=value)
        
def before_del_for_user(session, fromeid, rtype, toeid):
    key = session.execute('Any K WHERE P eid %(x)s, P pkey K',
                          {'x': fromeid}, 'x')[0][0]
    relation_deleted(session, fromeid, rtype, toeid)
    for session_ in get_user_sessions(session.repo, toeid):
        DelEPropertyOp(session, epropdict=session_.user.properties, key=key)

def _register_eproperty_hooks(hm):
    """register workflow related hooks on the hooks manager"""
    hm.register_hook(after_add_eproperty, 'after_add_entity', 'EProperty')
    hm.register_hook(after_update_eproperty, 'after_update_entity', 'EProperty')
    hm.register_hook(before_del_eproperty, 'before_delete_entity', 'EProperty')
    hm.register_hook(after_add_for_user, 'after_add_relation', 'for_user')
    hm.register_hook(before_del_for_user, 'before_delete_relation', 'for_user')
