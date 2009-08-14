"""Core hooks: check for data integrity according to the instance'schema
validity

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import ValidationError
from cubicweb.selectors import entity_implements
from cubicweb.server.hook import Hook
from cubicweb.server.pool import LateOperation, PreCommitOperation
from cubicweb.server.hookhelper import rproperty

# special relations that don't have to be checked for integrity, usually
# because they are handled internally by hooks (so we trust ourselves)
DONT_CHECK_RTYPES_ON_ADD = set(('owned_by', 'created_by',
                                'is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))
DONT_CHECK_RTYPES_ON_DEL = set(('is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))


class _CheckRequiredRelationOperation(LateOperation):
    """checking relation cardinality has to be done after commit in
    case the relation is being replaced
    """
    eid, rtype = None, None

    def precommit_event(self):
        # recheck pending eids
        if self.eid in self.session.transaction_data.get('pendingeids', ()):
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


class _CheckSRelationOp(_CheckRequiredRelationOperation):
    """check required subject relation"""
    def _rql(self):
        return 'Any O WHERE S eid %%(x)s, S %s O' % self.rtype, {'x': self.eid}, 'x'


class _CheckORelationOp(_CheckRequiredRelationOperation):
    """check required object relation"""
    def _rql(self):
        return 'Any S WHERE O eid %%(x)s, S %s O' % self.rtype, {'x': self.eid}, 'x'


class CheckCardinalityHook(Hook):
    """check cardinalities are satisfied"""
    __id__ = 'checkcard'
    category = 'integrity'
    events = ('after_add_entity', 'before_delete_relation')

    def __call__(self):
        getattr(self, self.event)()

    def checkrel_if_necessary(self, opcls, rtype, eid):
        """check an equivalent operation has not already been added"""
        for op in self.cw_req.pending_operations:
            if isinstance(op, opcls) and op.rtype == rtype and op.eid == eid:
                break
        else:
            opcls(self.cw_req, rtype=rtype, eid=eid)

    def after_add_entity(self):
        eid = self.entity.eid
        eschema = self.entity.e_schema
        for rschema, targetschemas, x in eschema.relation_definitions():
            # skip automatically handled relations
            if rschema.type in DONT_CHECK_RTYPES_ON_ADD:
                continue
            if x == 'subject':
                subjtype = eschema
                objtype = targetschemas[0].type
                cardindex = 0
                opcls = _CheckSRelationOp
            else:
                subjtype = targetschemas[0].type
                objtype = eschema
                cardindex = 1
                opcls = _CheckORelationOp
            card = rschema.rproperty(subjtype, objtype, 'cardinality')
            if card[cardindex] in '1+':
                self.checkrel_if_necessary(opcls, rschema.type, eid)

    def before_delete_relation(self):
        rtype = self.rtype
        if rtype in DONT_CHECK_RTYPES_ON_DEL:
            return
        session = self.cw_req
        eidfrom, eidto = self.eidfrom, self.eidto
        card = rproperty(session, rtype, eidfrom, eidto, 'cardinality')
        pendingrdefs = session.transaction_data.get('pendingrdefs', ())
        if (session.describe(eidfrom)[0], rtype, session.describe(eidto)[0]) in pendingrdefs:
            return
        pendingeids = session.transaction_data.get('pendingeids', ())
        if card[0] in '1+' and not eidfrom in pendingeids:
            self.checkrel_if_necessary(_CheckSRelationOp, rtype, eidfrom)
        if card[1] in '1+' and not eidto in pendingeids:
            self.checkrel_if_necessary(_CheckORelationOp, rtype, eidto)


class _CheckConstraintsOp(LateOperation):
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


class CheckConstraintHook(Hook):
    """check the relation satisfy its constraints

    this is delayed to a precommit time operation since other relation which
    will make constraint satisfied may be added later.
    """
    __id__ = 'checkconstraint'
    category = 'integrity'
    events = ('after_add_relation',)
    def __call__(self):
        constraints = rproperty(self.cw_req, self.rtype, self.eidfrom, self.eidto,
                                'constraints')
        if constraints:
            _CheckConstraintsOp(self.cw_req, constraints=constraints,
                               rdef=(self.eidfrom, self.rtype, self.eidto))

class CheckUniqueHook(Hook):
    __id__ = 'checkunique'
    category = 'integrity'
    events = ('before_add_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        eschema = entity.e_schema
        for attr in entity.edited_attributes:
            val = entity[attr]
            if val is None:
                continue
            if eschema.subject_relation(attr).is_final() and \
                   eschema.has_unique_values(attr):
                rql = '%s X WHERE X %s %%(val)s' % (entity.e_schema, attr)
                rset = self.cw_req.unsafe_execute(rql, {'val': val})
                if rset and rset[0][0] != entity.eid:
                    msg = self.cw_req._('the value "%s" is already used, use another one')
                    raise ValidationError(entity.eid, {attr: msg % val})


class _DelayedDeleteOp(PreCommitOperation):
    """delete the object of composite relation except if the relation
    has actually been redirected to another composite
    """

    def precommit_event(self):
        session = self.session
        # don't do anything if the entity is being created or deleted
        if not (self.eid in session.transaction_data.get('pendingeids', ()) or
                self.eid in session.transaction_data.get('neweids', ())):
            etype = session.describe(self.eid)[0]
            session.unsafe_execute('DELETE %s X WHERE X eid %%(x)s, NOT %s'
                                   % (etype, self.relation),
                                   {'x': self.eid}, 'x')


class DeleteCompositeOrphanHook(Hook):
    """delete the composed of a composite relation when this relation is deleted
    """
    __id__ = 'deletecomposite'
    category = 'integrity'
    events = ('before_delete_relation',)
    def __call__(self):
        composite = rproperty(self.cw_req, self.rtype, self.eidfrom, self.eidto,
                              'composite')
        if composite == 'subject':
            _DelayedDeleteOp(self.cw_req, eid=self.eidto,
                             relation='Y %s X' % self.rtype)
        elif composite == 'object':
            _DelayedDeleteOp(self.cw_req, eid=self.eidfrom,
                             relation='X %s Y' % self.rtype)


class DontRemoveOwnersGroupHook(Hook):
    """delete the composed of a composite relation when this relation is deleted
    """
    __id__ = 'checkownersgroup'
    __select__ = Hook.__select__ & entity_implements('CWGroup')
    category = 'integrity'
    events = ('before_delete_entity', 'before_update_entity')

    def __call__(self):
        if self.event == 'before_delete_entity' and self.entity.name == 'owners':
            raise ValidationError(self.entity.eid, {None: self.cw_req._('can\'t be deleted')})
        elif self.event == 'before_update_entity' and 'name' in self.entity.edited_attribute:
            newname = self.entity.pop('name')
            oldname = self.entity.name
            if oldname == 'owners' and newname != oldname:
                raise ValidationError(self.entity.eid, {'name': self.cw_req._('can\'t be changed')})
            self.entity['name'] = newname


