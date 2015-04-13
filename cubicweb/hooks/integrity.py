# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from cubicweb import _

from threading import Lock

from six import text_type

from cubicweb import validation_error, neg_role
from cubicweb.schema import (META_RTYPES, WORKFLOW_RTYPES,
                             RQLConstraint, RQLUniqueConstraint)
from cubicweb.predicates import is_instance, composite_etype
from cubicweb.uilib import soup2xhtml
from cubicweb.server import hook

# special relations that don't have to be checked for integrity, usually
# because they are handled internally by hooks (so we trust ourselves)
DONT_CHECK_RTYPES_ON_ADD = META_RTYPES | WORKFLOW_RTYPES
DONT_CHECK_RTYPES_ON_DEL = META_RTYPES | WORKFLOW_RTYPES

_UNIQUE_CONSTRAINTS_LOCK = Lock()
_UNIQUE_CONSTRAINTS_HOLDER = None


def _acquire_unique_cstr_lock(cnx):
    """acquire the _UNIQUE_CONSTRAINTS_LOCK for the cnx.

    This lock used to avoid potential integrity pb when checking
    RQLUniqueConstraint in two different transactions, as explained in
    https://extranet.logilab.fr/3577926
    """
    if 'uniquecstrholder' in cnx.transaction_data:
        return
    _UNIQUE_CONSTRAINTS_LOCK.acquire()
    cnx.transaction_data['uniquecstrholder'] = True
    # register operation responsible to release the lock on commit/rollback
    _ReleaseUniqueConstraintsOperation(cnx)

def _release_unique_cstr_lock(cnx):
    if 'uniquecstrholder' in cnx.transaction_data:
        del cnx.transaction_data['uniquecstrholder']
        _UNIQUE_CONSTRAINTS_LOCK.release()

class _ReleaseUniqueConstraintsOperation(hook.Operation):
    def postcommit_event(self):
        _release_unique_cstr_lock(self.cnx)
    def rollback_event(self):
        _release_unique_cstr_lock(self.cnx)


class _CheckRequiredRelationOperation(hook.DataOperationMixIn,
                                      hook.LateOperation):
    """checking relation cardinality has to be done after commit in case the
    relation is being replaced
    """
    containercls = list
    role = key = base_rql = None

    def precommit_event(self):
        cnx = self.cnx
        pendingeids = cnx.transaction_data.get('pendingeids', ())
        pendingrtypes = cnx.transaction_data.get('pendingrtypes', ())
        for eid, rtype in self.get_data():
            # recheck pending eids / relation types
            if eid in pendingeids:
                continue
            if rtype in pendingrtypes:
                continue
            if not cnx.execute(self.base_rql % rtype, {'x': eid}):
                etype = cnx.entity_metas(eid)['type']
                msg = _('at least one relation %(rtype)s is required on '
                        '%(etype)s (%(eid)s)')
                raise validation_error(eid, {(rtype, self.role): msg},
                                       {'rtype': rtype, 'etype': etype, 'eid': eid},
                                       ['rtype', 'etype'])


class _CheckSRelationOp(_CheckRequiredRelationOperation):
    """check required subject relation"""
    role = 'subject'
    base_rql = 'Any O WHERE S eid %%(x)s, S %s O'

class _CheckORelationOp(_CheckRequiredRelationOperation):
    """check required object relation"""
    role = 'object'
    base_rql = 'Any S WHERE O eid %%(x)s, S %s O'


class IntegrityHook(hook.Hook):
    __abstract__ = True
    category = 'integrity'


class _EnsureSymmetricRelationsAdd(hook.Hook):
    """ ensure X r Y => Y r X iff r is symmetric """
    __regid__ = 'cw.add_ensure_symmetry'
    __abstract__ = True
    category = 'activeintegrity'
    events = ('after_add_relation',)
    # __select__ is set in the registration callback

    def __call__(self):
        self._cw.repo.system_source.add_relation(self._cw, self.eidto,
                                                 self.rtype, self.eidfrom)


