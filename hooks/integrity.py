"""Core hooks: check for data integrity according to the instance'schema
validity

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import ValidationError
from cubicweb.schema import RQLConstraint, RQLUniqueConstraint
from cubicweb.selectors import entity_implements
from cubicweb.common.uilib import soup2xhtml
from cubicweb.server import hook

# special relations that don't have to be checked for integrity, usually
# because they are handled internally by hooks (so we trust ourselves)
DONT_CHECK_RTYPES_ON_ADD = set(('owned_by', 'created_by',
                                'is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))
DONT_CHECK_RTYPES_ON_DEL = set(('is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))


class _CheckRequiredRelationOperation(hook.LateOperation):
    """checking relation cardinality has to be done after commit in
    case the relation is being replaced
    """
    eid, rtype = None, None

    def precommit_event(self):
        # recheck pending eids
        if self.session.deleted_in_transaction(self.eid):
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


class _CheckSRelationOp(_CheckRequiredRelationOperation):
    """check required subject relation"""
    def _rql(self):
        return 'Any O WHERE S eid %%(x)s, S %s O' % self.rtype, {'x': self.eid}, 'x'


class _CheckORelationOp(_CheckRequiredRelationOperation):
    """check required object relation"""
    def _rql(self):
        return 'Any S WHERE O eid %%(x)s, S %s O' % self.rtype, {'x': self.eid}, 'x'


class IntegrityHook(hook.Hook):
    __abstract__ = True
    category = 'integrity'

class UserIntegrityHook(IntegrityHook):
    __abstract__ = True
    __select__ = IntegrityHook.__select__ & ~hook.regular_session()


class CheckCardinalityHook(UserIntegrityHook):
    """check cardinalities are satisfied"""
    __regid__ = 'checkcard'
    events = ('after_add_entity', 'before_delete_relation')

    def __call__(self):
        getattr(self, self.event)()

    def checkrel_if_necessary(self, opcls, rtype, eid):
        """check an equivalent operation has not already been added"""
        for op in self._cw.pending_operations:
            if isinstance(op, opcls) and op.rtype == rtype and op.eid == eid:
                break
        else:
            opcls(self._cw, rtype=rtype, eid=eid)

    def after_add_entity(self):
        eid = self.entity.eid
        eschema = self.entity.e_schema
        for rschema, targetschemas, role in eschema.relation_definitions():
            # skip automatically handled relations
            if rschema.type in DONT_CHECK_RTYPES_ON_ADD:
                continue
            opcls = role == 'subject' and _CheckSRelationOp or _CheckORelationOp
            rdef = rschema.role_rdef(eschema, targetschemas[0], role)
            if rdef.role_cardinality(role) in '1+':
                self.checkrel_if_necessary(opcls, rschema.type, eid)

    def before_delete_relation(self):
        rtype = self.rtype
        if rtype in DONT_CHECK_RTYPES_ON_DEL:
            return
        session = self._cw
        eidfrom, eidto = self.eidfrom, self.eidto
        card = session.schema_rproperty(rtype, eidfrom, eidto, 'cardinality')
        pendingrdefs = session.transaction_data.get('pendingrdefs', ())
        if (session.describe(eidfrom)[0], rtype, session.describe(eidto)[0]) in pendingrdefs:
            return
        if card[0] in '1+' and not session.deleted_in_transaction(eidfrom):
            self.checkrel_if_necessary(_CheckSRelationOp, rtype, eidfrom)
        if card[1] in '1+' and not session.deleted_in_transaction(eidto):
            self.checkrel_if_necessary(_CheckORelationOp, rtype, eidto)


class _CheckConstraintsOp(hook.LateOperation):
    """check a new relation satisfy its constraints
    """
    def precommit_event(self):
        eidfrom, rtype, eidto = self.rdef
        # first check related entities have not been deleted in the same
        # transaction
        if self.session.deleted_in_transaction(eidfrom):
            return
        if self.session.deleted_in_transaction(eidto):
            return
        for constraint in self.constraints:
            try:
                constraint.repo_check(self.session, eidfrom, rtype, eidto)
            except NotImplementedError:
                self.critical('can\'t check constraint %s, not supported',
                              constraint)

    def commit_event(self):
        pass


class CheckConstraintHook(UserIntegrityHook):
    """check the relation satisfy its constraints

    this is delayed to a precommit time operation since other relation which
    will make constraint satisfied (or unsatisfied) may be added later.
    """
    __regid__ = 'checkconstraint'
    events = ('after_add_relation',)

    def __call__(self):
        # XXX get only RQL[Unique]Constraints?
        constraints = self._cw.schema_rproperty(self.rtype, self.eidfrom, self.eidto,
                                                'constraints')
        if constraints:
            _CheckConstraintsOp(self._cw, constraints=constraints,
                               rdef=(self.eidfrom, self.rtype, self.eidto))

class CheckAttributeConstraintHook(UserIntegrityHook):
    """check the attribute relation satisfy its constraints

    this is delayed to a precommit time operation since other relation which
    will make constraint satisfied (or unsatisfied) may be added later.
    """
    __regid__ = 'checkattrconstraint'
    events = ('after_add_entity', 'after_update_entity')

    def __call__(self):
        schema = self._cw.vreg.schema
        entity = self.entity
        for attr in entity.edited_attributes:
            if schema.rschema(attr).final:
                constraints = [c for c in entity.e_schema.rdef(attr).constraints
                               if isinstance(c, (RQLUniqueConstraint, RQLConstraint))]
                if constraints:
                    _CheckConstraintsOp(self._cw, constraints=constraints,
                                        rdef=(entity.eid, attr, None))


class CheckUniqueHook(UserIntegrityHook):
    __regid__ = 'checkunique'
    events = ('before_add_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        eschema = entity.e_schema
        for attr in entity.edited_attributes:
            if eschema.subject_relation(attr).final and \
                   eschema.has_unique_values(attr):
                val = entity[attr]
                if val is None:
                    continue
                rql = '%s X WHERE X %s %%(val)s' % (entity.e_schema, attr)
                rset = self._cw.unsafe_execute(rql, {'val': val})
                if rset and rset[0][0] != entity.eid:
                    msg = self._cw._('the value "%s" is already used, use another one')
                    raise ValidationError(entity.eid, {attr: msg % val})


class _DelayedDeleteOp(hook.Operation):
    """delete the object of composite relation except if the relation
    has actually been redirected to another composite
    """

    def precommit_event(self):
        session = self.session
        # don't do anything if the entity is being created or deleted
        if not (session.deleted_in_transaction(self.eid) or
                session.added_in_transaction(self.eid)):
            etype = session.describe(self.eid)[0]
            session.unsafe_execute('DELETE %s X WHERE X eid %%(x)s, NOT %s'
                                   % (etype, self.relation),
                                   {'x': self.eid}, 'x')


class DeleteCompositeOrphanHook(IntegrityHook):
    """delete the composed of a composite relation when this relation is deleted
    """
    __regid__ = 'deletecomposite'
    events = ('before_delete_relation',)

    def __call__(self):
        # if the relation is being delete, don't delete composite's components
        # automatically
        pendingrdefs = self._cw.transaction_data.get('pendingrdefs', ())
        if (self._cw.describe(self.eidfrom)[0], self.rtype,
            self._cw.describe(self.eidto)[0]) in pendingrdefs:
            return
        composite = self._cw.schema_rproperty(self.rtype, self.eidfrom, self.eidto,
                                                 'composite')
        if composite == 'subject':
            _DelayedDeleteOp(self._cw, eid=self.eidto,
                             relation='Y %s X' % self.rtype)
        elif composite == 'object':
            _DelayedDeleteOp(self._cw, eid=self.eidfrom,
                             relation='X %s Y' % self.rtype)


class DontRemoveOwnersGroupHook(IntegrityHook):
    """delete the composed of a composite relation when this relation is deleted
    """
    __regid__ = 'checkownersgroup'
    __select__ = IntegrityHook.__select__ & entity_implements('CWGroup')
    events = ('before_delete_entity', 'before_update_entity')

    def __call__(self):
        if self.event == 'before_delete_entity' and self.entity.name == 'owners':
            raise ValidationError(self.entity.eid, {None: self._cw._('can\'t be deleted')})
        elif self.event == 'before_update_entity' and 'name' in self.entity.edited_attributes:
            newname = self.entity.pop('name')
            oldname = self.entity.name
            if oldname == 'owners' and newname != oldname:
                raise ValidationError(self.entity.eid, {'name': self._cw._('can\'t be changed')})
            self.entity['name'] = newname


class TidyHtmlFields(UserIntegrityHook):
    """tidy HTML in rich text strings"""
    __regid__ = 'htmltidy'
    events = ('before_add_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        metaattrs = entity.e_schema.meta_attributes()
        for metaattr, (metadata, attr) in metaattrs.iteritems():
            if metadata == 'format' and attr in entity.edited_attributes:
                try:
                    value = entity[attr]
                except KeyError:
                    continue # no text to tidy
                if isinstance(value, unicode): # filter out None and Binary
                    if getattr(entity, str(metaattr)) == 'text/html':
                        entity[attr] = soup2xhtml(value, self._cw.encoding)


class StripCWUserLoginHook(IntegrityHook):
    """ensure user logins are stripped"""
    __regid__ = 'stripuserlogin'
    __select__ = IntegrityHook.__select__ & entity_implements('CWUser')
    events = ('before_add_entity', 'before_update_entity',)

    def __call__(self):
        user = self.entity
        if 'login' in user.edited_attributes and user.login:
            user.login = user.login.strip()
