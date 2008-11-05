"""workflow definition and history related entities

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.entities import AnyEntity, fetch_config


class Transition(AnyEntity):
    """customized class for Transition entities

    provides a specific may_be_passed method to check if the relation may be
    passed by the logged user
    """
    id = 'Transition'
    fetch_attrs, fetch_order = fetch_config(['name'])
    __rtags__ = {('destination_state',  '*', 'subject'):  'create',
                 ('allowed_transition', '*', 'object') :  'create',
                  }
                 
    def may_be_passed(self, eid, stateeid):
        """return true if the logged user may pass this transition

        `eid` is the eid of the object on which we may pass the transition
        `stateeid` is the eid of the current object'state XXX unused
        """
        user = self.req.user
        # check user is at least in one of the required groups if any
        groups = frozenset(g.name for g in self.require_group)
        if groups:
            matches = user.matching_groups(groups)
            if matches:
                return matches
            if 'owners' in groups and user.owns(eid):
                return True
        # check one of the rql expression conditions matches if any
        if self.condition:
            for rqlexpr in self.condition:
                if rqlexpr.check_expression(self.req, eid):
                    return True
        if self.condition or groups:
            return False
        return True

    def destination(self):
        return self.destination_state[0]
    
    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.transition_of:
            return self.transition_of[0].rest_path(), {'vid': 'workflow'}
        return super(Transition, self).after_deletion_path()

    
class State(AnyEntity):
    """customized class for State entities

    provides a specific transitions method returning transitions that may be
    passed by the current user for the given entity
    """
    id = 'State'
    fetch_attrs, fetch_order = fetch_config(['name'])
    rest_attr = 'eid'
    
    __rtags__ = {'destination_state' : 'create',
                 'allowed_transition' : 'create'
                 }
    
    def transitions(self, entity, desteid=None):
        rql = ('Any T,N,DS where S allowed_transition T, S eid %(x)s, '
               'T name N, T destination_state DS, '
               'T transition_of ET, ET name %(et)s')
        if desteid is not None:
            rql += ', DS eid %(ds)s'
        rset = self.req.execute(rql, {'x': self.eid, 'et': str(entity.e_schema),
                                         'ds': desteid}, 'x')
        for tr in rset.entities():
            if tr.may_be_passed(entity.eid, self.eid):
                yield tr
                
    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.state_of:
            return self.state_of[0].rest_path(), {'vid': 'workflow'}
        return super(State, self).after_deletion_path()

    
class TrInfo(AnyEntity):
    """customized class for Transition information entities
    """
    id = 'TrInfo'
    fetch_attrs, fetch_order = fetch_config(['creation_date', 'comment'],
                                            pclass=None) # don't want modification_date
    @property
    def for_entity(self):
        return self.wf_info_for and self.wf_info_for[0]
    @property
    def previous_state(self):
        return self.from_state and self.from_state[0]
    
    @property
    def new_state(self):
        return self.to_state[0]

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.for_entity:
            return self.for_entity.rest_path(), {}
        return 'view', {}
