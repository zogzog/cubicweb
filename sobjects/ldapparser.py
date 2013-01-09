# copyright 2011-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb ldap feed source

unlike ldapuser source, this source is copy based and will import ldap content
(beside passwords for authentication) into the system source.
"""
from __future__ import with_statement

from logilab.common.decorators import cached, cachedproperty
from logilab.common.shellutils import generate_password

from cubicweb import Binary, ConfigurationError
from cubicweb.server.utils import crypt_password
from cubicweb.server.sources import datafeed


class DataFeedLDAPAdapter(datafeed.DataFeedParser):
    __regid__ = 'ldapfeed'
    # attributes that may appears in source user_attrs dict which are not
    # attributes of the cw user
    non_attribute_keys = set(('email',))

    @cachedproperty
    def searchfilterstr(self):
        """ ldap search string, including user-filter """
        return '(&%s)' % ''.join(self.source.base_filters)

    @cachedproperty
    def source_entities_by_extid(self):
        source = self.source
        return dict((userdict['dn'], userdict)
                    for userdict in source._search(self._cw,
                                                   source.user_base_dn,
                                                   source.user_base_scope,
                                                   self.searchfilterstr))

    def process(self, url, raise_on_error=False):
        """IDataFeedParser main entry point"""
        self.debug('processing ldapfeed source %s %s', self.source, self.searchfilterstr)
        for userdict in self.source_entities_by_extid.itervalues():
            self.warning('fetched user %s', userdict)
            extid = userdict['dn']
            entity = self.extid2entity(extid, 'CWUser', **userdict)
            if entity is not None and not self.created_during_pull(entity):
                self.notify_updated(entity)
                attrs = self.ldap2cwattrs(userdict)
                self.update_if_necessary(entity, attrs)
                self._process_email(entity, userdict)


    def handle_deletion(self, config, session, myuris):
        if config['delete-entities']:
            super(DataFeedLDAPAdapter, self).handle_deletion(config, session, myuris)
            return
        if myuris:
            byetype = {}
            for extid, (eid, etype) in myuris.iteritems():
                if self.is_deleted(extid, etype, eid):
                    byetype.setdefault(etype, []).append(str(eid))

            for etype, eids in byetype.iteritems():
                if etype != 'CWUser':
                    continue
                self.warning('deactivate %s %s entities', len(eids), etype)
                for eid in eids:
                    wf = session.entity_from_eid(eid).cw_adapt_to('IWorkflowable')
                    wf.fire_transition_if_possible('deactivate')
        session.commit(free_cnxset=False)

    def update_if_necessary(self, entity, attrs):
        # disable read security to allow password selection
        with entity._cw.security_enabled(read=False):
            entity.complete(tuple(attrs))
        if entity.__regid__ == 'CWUser':
            wf = entity.cw_adapt_to('IWorkflowable')
            if wf.state == 'deactivated':
                wf.fire_transition('activate')
                self.warning('user %s reactivated', entity.login)
        mdate = attrs.get('modification_date')
        if not mdate or mdate > entity.modification_date:
            attrs = dict( (k, v) for k, v in attrs.iteritems()
                          if v != getattr(entity, k))
            if attrs:
                entity.set_attributes(**attrs)
                self.notify_updated(entity)

    def ldap2cwattrs(self, sdict, tdict=None):
        if tdict is None:
            tdict = {}
        for sattr, tattr in self.source.user_attrs.iteritems():
            if tattr not in self.non_attribute_keys:
                try:
                    tdict[tattr] = sdict[sattr]
                except KeyError:
                    raise ConfigurationError('source attribute %s is not present '
                                             'in the source, please check the '
                                             'user-attrs-map field' % sattr)
        return tdict

    def before_entity_copy(self, entity, sourceparams):
        if entity.__regid__ == 'EmailAddress':
            entity.cw_edited['address'] = sourceparams['address']
        else:
            self.ldap2cwattrs(sourceparams, entity.cw_edited)
            pwd = entity.cw_edited.get('upassword')
            if not pwd:
                # generate a dumb password if not fetched from ldap (see
                # userPassword)
                pwd = crypt_password(generate_password())
                entity.cw_edited['upassword'] = Binary(pwd)
        return entity

    def after_entity_copy(self, entity, sourceparams):
        super(DataFeedLDAPAdapter, self).after_entity_copy(entity, sourceparams)
        if entity.__regid__ == 'EmailAddress':
            return
        groups = [self._get_group(n) for n in self.source.user_default_groups]
        entity.set_relations(in_group=groups)
        self._process_email(entity, sourceparams)

    def is_deleted(self, extidplus, etype, eid):
        try:
            extid, _ = extidplus.rsplit('@@', 1)
        except ValueError:
            # for some reason extids here tend to come in both forms, e.g:
            # dn, dn@@Babar
            extid = extidplus
        return extid not in self.source_entities_by_extid

    def _process_email(self, entity, userdict):
        try:
            emailaddrs = userdict[self.source.user_rev_attrs['email']]
        except KeyError:
            return # no email for that user, nothing to do
        if not isinstance(emailaddrs, list):
            emailaddrs = [emailaddrs]
        for emailaddr in emailaddrs:
            # search for existant email first, may be coming from another source
            rset = self._cw.execute('EmailAddress X WHERE X address %(addr)s',
                                   {'addr': emailaddr})
            if not rset:
                # not found, create it. first forge an external id
                emailextid = userdict['dn'] + '@@' + emailaddr
                email = self.extid2entity(emailextid, 'EmailAddress',
                                          address=emailaddr)
                if entity.primary_email:
                    entity.set_relations(use_email=email)
                else:
                    entity.set_relations(primary_email=email)
            elif self.sourceuris:
                # pop from sourceuris anyway, else email may be removed by the
                # source once import is finished
                uri = userdict['dn'] + '@@' + emailaddr.encode('utf-8')
                self.sourceuris.pop(uri, None)
            # XXX else check use_email relation?

    @cached
    def _get_group(self, name):
        return self._cw.execute('Any X WHERE X is CWGroup, X name %(name)s',
                                {'name': name}).get_entity(0, 0)
