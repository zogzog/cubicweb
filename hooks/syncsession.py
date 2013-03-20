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
"""Core hooks: synchronize living session on persistent data changes"""

__docformat__ = "restructuredtext en"
_ = unicode

from cubicweb import UnknownProperty, BadConnectionId, validation_error
from cubicweb.predicates import is_instance
from cubicweb.server import hook


def get_user_sessions(repo, ueid):
    for session in repo._sessions.itervalues():
        if ueid == session.user.eid:
            yield session


class SyncSessionHook(hook.Hook):
    __abstract__ = True
    category = 'syncsession'


# user/groups synchronisation #################################################

class _GroupOperation(hook.Operation):
    """base class for group operation"""
    cnxuser = None # make pylint happy

    def __init__(self, session, *args, **kwargs):
        """override to get the group name before actual groups manipulation:

        we may temporarily loose right access during a commit event, so
        no query should be emitted while comitting
        """
        rql = 'Any N WHERE G eid %(x)s, G name N'
        result = session.execute(rql, {'x': kwargs['geid']}, build_descr=False)
        hook.Operation.__init__(self, session, *args, **kwargs)
        self.group = result[0][0]


class _DeleteGroupOp(_GroupOperation):
    """synchronize user when a in_group relation has been deleted"""

    def postcommit_event(self):
        """the observed connections set has been commited"""
        groups = self.cnxuser.groups
        try:
            groups.remove(self.group)
        except KeyError:
            self.error('user %s not in group %s',  self.cnxuser, self.group)


class _AddGroupOp(_GroupOperation):
    """synchronize user when a in_group relation has been added"""
    def postcommit_event(self):
        """the observed connections set has been commited"""
        groups = self.cnxuser.groups
        if self.group in groups:
            self.warning('user %s already in group %s', self.cnxuser,
                         self.group)
        else:
            groups.add(self.group)


class SyncInGroupHook(SyncSessionHook):
    __regid__ = 'syncingroup'
    __select__ = SyncSessionHook.__select__ & hook.match_rtype('in_group')
    events = ('after_delete_relation', 'after_add_relation')

    def __call__(self):
        if self.event == 'after_delete_relation':
            opcls = _DeleteGroupOp
        else:
            opcls = _AddGroupOp
        for session in get_user_sessions(self._cw.repo, self.eidfrom):
            opcls(self._cw, cnxuser=session.user, geid=self.eidto)


class _DelUserOp(hook.Operation):
    """close associated user's session when it is deleted"""
    def __init__(self, session, cnxid):
        self.cnxid = cnxid
        hook.Operation.__init__(self, session)

    def postcommit_event(self):
        """the observed connections set has been commited"""
        try:
            self.session.repo.close(self.cnxid)
        except BadConnectionId:
            pass # already closed


class CloseDeletedUserSessionsHook(SyncSessionHook):
    __regid__ = 'closession'
    __select__ = SyncSessionHook.__select__ & is_instance('CWUser')
    events = ('after_delete_entity',)

    def __call__(self):
        """modify user permission, need to update users"""
        for session in get_user_sessions(self._cw.repo, self.entity.eid):
            _DelUserOp(self._cw, session.id)


# CWProperty hooks #############################################################

class _DelCWPropertyOp(hook.Operation):
    """a user's custom properties has been deleted"""
    cwpropdict = key = None # make pylint happy

    def postcommit_event(self):
        """the observed connections set has been commited"""
        try:
            del self.cwpropdict[self.key]
        except KeyError:
            self.error('%s has no associated value', self.key)


class _ChangeCWPropertyOp(hook.Operation):
    """a user's custom properties has been added/changed"""
    cwpropdict = key = value = None # make pylint happy

    def postcommit_event(self):
        """the observed connections set has been commited"""
        self.cwpropdict[self.key] = self.value


class _AddCWPropertyOp(hook.Operation):
    """a user's custom properties has been added/changed"""
    cwprop = None # make pylint happy

    def postcommit_event(self):
        """the observed connections set has been commited"""
        cwprop = self.cwprop
        if not cwprop.for_user:
            self.session.vreg['propertyvalues'][cwprop.pkey] = cwprop.value
        # if for_user is set, update is handled by a ChangeCWPropertyOp operation


