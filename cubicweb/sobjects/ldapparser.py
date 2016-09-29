# copyright 2011-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from six.moves import map, filter

from logilab.common.decorators import cached, cachedproperty
from logilab.common.shellutils import generate_password

from cubicweb import ConfigurationError
from cubicweb.server.utils import crypt_password
from cubicweb.server.sources import datafeed
from cubicweb.dataimport import stores, importer


class UserMetaGenerator(stores.MetadataGenerator):
    """Specific metadata generator, used to see newly created user into their initial state.
    """
    @cached
    def base_etype_rels(self, etype):
        rels = super(UserMetaGenerator, self).base_etype_rels(etype)
        if etype == 'CWUser':
            wf_state = self._cnx.execute('Any S WHERE ET default_workflow WF, ET name %(etype)s, '
                                         'WF initial_state S', {'etype': etype}).one()
            rels['in_state'] = wf_state.eid
        return rels


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
            attrs = list(map(str, source.user_attrs.keys()))
            return dict((userdict['dn'].encode('ascii'), userdict)
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
            attrs = list(map(str, ['modifyTimestamp'] + list(source.group_attrs.keys())))
            return dict((groupdict['dn'].encode('ascii'), groupdict)
                        for groupdict in source._search(self._cw,
                                                        source.group_base_dn,
                                                        source.group_base_scope,
                                                        self.searchgroupfilterstr,
                                                        attrs))
        return {}

    def process_urls(self, *args, **kwargs):
        """IDataFeedParser main entry point."""
        self._source_uris = {}
        self._group_members = {}
        error = super(DataFeedLDAPAdapter, self).process_urls(*args, **kwargs)
        if not error:
            self.handle_deletion()
        return error

    def process(self, url, raise_on_error=False):
        """Called once by process_urls (several URL are not expected with this parser)."""
        self.debug('processing ldapfeed source %s %s', self.source, self.searchfilterstr)
        eeimporter = self.build_importer(raise_on_error)
        for name in self.source.user_default_groups:
            geid = self._get_group(name)
            eeimporter.extid2eid[geid] = geid
        entities = self.extentities_generator()
        set_cwuri = importer.use_extid_as_cwuri(eeimporter.extid2eid)
        eeimporter.import_entities(set_cwuri(entities))
        self.stats['created'] = eeimporter.created
        self.stats['updated'] = eeimporter.updated
        # handle in_group relation
        for group, members in self._group_members.items():
            self._cw.execute('DELETE U in_group G WHERE G name %(g)s', {'g': group})
            if members:
                members = ["'%s'" % e for e in members]
                rql = 'SET U in_group G WHERE G name %%(g)s, U login IN (%s)' % ','.join(members)
                self._cw.execute(rql, {'g': group})
        # ensure updated users are activated
        for eid in eeimporter.updated:
            entity = self._cw.entity_from_eid(eid)
            if entity.cw_etype == 'CWUser':
                self.ensure_activated(entity)
        # manually set primary email if necessary, it's not handled automatically since hooks are
        # deactivated
        self._cw.execute('SET X primary_email E WHERE NOT X primary_email E, X use_email E, '
                         'X cw_source S, S eid %(s)s, X in_state ST, TS name "activated"',
                         {'s': self.source.eid})

    def build_importer(self, raise_on_error):
        """Instantiate and configure an importer"""
        etypes = ('CWUser', 'EmailAddress', 'CWGroup')
        extid2eid = {}
        for etype in etypes:
            rset = self._cw.execute('Any XURI, X WHERE X cwuri XURI, X is {0},'
                                    ' X cw_source S, S name %(source)s'.format(etype),
                                    {'source': self.source.uri})
            for extid, eid in rset:
                extid = extid.encode('ascii')
                extid2eid[extid] = eid
                self._source_uris[extid] = (eid, etype)
        existing_relations = {}
        for rtype in ('in_group', 'use_email', 'owned_by'):
            rql = 'Any S,O WHERE S {} O, S cw_source SO, SO eid %(s)s'.format(rtype)
            rset = self._cw.execute(rql, {'s': self.source.eid})
            existing_relations[rtype] = set(tuple(x) for x in rset)
        return importer.ExtEntitiesImporter(self._cw.vreg.schema, self.build_store(),
                                            extid2eid=extid2eid,
                                            existing_relations=existing_relations,
                                            etypes_order_hint=etypes,
                                            import_log=self.import_log,
                                            raise_on_error=raise_on_error)

    def build_store(self):
        """Instantiate and configure a store"""
        metagenerator = UserMetaGenerator(self._cw, source=self.source)
        return stores.NoHookRQLObjectStore(self._cw, metagenerator)

    def extentities_generator(self):
        self.debug('processing ldapfeed source %s %s', self.source, self.searchgroupfilterstr)
        # generate users and email addresses
        for userdict in self.user_source_entities_by_extid.values():
            attrs = self.ldap2cwattrs(userdict, 'CWUser')
            pwd = attrs.get('upassword')
            if not pwd:
                # generate a dumb password if not fetched from ldap (see
                # userPassword)
                pwd = crypt_password(generate_password())
                attrs['upassword'] = set([pwd])
            self._source_uris.pop(userdict['dn'], None)
            extuser = importer.ExtEntity('CWUser', userdict['dn'].encode('ascii'), attrs)
            extuser.values['owned_by'] = set([extuser.extid])
            for extemail in self._process_email(extuser, userdict):
                yield extemail
            groups = list(filter(None, [self._get_group(name)
                                        for name in self.source.user_default_groups]))
            if groups:
                extuser.values['in_group'] = groups
            yield extuser
        # generate groups
        for groupdict in self.group_source_entities_by_extid.values():
            attrs = self.ldap2cwattrs(groupdict, 'CWGroup')
            self._source_uris.pop(groupdict['dn'], None)
            extgroup = importer.ExtEntity('CWGroup', groupdict['dn'].encode('ascii'), attrs)
            yield extgroup
            # record group membership for later insertion
            members = groupdict.get(self.source.group_rev_attrs['member'], ())
            self._group_members[attrs['name']] = members

    def _process_email(self, extuser, userdict):
        try:
            emailaddrs = userdict.pop(self.source.user_rev_attrs['email'])
        except KeyError:
            return  # no email for that user, nothing to do
        if not isinstance(emailaddrs, list):
            emailaddrs = [emailaddrs]
        for emailaddr in emailaddrs:
            # search for existing email first, may be coming from another source
            rset = self._cw.execute('EmailAddress X WHERE X address %(addr)s',
                                    {'addr': emailaddr})
            emailextid = (userdict['dn'] + '@@' + emailaddr).encode('ascii')
            self._source_uris.pop(emailextid, None)
            if not rset:
                # not found, create it. first forge an external id
                extuser.values.setdefault('use_email', []).append(emailextid)
                yield importer.ExtEntity('EmailAddress', emailextid, dict(address=[emailaddr]))
            # XXX else check use_email relation?

    def handle_deletion(self):
        for extid, (eid, etype) in self._source_uris.items():
            if etype != 'CWUser' or not self.is_deleted(extid, etype, eid):
                continue
            self.info('deactivate user %s', eid)
            wf = self._cw.entity_from_eid(eid).cw_adapt_to('IWorkflowable')
            wf.fire_transition_if_possible('deactivate')

    def ensure_activated(self, entity):
        if entity.cw_etype == 'CWUser':
            wf = entity.cw_adapt_to('IWorkflowable')
            if wf.state == 'deactivated':
                wf.fire_transition('activate')
                self.info('user %s reactivated', entity.login)

    def ldap2cwattrs(self, sdict, etype):
        """Transform dictionary of LDAP attributes to CW.

        etype must be CWUser or CWGroup
        """
        assert etype in ('CWUser', 'CWGroup'), etype
        tdict = {}
        if etype == 'CWUser':
            items = self.source.user_attrs.items()
        elif etype == 'CWGroup':
            items = self.source.group_attrs.items()
        for sattr, tattr in items:
            if tattr not in self.non_attribute_keys:
                try:
                    value = sdict[sattr]
                except KeyError:
                    raise ConfigurationError(
                        'source attribute %s has not been found in the source, '
                        'please check the %s-attrs-map field and the permissions of '
                        'the LDAP binding user' % (sattr, etype[2:].lower()))
                if not isinstance(value, list):
                    value = [value]
                tdict[tattr] = value
        return tdict

    def is_deleted(self, extidplus, etype, eid):
        try:
            extid = extidplus.rsplit(b'@@', 1)[0]
        except ValueError:
            # for some reason extids here tend to come in both forms, e.g:
            # dn, dn@@Babar
            extid = extidplus
        return extid not in self.user_source_entities_by_extid

    @cached
    def _get_group(self, name):
        try:
            return self._cw.execute('Any X WHERE X is CWGroup, X name %(name)s',
                                    {'name': name})[0][0]
        except IndexError:
            self.error('group %r referenced by source configuration %r does not exist',
                       name, self.source.uri)
            return None
