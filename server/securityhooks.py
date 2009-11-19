"""Security hooks: check permissions to add/delete/update entities according to
the user connected to a session

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import Unauthorized
from cubicweb.server.pool import LateOperation
from cubicweb.server import BEFORE_ADD_RELATIONS, ON_COMMIT_ADD_RELATIONS

def check_entity_attributes(session, entity):
    eid = entity.eid
    eschema = entity.e_schema
    # ._default_set is only there on entity creation to indicate unspecified
    # attributes which has been set to a default value defined in the schema
    defaults = getattr(entity, '_default_set', ())
    try:
        editedattrs = entity.edited_attributes
    except AttributeError:
        editedattrs = entity.keys()
    for attr in editedattrs:
        if attr in defaults:
            continue
        rdef = eschema.rdef(attr)
        if rdef.final: # non final relation are checked by other hooks
            # add/delete should be equivalent (XXX: unify them into 'update' ?)
            rdef.check_perm(session, 'add', eid=eid)


class CheckEntityPermissionOp(LateOperation):
    def precommit_event(self):
        #print 'CheckEntityPermissionOp', self.session.user, self.entity, self.action
        self.entity.check_perm(self.action)
        check_entity_attributes(self.session, self.entity)

    def commit_event(self):
        pass


class CheckRelationPermissionOp(LateOperation):
    def precommit_event(self):
        rdef = self.rschema.rdef(self.session.describe(self.fromeid)[0],
                                 self.session.describe(self.toeid)[0])
        rdef.check_perm(self.session, self.action,
                        fromeid=self.fromeid, toeid=self.toeid)

    def commit_event(self):
        pass

def after_add_entity(session, entity):
    if not session.is_super_session:
        CheckEntityPermissionOp(session, entity=entity, action='add')

def after_update_entity(session, entity):
    if not session.is_super_session:
        try:
            # check user has permission right now, if not retry at commit time
            entity.check_perm('update')
            check_entity_attributes(session, entity)
        except Unauthorized:
            entity.clear_local_perm_cache('update')
            CheckEntityPermissionOp(session, entity=entity, action='update')

def before_del_entity(session, eid):
    if not session.is_super_session:
        eschema = session.repo.schema[session.describe(eid)[0]]
        eschema.check_perm(session, 'delete', eid=eid)


def before_add_relation(session, fromeid, rtype, toeid):
    if rtype in BEFORE_ADD_RELATIONS and not session.is_super_session:
        nocheck = session.transaction_data.get('skip-security', ())
        if (fromeid, rtype, toeid) in nocheck:
            return
        rschema = session.repo.schema[rtype]
        rdef = rschema.rdef(session.describe(fromeid)[0],
                            session.describe(toeid)[0])
        rdef.check_perm(session, 'add', fromeid=fromeid, toeid=toeid)

def after_add_relation(session, fromeid, rtype, toeid):
    if not rtype in BEFORE_ADD_RELATIONS and not session.is_super_session:
        nocheck = session.transaction_data.get('skip-security', ())
        if (fromeid, rtype, toeid) in nocheck:
            return
        rschema = session.repo.schema.rschema(rtype)
        if rtype in ON_COMMIT_ADD_RELATIONS:
            CheckRelationPermissionOp(session, action='add', rschema=rschema,
                                      fromeid=fromeid, toeid=toeid)
        else:
            rdef = rschema.rdef(session.describe(fromeid)[0],
                                session.describe(toeid)[0])
            rdef.check_perm(session, 'add', fromeid=fromeid, toeid=toeid)

def before_del_relation(session, fromeid, rtype, toeid):
    if not session.is_super_session:
        nocheck = session.transaction_data.get('skip-security', ())
        if (fromeid, rtype, toeid) in nocheck:
            return
        rschema = session.vreg.schema.rschema(rtype)
        rdef = rschema.rdef(session.describe(fromeid)[0],
                            session.describe(toeid)[0])
        rdef.check_perm(session, 'delete', fromeid=fromeid, toeid=toeid)

def register_security_hooks(hm):
    """register meta-data related hooks on the hooks manager"""
    hm.register_hook(after_add_entity, 'after_add_entity', '')
    hm.register_hook(after_update_entity, 'after_update_entity', '')
    hm.register_hook(before_del_entity, 'before_delete_entity', '')
    hm.register_hook(before_add_relation, 'before_add_relation', '')
    hm.register_hook(after_add_relation, 'after_add_relation', '')
    hm.register_hook(before_del_relation, 'before_delete_relation', '')

