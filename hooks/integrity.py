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
from cubicweb.schema import (META_RTYPES, WORKFLOW_RTYPES,
                             RQLConstraint, RQLUniqueConstraint)
from cubicweb.selectors import is_instance
from cubicweb.uilib import soup2xhtml
from cubicweb.server import hook

# special relations that don't have to be checked for integrity, usually
# because they are handled internally by hooks (so we trust ourselves)
DONT_CHECK_RTYPES_ON_ADD = META_RTYPES | WORKFLOW_RTYPES
DONT_CHECK_RTYPES_ON_DEL = META_RTYPES | WORKFLOW_RTYPES

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
    def postcommit_event(self):
        _release_unique_cstr_lock(self.session)
    def rollback_event(self):
        _release_unique_cstr_lock(self.session)


class _CheckRequiredRelationOperation(hook.DataOperationMixIn,
                                      hook.LateOperation):
    """checking relation cardinality has to be done after commit in case the
    relation is being replaced
    """
    containercls = list
    role = key = base_rql = None

    def precommit_event(self):
        session = self.session
        pendingeids = session.transaction_data.get('pendingeids', ())
        pendingrtypes = session.transaction_data.get('pendingrtypes', ())
        # poping key is not optional: if further operation trigger new deletion
        # of relation, we'll need a new operation
        for eid, rtype in self.get_data():
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
    base_rql = 'Any O WHERE S eid %%(x)s, S %s O'

class _CheckORelationOp(_CheckRequiredRelationOperation):
    """check required object relation"""
    role = 'object'
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
                    op = _CheckSRelationOp.get_instance(self._cw)
                else:
                    op = _CheckORelationOp.get_instance(self._cw)
                op.add_data((eid, rschema.type))

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
            _CheckSRelationOp.get_instance(self._cw).add_data((eidfrom, rtype))
        if card[1] in '1+' and not session.deleted_in_transaction(eidto):
            _CheckORelationOp.get_instance(self._cw).add_data((eidto, rtype))


class _CheckConstraintsOp(hook.DataOperationMixIn, hook.LateOperation):
    """ check a new relation satisfy its constraints """
    containercls = list
    def precommit_event(self):
        session = self.session
        for values in self.get_data():
            eidfrom, rtype, eidto, constraints = values
            # first check related entities have not been deleted in the same
            # transaction
            if session.deleted_in_transaction(eidfrom):
                return
            if session.deleted_in_transaction(eidto):
                return
            for constraint in constraints:
                # XXX
                # * lock RQLConstraint as well?
                # * use a constraint id to use per constraint lock and avoid
                #   unnecessary commit serialization ?
                if isinstance(constraint, RQLUniqueConstraint):
                    _acquire_unique_cstr_lock(session)
                try:
                    constraint.repo_check(session, eidfrom, rtype, eidto)
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
        constraints = self._cw.schema_rproperty(self.rtype, self.eidfrom, self.eidto,
                                                'constraints')
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


class CheckUniqueHook(IntegrityHook):
    __regid__ = 'checkunique'
    events = ('before_add_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        eschema = entity.e_schema
        for attr, val in entity.cw_edited.iteritems():
            if eschema.subjrels[attr].final and eschema.has_unique_values(attr):
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
    __select__ = IntegrityHook.__select__ & is_instance('CWGroup')
    events = ('before_delete_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        if self.event == 'before_delete_entity' and entity.name == 'owners':
            msg = self._cw._('can\'t be deleted')
            raise ValidationError(entity.eid, {None: msg})
        elif self.event == 'before_update_entity' \
                 and 'name' in entity.cw_edited:
            oldname, newname = entity.cw_edited.oldnewvalue('name')
            if oldname == 'owners' and newname != oldname:
                qname = role_name('name', 'subject')
                msg = self._cw._('can\'t be changed')
                raise ValidationError(entity.eid, {qname: msg})


class TidyHtmlFields(IntegrityHook):
    """tidy HTML in rich text strings"""
    __regid__ = 'htmltidy'
    events = ('before_add_entity', 'before_update_entity')

    def __call__(self):
        entity = self.entity
        metaattrs = entity.e_schema.meta_attributes()
        edited = entity.cw_edited
        for metaattr, (metadata, attr) in metaattrs.iteritems():
            if metadata == 'format' and attr in edited:
                try:
                    value = edited[attr]
                except KeyError:
                    continue # no text to tidy
                if isinstance(value, unicode): # filter out None and Binary
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


# 'active' integrity hooks: you usually don't want to deactivate them, they are
# not really integrity check, they maintain consistency on changes

class _DelayedDeleteOp(hook.DataOperationMixIn, hook.Operation):
    """delete the object of composite relation except if the relation has
    actually been redirected to another composite
    """
    base_rql = None

    def precommit_event(self):
        session = self.session
        pendingeids = session.transaction_data.get('pendingeids', ())
        neweids = session.transaction_data.get('neweids', ())
        # poping key is not optional: if further operation trigger new deletion
        # of composite relation, we'll need a new operation
        for eid, rtype in self.get_data():
            # don't do anything if the entity is being created or deleted
            if not (eid in pendingeids or eid in neweids):
                etype = session.describe(eid)[0]
                session.execute(self.base_rql % (etype, rtype), {'x': eid})

class _DelayedDeleteSEntityOp(_DelayedDeleteOp):
    """delete orphan subject entity of a composite relation"""
    base_rql = 'DELETE %s X WHERE X eid %%(x)s, NOT X %s Y'

class _DelayedDeleteOEntityOp(_DelayedDeleteOp):
    """check required object relation"""
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
            _DelayedDeleteOEntityOp.get_instance(self._cw).add_data(
                (self.eidto, self.rtype))
        elif composite == 'object':
            _DelayedDeleteSEntityOp.get_instance(self._cw).add_data(
                (self.eidfrom, self.rtype))