class _EnsureSymmetricRelationsDelete(hook.Hook):
    """ ensure X r Y => Y r X iff r is symmetric """
    __regid__ = 'cw.delete_ensure_symmetry'
    __abstract__ = True
    category = 'activeintegrity'
    events = ('after_delete_relation',)
    # __select__ is set in the registration callback

    def __call__(self):
        self._cw.repo.system_source.delete_relation(self._cw, self.eidto,
                                                    self.rtype, self.eidfrom)


class CheckCardinalityHookBeforeDeleteRelation(IntegrityHook):
    """check cardinalities are satisfied"""
    __regid__ = 'checkcard_before_delete_relation'
    events = ('before_delete_relation',)

    def __call__(self):
        rtype = self.rtype
        if rtype in DONT_CHECK_RTYPES_ON_DEL:
            return
        cnx = self._cw
        eidfrom, eidto = self.eidfrom, self.eidto
        rdef = cnx.rtype_eids_rdef(rtype, eidfrom, eidto)
        if (rdef.subject, rtype, rdef.object) in cnx.transaction_data.get('pendingrdefs', ()):
            return
        card = rdef.cardinality
        if card[0] in '1+' and not cnx.deleted_in_transaction(eidfrom):
            _CheckSRelationOp.get_instance(cnx).add_data((eidfrom, rtype))
        if card[1] in '1+' and not cnx.deleted_in_transaction(eidto):
            _CheckORelationOp.get_instance(cnx).add_data((eidto, rtype))


class CheckCardinalityHookAfterAddEntity(IntegrityHook):
    """check cardinalities are satisfied"""
    __regid__ = 'checkcard_after_add_entity'
    events = ('after_add_entity',)

    def __call__(self):
        eid = self.entity.eid
        eschema = self.entity.e_schema
        for rschema, targetschemas, role in eschema.relation_definitions():
            # skip automatically handled relations
            if rschema.type in DONT_CHECK_RTYPES_ON_ADD:
                continue
            rdef = rschema.role_rdef(eschema, targetschemas[0], role)
            if rdef.role_cardinality(role) in '1+':
                if role == 'subject':
                    op = _CheckSRelationOp.get_instance(self._cw)
                else:
                    op = _CheckORelationOp.get_instance(self._cw)
                op.add_data((eid, rschema.type))


class _CheckConstraintsOp(hook.DataOperationMixIn, hook.LateOperation):
    """ check a new relation satisfy its constraints """
    containercls = list
    def precommit_event(self):
        cnx = self.cnx
        for values in self.get_data():
            eidfrom, rtype, eidto, constraints = values
            # first check related entities have not been deleted in the same
            # transaction
            if cnx.deleted_in_transaction(eidfrom):
                continue
            if cnx.deleted_in_transaction(eidto):
                continue
            for constraint in constraints:
                # XXX
                # * lock RQLConstraint as well?
                # * use a constraint id to use per constraint lock and avoid
                #   unnecessary commit serialization ?
                if isinstance(constraint, RQLUniqueConstraint):
                    _acquire_unique_cstr_lock(cnx)
                try:
                    constraint.repo_check(cnx, eidfrom, rtype, eidto)
                except NotImplementedError:
                    self.critical('can\'t check constraint %s, not supported',
                                  constraint)


class CheckConstraintHook(IntegrityHook):
    """check the relation satisfy its constraints

    this is delayed to a precommit time operation since other relation which
    will make constraint satisfied (or unsatisfied) may be added later.
    """
    __regid__ = 'checkconstraint'
    events = ('after_add_relation',)

    def __call__(self):
        # XXX get only RQL[Unique]Constraints?
        rdef = self._cw.rtype_eids_rdef(self.rtype, self.eidfrom, self.eidto)
        constraints = rdef.constraints
        if constraints:
            _CheckConstraintsOp.get_instance(self._cw).add_data(
                (self.eidfrom, self.rtype, self.eidto, constraints))


