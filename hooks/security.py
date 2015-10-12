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
"""Security hooks: check permissions to add/delete/update entities according to
the connected user
"""

__docformat__ = "restructuredtext en"
from warnings import warn

from logilab.common.registry import objectify_predicate

from yams import buildobjs

from cubicweb import Unauthorized
from cubicweb.server import BEFORE_ADD_RELATIONS, ON_COMMIT_ADD_RELATIONS, hook



def check_entity_attributes(cnx, entity, action, editedattrs=None):
    eid = entity.eid
    eschema = entity.e_schema
    if action == 'delete':
        eschema.check_perm(session, action, eid=eid)
        return
    # ._cw_skip_security_attributes is there to bypass security for attributes
    # set by hooks by modifying the entity's dictionary
    if editedattrs is None:
        editedattrs = entity.cw_edited
    dontcheck = editedattrs.skip_security
    etypechecked = False
    for attr in editedattrs:
        if attr in dontcheck:
            continue
        rdef = eschema.rdef(attr, takefirst=True)
        if rdef.final: # non final relation are checked by standard hooks
            perms = rdef.permissions.get(action)
            # comparison below works because the default update perm is:
            #
            #  ('managers', ERQLExpression(Any X WHERE U has_update_permission X,
            #                              X eid %(x)s, U eid %(u)s))
            #
            # is deserialized in this order (groups first), and ERQLExpression
            # implements comparison by rql expression.
            if perms == buildobjs.DEFAULT_ATTRPERMS[action]:
                # The default rule is to delegate to the entity
                # rule. This needs to be checked only once.
                if not etypechecked:
                    entity.cw_check_perm(action)
                    etypechecked = True
                continue
            if perms == ():
                # That means an immutable attribute; as an optimization, avoid
                # going through check_perm.
                raise Unauthorized(action, str(rdef))
            rdef.check_perm(cnx, action, eid=eid)

    if action == 'add' and not etypechecked:
        # think about cnx.create_entity('Foo')
        # the standard metadata were inserted by a hook
        # with a bypass ... we conceptually need to check
        # the eid attribute at *creation* time
        entity.cw_check_perm(action)


class CheckEntityPermissionOp(hook.DataOperationMixIn, hook.LateOperation):
    def precommit_event(self):
        cnx = self.cnx
        for eid, action, edited in self.get_data():
            entity = cnx.entity_from_eid(eid)
            check_entity_attributes(cnx, entity, action, edited)


class CheckRelationPermissionOp(hook.DataOperationMixIn, hook.LateOperation):
    def precommit_event(self):
        cnx = self.cnx
        for action, rschema, eidfrom, eidto in self.get_data():
            rdef = rschema.rdef(cnx.entity_metas(eidfrom)['type'],
                                cnx.entity_metas(eidto)['type'])
            rdef.check_perm(cnx, action, fromeid=eidfrom, toeid=eidto)


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
        # save back editedattrs in case the entity is reedited later in the
        # same transaction, which will lead to cw_edited being
        # overwritten
        action = 'add' if self._cw.added_in_transaction(self.entity.eid) else 'update'
        CheckEntityPermissionOp.get_instance(self._cw).add_data(
            (self.entity.eid, action, self.entity.cw_edited) )


class BeforeDelEntitySecurityHook(SecurityHook):
    __regid__ = 'securitybeforedelentity'
    events = ('before_delete_entity',)

    def __call__(self):
        self.entity.cw_check_perm('delete')


def skip_inlined_relation_security(cnx, rschema, eid):
    """return True if security for the given inlined relation should be skipped,
    in case where the relation has been set through modification of
    `entity.cw_edited` in a hook
    """
    assert rschema.inlined
    try:
        entity = cnx.entity_cache(eid)
    except KeyError:
        return False
    edited = getattr(entity, 'cw_edited', None)
    if edited is None:
        return False
    return rschema.type in edited.skip_security


class BeforeAddRelationSecurityHook(SecurityHook):
    __regid__ = 'securitybeforeaddrelation'
    events = ('before_add_relation',)

    def __call__(self):
        if self.rtype in BEFORE_ADD_RELATIONS:
            nocheck = self._cw.transaction_data.get('skip-security', ())
            if (self.eidfrom, self.rtype, self.eidto) in nocheck:
                return
            rschema = self._cw.repo.schema[self.rtype]
            if rschema.inlined and skip_inlined_relation_security(
                    self._cw, rschema, self.eidfrom):
                return
            rdef = rschema.rdef(self._cw.entity_metas(self.eidfrom)['type'],
                                self._cw.entity_metas(self.eidto)['type'])
            rdef.check_perm(self._cw, 'add', fromeid=self.eidfrom, toeid=self.eidto)


class AfterAddRelationSecurityHook(SecurityHook):
    __regid__ = 'securityafteraddrelation'
    events = ('after_add_relation',)

    def __call__(self):
        if self.rtype not in BEFORE_ADD_RELATIONS:
            nocheck = self._cw.transaction_data.get('skip-security', ())
            if (self.eidfrom, self.rtype, self.eidto) in nocheck:
                return
            rschema = self._cw.repo.schema[self.rtype]
            if rschema.inlined and skip_inlined_relation_security(
                    self._cw, rschema, self.eidfrom):
                return
            if self.rtype in ON_COMMIT_ADD_RELATIONS:
                CheckRelationPermissionOp.get_instance(self._cw).add_data(
                    ('add', rschema, self.eidfrom, self.eidto) )
            else:
                rdef = rschema.rdef(self._cw.entity_metas(self.eidfrom)['type'],
                                    self._cw.entity_metas(self.eidto)['type'])
                rdef.check_perm(self._cw, 'add', fromeid=self.eidfrom, toeid=self.eidto)


class BeforeDeleteRelationSecurityHook(SecurityHook):
    __regid__ = 'securitybeforedelrelation'
    events = ('before_delete_relation',)

    def __call__(self):
        nocheck = self._cw.transaction_data.get('skip-security', ())
        if (self.eidfrom, self.rtype, self.eidto) in nocheck:
            return
        rschema = self._cw.repo.schema[self.rtype]
        if rschema.inlined and skip_inlined_relation_security(
                self._cw, rschema, self.eidfrom):
            return
        rdef = rschema.rdef(self._cw.entity_metas(self.eidfrom)['type'],
                            self._cw.entity_metas(self.eidto)['type'])
        rdef.check_perm(self._cw, 'delete', fromeid=self.eidfrom, toeid=self.eidto)

