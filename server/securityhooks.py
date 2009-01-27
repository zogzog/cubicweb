"""Security hooks: check permissions to add/delete/update entities according to
the user connected to a session

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
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
    for attr in entity.keys():
        if attr in defaults:
            continue
        rschema = eschema.subject_relation(attr)
        if rschema.is_final(): # non final relation are checked by other hooks
            # add/delete should be equivalent (XXX: unify them into 'update' ?)
            rschema.check_perm(session, 'add', eid)
            
    
class CheckEntityPermissionOp(LateOperation):
    def precommit_event(self):
        #print 'CheckEntityPermissionOp', self.session.user, self.entity, self.action
        self.entity.check_perm(self.action)
        check_entity_attributes(self.session, self.entity)
        
    def commit_event(self):
        pass
            
    
class CheckRelationPermissionOp(LateOperation):
    def precommit_event(self):
        self.rschema.check_perm(self.session, self.action, self.fromeid, self.toeid)
        
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
        eschema.check_perm(session, 'delete', eid)


def before_add_relation(session, fromeid, rtype, toeid):
    if rtype in BEFORE_ADD_RELATIONS and not session.is_super_session:
        rschema = session.repo.schema[rtype]
        rschema.check_perm(session, 'add', fromeid, toeid)
        
def after_add_relation(session, fromeid, rtype, toeid):
    if not rtype in BEFORE_ADD_RELATIONS and not session.is_super_session:
        rschema = session.repo.schema[rtype]
        if rtype in ON_COMMIT_ADD_RELATIONS:
            CheckRelationPermissionOp(session, action='add', rschema=rschema,
                                      fromeid=fromeid, toeid=toeid)
        else:
            rschema.check_perm(session, 'add', fromeid, toeid)

def before_del_relation(session, fromeid, rtype, toeid):
    if not session.is_super_session:
        session.repo.schema[rtype].check_perm(session, 'delete', fromeid, toeid)

def register_security_hooks(hm):
    """register meta-data related hooks on the hooks manager"""
    hm.register_hook(after_add_entity, 'after_add_entity', '')
    hm.register_hook(after_update_entity, 'after_update_entity', '')
    hm.register_hook(before_del_entity, 'before_delete_entity', '')
    hm.register_hook(before_add_relation, 'before_add_relation', '')
    hm.register_hook(after_add_relation, 'after_add_relation', '')
    hm.register_hook(before_del_relation, 'before_delete_relation', '')
    
