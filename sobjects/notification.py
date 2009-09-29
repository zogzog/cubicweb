"""some hooks and views to handle notification on entity's changes

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from itertools import repeat

from logilab.common.textutils import normalize_text
from logilab.common.deprecation import class_renamed, deprecated

from cubicweb import RegistryException
from cubicweb.selectors import implements, yes
from cubicweb.view import Component
from cubicweb.common.mail import NotificationView, parse_message_id
from cubicweb.server.pool import PreCommitOperation, SingleLastOperation
from cubicweb.server.hookhelper import SendMailOp
from cubicweb.server.hooksmanager import Hook

parse_message_id = deprecated('parse_message_id is now defined in cubicweb.common.mail')(parse_message_id)


class RecipientsFinder(Component):
    """this component is responsible to find recipients of a notification

    by default user's with their email set are notified if any, else the default
    email addresses specified in the configuration are used
    """
    id = 'recipients_finder'
    __select__ = yes()
    user_rql = ('Any X,E,A WHERE X is CWUser, X in_state S, S name "activated",'
                'X primary_email E, E address A')

    def recipients(self):
        mode = self.config['default-recipients-mode']
        if mode == 'users':
            # use unsafe execute else we may don't have the right to see users
            # to notify...
            execute = self.req.unsafe_execute
            dests = [(u.get_email(), u.property_value('ui.language'))
                     for u in execute(self.user_rql, build_descr=True, propagate=True).entities()]
        elif mode == 'default-dest-addrs':
            lang = self.vreg.property_value('ui.language')
            dests = zip(self.config['default-dest-addrs'], repeat(lang))
        else: # mode == 'none'
            dests = []
        return dests


# hooks #######################################################################

class EntityUpdatedNotificationOp(SingleLastOperation):

    def precommit_event(self):
        session = self.session
        for eid in session.transaction_data['changes']:
            view = session.vreg['views'].select('notif_entity_updated', session,
                                                rset=session.eid_rset(eid),
                                                row=0)
            RenderAndSendNotificationView(session, view=view)

    def commit_event(self):
        pass


class RenderAndSendNotificationView(PreCommitOperation):
    """delay rendering of notification view until precommit"""
    def precommit_event(self):
        view = self.view
        if view.rset is not None and not view.rset:
            return # entity added and deleted in the same transaction (cache effect)
        if view.rset and view.rset[0][0] in self.session.transaction_data.get('pendingeids', ()):
            return # entity added and deleted in the same transaction
        self.view.render_and_send(**getattr(self, 'viewargs', {}))


class StatusChangeHook(Hook):
    """notify when a workflowable entity has its state modified"""
    events = ('after_add_entity',)
    accepts = ('TrInfo',)

    def call(self, session, entity):
        if not entity.from_state: # not a transition
            return
        rset = entity.related('wf_info_for')
        try:
            view = session.vreg['views'].select('notif_status_change', session,
                                                rset=rset, row=0)
        except RegistryException:
            return
        comment = entity.printable_value('comment', format='text/plain')
        # XXX don't try to wrap rest until we've a proper transformation (see
        # #103822)
        if comment and entity.comment_format != 'text/rest':
            comment = normalize_text(comment, 80)
        RenderAndSendNotificationView(session, view=view, viewargs={
            'comment': comment, 'previous_state': entity.previous_state.name,
            'current_state': entity.new_state.name})


class RelationChangeHook(Hook):
    events = ('before_add_relation', 'after_add_relation',
              'before_delete_relation', 'after_delete_relation')
    accepts = ('Any',)
    def call(self, session, fromeid, rtype, toeid):
        """if a notification view is defined for the event, send notification
        email defined by the view
        """
        rset = session.eid_rset(fromeid)
        vid = 'notif_%s_%s' % (self.event,  rtype)
        try:
            view = session.vreg['views'].select(vid, session, rset=rset, row=0)
        except RegistryException:
            return
        RenderAndSendNotificationView(session, view=view)


class EntityChangeHook(Hook):
    events = ('after_add_entity',
              'after_update_entity')
    accepts = ('Any',)
    def call(self, session, entity):
        """if a notification view is defined for the event, send notification
        email defined by the view
        """
        rset = entity.as_rset()
        vid = 'notif_%s' % self.event
        try:
            view = session.vreg['views'].select(vid, session, rset=rset, row=0)
        except RegistryException:
            return
        RenderAndSendNotificationView(session, view=view)

class EntityUpdateHook(Hook):
    events = ('before_update_entity',)
    accepts = ()
    skip_attrs = set()

    def call(self, session, entity):
        if entity.eid in session.transaction_data.get('neweids', ()):
            return # entity is being created
        if session.is_super_session:
            return # ignore changes triggered by hooks
        # then compute changes
        changes = session.transaction_data.setdefault('changes', {})
        thisentitychanges = changes.setdefault(entity.eid, set())
        attrs = [k for k in entity.edited_attributes if not k in self.skip_attrs]
        if not attrs:
            return
        rqlsel, rqlrestr = [], ['X eid %(x)s']
        for i, attr in enumerate(attrs):
            var = chr(65+i)
            rqlsel.append(var)
            rqlrestr.append('X %s %s' % (attr, var))
        rql = 'Any %s WHERE %s' % (','.join(rqlsel), ','.join(rqlrestr))
        rset = session.execute(rql, {'x': entity.eid}, 'x')
        for i, attr in enumerate(attrs):
            oldvalue = rset[0][i]
            newvalue = entity[attr]
            if oldvalue != newvalue:
                thisentitychanges.add((attr, oldvalue, newvalue))
        if thisentitychanges:
            EntityUpdatedNotificationOp(session)

# abstract or deactivated notification views and mixin ########################

class NotificationView(NotificationView):
    """overriden to delay actual sending of mails to a commit operation by
    default
    """

    def send_on_commit(self, recipients, msg):
        SendMailOp(self.req, recipients=recipients, msg=msg)
    send = send_on_commit

class StatusChangeMixIn(object):
    id = 'notif_status_change'
    msgid_timestamp = True
    message = _('status changed')
    content = _("""
