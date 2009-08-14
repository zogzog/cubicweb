"""Core hooks: synchronize living session on persistent data changes

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import UnknownProperty, ValidationError, BadConnectionId
from cubicweb.selectors import entity_implements
from cubicweb.server.hook import Hook, match_rtype
from cubicweb.server.pool import Operation
from cubicweb.server.hookhelper import get_user_sessions


# user/groups synchronisation #################################################

class _GroupOperation(Operation):
    """base class for group operation"""
    geid = None
    def __init__(self, session, *args, **kwargs):
        """override to get the group name before actual groups manipulation:

        we may temporarily loose right access during a commit event, so
        no query should be emitted while comitting
        """
        rql = 'Any N WHERE G eid %(x)s, G name N'
        result = session.execute(rql, {'x': kwargs['geid']}, 'x', build_descr=False)
        Operation.__init__(self, session, *args, **kwargs)
        self.group = result[0][0]


class _DeleteGroupOp(_GroupOperation):
    """synchronize user when a in_group relation has been deleted"""
    def commit_event(self):
        """the observed connections pool has been commited"""
        groups = self.cnxuser.groups
        try:
            groups.remove(self.group)
        except KeyError:
            self.error('user %s not in group %s',  self.cnxuser, self.group)
            return


class _AddGroupOp(_GroupOperation):
    """synchronize user when a in_group relation has been added"""
    def commit_event(self):
        """the observed connections pool has been commited"""
        groups = self.cnxuser.groups
        if self.group in groups:
            self.warning('user %s already in group %s', self.cnxuser,
                         self.group)
            return
        groups.add(self.group)


class SyncInGroupHook(Hook):
    __id__ = 'syncingroup'
    __select__ = Hook.__select__ & match_rtype('in_group')
    events = ('after_delete_relation', 'after_add_relation')
    category = 'syncsession'

    def __call__(self):
        if self.event == 'after_delete_relation':
            opcls = _DeleteGroupOp
        else:
            opcls = _AddGroupOp
        for session in get_user_sessions(self.cw_req.repo, self.eidfrom):
            opcls(self.cw_req, cnxuser=session.user, geid=self.eidto)


class _DelUserOp(Operation):
    """close associated user's session when it is deleted"""
    def __init__(self, session, cnxid):
        self.cnxid = cnxid
        Operation.__init__(self, session)

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            self.repo.close(self.cnxid)
        except BadConnectionId:
            pass # already closed


class CloseDeletedUserSessionsHook(Hook):
    __id__ = 'closession'
    __select__ = Hook.__select__ & entity_implements('CWUser')
    events = ('after_delete_entity',)
    category = 'syncsession'

    def __call__(self):
        """modify user permission, need to update users"""
        for session in get_user_sessions(self.cw_req.repo, self.entity.eid):
            _DelUserOp(self.cw_req, session.id)


# CWProperty hooks #############################################################


class _DelCWPropertyOp(Operation):
    """a user's custom properties has been deleted"""

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            del self.epropdict[self.key]
        except KeyError:
            self.error('%s has no associated value', self.key)


class _ChangeCWPropertyOp(Operation):
    """a user's custom properties has been added/changed"""

    def commit_event(self):
        """the observed connections pool has been commited"""
        self.epropdict[self.key] = self.value


class _AddCWPropertyOp(Operation):
    """a user's custom properties has been added/changed"""

    def commit_event(self):
        """the observed connections pool has been commited"""
        eprop = self.eprop
        if not eprop.for_user:
            self.repo.vreg.eprop_values[eprop.pkey] = eprop.value
        # if for_user is set, update is handled by a ChangeCWPropertyOp operation


class AddCWPropertyHook(Hook):
    __id__ = 'addcwprop'
    __select__ = Hook.__select__ & entity_implements('CWProperty')
    category = 'syncsession'
    events = ('after_add_entity',)

    def __call__(self):
        key, value = self.entity.pkey, self.entity.value
        session = self.cw_req
        try:
            value = session.vreg.typed_value(key, value)
        except UnknownProperty:
            raise ValidationError(self.entity.eid,
                                  {'pkey': session._('unknown property key')})
        except ValueError, ex:
            raise ValidationError(self.entity.eid,
                                  {'value': session._(str(ex))})
        if not session.user.matching_groups('managers'):
            session.add_relation(entity.eid, 'for_user', session.user.eid)
        else:
            _AddCWPropertyOp(session, eprop=entity)


class UpdateCWPropertyHook(AddCWPropertyHook):
    __id__ = 'updatecwprop'
    events = ('after_update_entity',)

    def __call__(self):
        entity = self.entity
        if not ('pkey' in entity.edited_attributes or
                'value' in entity.edited_attributes):
            return
        key, value = entity.pkey, entity.value
        session = self.cw_req
        try:
            value = session.vreg.typed_value(key, value)
        except UnknownProperty:
            return
        except ValueError, ex:
            raise ValidationError(entity.eid, {'value': session._(str(ex))})
        if entity.for_user:
            for session_ in get_user_sessions(session.repo, entity.for_user[0].eid):
                _ChangeCWPropertyOp(session, epropdict=session_.user.properties,
                                  key=key, value=value)
        else:
            # site wide properties
            _ChangeCWPropertyOp(session, epropdict=session.vreg.eprop_values,
                              key=key, value=value)


class DeleteCWPropertyHook(AddCWPropertyHook):
    __id__ = 'delcwprop'
    events = ('before_delete_entity',)

    def __call__(self):
        eid = self.entity.eid
        session = self.cw_req
        for eidfrom, rtype, eidto in session.transaction_data.get('pendingrelations', ()):
            if rtype == 'for_user' and eidfrom == self.entity.eid:
                # if for_user was set, delete has already been handled
                break
        else:
            _DelCWPropertyOp(session, epropdict=session.vreg.eprop_values, key=entity.pkey)


class AddForUserRelationHook(Hook):
    __id__ = 'addcwpropforuser'
    __select__ = Hook.__select__ & match_rtype('for_user')
    events = ('after_add_relation',)
    category = 'syncsession'

    def __call__(self):
        session = self.cw_req
        eidfrom = self.eidfrom
        if not session.describe(eidfrom)[0] == 'CWProperty':
            return
        key, value = session.execute('Any K,V WHERE P eid %(x)s,P pkey K,P value V',
                                     {'x': eidfrom}, 'x')[0]
        if session.vreg.property_info(key)['sitewide']:
            raise ValidationError(eidfrom,
                                  {'for_user': session._("site-wide property can't be set for user")})
        for session_ in get_user_sessions(session.repo, self.eidto):
            _ChangeCWPropertyOp(session, epropdict=session_.user.properties,
                              key=key, value=value)


class DelForUserRelationHook(AddForUserRelationHook):
    __id__ = 'delcwpropforuser'
    events = ('after_delete_relation',)

    def __call__(self):
        session = self.cw_req
        key = session.execute('Any K WHERE P eid %(x)s, P pkey K',
                              {'x': self.eidfrom}, 'x')[0][0]
        session.transaction_data.setdefault('pendingrelations', []).append(
            (self.eidfrom, self.rtype, self.eidto))
        for session_ in get_user_sessions(session.repo, self.eidto):
            _DelCWPropertyOp(session, epropdict=session_.user.properties, key=key)
