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
"""some views to handle notification on data changes"""

__docformat__ = "restructuredtext en"
_ = unicode

from itertools import repeat

from logilab.common.textutils import normalize_text
from logilab.common.deprecation import class_renamed, class_moved, deprecated

from cubicweb.selectors import yes
from cubicweb.view import Component
from cubicweb.mail import NotificationView, SkipEmail
from cubicweb.server.hook import SendMailOp


class RecipientsFinder(Component):
    """this component is responsible to find recipients of a notification

    by default user's with their email set are notified if any, else the default
    email addresses specified in the configuration are used
    """
    __regid__ = 'recipients_finder'
    __select__ = yes()
    user_rql = ('Any X,E,A WHERE X is CWUser, X in_state S, S name "activated",'
                'X primary_email E, E address A')

    def recipients(self):
        mode = self._cw.vreg.config['default-recipients-mode']
        if mode == 'users':
            execute = self._cw.execute
            dests = [(u.cw_adapt_to('IEmailable').get_email(),
                      u.property_value('ui.language'))
                     for u in execute(self.user_rql, build_descr=True).entities()]
        elif mode == 'default-dest-addrs':
            lang = self._cw.vreg.property_value('ui.language')
            dests = zip(self._cw.vreg.config['default-dest-addrs'], repeat(lang))
        else: # mode == 'none'
            dests = []
        return dests


# abstract or deactivated notification views and mixin ########################

class NotificationView(NotificationView):
    """overriden to delay actual sending of mails to a commit operation by
    default
    """
    def send_on_commit(self, recipients, msg):
        SendMailOp(self._cw, recipients=recipients, msg=msg)
    send = send_on_commit


class StatusChangeMixIn(object):
    __regid__ = 'notif_status_change'
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
    __regid__ = 'notif_after_add_entity'
    msgid_timestamp = False
    message = _('new')
    content = """
%(title)s

%(content)s

url: %(url)s
"""

    def context(self, **kwargs):
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
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
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        return  u'%s #%s (%s)' % (self._cw.__('New %s' % entity.e_schema),
                                  entity.eid, self.user_data['login'])


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
    __regid__ = 'notif_entity_updated'
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
        changes = self._cw.transaction_data['changes'][self.cw_rset[0][0]]
        _ = self._cw._
        formatted_changes = []
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        for attr, oldvalue, newvalue in sorted(changes):
            # check current user has permission to see the attribute
            rschema = self._cw.vreg.schema[attr]
            if rschema.final:
                rdef = entity.e_schema.rdef(rschema)
                if not rdef.has_perm(self._cw, 'read', eid=self.cw_rset[0][0]):
                    continue
            # XXX suppose it's a subject relation...
            elif not rschema.has_perm(self._cw, 'read',
                                      fromeid=self.cw_rset[0][0]):
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
        entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        return  u'%s #%s (%s)' % (self._cw.__('Updated %s' % entity.e_schema),
                                  entity.eid, self.user_data['login'])


from cubicweb.hooks.notification import RenderAndSendNotificationView
from cubicweb.mail import parse_message_id

NormalizedTextView = class_renamed('NormalizedTextView', ContentAddedView)
RenderAndSendNotificationView = class_moved(RenderAndSendNotificationView)
parse_message_id = deprecated('parse_message_id is now defined in cubicweb.mail')(parse_message_id)

