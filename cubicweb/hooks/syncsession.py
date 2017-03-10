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

from cubicweb import _
from cubicweb import UnknownProperty, BadConnectionId, validation_error
from cubicweb.predicates import is_instance
from cubicweb.server import hook
from cubicweb.entities.authobjs import user_session_cache_key


def get_user_sessions(cnx, user_eid):
    if cnx.user.eid == user_eid:
        yield cnx


class CachedValueMixin(object):
    """Mixin class providing methods to retrieve some value, specified through
    `value_name` attribute, in session data.
    """
    value_name = None
    session = None  # make pylint happy

    @property
    def cached_value(self):
        """Return cached value for the user, or None"""
        key = user_session_cache_key(self.session.user.eid, self.value_name)
        return self.session.data.get(key, None)

    def update_cached_value(self, value):
        """Update cached value for the user (modifying the set returned by cached_value may not be
        necessary depending on session data implementation, e.g. redis)
        """
        key = user_session_cache_key(self.session.user.eid, self.value_name)
        self.session.data[key] = value


class SyncSessionHook(hook.Hook):
    __abstract__ = True
    category = 'syncsession'


# user/groups synchronisation #################################################

class _GroupOperation(CachedValueMixin, hook.Operation):
    """Base class for group operation"""
    value_name = 'groups'

    def __init__(self, cnx, *args, **kwargs):
        """Override to get the group name before actual groups manipulation

        we may temporarily loose right access during a commit event, so
        no query should be emitted while comitting
        """
        rql = 'Any N WHERE G eid %(x)s, G name N'
        result = cnx.execute(rql, {'x': kwargs['group_eid']}, build_descr=False)
        hook.Operation.__init__(self, cnx, *args, **kwargs)
        self.group = result[0][0]


class _DeleteGroupOp(_GroupOperation):
    """Synchronize user when a in_group relation has been deleted"""

    def postcommit_event(self):
        cached_groups = self.cached_value
        if cached_groups is not None:
            cached_groups.remove(self.group)
            self.update_cached_value(cached_groups)


class _AddGroupOp(_GroupOperation):
    """Synchronize user when a in_group relation has been added"""

    def postcommit_event(self):
        cached_groups = self.cached_value
        if cached_groups is not None:
            cached_groups.add(self.group)
            self.update_cached_value(cached_groups)


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
        for session in get_user_sessions(self._cw, self.eidfrom):
            opcls(self._cw, session=session, group_eid=self.eidto)


class _CloseSessionOp(hook.Operation):
    """Close user's session when it has been deleted"""

    def postcommit_event(self):
        try:
            # remove cached groups for the user
            key = user_session_cache_key(self.session.user.eid, 'groups')
            self.session.data.pop(key, None)
        except BadConnectionId:
            pass  # already closed


class UserDeletedHook(SyncSessionHook):
    """Watch deletion of user to close its opened session"""
    __regid__ = 'closession'
    __select__ = SyncSessionHook.__select__ & is_instance('CWUser')
    events = ('after_delete_entity',)

    def __call__(self):
        for session in get_user_sessions(self._cw, self.entity.eid):
            _CloseSessionOp(self._cw, session=session)


# CWProperty hooks #############################################################


class _UserPropertyOperation(CachedValueMixin, hook.Operation):
    """Base class for property operation"""
    value_name = 'properties'
    key = None  # make pylint happy


class _ChangeUserCWPropertyOp(_UserPropertyOperation):
    """Synchronize cached user's properties when one has been added/updated"""
    value = None  # make pylint happy

    def postcommit_event(self):
        cached_props = self.cached_value
        if cached_props is not None:
            cached_props[self.key] = self.value
            self.update_cached_value(cached_props)


class _DelUserCWPropertyOp(_UserPropertyOperation):
    """Synchronize cached user's properties when one has been deleted"""

    def postcommit_event(self):
        cached_props = self.cached_value
        if cached_props is not None:
            cached_props.pop(self.key, None)
            self.update_cached_value(cached_props)


class _ChangeSiteWideCWPropertyOp(hook.Operation):
    """Synchronize site wide properties when one has been added/updated"""
    cwprop = None  # make pylint happy

    def postcommit_event(self):
        cwprop = self.cwprop
        if not cwprop.for_user:
            self.cnx.vreg['propertyvalues'][cwprop.pkey] = \
                self.cnx.vreg.typed_value(cwprop.pkey, cwprop.value)
        # if for_user is set, update is handled by a ChangeUserCWPropertyOp operation


class _DelSiteWideCWPropertyOp(hook.Operation):
    """Synchronize site wide properties when one has been deleted"""
    key = None  # make pylint happy

    def postcommit_event(self):
        self.cnx.vreg['propertyvalues'].pop(self.key, None)


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
            raise validation_error(self.entity, {('value', 'subject'): str(ex)})
        if cnx.user.matching_groups('managers'):
            _ChangeSiteWideCWPropertyOp(cnx, cwprop=self.entity)
        else:
            cnx.add_relation(self.entity.eid, 'for_user', cnx.user.eid)


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
            for session in get_user_sessions(cnx, entity.for_user[0].eid):
                _ChangeUserCWPropertyOp(cnx, session=session, key=key, value=value)
        else:
            _ChangeSiteWideCWPropertyOp(cnx, cwprop=self.entity)


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
            _DelSiteWideCWPropertyOp(cnx, key=self.entity.pkey)


class AddForUserRelationHook(SyncSessionHook):
    __regid__ = 'addcwpropforuser'
    __select__ = SyncSessionHook.__select__ & hook.match_rtype('for_user')
    events = ('after_add_relation',)

    def __call__(self):
        cnx = self._cw
        eidfrom = self.eidfrom
        if not cnx.entity_type(eidfrom) == 'CWProperty':
            return
        key, value = cnx.execute('Any K,V WHERE P eid %(x)s,P pkey K,P value V',
                                 {'x': eidfrom})[0]
        if cnx.vreg.property_info(key)['sitewide']:
            msg = _("site-wide property can't be set for user")
            raise validation_error(eidfrom, {('for_user', 'subject'): msg})
        for session in get_user_sessions(cnx, self.eidto):
            _ChangeUserCWPropertyOp(cnx, session=session, key=key, value=value)


class DelForUserRelationHook(AddForUserRelationHook):
    __regid__ = 'delcwpropforuser'
    events = ('after_delete_relation',)

    def __call__(self):
        cnx = self._cw
        key = cnx.execute('Any K WHERE P eid %(x)s, P pkey K', {'x': self.eidfrom})[0][0]
        cnx.transaction_data.setdefault('pendingrelations', []).append(
            (self.eidfrom, self.rtype, self.eidto))
        for session in get_user_sessions(cnx, self.eidto):
            _DelUserCWPropertyOp(cnx, session=session, key=key)
