# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""some hooks to handle notification on entity's changes

"""
__docformat__ = "restructuredtext en"

from logilab.common.textutils import normalize_text

from cubicweb import RegistryNotFound
from cubicweb.selectors import is_instance
from cubicweb.server import hook
from cubicweb.sobjects.supervising import SupervisionMailOp

class RenderAndSendNotificationView(hook.Operation):
    """delay rendering of notification view until precommit"""
    def precommit_event(self):
        view = self.view
        if view.cw_rset is not None and not view.cw_rset:
            return # entity added and deleted in the same transaction (cache effect)
        if view.cw_rset and self.session.deleted_in_transaction(view.cw_rset[view.cw_row or 0][view.cw_col or 0]):
            return # entity added and deleted in the same transaction
        self.view.render_and_send(**getattr(self, 'viewargs', {}))


class NotificationHook(hook.Hook):
    __abstract__ = True
    category = 'notification'

    def select_view(self, vid, rset, row=0, col=0):
        try:
            return self._cw.vreg['views'].select_or_none(vid, self._cw, rset=rset,
                                                         row=row, col=col)
        except RegistryNotFound: # can happen in some config
                                 # (e.g. repo only config with no
                                 # notification views registered by
                                 # the instance's cubes)
            return None


class StatusChangeHook(NotificationHook):
    """notify when a workflowable entity has its state modified"""
    __regid__ = 'notifystatuschange'
    __select__ = NotificationHook.__select__ & is_instance('TrInfo')
    events = ('after_add_entity',)

    def __call__(self):
        entity = self.entity
        if not entity.from_state: # not a transition
            return
        rset = entity.related('wf_info_for')
        view = self.select_view('notif_status_change', rset=rset, row=0)
        if view is None:
            return
        comment = entity.printable_value('comment', format='text/plain')
        # XXX don't try to wrap rest until we've a proper transformation (see
        # #103822)
        if comment and entity.comment_format != 'text/rest':
            comment = normalize_text(comment, 80)
        RenderAndSendNotificationView(self._cw, view=view, viewargs={
            'comment': comment, 'previous_state': entity.previous_state.name,
            'current_state': entity.new_state.name})

class RelationChangeHook(NotificationHook):
    __regid__ = 'notifyrelationchange'
    events = ('before_add_relation', 'after_add_relation',
              'before_delete_relation', 'after_delete_relation')

    def __call__(self):
        """if a notification view is defined for the event, send notification
        email defined by the view
        """
        rset = self._cw.eid_rset(self.eidfrom)
        view = self.select_view('notif_%s_%s' % (self.event,  self.rtype),
                                rset=rset, row=0)
        if view is None:
            return
        RenderAndSendNotificationView(self._cw, view=view)


class EntityChangeHook(NotificationHook):
    """if a notification view is defined for the event, send notification
    email defined by the view
    """
    __regid__ = 'notifyentitychange'
    events = ('after_add_entity', 'after_update_entity')

    def __call__(self):
        rset = self.entity.as_rset()
        view = self.select_view('notif_%s' % self.event, rset=rset, row=0)
        if view is None:
            return
        RenderAndSendNotificationView(self._cw, view=view)


class EntityUpdatedNotificationOp(hook.SingleLastOperation):

    def precommit_event(self):
        session = self.session
        for eid in session.transaction_data['changes']:
            view = session.vreg['views'].select('notif_entity_updated', session,
                                                rset=session.eid_rset(eid),
                                                row=0)
            RenderAndSendNotificationView(session, view=view)


class EntityUpdateHook(NotificationHook):
    __regid__ = 'notifentityupdated'
    __abstract__ = True # do not register by default
    __select__ = NotificationHook.__select__ & hook.from_dbapi_query()
    events = ('before_update_entity',)
    skip_attrs = set()

    def __call__(self):
        session = self._cw
        if session.added_in_transaction(self.entity.eid):
            return # entity is being created
        # then compute changes
        attrs = [k for k in self.entity.cw_edited
                 if not k in self.skip_attrs]
        if not attrs:
            return
        changes = session.transaction_data.setdefault('changes', {})
        thisentitychanges = changes.setdefault(self.entity.eid, set())
        rqlsel, rqlrestr = [], ['X eid %(x)s']
        for i, attr in enumerate(attrs):
            var = chr(65+i)
            rqlsel.append(var)
            rqlrestr.append('X %s %s' % (attr, var))
        rql = 'Any %s WHERE %s' % (','.join(rqlsel), ','.join(rqlrestr))
        rset = session.execute(rql, {'x': self.entity.eid})
        for i, attr in enumerate(attrs):
            oldvalue = rset[0][i]
            newvalue = self.entity.cw_edited[attr]
            if oldvalue != newvalue:
                thisentitychanges.add((attr, oldvalue, newvalue))
        if thisentitychanges:
            EntityUpdatedNotificationOp(session)


# supervising ##################################################################

class SomethingChangedHook(NotificationHook):
    __regid__ = 'supervising'
    __select__ = NotificationHook.__select__ & hook.from_dbapi_query()
    events = ('before_add_relation', 'before_delete_relation',
              'after_add_entity', 'before_update_entity')

    def __call__(self):
        dest = self._cw.vreg.config['supervising-addrs']
        if not dest: # no supervisors, don't do this for nothing...
            return
        if self._call():
            SupervisionMailOp(self._cw)

    def _call(self):
        event = self.event.split('_', 1)[1]
        if event == 'update_entity':
            if self._cw.added_in_transaction(self.entity.eid):
                return False
            if self.entity.e_schema == 'CWUser':
                if not (frozenset(self.entity.cw_edited)
                        - frozenset(('eid', 'modification_date',
                                     'last_login_time'))):
                    # don't record last_login_time update which are done
                    # automatically at login time
                    return False
        self._cw.transaction_data.setdefault('pendingchanges', []).append(
            (event, self))
        return True


class EntityDeleteHook(SomethingChangedHook):
    __regid__ = 'supervisingentitydel'
    events = ('before_delete_entity',)

    def _call(self):
        try:
            title = self.entity.dc_title()
        except:
            # may raise an error during deletion process, for instance due to
            # missing required relation
            title = '#%s' % self.entity.eid
        self._cw.transaction_data.setdefault('pendingchanges', []).append(
            ('delete_entity', (self.entity.eid, self.entity.__regid__, title)))
        return True
