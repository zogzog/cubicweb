# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Core hooks: check for data integrity according to the instance'schema
validity

"""
__docformat__ = "restructuredtext en"

from threading import Lock

from yams.schema import role_name

from cubicweb import ValidationError
from cubicweb.schema import RQLConstraint, RQLUniqueConstraint
from cubicweb.selectors import implements
from cubicweb.uilib import soup2xhtml
from cubicweb.server import hook
from cubicweb.server.hook import set_operation

# special relations that don't have to be checked for integrity, usually
# because they are handled internally by hooks (so we trust ourselves)
DONT_CHECK_RTYPES_ON_ADD = set(('owned_by', 'created_by',
                                'is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))
DONT_CHECK_RTYPES_ON_DEL = set(('is', 'is_instance_of',
                                'wf_info_for', 'from_state', 'to_state'))

_UNIQUE_CONSTRAINTS_LOCK = Lock()
_UNIQUE_CONSTRAINTS_HOLDER = None


def _acquire_unique_cstr_lock(session):
    """acquire the _UNIQUE_CONSTRAINTS_LOCK for the session.

    This lock used to avoid potential integrity pb when checking
    RQLUniqueConstraint in two different transactions, as explained in
    http://intranet.logilab.fr/jpl/ticket/36564
    """
    if 'uniquecstrholder' in session.transaction_data:
        return
    _UNIQUE_CONSTRAINTS_LOCK.acquire()
    session.transaction_data['uniquecstrholder'] = True
    # register operation responsible to release the lock on commit/rollback
    _ReleaseUniqueConstraintsOperation(session)

def _release_unique_cstr_lock(session):
    if 'uniquecstrholder' in session.transaction_data:
        del session.transaction_data['uniquecstrholder']
        _UNIQUE_CONSTRAINTS_LOCK.release()

class _ReleaseUniqueConstraintsOperation(hook.Operation):
    def commit_event(self):
        pass
    def postcommit_event(self):
        _release_unique_cstr_lock(self.session)
    def rollback_event(self):
        _release_unique_cstr_lock(self.session)


class _CheckRequiredRelationOperation(hook.LateOperation):
    """checking relation cardinality has to be done after commit in
    case the relation is being replaced
    """
    role = key = base_rql = None

    def precommit_event(self):
        session =self.session
        pendingeids = session.transaction_data.get('pendingeids', ())
        pendingrtypes = session.transaction_data.get('pendingrtypes', ())
        # poping key is not optional: if further operation trigger new deletion
        # of relation, we'll need a new operation
        for eid, rtype in session.transaction_data.pop(self.key):
            # recheck pending eids / relation types
            if eid in pendingeids:
                continue
            if rtype in pendingrtypes:
                continue
            if not session.execute(self.base_rql % rtype, {'x': eid}):
                etype = session.describe(eid)[0]
                _ = session._
                msg = _('at least one relation %(rtype)s is required on '
                        '%(etype)s (%(eid)s)')
                msg %= {'rtype': _(rtype), 'etype': _(etype), 'eid': eid}
                raise ValidationError(eid, {role_name(rtype, self.role): msg})


class _CheckSRelationOp(_CheckRequiredRelationOperation):
    """check required subject relation"""
    role = 'subject'
    key = '_cwisrel'
    base_rql = 'Any O WHERE S eid %%(x)s, S %s O'

class _CheckORelationOp(_CheckRequiredRelationOperation):
    """check required object relation"""
    role = 'object'
    key = '_cwiorel'
    base_rql = 'Any S WHERE O eid %%(x)s, S %s O'


class IntegrityHook(hook.Hook):
    __abstract__ = True
    category = 'integrity'


class CheckCardinalityHook(IntegrityHook):
    """check cardinalities are satisfied"""
    __regid__ = 'checkcard'
    events = ('after_add_entity', 'before_delete_relation')

    def __call__(self):
        getattr(self, self.event)()

    def after_add_entity(self):
        eid = self.entity.eid
        eschema = self.entity.e_schema
        for rschema, targetschemas, role in eschema.relation_definitions():
            # skip automatically handled relations
            if rschema.type in DONT_CHECK_RTYPES_ON_ADD:
                continue
            rdef = rschema.role_rdef(eschema, targetschemas[0], role)
            if rdef.role_cardinality(role) in '1+':
                if role == 'subject':
                    set_operation(self._cw, '_cwisrel', (eid, rschema.type),
                                  _CheckSRelationOp)
                else:
                    set_operation(self._cw, '_cwiorel', (eid, rschema.type),
                                  _CheckORelationOp)

    def before_delete_relation(self):
        rtype = self.rtype
        if rtype in DONT_CHECK_RTYPES_ON_DEL:
            return
        session = self._cw
        eidfrom, eidto = self.eidfrom, self.eidto
        pendingrdefs = session.transaction_data.get('pendingrdefs', ())
        if (session.describe(eidfrom)[0], rtype, session.describe(eidto)[0]) in pendingrdefs:
            return
        card = session.schema_rproperty(rtype, eidfrom, eidto, 'cardinality')
        if card[0] in '1+' and not session.deleted_in_transaction(eidfrom):
            set_operation(self._cw, '_cwisrel', (eidfrom, rtype),
                          _CheckSRelationOp)
        if card[1] in '1+' and not session.deleted_in_transaction(eidto):
            set_operation(self._cw, '_cwiorel', (eidto, rtype),
                          _CheckORelationOp)


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
            # XXX
            # * lock RQLConstraint as well?
            # * use a constraint id to use per constraint lock and avoid
            #   unnecessary commit serialization ?
            if isinstance(constraint, RQLUniqueConstraint):
                _acquire_unique_cstr_lock(self.session)
            try:
                constraint.repo_check(self.session, eidfrom, rtype, eidto)
            except NotImplementedError:
                self.critical('can\'t check constraint %s, not supported',
                              constraint)

    def commit_event(self):
        pass


class CheckConstraintHook(IntegrityHook):
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


class CheckAttributeConstraintHook(IntegrityHook):
    """check the attribute relation satisfy its constraints

    this is delayed to a precommit time operation since other relation which
    will make constraint satisfied (or unsatisfied) may be added later.
    """
    __regid__ = 'checkattrconstraint'
    events = ('after_add_entity', 'after_update_entity')

    def __call__(self):
        eschema = self.entity.e_schema
        for attr in self.entity.edited_attributes:
            if eschema.subjrels[attr].final:
                constraints = [c for c in eschema.rdef(attr).constraints
                               if isinstance(c, (RQLUniqueConstraint, RQLConstraint))]
                if constraints:
                    _CheckConstraintsOp(self._cw, constraints=constraints,
                                        rdef=(self.entity.eid, attr, None))


class CheckUniqueHook(IntegrityHook):
    __regid__ = 'checkunique'
    events = ('before_add_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        eschema = entity.e_schema
        for attr in entity.edited_attributes:
            if eschema.subjrels[attr].final and eschema.has_unique_values(attr):
                val = entity[attr]
                if val is None:
                    continue
                rql = '%s X WHERE X %s %%(val)s' % (entity.e_schema, attr)
                rset = self._cw.execute(rql, {'val': val})
                if rset and rset[0][0] != entity.eid:
                    msg = self._cw._('the value "%s" is already used, use another one')
                    qname = role_name(attr, 'subject')
                    raise ValidationError(entity.eid, {qname: msg % val})


class DontRemoveOwnersGroupHook(IntegrityHook):
    """delete the composed of a composite relation when this relation is deleted
    """
    __regid__ = 'checkownersgroup'
    __select__ = IntegrityHook.__select__ & implements('CWGroup')
    events = ('before_delete_entity', 'before_update_entity')

    def __call__(self):
        if self.event == 'before_delete_entity' and self.entity.name == 'owners':
            msg = self._cw._('can\'t be deleted')
            raise ValidationError(self.entity.eid, {None: msg})
        elif self.event == 'before_update_entity' and \
                 'name' in self.entity.edited_attributes:
            newname = self.entity.pop('name')
            oldname = self.entity.name
            if oldname == 'owners' and newname != oldname:
                qname = role_name('name', 'subject')
                msg = self._cw._('can\'t be changed')
                raise ValidationError(self.entity.eid, {qname: msg})
            self.entity['name'] = newname


class TidyHtmlFields(IntegrityHook):
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
    __select__ = IntegrityHook.__select__ & implements('CWUser')
    events = ('before_add_entity', 'before_update_entity',)

    def __call__(self):
        user = self.entity
        if 'login' in user.edited_attributes and user.login:
            user.login = user.login.strip()


# 'active' integrity hooks: you usually don't want to deactivate them, they are
# not really integrity check, they maintain consistency on changes

class _DelayedDeleteOp(hook.Operation):
    """delete the object of composite relation except if the relation has
    actually been redirected to another composite
    """
    key = base_rql = None

    def precommit_event(self):
        session = self.session
        pendingeids = session.transaction_data.get('pendingeids', ())
        neweids = session.transaction_data.get('neweids', ())
        # poping key is not optional: if further operation trigger new deletion
        # of composite relation, we'll need a new operation
        for eid, rtype in session.transaction_data.pop(self.key):
            # don't do anything if the entity is being created or deleted
            if not (eid in pendingeids or eid in neweids):
                etype = session.describe(eid)[0]
                session.execute(self.base_rql % (etype, rtype), {'x': eid})

class _DelayedDeleteSEntityOp(_DelayedDeleteOp):
    """delete orphan subject entity of a composite relation"""
    key = '_cwiscomp'
    base_rql = 'DELETE %s X WHERE X eid %%(x)s, NOT X %s Y'

class _DelayedDeleteOEntityOp(_DelayedDeleteOp):
    """check required object relation"""
    key = '_cwiocomp'
    base_rql = 'DELETE %s X WHERE X eid %%(x)s, NOT Y %s X'


class DeleteCompositeOrphanHook(hook.Hook):
    """delete the composed of a composite relation when this relation is deleted
    """
    __regid__ = 'deletecomposite'
    events = ('before_delete_relation',)
    category = 'activeintegrity'

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
            set_operation(self._cw, '_cwiocomp', (self.eidto, self.rtype),
                          _DelayedDeleteOEntityOp)
        elif composite == 'object':
            set_operation(self._cw, '_cwiscomp', (self.eidfrom, self.rtype),
                          _DelayedDeleteSEntityOp)
