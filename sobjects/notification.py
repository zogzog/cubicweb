"""some hooks and views to handle notification on entity's changes

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from base64 import b64encode, b64decode
from itertools import repeat
from time import time
try:
    from socket import gethostname
except ImportError:
    def gethostname(): # gae
        return 'XXX'

from logilab.common.textutils import normalize_text
from logilab.common.deprecation import class_renamed

from cubicweb import RegistryException
from cubicweb.selectors import implements, yes
from cubicweb.view import EntityView, Component
from cubicweb.common.mail import format_mail

from cubicweb.server.pool import PreCommitOperation
from cubicweb.server.hookhelper import SendMailOp
from cubicweb.server.hooksmanager import Hook


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
        mode = self.req.vreg.config['default-recipients-mode']
        if mode == 'users':
            # use unsafe execute else we may don't have the right to see users
            # to notify...
            execute = self.req.unsafe_execute
            dests = [(u.get_email(), u.property_value('ui.language'))
                     for u in execute(self.user_rql, build_descr=True, propagate=True).entities()]
        elif mode == 'default-dest-addrs':
            lang = self.vreg.property_value('ui.language')
            dests = zip(self.req.vreg.config['default-dest-addrs'], repeat(lang))
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

class NotificationView(EntityView):
    """abstract view implementing the email API

    all you have to do by default is :
    * set id and accepts attributes to match desired events and entity types
    * set a content attribute to define the content of the email (unless you
      override call)
    """
    # XXX refactor this class to work with len(rset) > 1

    msgid_timestamp = True

    def recipients(self):
        finder = self.vreg['components'].select('recipients_finder', self.req,
                                  rset=self.rset)
        return finder.recipients()

    def subject(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        subject = self.req._(self.message)
        etype = entity.dc_type()
        eid = entity.eid
        login = self.user_login()
        return self.req._('%(subject)s %(etype)s #%(eid)s (%(login)s)') % locals()

    def user_login(self):
        # req is actually a session (we are on the server side), and we have to
        # prevent nested internal session
        return self.req.actual_session().user.login

    def context(self, **kwargs):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        for key, val in kwargs.iteritems():
            if val and isinstance(val, unicode) and val.strip():
               kwargs[key] = self.req._(val)
        kwargs.update({'user': self.user_login(),
                       'eid': entity.eid,
                       'etype': entity.dc_type(),
                       'url': entity.absolute_url(),
                       'title': entity.dc_long_title(),})
        return kwargs

    def cell_call(self, row, col=0, **kwargs):
        self.w(self.req._(self.content) % self.context(**kwargs))

    def construct_message_id(self, eid):
        return construct_message_id(self.req.vreg.config.appid, eid, self.msgid_timestamp)

    def render_and_send(self, **kwargs):
        """generate and send an email message for this view"""
        self._kwargs = kwargs
        recipients = self.recipients()
        if not recipients:
            self.info('skipping %s notification, no recipients', self.id)
            return
        if not isinstance(recipients[0], tuple):
            from warnings import warn
            warn('recipients should now return a list of 2-uple (email, language)',
                 DeprecationWarning, stacklevel=1)
            lang = self.vreg.property_value('ui.language')
            recipients = zip(recipients, repeat(lang))
        if self.rset is not None:
            entity = self.rset.get_entity(self.row or 0, self.col or 0)
            # if the view is using timestamp in message ids, no way to reference
            # previous email
            if not self.msgid_timestamp:
                refs = [self.construct_message_id(eid)
                        for eid in entity.notification_references(self)]
            else:
                refs = ()
            msgid = self.construct_message_id(entity.eid)
        else:
            refs = ()
            msgid = None
        userdata = self.req.user_data()
        origlang = self.req.lang
        for emailaddr, lang in recipients:
            self.req.set_language(lang)
            # since the same view (eg self) may be called multiple time and we
            # need a fresh stream at each iteration, reset it explicitly
            self.w = None
            # XXX call render before subject to set .row/.col attributes on the
            #     view
            content = self.render(row=0, col=0, **kwargs)
            subject = self.subject()
            msg = format_mail(userdata, [emailaddr], content, subject,
                              config=self.req.vreg.config, msgid=msgid, references=refs)
            self.send([emailaddr], msg)
        # restore language
        self.req.set_language(origlang)

    def send(self, recipients, msg):
        SendMailOp(self.req, recipients=recipients, msg=msg)


def construct_message_id(appid, eid, withtimestamp=True):
    if withtimestamp:
        addrpart = 'eid=%s&timestamp=%.10f' % (eid, time())
    else:
        addrpart = 'eid=%s' % eid
    # we don't want any equal sign nor trailing newlines
    leftpart = b64encode(addrpart, '.-').rstrip().rstrip('=')
    return '<%s@%s.%s>' % (leftpart, appid, gethostname())


def parse_message_id(msgid, appid):
    if msgid[0] == '<':
        msgid = msgid[1:]
    if msgid[-1] == '>':
        msgid = msgid[:-1]
    try:
        values, qualif = msgid.split('@')
        padding = len(values) % 4
        values = b64decode(str(values + '='*padding), '.-')
        values = dict(v.split('=') for v in values.split('&'))
        fromappid, host = qualif.split('.', 1)
    except:
        return None
    if appid != fromappid or host != gethostname():
        return None
    return values


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
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        content = entity.printable_value(self.content_attr, format='text/plain')
        if content:
            contentformat = getattr(entity, self.content_attr + '_format', 'text/rest')
            content = normalize_text(content, 80, rest=contentformat=='text/rest')
        return super(ContentAddedView, self).context(content=content, **kwargs)

    def subject(self):
        entity = self.rset.get_entity(self.row or 0, self.col or 0)
        return  u'%s #%s (%s)' % (self.req.__('New %s' % entity.e_schema),
                                  entity.eid, self.user_login())

NormalizedTextView = class_renamed('NormalizedTextView', ContentAddedView)
