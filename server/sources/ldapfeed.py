# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb ldap feed source"""

import ldap
from ldap.filter import filter_format

from logilab.common.configuration import merge_options

from cubicweb.server.sources import datafeed
from cubicweb.server import ldaputils, utils
from cubicweb import Binary

_ = unicode

# search scopes
ldapscope = {'BASE': ldap.SCOPE_BASE,
             'ONELEVEL': ldap.SCOPE_ONELEVEL,
             'SUBTREE': ldap.SCOPE_SUBTREE}

class LDAPFeedSource(ldaputils.LDAPSourceMixIn,
                     datafeed.DataFeedSource):
    """LDAP feed source: unlike ldapuser source, this source is copy based and
    will import ldap content (beside passwords for authentication) into the
    system source.
    """
    support_entities = {'CWUser': False}
    use_cwuri_as_url = False

    options_group = (
        ('group-base-dn',
         {'type' : 'string',
          'default': '',
          'help': 'base DN to lookup for groups; disable group importation mechanism if unset',
          'group': 'ldap-source', 'level': 1,
          }),
        ('group-scope',
         {'type' : 'choice',
          'default': 'ONELEVEL',
          'choices': ('BASE', 'ONELEVEL', 'SUBTREE'),
          'help': 'group search scope (valid values: "BASE", "ONELEVEL", "SUBTREE")',
          'group': 'ldap-source', 'level': 1,
          }),
        ('group-classes',
         {'type' : 'csv',
          'default': ('top', 'posixGroup'),
          'help': 'classes of group',
          'group': 'ldap-source', 'level': 1,
          }),
        ('group-filter',
         {'type': 'string',
          'default': '',
          'help': 'additional filters to be set in the ldap query to find valid groups',
          'group': 'ldap-source', 'level': 2,
          }),
        ('group-attrs-map',
         {'type' : 'named',
          'default': {'cn': 'name', 'memberUid': 'member'},
          'help': 'map from ldap group attributes to cubicweb attributes',
          'group': 'ldap-source', 'level': 1,
          }),
    )

    options = merge_options(datafeed.DataFeedSource.options
                            + ldaputils.LDAPSourceMixIn.options
                            + options_group,
                            optgroup='ldap-source',)

    def update_config(self, source_entity, typedconfig):
        """update configuration from source entity. `typedconfig` is config
        properly typed with defaults set
        """
        super(LDAPFeedSource, self).update_config(source_entity, typedconfig)
        self.group_base_dn = str(typedconfig['group-base-dn'])
        self.group_base_scope = ldapscope[typedconfig['group-scope']]
        self.group_attrs = typedconfig['group-attrs-map']
        self.group_attrs = {'dn': 'eid', 'modifyTimestamp': 'modification_date'}
        self.group_attrs.update(typedconfig['group-attrs-map'])
        self.group_rev_attrs = dict((v, k) for k, v in self.group_attrs.iteritems())
        self.group_base_filters = [filter_format('(%s=%s)', ('objectClass', o))
                                   for o in typedconfig['group-classes']]
        if typedconfig['group-filter']:
            self.group_base_filters.append(typedconfig['group-filter'])

    def _process_ldap_item(self, dn, iterator):
        itemdict = super(LDAPFeedSource, self)._process_ldap_item(dn, iterator)
        # we expect memberUid to be a list of user ids, make sure of it
        member = self.group_rev_attrs['member']
        if isinstance(itemdict.get(member), basestring):
            itemdict[member] = [itemdict[member]]
        return itemdict
