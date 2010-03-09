"""Security hooks: check permissions to add/delete/update entities according to
the user connected to a session

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import Unauthorized
from cubicweb.selectors import objectify_selector, lltrace
from cubicweb.server import BEFORE_ADD_RELATIONS, ON_COMMIT_ADD_RELATIONS, hook


def check_entity_attributes(session, entity, editedattrs=None):
    eid = entity.eid
    eschema = entity.e_schema
    # ._default_set is only there on entity creation to indicate unspecified
    # attributes which has been set to a default value defined in the schema
    defaults = getattr(entity, '_default_set', ())
    if editedattrs is None:
        try:
            editedattrs = entity.edited_attributes
        except AttributeError:
            editedattrs = entity
    for attr in editedattrs:
        if attr in defaults:
            continue
        rdef = eschema.rdef(attr)
        if rdef.final: # non final relation are checked by other hooks
            # add/delete should be equivalent (XXX: unify them into 'update' ?)
            rdef.check_perm(session, 'update', eid=eid)


class _CheckEntityPermissionOp(hook.LateOperation):
    def precommit_event(self):
        #print 'CheckEntityPermissionOp', self.session.user, self.entity, self.action
        self.entity.check_perm(self.action)
        check_entity_attributes(self.session, self.entity, self.editedattrs)

    def commit_event(self):
        pass


class _CheckRelationPermissionOp(hook.LateOperation):
    def precommit_event(self):
        rdef = self.rschema.rdef(self.session.describe(self.eidfrom)[0],
                                 self.session.describe(self.eidto)[0])
        rdef.check_perm(self.session, self.action,
                        fromeid=self.eidfrom, toeid=self.eidto)

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
        _CheckEntityPermissionOp(self._cw, entity=self.entity,
                                 editedattrs=tuple(self.entity.edited_attributes),
                                 action='add')


class AfterUpdateEntitySecurityHook(SecurityHook):
    __regid__ = 'securityafterupdateentity'
    events = ('after_update_entity',)

    def __call__(self):
        try:
            # check user has permission right now, if not retry at commit time
            self.entity.check_perm('update')
            check_entity_attributes(self._cw, self.entity)
        except Unauthorized:
            self.entity.clear_local_perm_cache('update')
            # save back editedattrs in case the entity is reedited later in the
            # same transaction, which will lead to edited_attributes being
            # overwritten
            _CheckEntityPermissionOp(self._cw, entity=self.entity,
                                     editedattrs=tuple(self.entity.edited_attributes),
                                     action='update')


class BeforeDelEntitySecurityHook(SecurityHook):
    __regid__ = 'securitybeforedelentity'
    events = ('before_delete_entity',)

    def __call__(self):
        self.entity.check_perm('delete')


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
                _CheckRelationPermissionOp(self._cw, action='add',
                                           rschema=rschema,
                                           eidfrom=self.eidfrom,
                                           eidto=self.eidto)
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

