"""some hooks and views to handle supervising of any data changes


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb import UnknownEid
from cubicweb.selectors import none_rset
from cubicweb.common.view import Component
from cubicweb.common.mail import format_mail
from cubicweb.server.hooksmanager import Hook
from cubicweb.server.hookhelper import SendMailOp


class SomethingChangedHook(Hook):
    events = ('before_add_relation', 'before_delete_relation',
              'after_add_entity', 'before_update_entity')
    accepts = ('Any',)
    
    def call(self, session, *args):
        dest = self.config['supervising-addrs']
        if not dest: # no supervisors, don't do this for nothing...
            return
        self.session = session
        if self._call(*args):
            SupervisionMailOp(session)
        
    def _call(self, *args):
        if self._event() == 'update_entity' and args[0].e_schema == 'EUser':
            updated = set(args[0].iterkeys())
            if not (updated - frozenset(('eid', 'modification_date', 'last_login_time'))):
                # don't record last_login_time update which are done 
                # automatically at login time
                return False
        self.session.add_query_data('pendingchanges', (self._event(), args))
        return True
        
    def _event(self):
        return self.event.split('_', 1)[1]


class EntityDeleteHook(SomethingChangedHook):
    events = ('before_delete_entity',)
    
    def _call(self, eid):
        entity = self.session.entity(eid)
        try:
            title = entity.dc_title()
        except:
            # may raise an error during deletion process, for instance due to
            # missing required relation
            title = '#%s' % eid
        self.session.add_query_data('pendingchanges',
                                    ('delete_entity',
                                     (eid, str(entity.e_schema),
                                      title)))
        return True


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
            entity = changedescr[0]
            added.add(entity.eid)
            if entity.e_schema == 'TrInfo':
                changes.remove(change)
                if entity.from_state:
                    try:
                        changes.remove( ('delete_relation', 
                                         (entity.wf_info_for[0].eid, 'in_state', 
                                          entity.from_state[0].eid)) )
                    except ValueError:
                        pass
                    try:
                        changes.remove( ('add_relation', 
                                         (entity.wf_info_for[0].eid, 'in_state', 
                                          entity.to_state[0].eid)) )
                    except ValueError:
                        pass
                    event = 'change_state'
                    change = (event, 
                              (entity.wf_info_for[0],
                               entity.from_state[0], entity.to_state[0]))
                    changes.append(change)
        elif event == 'delete_entity':
            deleted.add(changedescr[0])
        index.setdefault(event, set()).add(change)
    # filter changes
    for eid in added:
        try:
            for change in index['add_relation'].copy():
                changedescr = change[1]
                # skip meta-relations which are set automatically
                # XXX generate list below using rtags (category = 'generated')
                if changedescr[1] in ('created_by', 'owned_by', 'is', 'is_instance_of',
                                      'from_state', 'to_state', 'wf_info_for',) \
                       and changedescr[0] == eid:
                    index['add_relation'].remove(change)
                # skip in_state relation if the entity is being created
                # XXX this may be automatized by skipping all mandatory relation
                #     at entity creation time
                elif changedescr[1] == 'in_state' and changedescr[0] in added:
                    index['add_relation'].remove(change)
                    
        except KeyError:
            break
    for eid in deleted:
        try:
            for change in index['delete_relation'].copy():
                fromeid, rtype, toeid = change[1]
                if fromeid == eid:
                    index['delete_relation'].remove(change)
                elif toeid == eid:
                    index['delete_relation'].remove(change)
                    if rtype == 'wf_info_for':
                        for change in index['delete_entity'].copy():
                            if change[1][0] == fromeid:
                                index['delete_entity'].remove(change)
        except KeyError:
            break
    for change in changes:
        event, changedescr = change
        if change in index[event]:
            yield change


class SupervisionEmailView(Component):
    """view implementing the email API for data changes supervision notification
    """
    __select__ = none_rset()
    id = 'supervision_notif'

    def recipients(self):
        return self.config['supervising-addrs']
        
    def subject(self):
        return self.req._('[%s supervision] changes summary') % self.config.appid
    
    def call(self, changes):
        user = self.req.actual_session().user
        self.w(self.req._('user %s has made the following change(s):\n\n')
               % user.login)
        for event, changedescr in filter_changes(changes):
            self.w(u'* ')
            getattr(self, event)(*changedescr)
            self.w(u'\n\n')

    def _entity_context(self, entity):
        return {'eid': entity.eid,
                'etype': entity.dc_type().lower(),
                'title': entity.dc_title()}
    
    def add_entity(self, entity):
        msg = self.req._('added %(etype)s #%(eid)s (%(title)s)')
        self.w(u'%s\n' % (msg % self._entity_context(entity)))
        self.w(u'  %s' % entity.absolute_url())
            
    def update_entity(self, entity):
        msg = self.req._('updated %(etype)s #%(eid)s (%(title)s)')
        self.w(u'%s\n' % (msg % self._entity_context(entity)))
        # XXX print changes
        self.w(u'  %s' % entity.absolute_url())
            
    def delete_entity(self, eid, etype, title):
        msg = self.req._('deleted %(etype)s #%(eid)s (%(title)s)')
        etype = display_name(self.req, etype).lower()
        self.w(msg % locals())
        
    def change_state(self, entity, fromstate, tostate):
        msg = self.req._('changed state of %(etype)s #%(eid)s (%(title)s)')
        self.w(u'%s\n' % (msg % self._entity_context(entity)))
        self.w(_('  from state %(fromstate)s to state %(tostate)s\n' % 
                 {'fromstate': _(fromstate.name), 'tostate': _(tostate.name)}))
        self.w(u'  %s' % entity.absolute_url())
        
    def _relation_context(self, fromeid, rtype, toeid):
        _ = self.req._
        session = self.req.actual_session()
        def describe(eid):
            try:
                return _(session.describe(eid)[0]).lower()
            except UnknownEid:
                # may occurs when an entity has been deleted from an external
                # source and we're cleaning its relation
                return _('unknown external entity')
        return {'rtype': _(rtype),
                'fromeid': fromeid,
                'frometype': describe(fromeid),
                'toeid': toeid,
                'toetype': describe(toeid)}
        
    def add_relation(self, fromeid, rtype, toeid):
        msg = self.req._('added relation %(rtype)s from %(frometype)s #%(fromeid)s to %(toetype)s #%(toeid)s')
        self.w(msg % self._relation_context(fromeid, rtype, toeid))

    def delete_relation(self, fromeid, rtype, toeid):
        msg = self.req._('deleted relation %(rtype)s from %(frometype)s #%(fromeid)s to %(toetype)s #%(toeid)s')
        self.w(msg % self._relation_context(fromeid, rtype, toeid))
        
                
class SupervisionMailOp(SendMailOp):
    """special send email operation which should be done only once for a bunch
    of changes
    """
    def _get_view(self):
        return self.session.vreg.select_component('supervision_notif',
                                                  self.session, None)
        
    def _prepare_email(self):
        session = self.session
        config = session.vreg.config
        uinfo = {'email': config['sender-addr'],
                 'name': config['sender-name']}
        view = self._get_view()
        content = view.dispatch(changes=session.query_data('pendingchanges'))
        recipients = view.recipients()
        msg = format_mail(uinfo, recipients, content, view.subject(), config=config)
        self.to_send = [(msg, recipients)]

    def commit_event(self):
        self._prepare_email()
        SendMailOp.commit_event(self)