class AddCWPropertyHook(SyncSessionHook):
    __regid__ = 'addcwprop'
    __select__ = SyncSessionHook.__select__ & is_instance('CWProperty')
    events = ('after_add_entity',)

    def __call__(self):
        key, value = self.entity.pkey, self.entity.value
        if key.startswith('sources.'):
            return
        session = self._cw
        try:
            value = session.vreg.typed_value(key, value)
        except UnknownProperty:
            msg = _('unknown property key %s')
            raise validation_error(self.entity, {('pkey', 'subject'): msg}, (key,))
        except ValueError as ex:
            raise validation_error(self.entity,
                                  {('value', 'subject'): str(ex)})
        if not session.user.matching_groups('managers'):
            session.add_relation(self.entity.eid, 'for_user', session.user.eid)
        else:
            _AddCWPropertyOp(session, cwprop=self.entity)


class UpdateCWPropertyHook(AddCWPropertyHook):
    __regid__ = 'updatecwprop'
    events = ('after_update_entity',)

    def __call__(self):
        entity = self.entity
        if not ('pkey' in entity.cw_edited or
                'value' in entity.cw_edited):
            return
        key, value = entity.pkey, entity.value
        if key.startswith('sources.'):
            return
        session = self._cw
        try:
            value = session.vreg.typed_value(key, value)
        except UnknownProperty:
            return
        except ValueError as ex:
            raise validation_error(entity, {('value', 'subject'): str(ex)})
        if entity.for_user:
            for session_ in get_user_sessions(session.repo, entity.for_user[0].eid):
                _ChangeCWPropertyOp(session, cwpropdict=session_.user.properties,
                                    key=key, value=value)
        else:
            # site wide properties
            _ChangeCWPropertyOp(session, cwpropdict=session.vreg['propertyvalues'],
                              key=key, value=value)


class DeleteCWPropertyHook(AddCWPropertyHook):
    __regid__ = 'delcwprop'
    events = ('before_delete_entity',)

    def __call__(self):
        eid = self.entity.eid
        session = self._cw
        for eidfrom, rtype, eidto in session.transaction_data.get('pendingrelations', ()):
            if rtype == 'for_user' and eidfrom == self.entity.eid:
                # if for_user was set, delete has already been handled
                break
        else:
            _DelCWPropertyOp(session, cwpropdict=session.vreg['propertyvalues'],
                             key=self.entity.pkey)


class AddForUserRelationHook(SyncSessionHook):
    __regid__ = 'addcwpropforuser'
    __select__ = SyncSessionHook.__select__ & hook.match_rtype('for_user')
    events = ('after_add_relation',)

    def __call__(self):
        session = self._cw
        eidfrom = self.eidfrom
        if not session.describe(eidfrom)[0] == 'CWProperty':
            return
        key, value = session.execute('Any K,V WHERE P eid %(x)s,P pkey K,P value V',
                                     {'x': eidfrom})[0]
        if session.vreg.property_info(key)['sitewide']:
            msg = _("site-wide property can't be set for user")
            raise validation_error(eidfrom, {('for_user', 'subject'): msg})
        for session_ in get_user_sessions(session.repo, self.eidto):
            _ChangeCWPropertyOp(session, cwpropdict=session_.user.properties,
                              key=key, value=value)


class DelForUserRelationHook(AddForUserRelationHook):
    __regid__ = 'delcwpropforuser'
    events = ('after_delete_relation',)

    def __call__(self):
        session = self._cw
        key = session.execute('Any K WHERE P eid %(x)s, P pkey K',
                              {'x': self.eidfrom})[0][0]
        session.transaction_data.setdefault('pendingrelations', []).append(
            (self.eidfrom, self.rtype, self.eidto))
        for session_ in get_user_sessions(session.repo, self.eidto):
            _DelCWPropertyOp(session, cwpropdict=session_.user.properties, key=key)
