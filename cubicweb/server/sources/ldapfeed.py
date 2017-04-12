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
"""cubicweb ldap feed source"""

from __future__ import division  # XXX why?

from datetime import datetime

from six import PY2, string_types

import ldap3

from logilab.common.configuration import merge_options

from cubicweb import ValidationError, AuthenticationError, Binary
from cubicweb.server import utils
from cubicweb.server.sources import datafeed

from cubicweb import _

# search scopes
BASE = ldap3.SEARCH_SCOPE_BASE_OBJECT
ONELEVEL = ldap3.SEARCH_SCOPE_SINGLE_LEVEL
SUBTREE = ldap3.SEARCH_SCOPE_WHOLE_SUBTREE
LDAP_SCOPES = {'BASE': BASE,
               'ONELEVEL': ONELEVEL,
               'SUBTREE': SUBTREE}

# map ldap protocol to their standard port
PROTO_PORT = {'ldap': 389,
              'ldaps': 636,
              'ldapi': None,
              }


def replace_filter(s):
    s = s.replace('*', '\\2A')
    s = s.replace('(', '\\28')
    s = s.replace(')', '\\29')
    s = s.replace('\\', '\\5c')
    s = s.replace('\0', '\\00')
    return s


class LDAPFeedSource(datafeed.DataFeedSource):
    """LDAP feed source: unlike ldapuser source, this source is copy based and
    will import ldap content (beside passwords for authentication) into the
    system source.
    """
    support_entities = {'CWUser': False}
    use_cwuri_as_url = False

    options = (
        ('auth-mode',
         {'type' : 'choice',
          'default': 'simple',
          'choices': ('simple', 'digest_md5', 'gssapi'),
          'help': 'authentication mode used to authenticate user to the ldap.',
          'group': 'ldap-source', 'level': 3,
          }),
        ('auth-realm',
         {'type' : 'string',
          'default': None,
          'help': 'realm to use when using gssapi/kerberos authentication.',
          'group': 'ldap-source', 'level': 3,
          }),

        ('data-cnx-dn',
         {'type' : 'string',
          'default': '',
          'help': 'user dn to use to open data connection to the ldap (eg used \
to respond to rql queries). Leave empty for anonymous bind',
          'group': 'ldap-source', 'level': 1,
          }),
        ('data-cnx-password',
         {'type' : 'string',
          'default': '',
          'help': 'password to use to open data connection to the ldap (eg used to respond to rql queries). Leave empty for anonymous bind.',
          'group': 'ldap-source', 'level': 1,
          }),

        ('user-base-dn',
         {'type' : 'string',
          'default': '',
          'help': 'base DN to lookup for users; disable user importation mechanism if unset',
          'group': 'ldap-source', 'level': 1,
          }),
        ('user-scope',
         {'type' : 'choice',
          'default': 'ONELEVEL',
          'choices': ('BASE', 'ONELEVEL', 'SUBTREE'),
          'help': 'user search scope (valid values: "BASE", "ONELEVEL", "SUBTREE")',
          'group': 'ldap-source', 'level': 1,
          }),
        ('user-classes',
         {'type' : 'csv',
          'default': ('top', 'posixAccount'),
          'help': 'classes of user (with Active Directory, you want to say "user" here)',
          'group': 'ldap-source', 'level': 1,
          }),
        ('user-filter',
         {'type': 'string',
          'default': '',
          'help': 'additional filters to be set in the ldap query to find valid users',
          'group': 'ldap-source', 'level': 2,
          }),
        ('user-login-attr',
         {'type' : 'string',
          'default': 'uid',
          'help': 'attribute used as login on authentication (with Active Directory, you want to use "sAMAccountName" here)',
          'group': 'ldap-source', 'level': 1,
          }),
        ('user-default-group',
         {'type' : 'csv',
          'default': ('users',),
          'help': 'name of a group in which ldap users will be by default. \
You can set multiple groups by separating them by a comma.',
          'group': 'ldap-source', 'level': 1,
          }),
        ('user-attrs-map',
         {'type' : 'named',
          'default': {'uid': 'login'},
          'help': 'map from ldap user attributes to cubicweb attributes (with Active Directory, you want to use sAMAccountName:login,mail:email,givenName:firstname,sn:surname)',
          'group': 'ldap-source', 'level': 1,
          }),
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

    options = merge_options(datafeed.DataFeedSource.options + options,
                            optgroup='ldap-source',)

    _conn = None

    def check_urls(self, source_entity):
        urls = super(LDAPFeedSource, self).check_urls(source_entity)

        if len(urls) > 1:
            raise ValidationError(source_entity.eid, {'url': _('can only have one url')})

        try:
            protocol, hostport = urls[0].split('://')
        except ValueError:
            raise ValidationError(source_entity.eid, {'url': _('badly formatted url')})
        if protocol not in PROTO_PORT:
            raise ValidationError(source_entity.eid, {'url': _('unsupported protocol')})

        return urls

    def init(self, source_entity):
        super(LDAPFeedSource, self).init(source_entity)
        typedconfig = self.config
        self.authmode = typedconfig['auth-mode']
        self._authenticate = getattr(self, '_auth_%s' % self.authmode)
        self.cnx_dn = typedconfig['data-cnx-dn']
        self.cnx_pwd = typedconfig['data-cnx-password']
        self.user_base_dn = str(typedconfig['user-base-dn'])
        self.user_base_scope = globals()[typedconfig['user-scope']]
        self.user_login_attr = typedconfig['user-login-attr']
        self.user_default_groups = typedconfig['user-default-group']
        self.user_attrs = {'dn': 'eid', 'modifyTimestamp': 'modification_date'}
        self.user_attrs.update(typedconfig['user-attrs-map'])
        self.user_rev_attrs = dict((v, k) for k, v in self.user_attrs.items())
        self.base_filters = ['(objectclass=%s)' % replace_filter(o)
                             for o in typedconfig['user-classes']]
        if typedconfig['user-filter']:
            self.base_filters.append(typedconfig['user-filter'])
        self.group_base_dn = str(typedconfig['group-base-dn'])
        self.group_base_scope = LDAP_SCOPES[typedconfig['group-scope']]
        self.group_attrs = typedconfig['group-attrs-map']
        self.group_attrs = {'dn': 'eid', 'modifyTimestamp': 'modification_date'}
        self.group_attrs.update(typedconfig['group-attrs-map'])
        self.group_rev_attrs = dict((v, k) for k, v in self.group_attrs.items())
        self.group_base_filters = ['(objectClass=%s)' % replace_filter(o)
                                   for o in typedconfig['group-classes']]
        if typedconfig['group-filter']:
            self.group_base_filters.append(typedconfig['group-filter'])
        self._conn = None

    def connection_info(self):
        assert len(self.urls) == 1, self.urls
        protocol, hostport = self.urls[0].split('://')
        if protocol != 'ldapi' and ':' in hostport:
            host, port = hostport.rsplit(':', 1)
        else:
            host, port = hostport, PROTO_PORT[protocol]
        return protocol, host, port

    def authenticate(self, cnx, login, password=None, **kwargs):
        """return CWUser eid for the given login/password if this account is
        defined in this source, else raise `AuthenticationError`

        two queries are needed since passwords are stored crypted, so we have
        to fetch the salt first
        """
        self.info('ldap authenticate %s', login)
        if not password:
            # On Windows + ADAM this would have succeeded (!!!)
            # You get Authenticated as: 'NT AUTHORITY\ANONYMOUS LOGON'.
            # we really really don't want that
            raise AuthenticationError()
        searchfilter = ['(%s=%s)' % (replace_filter(self.user_login_attr), replace_filter(login))]
        searchfilter.extend(self.base_filters)
        searchstr = '(&%s)' % ''.join(searchfilter)
        # first search the user
        try:
            user = self._search(cnx, self.user_base_dn,
                                self.user_base_scope, searchstr)[0]
        except IndexError:
            # no such user
            raise AuthenticationError()
        # check password by establishing a (unused) connection
        try:
            self._connect(user, password)
        except ldap3.LDAPException as ex:
            # Something went wrong, most likely bad credentials
            self.info('while trying to authenticate %s: %s', user, ex)
            raise AuthenticationError()
        except Exception:
            self.error('while trying to authenticate %s', user, exc_info=True)
            raise AuthenticationError()
        rset = cnx.execute('Any X,SN WHERE X cwuri %(extid)s, X is CWUser, '
                           'X cw_source S, S name SN', {'extid': user['dn']})
        if not rset or rset[0][1] != self.uri:
            # user is not known or has been moved away from this source
            raise AuthenticationError()
        return rset[0][0]

    def _connect(self, user=None, userpwd=None):
        protocol, host, port = self.connection_info()
        self.info('connecting %s://%s:%s as %s', protocol, host, port,
                  user and user['dn'] or 'anonymous')
        server = ldap3.Server(host, port=int(port))
        conn = ldap3.Connection(server, user=user and user['dn'], client_strategy=ldap3.STRATEGY_SYNC_RESTARTABLE, auto_referrals=False)
        # Now bind with the credentials given. Let exceptions propagate out.
        if user is None:
            # XXX always use simple bind for data connection
            if not self.cnx_dn:
                conn.bind()
            else:
                self._authenticate(conn, {'dn': self.cnx_dn}, self.cnx_pwd)
        else:
            # user specified, we want to check user/password, no need to return
            # the connection which will be thrown out
            if not self._authenticate(conn, user, userpwd):
                raise AuthenticationError()
        return conn

    def _auth_simple(self, conn, user, userpwd):
        conn.authentication = ldap3.AUTH_SIMPLE
        conn.user = user['dn']
        conn.password = userpwd
        return conn.bind()

    def _auth_digest_md5(self, conn, user, userpwd):
        conn.authentication = ldap3.AUTH_SASL
        conn.sasl_mechanism = 'DIGEST-MD5'
        # realm, user, password, authz-id
        conn.sasl_credentials = (None, user['dn'], userpwd, None)
        return conn.bind()

    def _auth_gssapi(self, conn, user, userpwd):
        conn.authentication = ldap3.AUTH_SASL
        conn.sasl_mechanism = 'GSSAPI'
        return conn.bind()

    def _search(self, cnx, base, scope,
                searchstr='(objectClass=*)', attrs=()):
        """make an ldap query"""
        self.debug('ldap search %s %s %s %s %s', self.uri, base, scope,
                   searchstr, list(attrs))
        if self._conn is None:
            self._conn = self._connect()
        ldapcnx = self._conn
        if not ldapcnx.search(base, searchstr, search_scope=scope, attributes=attrs):
            return []
        result = []
        for rec in ldapcnx.response:
            if rec['type'] != 'searchResEntry':
                continue
            items = rec['attributes'].items()
            itemdict = self._process_ldap_item(rec['dn'], items)
            result.append(itemdict)
        self.debug('ldap built results %s', len(result))
        return result

    def _process_ldap_item(self, dn, iterator):
        """Turn an ldap received item into a proper dict."""
        itemdict = {'dn': dn}
        for key, value in iterator:
            if self.user_attrs.get(key) == 'upassword': # XXx better password detection
                value = value[0].encode('utf-8')
                # we only support ldap_salted_sha1 for ldap sources, see: server/utils.py
                if not value.startswith(b'{SSHA}'):
                    value = utils.crypt_password(value)
                itemdict[key] = Binary(value)
            elif self.user_attrs.get(key) == 'modification_date':
                itemdict[key] = datetime.strptime(value[0], '%Y%m%d%H%M%SZ')
            else:
                if PY2 and value and isinstance(value[0], str):
                    value = [unicode(val, 'utf-8', 'replace') for val in value]
                if len(value) == 1:
                    itemdict[key] = value = value[0]
                else:
                    itemdict[key] = value
        # we expect memberUid to be a list of user ids, make sure of it
        member = self.group_rev_attrs['member']
        if isinstance(itemdict.get(member), string_types):
            itemdict[member] = [itemdict[member]]
        return itemdict

    def _process_no_such_object(self, cnx, dn):
        """Some search return NO_SUCH_OBJECT error, handle this (usually because
        an object whose dn is no more existent in ldap as been encountered).

        Do nothing by default, let sub-classes handle that.
        """
