"""Security hooks: check permissions to add/delete/update entities according to
the user connected to a session

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import Unauthorized
from cubicweb.server import BEFORE_ADD_RELATIONS, ON_COMMIT_ADD_RELATIONS, hook


def check_entity_attributes(session, entity):
    eid = entity.eid
    eschema = entity.e_schema
    # ._default_set is only there on entity creation to indicate unspecified
    # attributes which has been set to a default value defined in the schema
    defaults = getattr(entity, '_default_set', ())
    try:
        editedattrs = entity.edited_attributes
    except AttributeError:
        editedattrs = entity
    for attr in editedattrs:
        if attr in defaults:
            continue
        rschema = eschema.subject_relation(attr)
        if rschema.is_final(): # non final relation are checked by other hooks
            # add/delete should be equivalent (XXX: unify them into 'update' ?)
            rschema.check_perm(session, 'add', eid)


class _CheckEntityPermissionOp(hook.LateOperation):
    def precommit_event(self):
        #print 'CheckEntityPermissionOp', self.session.user, self.entity, self.action
        self.entity.check_perm(self.action)
        check_entity_attributes(self.session, self.entity)

    def commit_event(self):
        pass


class _CheckRelationPermissionOp(hook.LateOperation):
    def precommit_event(self):
        self.rschema.check_perm(self.session, self.action, self.eidfrom, self.eidto)

    def commit_event(self):
        pass


class SecurityHook(hook.Hook):
    __abstract__ = True
    category = 'security'
    __select__ = hook.Hook.__select__ & hook.regular_session()


class AfterAddEntitySecurityHook(SecurityHook):
    __id__ = 'securityafteraddentity'
    events = ('after_add_entity',)

    def __call__(self):
        _CheckEntityPermissionOp(self._cw, entity=self.entity, action='add')


class AfterUpdateEntitySecurityHook(SecurityHook):
    __id__ = 'securityafterupdateentity'
    events = ('after_update_entity',)

    def __call__(self):
        try:
            # check user has permission right now, if not retry at commit time
            self.entity.check_perm('update')
            check_entity_attributes(self._cw, self.entity)
        except Unauthorized:
            self.entity.clear_local_perm_cache('update')
            _CheckEntityPermissionOp(self._cw, entity=self.entity, action='update')


class BeforeDelEntitySecurityHook(SecurityHook):
    __id__ = 'securitybeforedelentity'
    events = ('before_delete_entity',)

    def __call__(self):
        self.entity.check_perm('delete')


class BeforeAddRelationSecurityHook(SecurityHook):
    __id__ = 'securitybeforeaddrelation'
    events = ('before_add_relation',)

    def __call__(self):
        if self.rtype in BEFORE_ADD_RELATIONS:
            rschema = self._cw.repo.schema[self.rtype]
            rschema.check_perm(self._cw, 'add', self.eidfrom, self.eidto)


class AfterAddRelationSecurityHook(SecurityHook):
    __id__ = 'securityafteraddrelation'
    events = ('after_add_relation',)

    def __call__(self):
        if not self.rtype in BEFORE_ADD_RELATIONS:
            rschema = self._cw.repo.schema[self.rtype]
            if self.rtype in ON_COMMIT_ADD_RELATIONS:
                _CheckRelationPermissionOp(self._cw, action='add',
                                           rschema=rschema,
                                           eidfrom=self.eidfrom,
                                           eidto=self.eidto)
            else:
                rschema.check_perm(self._cw, 'add', self.eidfrom, self.eidto)


class BeforeDelRelationSecurityHook(SecurityHook):
    __id__ = 'securitybeforedelrelation'
    events = ('before_delete_relation',)

    def __call__(self):
        self._cw.repo.schema[self.rtype].check_perm(self._cw, 'delete',
                                                       self.eidfrom, self.eidto)

