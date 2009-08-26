"""some hooks to handle notification on entity's changes

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.textutils import normalize_text

from cubicweb import RegistryException
from cubicweb.selectors import entity_implements
from cubicweb.server import hook


class RenderAndSendNotificationView(hook.Operation):
    """delay rendering of notification view until precommit"""
    def precommit_event(self):
        view = self.view
        if view.cw_rset and self.session.deleted_in_transaction(view.cw_rset[cw_rset.cw_row or 0][cw_rset.cw_col or 0]):
            return # entity added and deleted in the same transaction
        self.view.render_and_send(**getattr(self, 'viewargs', {}))


class NotificationHook(hook.Hook):
    __abstract__ = True
    category = 'notification'

    def select_view(self, vid, rset, row=0, col=0):
        return self._cw.vreg['views'].select_or_none(vid, self._cw,
                                                     rset=rset, row=0, col=0)


class StatusChangeHook(NotificationHook):
    """notify when a workflowable entity has its state modified"""
    __id__ = 'notifystatuschange'
    __select__ = NotificationHook.__select__ & entity_implements('TrInfo')
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
    __id__ = 'notifyrelationchange'
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
    __id__ = 'notifyentitychange'
    events = ('after_add_entity', 'after_update_entity')

    def __call__(self):
        rset = self.entity.as_rset()
        view = self.select_view('notif_%s' % self.event, rset=rset, row=0)
        if view is None:
            return
        RenderAndSendNotificationView(self._cw, view=view)


# supervising ##################################################################

class SomethingChangedHook(NotificationHook):
    __id__ = 'supervising'
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
                if not (self.entity.edited_attributes - frozenset(('eid', 'modification_date',
                                                                   'last_login_time'))):
                    # don't record last_login_time update which are done
                    # automatically at login time
                    return False
        self._cw.transaction_data.setdefault('pendingchanges', []).append(
            (event, self))
        return True


class EntityDeleteHook(SomethingChangedHook):
    __id__ = 'supervisingentitydel'
    events = ('before_delete_entity',)

    def _call(self):
        try:
            title = self.entity.dc_title()
        except:
            # may raise an error during deletion process, for instance due to
            # missing required relation
            title = '#%s' % eid
        self._cw.transaction_data.setdefault('pendingchanges', []).append(
            ('delete_entity', (self.eid, str(self.entity.e_schema), title)))
        return True
