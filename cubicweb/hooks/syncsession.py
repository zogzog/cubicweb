# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb import _
from cubicweb import UnknownProperty, BadConnectionId, validation_error
from cubicweb.predicates import is_instance
from cubicweb.server import hook


def get_user_sessions(repo, ueid):
    for session in repo._sessions.values():
        if ueid == session.user.eid:
            yield session


class SyncSessionHook(hook.Hook):
    __abstract__ = True
    category = 'syncsession'


# user/groups synchronisation #################################################

class _GroupOperation(hook.Operation):
    """base class for group operation"""
    cnxuser = None # make pylint happy

    def __init__(self, cnx, *args, **kwargs):
        """override to get the group name before actual groups manipulation:

        we may temporarily loose right access during a commit event, so
        no query should be emitted while comitting
        """
        rql = 'Any N WHERE G eid %(x)s, G name N'
        result = cnx.execute(rql, {'x': kwargs['geid']}, build_descr=False)
        hook.Operation.__init__(self, cnx, *args, **kwargs)
        self.group = result[0][0]


class _DeleteGroupOp(_GroupOperation):
    """Synchronize user when a in_group relation has been deleted"""

    def postcommit_event(self):
        """the observed connections set has been commited"""
        groups = self.cnxuser.groups
        try:
            groups.remove(self.group)
        except KeyError:
            self.error('user %s not in group %s',  self.cnxuser, self.group)


class _AddGroupOp(_GroupOperation):
    """Synchronize user when a in_group relation has been added"""

    def postcommit_event(self):
        """the observed connections set has been commited"""
        groups = self.cnxuser.groups
        if self.group in groups:
            self.warning('user %s already in group %s', self.cnxuser,
                         self.group)
        else:
            groups.add(self.group)


class SyncInGroupHook(SyncSessionHook):
    """Watch addition/removal of in_group relation to synchronize living sessions accordingly"""
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
    def __init__(self, cnx, sessionid):
        self.sessionid = sessionid
        hook.Operation.__init__(self, cnx)

    def postcommit_event(self):
        try:
            self.cnx.repo.close(self.sessionid)
        except BadConnectionId:
            pass  # already closed


class CloseDeletedUserSessionsHook(SyncSessionHook):
    __regid__ = 'closession'
    __select__ = SyncSessionHook.__select__ & is_instance('CWUser')
    events = ('after_delete_entity',)

    def __call__(self):
        for session in get_user_sessions(self._cw.repo, self.entity.eid):
            _DelUserOp(self._cw, session.sessionid)


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
            self.cnx.vreg['propertyvalues'][cwprop.pkey] = \
                self.cnx.vreg.typed_value(cwprop.pkey, cwprop.value)
        # if for_user is set, update is handled by a ChangeCWPropertyOp operation


class AddCWPropertyHook(SyncSessionHook):
    __regid__ = 'addcwprop'
    __select__ = SyncSessionHook.__select__ & is_instance('CWProperty')
    events = ('after_add_entity',)

    def __call__(self):
        key, value = self.entity.pkey, self.entity.value
        if key.startswith('sources.'):
            return
        cnx = self._cw
        try:
            value = cnx.vreg.typed_value(key, value)
        except UnknownProperty:
            msg = _('unknown property key %s')
            raise validation_error(self.entity, {('pkey', 'subject'): msg}, (key,))
        except ValueError as ex:
            raise validation_error(self.entity,
                                  {('value', 'subject'): str(ex)})
        if not cnx.user.matching_groups('managers'):
            cnx.add_relation(self.entity.eid, 'for_user', cnx.user.eid)
        else:
            _AddCWPropertyOp(cnx, cwprop=self.entity)


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
        cnx = self._cw
        try:
            value = cnx.vreg.typed_value(key, value)
        except UnknownProperty:
            return
        except ValueError as ex:
            raise validation_error(entity, {('value', 'subject'): str(ex)})
        if entity.for_user:
            for session in get_user_sessions(cnx.repo, entity.for_user[0].eid):
                _ChangeCWPropertyOp(cnx, cwpropdict=session.user.properties,
                                    key=key, value=value)
        else:
            # site wide properties
            _ChangeCWPropertyOp(cnx, cwpropdict=cnx.vreg['propertyvalues'],
                              key=key, value=value)


class DeleteCWPropertyHook(AddCWPropertyHook):
    __regid__ = 'delcwprop'
    events = ('before_delete_entity',)

    def __call__(self):
        cnx = self._cw
        for eidfrom, rtype, eidto in cnx.transaction_data.get('pendingrelations', ()):
            if rtype == 'for_user' and eidfrom == self.entity.eid:
                # if for_user was set, delete already handled by hook on for_user deletion
                break
        else:
            _DelCWPropertyOp(cnx, cwpropdict=cnx.vreg['propertyvalues'],
                             key=self.entity.pkey)


class AddForUserRelationHook(SyncSessionHook):
    __regid__ = 'addcwpropforuser'
    __select__ = SyncSessionHook.__select__ & hook.match_rtype('for_user')
    events = ('after_add_relation',)

    def __call__(self):
        cnx = self._cw
        eidfrom = self.eidfrom
        if not cnx.entity_metas(eidfrom)['type'] == 'CWProperty':
            return
        key, value = cnx.execute('Any K,V WHERE P eid %(x)s,P pkey K,P value V',
                                 {'x': eidfrom})[0]
        if cnx.vreg.property_info(key)['sitewide']:
            msg = _("site-wide property can't be set for user")
            raise validation_error(eidfrom, {('for_user', 'subject'): msg})
        for session in get_user_sessions(cnx.repo, self.eidto):
            _ChangeCWPropertyOp(cnx, cwpropdict=session.user.properties,
                              key=key, value=value)


class DelForUserRelationHook(AddForUserRelationHook):
    __regid__ = 'delcwpropforuser'
    events = ('after_delete_relation',)

    def __call__(self):
        cnx = self._cw
        key = cnx.execute('Any K WHERE P eid %(x)s, P pkey K', {'x': self.eidfrom})[0][0]
        cnx.transaction_data.setdefault('pendingrelations', []).append(
            (self.eidfrom, self.rtype, self.eidto))
        for session in get_user_sessions(cnx.repo, self.eidto):
            _DelCWPropertyOp(cnx, cwpropdict=session.user.properties, key=key)
