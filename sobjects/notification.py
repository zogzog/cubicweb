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
from cubicweb.server.pool import PreCommitOperation
from cubicweb.server.hookhelper import SendMailOp
from cubicweb.server.hooksmanager import Hook

parse_message_id = deprecated('parse_message_id is now defined in cubicweb.common.mail')


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

class RenderAndSendNotificationView(PreCommitOperation):
    """delay rendering of notification view until precommit"""
    def precommit_event(self):
        if self.view.rset and self.view.rset[0][0] in self.session.transaction_data.get('pendingeids', ()):
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
        if comment:
            comment = normalize_text(comment, 80,
                                     rest=entity.comment_format=='text/rest')
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
            contentformat = getattr(entity, self.content_attr + '_format', 'text/rest')
            content = normalize_text(content, 80, rest=contentformat=='text/rest')
        return super(ContentAddedView, self).context(content=content, **kwargs)

    def subject(self):
        entity = self.entity(self.row or 0, self.col or 0)
        return  u'%s #%s (%s)' % (self.req.__('New %s' % entity.e_schema),
                                  entity.eid, self.user_login())

NormalizedTextView = class_renamed('NormalizedTextView', ContentAddedView)
