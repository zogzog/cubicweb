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
"""Security hooks: check permissions to add/delete/update entities according to
the user connected to a session
"""

__docformat__ = "restructuredtext en"

from cubicweb import Unauthorized
from cubicweb.selectors import objectify_selector, lltrace
from cubicweb.server import BEFORE_ADD_RELATIONS, ON_COMMIT_ADD_RELATIONS, hook


def check_entity_attributes(session, entity, editedattrs=None, creation=False):
    eid = entity.eid
    eschema = entity.e_schema
    # ._cw_skip_security_attributes is there to bypass security for attributes
    # set by hooks by modifying the entity's dictionnary
    dontcheck = entity._cw_skip_security_attributes
    if editedattrs is None:
        try:
            editedattrs = entity.edited_attributes
        except AttributeError:
            editedattrs = entity # XXX unexpected
    for attr in editedattrs:
        if attr in dontcheck:
            continue
        rdef = eschema.rdef(attr)
        if rdef.final: # non final relation are checked by other hooks
            # add/delete should be equivalent (XXX: unify them into 'update' ?)
            if creation and not rdef.permissions.get('update'):
                continue
            rdef.check_perm(session, 'update', eid=eid)
    # don't update dontcheck until everything went fine: see usage in
    # after_update_entity, where if we got an Unauthorized at hook time, we will
    # retry and commit time
    dontcheck |= frozenset(editedattrs)


class _CheckEntityPermissionOp(hook.LateOperation):
    def precommit_event(self):
        #print 'CheckEntityPermissionOp', self.session.user, self.entity, self.action
        session = self.session
        for values in session.transaction_data.pop('check_entity_perm_op'):
            entity = session.entity_from_eid(values[0])
            action = values[1]
            entity.cw_check_perm(action)
            check_entity_attributes(session, entity, values[2:],
                                    creation=self.creation)

    def commit_event(self):
        pass


class _CheckRelationPermissionOp(hook.LateOperation):
    def precommit_event(self):
        session = self.session
        for args in session.transaction_data.pop('check_relation_perm_op'):
            action, rschema, eidfrom, eidto = args
            rdef = rschema.rdef(session.describe(eidfrom)[0],
                                session.describe(eidto)[0])
            rdef.check_perm(session, action, fromeid=eidfrom, toeid=eidto)

    def commit_event(self):
        pass


@objectify_selector
@lltrace
def write_security_enabled(cls, req, **kwargs):
    if req is None or not req.write_security:
        return 0
    return 1

class SecurityHook(hook.Hook):
    __abstract__ = True
    category = 'security'
    __select__ = hook.Hook.__select__ & write_security_enabled()


class AfterAddEntitySecurityHook(SecurityHook):
    __regid__ = 'securityafteraddentity'
    events = ('after_add_entity',)

    def __call__(self):
        hook.set_operation(self._cw, 'check_entity_perm_op',
                           (self.entity.eid, 'add') + tuple(self.entity.edited_attributes),
                           _CheckEntityPermissionOp, creation=True)


class AfterUpdateEntitySecurityHook(SecurityHook):
    __regid__ = 'securityafterupdateentity'
    events = ('after_update_entity',)

    def __call__(self):
        try:
            # check user has permission right now, if not retry at commit time
            self.entity.cw_check_perm('update')
            check_entity_attributes(self._cw, self.entity)
        except Unauthorized:
            self.entity._cw_clear_local_perm_cache('update')
            # save back editedattrs in case the entity is reedited later in the
            # same transaction, which will lead to edited_attributes being
            # overwritten
            hook.set_operation(self._cw, 'check_entity_perm_op',
                               (self.entity.eid, 'update') + tuple(self.entity.edited_attributes),
                               _CheckEntityPermissionOp, creation=False)


class BeforeDelEntitySecurityHook(SecurityHook):
    __regid__ = 'securitybeforedelentity'
    events = ('before_delete_entity',)

    def __call__(self):
        self.entity.cw_check_perm('delete')


class BeforeAddRelationSecurityHook(SecurityHook):
    __regid__ = 'securitybeforeaddrelation'
    events = ('before_add_relation',)

    def __call__(self):
        if self.rtype in BEFORE_ADD_RELATIONS:
            nocheck = self._cw.transaction_data.get('skip-security', ())
            if (self.eidfrom, self.rtype, self.eidto) in nocheck:
                return
            rschema = self._cw.repo.schema[self.rtype]
            rdef = rschema.rdef(self._cw.describe(self.eidfrom)[0],
                                self._cw.describe(self.eidto)[0])
            rdef.check_perm(self._cw, 'add', fromeid=self.eidfrom, toeid=self.eidto)


class AfterAddRelationSecurityHook(SecurityHook):
    __regid__ = 'securityafteraddrelation'
    events = ('after_add_relation',)

    def __call__(self):
        if not self.rtype in BEFORE_ADD_RELATIONS:
            nocheck = self._cw.transaction_data.get('skip-security', ())
            if (self.eidfrom, self.rtype, self.eidto) in nocheck:
                return
            rschema = self._cw.repo.schema[self.rtype]
            if self.rtype in ON_COMMIT_ADD_RELATIONS:
                hook.set_operation(self._cw, 'check_relation_perm_op',
                                   ('add', rschema, self.eidfrom, self.eidto),
                                   _CheckRelationPermissionOp)
            else:
                rdef = rschema.rdef(self._cw.describe(self.eidfrom)[0],
                                    self._cw.describe(self.eidto)[0])
                rdef.check_perm(self._cw, 'add', fromeid=self.eidfrom, toeid=self.eidto)


class BeforeDeleteRelationSecurityHook(SecurityHook):
    __regid__ = 'securitybeforedelrelation'
    events = ('before_delete_relation',)

    def __call__(self):
        nocheck = self._cw.transaction_data.get('skip-security', ())
        if (self.eidfrom, self.rtype, self.eidto) in nocheck:
            return
        rschema = self._cw.repo.schema[self.rtype]
        rdef = rschema.rdef(self._cw.describe(self.eidfrom)[0],
                            self._cw.describe(self.eidto)[0])
        rdef.check_perm(self._cw, 'delete', fromeid=self.eidfrom, toeid=self.eidto)