class CheckAttributeConstraintHook(IntegrityHook):
    """check the attribute relation satisfy its constraints

    this is delayed to a precommit time operation since other relation which
    will make constraint satisfied (or unsatisfied) may be added later.
    """
    __regid__ = 'checkattrconstraint'
    events = ('after_add_entity', 'after_update_entity')

    def __call__(self):
        eschema = self.entity.e_schema
        for attr in self.entity.cw_edited:
            if eschema.subjrels[attr].final:
                constraints = [c for c in eschema.rdef(attr).constraints
                               if isinstance(c, (RQLUniqueConstraint, RQLConstraint))]
                if constraints:
                    _CheckConstraintsOp.get_instance(self._cw).add_data(
                        (self.entity.eid, attr, None, constraints))


class DontRemoveOwnersGroupHook(IntegrityHook):
    """delete the composed of a composite relation when this relation is deleted
    """
    __regid__ = 'checkownersgroup'
    __select__ = IntegrityHook.__select__ & is_instance('CWGroup')
    events = ('before_delete_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        if self.event == 'before_delete_entity' and entity.name == 'owners':
            raise validation_error(entity, {None: _("can't be deleted")})
        elif self.event == 'before_update_entity' \
                 and 'name' in entity.cw_edited:
            oldname, newname = entity.cw_edited.oldnewvalue('name')
            if oldname == 'owners' and newname != oldname:
                raise validation_error(entity, {('name', 'subject'): _("can't be changed")})


class TidyHtmlFields(IntegrityHook):
    """tidy HTML in rich text strings"""
    __regid__ = 'htmltidy'
    events = ('before_add_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        metaattrs = entity.e_schema.meta_attributes()
        edited = entity.cw_edited
        for metaattr, (metadata, attr) in metaattrs.items():
            if metadata == 'format' and attr in edited:
                try:
                    value = edited[attr]
                except KeyError:
                    continue # no text to tidy
                if isinstance(value, text_type): # filter out None and Binary
                    if getattr(entity, str(metaattr)) == 'text/html':
                        edited[attr] = soup2xhtml(value, self._cw.encoding)


class StripCWUserLoginHook(IntegrityHook):
    """ensure user logins are stripped"""
    __regid__ = 'stripuserlogin'
    __select__ = IntegrityHook.__select__ & is_instance('CWUser')
    events = ('before_add_entity', 'before_update_entity',)

    def __call__(self):
        login = self.entity.cw_edited.get('login')
        if login:
            self.entity.cw_edited['login'] = login.strip()


class DeleteCompositeOrphanHook(hook.Hook):
    """Delete the composed of a composite relation when the composite is
    deleted (this is similar to the cascading ON DELETE CASCADE
    semantics of sql).
    """
    __regid__ = 'deletecomposite'
    __select__ = hook.Hook.__select__ & composite_etype()
    events = ('before_delete_entity',)
    category = 'activeintegrity'
    # give the application's before_delete_entity hooks a chance to run before we cascade
    order = 99

    def __call__(self):
        eid = self.entity.eid
        for rdef, role in self.entity.e_schema.composite_rdef_roles:
            rtype = rdef.rtype.type
            target = getattr(rdef, neg_role(role))
            expr = ('C %s X' % rtype) if role == 'subject' else ('X %s C' % rtype)
            self._cw.execute('DELETE %s X WHERE C eid %%(c)s, %s' % (target, expr),
                             {'c': eid})


def registration_callback(vreg):
    vreg.register_all(globals().values(), __name__)
    symmetric_rtypes = [rschema.type for rschema in vreg.schema.relations()
                        if rschema.symmetric]
    class EnsureSymmetricRelationsAdd(_EnsureSymmetricRelationsAdd):
        __select__ = _EnsureSymmetricRelationsAdd.__select__ & hook.match_rtype(*symmetric_rtypes)
    vreg.register(EnsureSymmetricRelationsAdd)
    class EnsureSymmetricRelationsDelete(_EnsureSymmetricRelationsDelete):
        __select__ = _EnsureSymmetricRelationsDelete.__select__ & hook.match_rtype(*symmetric_rtypes)
    vreg.register(EnsureSymmetricRelationsDelete)
