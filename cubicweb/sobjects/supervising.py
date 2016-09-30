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
"""some hooks and views to handle supervising of any data changes"""

from cubicweb import UnknownEid
from cubicweb.predicates import none_rset
from cubicweb.schema import display_name
from cubicweb.view import Component
from cubicweb.mail import format_mail
from cubicweb.server.hook import SendMailOp


def filter_changes(changes):
    """
    * when an entity has been deleted:
      * don't show deletion of its relations
      * don't show related TrInfo deletion if any
    * when an entity has been added don't show owned_by relation addition
    * don't show new TrInfo entities if any
    """
    # first build an index of changes
    index = {}
    added, deleted = set(), set()
    for change in changes[:]:
        event, changedescr = change
        if event == 'add_entity':
            entity = changedescr.entity
            added.add(entity.eid)
            if entity.e_schema == 'TrInfo':
                changes.remove(change)
                event = 'change_state'
                change = (event,
                          (entity.wf_info_for[0],
                           entity.from_state[0], entity.to_state[0]))
                changes.append(change)
        elif event == 'delete_entity':
            deleted.add(changedescr[0])
        index.setdefault(event, set()).add(change)
    for key in ('delete_relation', 'add_relation'):
        for change in index.get(key, {}).copy():
            if change[1].rtype == 'in_state':
                index[key].remove(change)
    # filter changes
    for eid in added:
        try:
            for change in index['add_relation'].copy():
                changedescr = change[1]
                # skip meta-relations which are set automatically
                # XXX generate list below using rtags (category = 'generated')
                if changedescr.rtype in ('created_by', 'owned_by', 'is', 'is_instance_of',
                                      'from_state', 'to_state', 'by_transition',
                                      'wf_info_for') \
                       and changedescr.eidfrom == eid:
                    index['add_relation'].remove(change)
        except KeyError:
            break
    for eid in deleted:
        try:
            for change in index['delete_relation'].copy():
                if change[1].eidfrom == eid:
                    index['delete_relation'].remove(change)
                elif change[1].eidto == eid:
                    index['delete_relation'].remove(change)
                    if change[1].rtype == 'wf_info_for':
                        for change_ in index['delete_entity'].copy():
                            if change_[1].eidfrom == change[1].eidfrom:
                                index['delete_entity'].remove(change_)
        except KeyError:
            break
    for change in changes:
        event, changedescr = change
        if change in index[event]:
            yield change


class SupervisionEmailView(Component):
    """view implementing the email API for data changes supervision notification
    """
    __regid__ = 'supervision_notif'
    __select__ = none_rset()

    def recipients(self):
        return self._cw.vreg.config['supervising-addrs']

    def subject(self):
        return self._cw._('[%s supervision] changes summary') % self._cw.vreg.config.appid

    def call(self, changes):
        user = self._cw.user
        self.w(self._cw._('user %s has made the following change(s):\n\n')
               % user.login)
        for event, changedescr in filter_changes(changes):
            self.w(u'* ')
            getattr(self, event)(changedescr)
            self.w(u'\n\n')

    def _entity_context(self, entity):
        return {'eid': entity.eid,
                'etype': entity.dc_type().lower(),
                'title': entity.dc_title()}

    def add_entity(self, changedescr):
        msg = self._cw._('added %(etype)s #%(eid)s (%(title)s)')
        self.w(u'%s\n' % (msg % self._entity_context(changedescr.entity)))
        self.w(u'  %s' % changedescr.entity.absolute_url())

    def update_entity(self, changedescr):
        msg = self._cw._('updated %(etype)s #%(eid)s (%(title)s)')
        self.w(u'%s\n' % (msg % self._entity_context(changedescr.entity)))
        # XXX print changes
        self.w(u'  %s' % changedescr.entity.absolute_url())

    def delete_entity(self, args):
        eid, etype, title = args
        msg = self._cw._('deleted %(etype)s #%(eid)s (%(title)s)')
        etype = display_name(self._cw, etype).lower()
        self.w(msg % locals())

    def change_state(self, args):
        _ = self._cw._
        entity, fromstate, tostate = args
        msg = _('changed state of %(etype)s #%(eid)s (%(title)s)')
        self.w(u'%s\n' % (msg % self._entity_context(entity)))
        self.w(_('  from state %(fromstate)s to state %(tostate)s\n' %
                 {'fromstate': _(fromstate.name), 'tostate': _(tostate.name)}))
        self.w(u'  %s' % entity.absolute_url())

    def _relation_context(self, changedescr):
        cnx = self._cw
        def describe(eid):
            try:
                return cnx._(cnx.entity_type(eid)).lower()
            except UnknownEid:
                # may occurs when an entity has been deleted from an external
                # source and we're cleaning its relation
                return cnx._('unknown external entity')
        eidfrom, rtype, eidto = changedescr.eidfrom, changedescr.rtype, changedescr.eidto
        return {'rtype': cnx._(rtype),
                'eidfrom': eidfrom,
                'frometype': describe(eidfrom),
                'eidto': eidto,
                'toetype': describe(eidto)}

    def add_relation(self, changedescr):
        msg = self._cw._('added relation %(rtype)s from %(frometype)s #%(eidfrom)s to %(toetype)s #%(eidto)s')
        self.w(msg % self._relation_context(changedescr))

    def delete_relation(self, changedescr):
        msg = self._cw._('deleted relation %(rtype)s from %(frometype)s #%(eidfrom)s to %(toetype)s #%(eidto)s')
        self.w(msg % self._relation_context(changedescr))


class SupervisionMailOp(SendMailOp):
    """special send email operation which should be done only once for a bunch
    of changes
    """
    def _get_view(self):
        return self.cnx.vreg['components'].select('supervision_notif', self.cnx)

    def _prepare_email(self):
        cnx = self.cnx
        config = cnx.vreg.config
        uinfo = {'email': config['sender-addr'],
                 'name': config['sender-name']}
        view = self._get_view()
        content = view.render(changes=cnx.transaction_data.get('pendingchanges'))
        recipients = view.recipients()
        msg = format_mail(uinfo, recipients, content, view.subject(), config=config)
        self.to_send = [(msg, recipients)]

    def postcommit_event(self):
        self._prepare_email()
        SendMailOp.postcommit_event(self)
