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

from __future__ import division # XXX why?

from datetime import datetime

import ldap
from ldap.ldapobject import ReconnectLDAPObject
from ldap.filter import filter_format
from ldapurl import LDAPUrl

from logilab.common.configuration import merge_options

from cubicweb import ValidationError, AuthenticationError, Binary
from cubicweb.server import utils
from cubicweb.server.sources import datafeed

_ = unicode

# search scopes
BASE = ldap.SCOPE_BASE
ONELEVEL = ldap.SCOPE_ONELEVEL
SUBTREE = ldap.SCOPE_SUBTREE
LDAP_SCOPES = {'BASE': ldap.SCOPE_BASE,
               'ONELEVEL': ldap.SCOPE_ONELEVEL,
               'SUBTREE': ldap.SCOPE_SUBTREE}

# map ldap protocol to their standard port
PROTO_PORT = {'ldap': 389,
              'ldaps': 636,
              'ldapi': None,
              }


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
          'choices': ('simple', 'cram_md5', 'digest_md5', 'gssapi'),
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

    def update_config(self, source_entity, typedconfig):
        """update configuration from source entity. `typedconfig` is config
        properly typed with defaults set
        """
        super(LDAPFeedSource, self).update_config(source_entity, typedconfig)
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
        self.user_rev_attrs = dict((v, k) for k, v in self.user_attrs.iteritems())
        self.base_filters = [filter_format('(%s=%s)', ('objectClass', o))
                             for o in typedconfig['user-classes']]
        if typedconfig['user-filter']:
            self.base_filters.append(typedconfig['user-filter'])
        self.group_base_dn = str(typedconfig['group-base-dn'])
        self.group_base_scope = LDAP_SCOPES[typedconfig['group-scope']]
        self.group_attrs = typedconfig['group-attrs-map']
        self.group_attrs = {'dn': 'eid', 'modifyTimestamp': 'modification_date'}
        self.group_attrs.update(typedconfig['group-attrs-map'])
        self.group_rev_attrs = dict((v, k) for k, v in self.group_attrs.iteritems())
        self.group_base_filters = [filter_format('(%s=%s)', ('objectClass', o))
                                   for o in typedconfig['group-classes']]
        if typedconfig['group-filter']:
            self.group_base_filters.append(typedconfig['group-filter'])
        self._conn = None

    def _entity_update(self, source_entity):
        super(LDAPFeedSource, self)._entity_update(source_entity)
        if self.urls:
            if len(self.urls) > 1:
                raise ValidationError(source_entity.eid, {'url': _('can only have one url')})
            try:
                protocol, hostport = self.urls[0].split('://')
            except ValueError:
                raise ValidationError(source_entity.eid, {'url': _('badly formatted url')})
            if protocol not in PROTO_PORT:
                raise ValidationError(source_entity.eid, {'url': _('unsupported protocol')})

    def connection_info(self):
        assert len(self.urls) == 1, self.urls
        protocol, hostport = self.urls[0].split('://')
        if protocol != 'ldapi' and not ':' in hostport:
            hostport = '%s:%s' % (hostport, PROTO_PORT[protocol])
        return protocol, hostport

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
        searchfilter = [filter_format('(%s=%s)', (self.user_login_attr, login))]
        searchfilter.extend(self.base_filters)
        searchstr = '(&%s)' % ''.join(searchfilter)
        # first search the user
        try:
            user = self._search(cnx, self.user_base_dn,
                                self.user_base_scope, searchstr)[0]
        except (IndexError, ldap.SERVER_DOWN):
            # no such user
            raise AuthenticationError()
        # check password by establishing a (unused) connection
        try:
            self._connect(user, password)
        except ldap.LDAPError as ex:
            # Something went wrong, most likely bad credentials
            self.info('while trying to authenticate %s: %s', user, ex)
            raise AuthenticationError()
        except Exception:
            self.error('while trying to authenticate %s', user, exc_info=True)
            raise AuthenticationError()
        eid = self.repo.extid2eid(self, user['dn'], 'CWUser', cnx, insert=False)
        if eid < 0:
            # user has been moved away from this source
            raise AuthenticationError()
        return eid

    def _connect(self, user=None, userpwd=None):
        protocol, hostport = self.connection_info()
        self.info('connecting %s://%s as %s', protocol, hostport,
                  user and user['dn'] or 'anonymous')
        # don't require server certificate when using ldaps (will
        # enable self signed certs)
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
        url = LDAPUrl(urlscheme=protocol, hostport=hostport)
        conn = ReconnectLDAPObject(url.initializeUrl())
        # Set the protocol version - version 3 is preferred
        try:
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
        except ldap.LDAPError: # Invalid protocol version, fall back safely
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION2)
        # Deny auto-chasing of referrals to be safe, we handle them instead
        # Required for AD
        try:
            conn.set_option(ldap.OPT_REFERRALS, 0)
        except ldap.LDAPError: # Cannot set referrals, so do nothing
            pass
        #conn.set_option(ldap.OPT_NETWORK_TIMEOUT, conn_timeout)
        #conn.timeout = op_timeout
        # Now bind with the credentials given. Let exceptions propagate out.
        if user is None:
            # XXX always use simple bind for data connection
            if not self.cnx_dn:
                conn.simple_bind_s(self.cnx_dn, self.cnx_pwd)
            else:
                self._authenticate(conn, {'dn': self.cnx_dn}, self.cnx_pwd)
        else:
            # user specified, we want to check user/password, no need to return
            # the connection which will be thrown out
            self._authenticate(conn, user, userpwd)
        return conn

    def _auth_simple(self, conn, user, userpwd):
        conn.simple_bind_s(user['dn'], userpwd)

    def _auth_cram_md5(self, conn, user, userpwd):
        from ldap import sasl
        auth_token = sasl.cram_md5(user['dn'], userpwd)
        conn.sasl_interactive_bind_s('', auth_token)

    def _auth_digest_md5(self, conn, user, userpwd):
        from ldap import sasl
        auth_token = sasl.digest_md5(user['dn'], userpwd)
        conn.sasl_interactive_bind_s('', auth_token)

    def _auth_gssapi(self, conn, user, userpwd):
        # print XXX not proper sasl/gssapi
        import kerberos
        if not kerberos.checkPassword(user[self.user_login_attr], userpwd):
            raise Exception('BAD login / mdp')
        #from ldap import sasl
        #conn.sasl_interactive_bind_s('', sasl.gssapi())

    def _search(self, cnx, base, scope,
                searchstr='(objectClass=*)', attrs=()):
        """make an ldap query"""
        self.debug('ldap search %s %s %s %s %s', self.uri, base, scope,
                   searchstr, list(attrs))
        if self._conn is None:
            self._conn = self._connect()
        ldapcnx = self._conn
        try:
            res = ldapcnx.search_s(base, scope, searchstr, attrs)
        except ldap.PARTIAL_RESULTS:
            res = ldapcnx.result(all=0)[1]
        except ldap.NO_SUCH_OBJECT:
            self.info('ldap NO SUCH OBJECT %s %s %s', base, scope, searchstr)
            self._process_no_such_object(cnx, base)
            return []
        # except ldap.REFERRAL as e:
        #     ldapcnx = self.handle_referral(e)
        #     try:
        #         res = ldapcnx.search_s(base, scope, searchstr, attrs)
        #     except ldap.PARTIAL_RESULTS:
        #         res_type, res = ldapcnx.result(all=0)
        result = []
        for rec_dn, rec_dict in res:
            # When used against Active Directory, "rec_dict" may not be
            # be a dictionary in some cases (instead, it can be a list)
            #
            # An example of a useless "res" entry that can be ignored
            # from AD is
            # (None, ['ldap://ForestDnsZones.PORTAL.LOCAL/DC=ForestDnsZones,DC=PORTAL,DC=LOCAL'])
            # This appears to be some sort of internal referral, but
            # we can't handle it, so we need to skip over it.
            try:
                items = rec_dict.iteritems()
            except AttributeError:
                continue
            else:
                itemdict = self._process_ldap_item(rec_dn, items)
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
                if not value.startswith('{SSHA}'):
                    value = utils.crypt_password(value)
                itemdict[key] = Binary(value)
            elif self.user_attrs.get(key) == 'modification_date':
                itemdict[key] = datetime.strptime(value[0], '%Y%m%d%H%M%SZ')
            else:
                value = [unicode(val, 'utf-8', 'replace') for val in value]
                if len(value) == 1:
                    itemdict[key] = value = value[0]
                else:
                    itemdict[key] = value
        # we expect memberUid to be a list of user ids, make sure of it
        member = self.group_rev_attrs['member']
        if isinstance(itemdict.get(member), basestring):
            itemdict[member] = [itemdict[member]]
        return itemdict

    def _process_no_such_object(self, cnx, dn):
        """Some search return NO_SUCH_OBJECT error, handle this (usually because
        an object whose dn is no more existent in ldap as been encountered).

        Do nothing by default, let sub-classes handle that.
        """
