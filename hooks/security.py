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
"""Security hooks: check permissions to add/delete/update entities according to
the user connected to a session
"""

__docformat__ = "restructuredtext en"

from logilab.common.registry import objectify_predicate

from yams import buildobjs

from cubicweb import Unauthorized
from cubicweb.server import BEFORE_ADD_RELATIONS, ON_COMMIT_ADD_RELATIONS, hook


_DEFAULT_UPDATE_ATTRPERM = buildobjs.DEFAULT_ATTRPERMS['update']
def check_entity_attributes(session, entity, editedattrs=None, creation=False):
    eid = entity.eid
    eschema = entity.e_schema
    # ._cw_skip_security_attributes is there to bypass security for attributes
    # set by hooks by modifying the entity's dictionary
    if editedattrs is None:
        editedattrs = entity.cw_edited
    dontcheck = editedattrs.skip_security
    for attr in editedattrs:
        if attr in dontcheck:
            continue
        rdef = eschema.rdef(attr, takefirst=True)
        if rdef.final: # non final relation are checked by standard hooks
            # attributes only have a specific 'update' permission
            updateperm = rdef.permissions.get('update')
            # comparison below works because the default update perm is:
            #
            #  ('managers', ERQLExpression(Any X WHERE U has_update_permission X, X eid %(x)s, U eid %(u)s))
            #
            # is deserialized in this order (groups first), and ERQLExpression
            # implements comparison by expression.
            if updateperm == _DEFAULT_UPDATE_ATTRPERM:
                # The default update permission is to delegate to the entity
                # update permission. This is an historical artefact but it is
                # costly (in general). Hence we take this permission object as a
                # marker saying "no specific" update permissions for this
                # attribute. Thus we just do nothing.
                continue
            if creation and updateperm == ():
                # That actually means an immutable attribute.  We make an
                # _exception_ to the `check attr update perms at entity create &
                # update time` rule for this case.
                continue
            rdef.check_perm(session, 'update', eid=eid)


class CheckEntityPermissionOp(hook.DataOperationMixIn, hook.LateOperation):
    def precommit_event(self):
        session = self.session
        for eid, action, edited in self.get_data():
            entity = session.entity_from_eid(eid)
            entity.cw_check_perm(action)
            check_entity_attributes(session, entity, edited,
                                    creation=(action == 'add'))


class CheckRelationPermissionOp(hook.DataOperationMixIn, hook.LateOperation):
    def precommit_event(self):
        session = self.session
        for action, rschema, eidfrom, eidto in self.get_data():
            rdef = rschema.rdef(session.describe(eidfrom)[0],
                                session.describe(eidto)[0])
            rdef.check_perm(session, action, fromeid=eidfrom, toeid=eidto)


@objectify_predicate
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
        CheckEntityPermissionOp.get_instance(self._cw).add_data(
            (self.entity.eid, 'add', self.entity.cw_edited) )


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
            # same transaction, which will lead to cw_edited being
            # overwritten
            CheckEntityPermissionOp.get_instance(self._cw).add_data(
                (self.entity.eid, 'update', self.entity.cw_edited) )


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
                CheckRelationPermissionOp.get_instance(self._cw).add_data(
                    ('add', rschema, self.eidfrom, self.eidto) )
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

