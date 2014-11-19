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
from logilab.common.decorators import cached, cachedproperty
from logilab.common.shellutils import generate_password

from cubicweb import Binary, ConfigurationError
from cubicweb.server.utils import crypt_password
from cubicweb.server.sources import datafeed


class DataFeedLDAPAdapter(datafeed.DataFeedParser):
    __regid__ = 'ldapfeed'
    # attributes that may appears in source user_attrs dict which are not
    # attributes of the cw user
    non_attribute_keys = set(('email', 'eid', 'member', 'modification_date'))

    @cachedproperty
    def searchfilterstr(self):
        """ ldap search string, including user-filter """
        return '(&%s)' % ''.join(self.source.base_filters)

    @cachedproperty
    def searchgroupfilterstr(self):
        """ ldap search string, including user-filter """
        return '(&%s)' % ''.join(self.source.group_base_filters)

    @cachedproperty
    def user_source_entities_by_extid(self):
        source = self.source
        if source.user_base_dn.strip():
            attrs = map(str, source.user_attrs.keys())
            return dict((userdict['dn'], userdict)
                        for userdict in source._search(self._cw,
                                                       source.user_base_dn,
                                                       source.user_base_scope,
                                                       self.searchfilterstr,
                                                       attrs))
        return {}

    @cachedproperty
    def group_source_entities_by_extid(self):
        source = self.source
        if source.group_base_dn.strip():
            attrs = map(str, ['modifyTimestamp'] + source.group_attrs.keys())
            return dict((groupdict['dn'], groupdict)
                        for groupdict in source._search(self._cw,
                                                        source.group_base_dn,
                                                        source.group_base_scope,
                                                        self.searchgroupfilterstr,
                                                        attrs))
        return {}

    def _process(self, etype, sdict, raise_on_error=False):
        self.debug('fetched %s %s', etype, sdict)
        extid = sdict['dn']
        entity = self.extid2entity(extid, etype,
                                   raise_on_error=raise_on_error, **sdict)
        if entity is not None and not self.created_during_pull(entity):
            self.notify_updated(entity)
            attrs = self.ldap2cwattrs(sdict, etype)
            self.update_if_necessary(entity, attrs)
            if etype == 'CWUser':
                self._process_email(entity, sdict)
            if etype == 'CWGroup':
                self._process_membership(entity, sdict)

    def process(self, url, raise_on_error=False):
        """IDataFeedParser main entry point"""
        self.debug('processing ldapfeed source %s %s', self.source, self.searchfilterstr)
        for userdict in self.user_source_entities_by_extid.itervalues():
            self._process('CWUser', userdict)
        self.debug('processing ldapfeed source %s %s', self.source, self.searchgroupfilterstr)
        for groupdict in self.group_source_entities_by_extid.itervalues():
            self._process('CWGroup', groupdict, raise_on_error=raise_on_error)

    def handle_deletion(self, config, cnx, myuris):
        if config['delete-entities']:
            super(DataFeedLDAPAdapter, self).handle_deletion(config, cnx, myuris)
            return
        if myuris:
            byetype = {}
            for extid, (eid, etype) in myuris.iteritems():
                if self.is_deleted(extid, etype, eid):
                    byetype.setdefault(etype, []).append(str(eid))

            for etype, eids in byetype.iteritems():
                if etype != 'CWUser':
                    continue
                self.info('deactivate %s %s entities', len(eids), etype)
                for eid in eids:
                    wf = cnx.entity_from_eid(eid).cw_adapt_to('IWorkflowable')
                    wf.fire_transition_if_possible('deactivate')
        cnx.commit()

    def update_if_necessary(self, entity, attrs):
        # disable read security to allow password selection
        with entity._cw.security_enabled(read=False):
            entity.complete(tuple(attrs))
        if entity.cw_etype == 'CWUser':
            wf = entity.cw_adapt_to('IWorkflowable')
            if wf.state == 'deactivated':
                wf.fire_transition('activate')
                self.info('user %s reactivated', entity.login)
        mdate = attrs.get('modification_date')
        if not mdate or mdate > entity.modification_date:
            attrs = dict( (k, v) for k, v in attrs.iteritems()
                          if v != getattr(entity, k))
            if attrs:
                entity.cw_set(**attrs)
                self.notify_updated(entity)

    def ldap2cwattrs(self, sdict, etype, tdict=None):
        """ Transform dictionary of LDAP attributes to CW
        etype must be CWUser or CWGroup """
        if tdict is None:
            tdict = {}
        if etype == 'CWUser':
            items = self.source.user_attrs.iteritems()
        elif etype == 'CWGroup':
            items = self.source.group_attrs.iteritems()
        for sattr, tattr in items:
            if tattr not in self.non_attribute_keys:
                try:
                    tdict[tattr] = sdict[sattr]
                except KeyError:
                    raise ConfigurationError('source attribute %s has not '
                                             'been found in the source, '
                                             'please check the %s-attrs-map '
                                             'field and the permissions of '
                                             'the LDAP binding user' %
                                             (sattr, etype[2:].lower()))
        return tdict

    def before_entity_copy(self, entity, sourceparams):
        etype = entity.cw_etype
        if etype == 'EmailAddress':
            entity.cw_edited['address'] = sourceparams['address']
        else:
            self.ldap2cwattrs(sourceparams, etype, tdict=entity.cw_edited)
            if etype == 'CWUser':
                pwd = entity.cw_edited.get('upassword')
                if not pwd:
                    # generate a dumb password if not fetched from ldap (see
                    # userPassword)
                    pwd = crypt_password(generate_password())
                    entity.cw_edited['upassword'] = Binary(pwd)
        return entity

    def after_entity_copy(self, entity, sourceparams):
        super(DataFeedLDAPAdapter, self).after_entity_copy(entity, sourceparams)
        etype = entity.cw_etype
        if etype == 'EmailAddress':
            return
        # all CWUsers must be treated before CWGroups to have the in_group relation
        # set correctly in _associate_ldapusers
        elif etype == 'CWUser':
            groups = filter(None, [self._get_group(name)
                                   for name in self.source.user_default_groups])
            if groups:
                entity.cw_set(in_group=groups)
            self._process_email(entity, sourceparams)
        elif etype == 'CWGroup':
            self._process_membership(entity, sourceparams)

    def is_deleted(self, extidplus, etype, eid):
        try:
            extid, _ = extidplus.rsplit('@@', 1)
        except ValueError:
            # for some reason extids here tend to come in both forms, e.g:
            # dn, dn@@Babar
            extid = extidplus
        return extid not in self.user_source_entities_by_extid

    def _process_email(self, entity, userdict):
        try:
            emailaddrs = userdict[self.source.user_rev_attrs['email']]
        except KeyError:
            return # no email for that user, nothing to do
        if not isinstance(emailaddrs, list):
            emailaddrs = [emailaddrs]
        for emailaddr in emailaddrs:
            # search for existing email first, may be coming from another source
            rset = self._cw.execute('EmailAddress X WHERE X address %(addr)s',
                                   {'addr': emailaddr})
            if not rset:
                # not found, create it. first forge an external id
                emailextid = userdict['dn'] + '@@' + emailaddr.encode('utf-8')
                email = self.extid2entity(emailextid, 'EmailAddress',
                                          address=emailaddr)
                entity.cw_set(use_email=email)
            elif self.sourceuris:
                # pop from sourceuris anyway, else email may be removed by the
                # source once import is finished
                uri = userdict['dn'] + '@@' + emailaddr.encode('utf-8')
                self.sourceuris.pop(uri, None)
            # XXX else check use_email relation?

    def _process_membership(self, entity, sourceparams):
        """ Find existing CWUsers with the same login as the memberUids in the
        CWGroup entity and create the in_group relationship """
        mdate = sourceparams.get('modification_date')
        if (not mdate or mdate > entity.modification_date):
            self._cw.execute('DELETE U in_group G WHERE G eid %(g)s',
                             {'g':entity.eid})
            members = sourceparams.get(self.source.group_rev_attrs['member'])
            if members:
                members = ["'%s'" % e for e in members]
                rql = 'SET U in_group G WHERE G eid %%(g)s, U login IN (%s)' % ','.join(members)
                self._cw.execute(rql, {'g':entity.eid,  })

    @cached
    def _get_group(self, name):
        try:
            return self._cw.execute('Any X WHERE X is CWGroup, X name %(name)s',
                                    {'name': name}).get_entity(0, 0)
        except IndexError:
            self.error('group %r referenced by source configuration %r does not exist',
                       name, self.source.uri)
            return None