%(user)s changed status from <%(previous_state)s> to <%(current_state)s> for entity
'%(title)s'

%(comment)s

url: %(url)s
""")


###############################################################################
# Actual notification views.                                                  #
#                                                                             #
# disable them at the recipients_finder level if you don't want them          #
###############################################################################

# XXX should be based on dc_title/dc_description, no?

class ContentAddedView(NotificationView):
    """abstract class for notification on entity/relation

    all you have to do by default is :
    * set id and __select__ attributes to match desired events and entity types
    * set a content attribute to define the content of the email (unless you
      override call)
    """
    __abstract__ = True
    id = 'notif_after_add_entity'
    msgid_timestamp = False
    message = _('new')
    content = """
%(title)s

%(content)s

url: %(url)s
"""

    def context(self, **kwargs):
        entity = self.entity(self.row or 0, self.col or 0)
        content = entity.printable_value(self.content_attr, format='text/plain')
        if content:
            contentformat = getattr(entity, self.content_attr + '_format',
                                    'text/rest')
            # XXX don't try to wrap rest until we've a proper transformation (see
            # #103822)
            if contentformat != 'text/rest':
                content = normalize_text(content, 80)
        return super(ContentAddedView, self).context(content=content, **kwargs)

    def subject(self):
        entity = self.entity(self.row or 0, self.col or 0)
        return  u'%s #%s (%s)' % (self.req.__('New %s' % entity.e_schema),
                                  entity.eid, self.user_data['login'])

NormalizedTextView = class_renamed('NormalizedTextView', ContentAddedView)

def format_value(value):
    if isinstance(value, unicode):
        return u'"%s"' % value
    return value

class EntityUpdatedNotificationView(NotificationView):
    """abstract class for notification on entity/relation

    all you have to do by default is :
    * set id and __select__ attributes to match desired events and entity types
    * set a content attribute to define the content of the email (unless you
      override call)
    """
    __abstract__ = True
    id = 'notif_entity_updated'
    msgid_timestamp = False
    message = _('updated')
    no_detailed_change_attrs = ()
    content = """
Properties have been updated by %(user)s:

%(changes)s

url: %(url)s
"""

    def context(self, **kwargs):
        context = super(EntityUpdatedNotificationView, self).context(**kwargs)
        changes = self.req.transaction_data['changes'][self.rset[0][0]]
        _ = self.req._
        formatted_changes = []
        for attr, oldvalue, newvalue in sorted(changes):
            # check current user has permission to see the attribute
            rschema = self.vreg.schema[attr]
            if rschema.is_final():
                if not rschema.has_perm(self.req, 'read', eid=self.rset[0][0]):
                    continue
            # XXX suppose it's a subject relation...
            elif not rschema.has_perm(self.req, 'read', fromeid=self.rset[0][0]):
                continue
            if attr in self.no_detailed_change_attrs:
                msg = _('%s updated') % _(attr)
            elif oldvalue not in (None, ''):
                msg = _('%(attr)s updated from %(oldvalue)s to %(newvalue)s') % {
                    'attr': _(attr),
                    'oldvalue': format_value(oldvalue),
                    'newvalue': format_value(newvalue)}
            else:
                msg = _('%(attr)s set to %(newvalue)s') % {
                    'attr': _(attr), 'newvalue': format_value(newvalue)}
            formatted_changes.append('* ' + msg)
        if not formatted_changes:
            # current user isn't allowed to see changes, skip this notification
            raise SkipEmail()
        context['changes'] = '\n'.join(formatted_changes)
        return context

    def subject(self):
        entity = self.entity(self.row or 0, self.col or 0)
        return  u'%s #%s (%s)' % (self.req.__('Updated %s' % entity.e_schema),
                                  entity.eid, self.user_data['login'])
