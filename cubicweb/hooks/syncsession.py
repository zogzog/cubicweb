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
from cubicweb import UnknownProperty, validation_error
from cubicweb.predicates import is_instance
from cubicweb.server import hook


class SyncSessionHook(hook.Hook):
    __abstract__ = True
    category = 'syncsession'


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
        if not entity.for_user:
            _ChangeSiteWideCWPropertyOp(cnx, cwprop=self.entity)


class DeleteCWPropertyHook(AddCWPropertyHook):
    __regid__ = 'delcwprop'
    events = ('before_delete_entity',)

    def __call__(self):
        cnx = self._cw
        for eidfrom, rtype, eidto in cnx.transaction_data.get('pendingrelations', ()):
            if rtype == 'for_user' and eidfrom == self.entity.eid:
                # not need to sync user specific properties
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


class DelForUserRelationHook(AddForUserRelationHook):
    __regid__ = 'delcwpropforuser'
    events = ('after_delete_relation',)

    def __call__(self):
        cnx = self._cw
        cnx.transaction_data.setdefault('pendingrelations', []).append(
            (self.eidfrom, self.rtype, self.eidto))
