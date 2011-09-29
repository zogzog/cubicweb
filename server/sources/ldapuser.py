# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb ldap user source

this source is for now limited to a read-only CWUser source

Part of the code is coming form Zope's LDAPUserFolder

Copyright (c) 2004 Jens Vagelpohl.
All Rights Reserved.

This software is subject to the provisions of the Zope Public License,
Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
FOR A PARTICULAR PURPOSE.
"""
from __future__ import division
from base64 import b64decode

import ldap
from ldap.ldapobject import ReconnectLDAPObject
from ldap.filter import filter_format, escape_filter_chars
from ldapurl import LDAPUrl

from rql.nodes import Relation, VariableRef, Constant, Function

from cubicweb import AuthenticationError, UnknownEid, RepositoryError
from cubicweb.server.utils import cartesian_product
from cubicweb.server.sources import (AbstractSource, TrFunc, GlobTrFunc,
                                     ConnectionWrapper, TimedCache)

# search scopes
BASE = ldap.SCOPE_BASE
ONELEVEL = ldap.SCOPE_ONELEVEL
SUBTREE = ldap.SCOPE_SUBTREE

# map ldap protocol to their standard port
PROTO_PORT = {'ldap': 389,
              'ldaps': 636,
              'ldapi': None,
              }


class LDAPUserSource(AbstractSource):
    """LDAP read-only CWUser source"""
    support_entities = {'CWUser': False}

    options = (
        ('host',
         {'type' : 'string',
          'default': 'ldap',
          'help': 'ldap host. It may contains port information using \
<host>:<port> notation.',
          'group': 'ldap-source', 'level': 1,
          }),
        ('protocol',
         {'type' : 'choice',
          'default': 'ldap',
          'choices': ('ldap', 'ldaps', 'ldapi'),
          'help': 'ldap protocol (allowed values: ldap, ldaps, ldapi)',
          'group': 'ldap-source', 'level': 1,
          }),
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
          'default': 'ou=People,dc=logilab,dc=fr',
          'help': 'base DN to lookup for users',
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
          'default': {'uid': 'login', 'gecos': 'email'},
          'help': 'map from ldap user attributes to cubicweb attributes (with Active Directory, you want to use sAMAccountName:login,mail:email,givenName:firstname,sn:surname)',
          'group': 'ldap-source', 'level': 1,
          }),

        ('synchronization-interval',
         {'type' : 'time',
          'default': '1d',
          'help': 'interval between synchronization with the ldap \
directory (default to once a day).',
          'group': 'ldap-source', 'level': 3,
          }),
        ('cache-life-time',
         {'type' : 'time',
          'default': '2h',
          'help': 'life time of query cache (default to two hours).',
          'group': 'ldap-source', 'level': 3,
          }),

    )

    def __init__(self, repo, source_config, eid=None):
        AbstractSource.__init__(self, repo, source_config, eid)
        self.update_config(None, self.check_conf_dict(eid, source_config))
        self._conn = None

    def update_config(self, source_entity, typedconfig):
        """update configuration from source entity. `typedconfig` is config
        properly typed with defaults set
        """
        self.host = typedconfig['host']
        self.protocol = typedconfig['protocol']
        self.authmode = typedconfig['auth-mode']
        self._authenticate = getattr(self, '_auth_%s' % self.authmode)
        self.cnx_dn = typedconfig['data-cnx-dn']
        self.cnx_pwd = typedconfig['data-cnx-password']
        self.user_base_dn = str(typedconfig['user-base-dn'])
        self.user_base_scope = globals()[typedconfig['user-scope']]
        self.user_login_attr = typedconfig['user-login-attr']
        self.user_default_groups = typedconfig['user-default-group']
        self.user_attrs = typedconfig['user-attrs-map']
        self.user_rev_attrs = {'eid': 'dn'}
        for ldapattr, cwattr in self.user_attrs.items():
            self.user_rev_attrs[cwattr] = ldapattr
        self.base_filters = [filter_format('(%s=%s)', ('objectClass', o))
                             for o in typedconfig['user-classes']]
        if typedconfig['user-filter']:
            self.base_filters.append(typedconfig['user-filter'])
        self._interval = typedconfig['synchronization-interval']
        self._cache_ttl = max(71, typedconfig['cache-life-time'])
        self.reset_caches()
        self._conn = None

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        self._cache = {}
        self._query_cache = TimedCache(self._cache_ttl)

    def init(self, activated, source_entity):
        """method called by the repository once ready to handle request"""
        if activated:
            self.info('ldap init')
            # set minimum period of 5min 1s (the additional second is to
            # minimize resonnance effet)
            self.repo.looping_task(max(301, self._interval), self.synchronize)
            self.repo.looping_task(self._cache_ttl // 10,
                                   self._query_cache.clear_expired)

    def synchronize(self):
        """synchronize content known by this repository with content in the
        external repository
        """
        self.info('synchronizing ldap source %s', self.uri)
        try:
            ldap_emailattr = self.user_rev_attrs['email']
        except KeyError:
            return # no email in ldap, we're done
        session = self.repo.internal_session()
        execute = session.execute
        try:
            cursor = session.system_sql("SELECT eid, extid FROM entities WHERE "
                                        "source='%s'" % self.uri)
            for eid, b64extid in cursor.fetchall():
                extid = b64decode(b64extid)
                self.debug('ldap eid %s', eid)
                # if no result found, _search automatically delete entity information
                res = self._search(session, extid, BASE)
                self.debug('ldap search %s', res)
                if res:
                    ldapemailaddr = res[0].get(ldap_emailattr)
                    if ldapemailaddr:
                        if isinstance(ldapemailaddr, list):
                            ldapemailaddr = ldapemailaddr[0] # XXX consider only the first email in the list
                        rset = execute('Any X,A WHERE '
                                       'X address A, U use_email X, U eid %(u)s',
                                       {'u': eid})
                        ldapemailaddr = unicode(ldapemailaddr)
                        for emaileid, emailaddr, in rset:
                            if emailaddr == ldapemailaddr:
                                break
                        else:
                            self.debug('updating email address of user %s to %s',
                                      extid, ldapemailaddr)
                            emailrset = execute('EmailAddress A WHERE A address %(addr)s',
                                                {'addr': ldapemailaddr})
                            if emailrset:
                                execute('SET U use_email X WHERE '
                                        'X eid %(x)s, U eid %(u)s',
                                        {'x': emailrset[0][0], 'u': eid})
                            elif rset:
                                if not execute('SET X address %(addr)s WHERE '
                                               'U primary_email X, U eid %(u)s',
                                               {'addr': ldapemailaddr, 'u': eid}):
                                    execute('SET X address %(addr)s WHERE '
                                            'X eid %(x)s',
                                            {'addr': ldapemailaddr, 'x': rset[0][0]})
                            else:
                                # no email found, create it
                                _insert_email(session, ldapemailaddr, eid)
        finally:
            session.commit()
            session.close()

    def get_connection(self):
        """open and return a connection to the source"""
        if self._conn is None:
            try:
                self._connect()
            except Exception:
                self.exception('unable to connect to ldap:')
        return ConnectionWrapper(self._conn)

    def authenticate(self, session, login, password=None, **kwargs):
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
            user = self._search(session, self.user_base_dn,
                                self.user_base_scope, searchstr)[0]
        except IndexError:
            # no such user
            raise AuthenticationError()
        # check password by establishing a (unused) connection
        try:
            self._connect(user, password)
        except ldap.LDAPError, ex:
            # Something went wrong, most likely bad credentials
            self.info('while trying to authenticate %s: %s', user, ex)
            raise AuthenticationError()
        except Exception:
            self.error('while trying to authenticate %s', user, exc_info=True)
            raise AuthenticationError()
        eid = self.repo.extid2eid(self, user['dn'], 'CWUser', session)
        if eid < 0:
            # user has been moved away from this source
            raise AuthenticationError()
        return eid

    def ldap_name(self, var):
        if var.stinfo['relations']:
            relname = iter(var.stinfo['relations']).next().r_type
            return self.user_rev_attrs.get(relname)
        return None

    def prepare_columns(self, mainvars, rqlst):
        """return two list describing how to build the final results
        from the result of an ldap search (ie a list of dictionnary)
        """
        columns = []
        global_transforms = []
        for i, term in enumerate(rqlst.selection):
            if isinstance(term, Constant):
                columns.append(term)
                continue
            if isinstance(term, Function): # LOWER, UPPER, COUNT...
                var = term.get_nodes(VariableRef)[0]
                var = var.variable
                try:
                    mainvar = var.stinfo['attrvar'].name
                except AttributeError: # no attrvar set
                    mainvar = var.name
                assert mainvar in mainvars
                trname = term.name
                ldapname = self.ldap_name(var)
                if trname in ('COUNT', 'MIN', 'MAX', 'SUM'):
                    global_transforms.append(GlobTrFunc(trname, i, ldapname))
                    columns.append((mainvar, ldapname))
                    continue
                if trname in ('LOWER', 'UPPER'):
                    columns.append((mainvar, TrFunc(trname, i, ldapname)))
                    continue
                raise NotImplementedError('no support for %s function' % trname)
            if term.name in mainvars:
                columns.append((term.name, 'dn'))
                continue
            var = term.variable
            mainvar = var.stinfo['attrvar'].name
            columns.append((mainvar, self.ldap_name(var)))
            #else:
            #    # probably a bug in rql splitting if we arrive here
            #    raise NotImplementedError
        return columns, global_transforms

    def syntax_tree_search(self, session, union,
                           args=None, cachekey=None, varmap=None, debug=0):
        """return result from this source for a rql query (actually from a rql
        syntax tree and a solution dictionary mapping each used variable to a
        possible type). If cachekey is given, the query necessary to fetch the
        results (but not the results themselves) may be cached using this key.
        """
        self.debug('ldap syntax tree search')
        # XXX not handled : transform/aggregat function, join on multiple users...
        assert len(union.children) == 1, 'union not supported'
        rqlst = union.children[0]
        assert not rqlst.with_, 'subquery not supported'
        rqlkey = rqlst.as_string(kwargs=args)
        try:
            results = self._query_cache[rqlkey]
        except KeyError:
            try:
                results = self.rqlst_search(session, rqlst, args)
                self._query_cache[rqlkey] = results
            except ldap.SERVER_DOWN:
                # cant connect to server
                msg = session._("can't connect to source %s, some data may be missing")
                session.set_shared_data('sources_error', msg % self.uri)
                return []
        return results

    def rqlst_search(self, session, rqlst, args):
        mainvars = []
        for varname in rqlst.defined_vars:
            for sol in rqlst.solutions:
                if sol[varname] == 'CWUser':
                    mainvars.append(varname)
                    break
        assert mainvars, rqlst
        columns, globtransforms = self.prepare_columns(mainvars, rqlst)
        eidfilters = [lambda x: x > 0]
        allresults = []
        generator = RQL2LDAPFilter(self, session, args, mainvars)
        for mainvar in mainvars:
            # handle restriction
            try:
                eidfilters_, ldapfilter = generator.generate(rqlst, mainvar)
            except GotDN, ex:
                assert ex.dn, 'no dn!'
                try:
                    res = [self._cache[ex.dn]]
                except KeyError:
                    res = self._search(session, ex.dn, BASE)
            except UnknownEid, ex:
                # raised when we are looking for the dn of an eid which is not
                # coming from this source
                res = []
            else:
                eidfilters += eidfilters_
                res = self._search(session, self.user_base_dn,
                                   self.user_base_scope, ldapfilter)
            allresults.append(res)
        # 1. get eid for each dn and filter according to that eid if necessary
        for i, res in enumerate(allresults):
            filteredres = []
            for resdict in res:
                # get sure the entity exists in the system table
                eid = self.repo.extid2eid(self, resdict['dn'], 'CWUser', session)
                for eidfilter in eidfilters:
                    if not eidfilter(eid):
                        break
                else:
                    resdict['eid'] = eid
                    filteredres.append(resdict)
            allresults[i] = filteredres
        # 2. merge result for each "mainvar": cartesian product
        allresults = cartesian_product(allresults)
        # 3. build final result according to column definition
        result = []
        for rawline in allresults:
            rawline = dict(zip(mainvars, rawline))
            line = []
            for varname, ldapname in columns:
                if ldapname is None:
                    value = None # no mapping available
                elif ldapname == 'dn':
                    value = rawline[varname]['eid']
                elif isinstance(ldapname, Constant):
                    if ldapname.type == 'Substitute':
                        value = args[ldapname.value]
                    else:
                        value = ldapname.value
                elif isinstance(ldapname, TrFunc):
                    value = ldapname.apply(rawline[varname])
                else:
                    value = rawline[varname].get(ldapname)
                line.append(value)
            result.append(line)
        for trfunc in globtransforms:
            result = trfunc.apply(result)
        #print '--> ldap result', result
        return result


    def _connect(self, user=None, userpwd=None):
        if self.protocol == 'ldapi':
            hostport = self.host
        elif not ':' in self.host:
            hostport = '%s:%s' % (self.host, PROTO_PORT[self.protocol])
        else:
            hostport = self.host
        self.info('connecting %s://%s as %s', self.protocol, hostport,
                  user and user['dn'] or 'anonymous')
        # don't require server certificate when using ldaps (will
        # enable self signed certs)
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
        url = LDAPUrl(urlscheme=self.protocol, hostport=hostport)
        conn = ReconnectLDAPObject(url.initializeUrl())
        # Set the protocol version - version 3 is preferred
        try:
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
        except ldap.LDAPError: # Invalid protocol version, fall back safely
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION2)
        # Deny auto-chasing of referrals to be safe, we handle them instead
        #try:
        #    connection.set_option(ldap.OPT_REFERRALS, 0)
        #except ldap.LDAPError: # Cannot set referrals, so do nothing
        #    pass
        #conn.set_option(ldap.OPT_NETWORK_TIMEOUT, conn_timeout)
        #conn.timeout = op_timeout
        # Now bind with the credentials given. Let exceptions propagate out.
        if user is None:
            # no user specified, we want to initialize the 'data' connection,
            assert self._conn is None
            self._conn = conn
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

    def _search(self, session, base, scope,
                searchstr='(objectClass=*)', attrs=()):
        """make an ldap query"""
        self.debug('ldap search %s %s %s %s %s', self.uri, base, scope,
                   searchstr, list(attrs))
        # XXX for now, we do not have connections set support for LDAP, so
        # this is always self._conn
        cnx = session.cnxset.connection(self.uri).cnx
        try:
            res = cnx.search_s(base, scope, searchstr, attrs)
        except ldap.PARTIAL_RESULTS:
            res = cnx.result(all=0)[1]
        except ldap.NO_SUCH_OBJECT:
            self.info('ldap NO SUCH OBJECT')
            eid = self.repo.extid2eid(self, base, 'CWUser', session, insert=False)
            if eid:
                self.warning('deleting ldap user with eid %s and dn %s',
                             eid, base)
                entity = session.entity_from_eid(eid, 'CWUser')
                self.repo.delete_info(session, entity, self.uri)
                self.reset_caches()
            return []
        # except ldap.REFERRAL, e:
        #     cnx = self.handle_referral(e)
        #     try:
        #         res = cnx.search_s(base, scope, searchstr, attrs)
        #     except ldap.PARTIAL_RESULTS:
        #         res_type, res = cnx.result(all=0)
        result = []
        for rec_dn, rec_dict in res:
            # When used against Active Directory, "rec_dict" may not be
            # be a dictionary in some cases (instead, it can be a list)
            # An example of a useless "res" entry that can be ignored
            # from AD is
            # (None, ['ldap://ForestDnsZones.PORTAL.LOCAL/DC=ForestDnsZones,DC=PORTAL,DC=LOCAL'])
            # This appears to be some sort of internal referral, but
            # we can't handle it, so we need to skip over it.
            try:
                items =  rec_dict.items()
            except AttributeError:
                # 'items' not found on rec_dict, skip
                continue
            for key, value in items: # XXX syt: huuum ?
                if not isinstance(value, str):
                    try:
                        for i in range(len(value)):
                            value[i] = unicode(value[i], 'utf8')
                    except Exception:
                        pass
                if isinstance(value, list) and len(value) == 1:
                    rec_dict[key] = value = value[0]
            rec_dict['dn'] = rec_dn
            self._cache[rec_dn] = rec_dict
            result.append(rec_dict)
        #print '--->', result
        self.debug('ldap built results %s', len(result))
        return result

    def before_entity_insertion(self, session, lid, etype, eid, sourceparams):
        """called by the repository when an eid has been attributed for an
        entity stored here but the entity has not been inserted in the system
        table yet.

        This method must return the an Entity instance representation of this
        entity.
        """
        self.debug('ldap before entity insertion')
        entity = super(LDAPUserSource, self).before_entity_insertion(
            session, lid, etype, eid, sourceparams)
        res = self._search(session, lid, BASE)[0]
        for attr in entity.e_schema.indexable_attributes():
            entity.cw_edited[attr] = res[self.user_rev_attrs[attr]]
        return entity

    def after_entity_insertion(self, session, lid, entity, sourceparams):
        """called by the repository after an entity stored here has been
        inserted in the system table.
        """
        self.debug('ldap after entity insertion')
        super(LDAPUserSource, self).after_entity_insertion(
            session, lid, entity, sourceparams)
        dn = lid
        for group in self.user_default_groups:
            session.execute('SET X in_group G WHERE X eid %(x)s, G name %(group)s',
                            {'x': entity.eid, 'group': group})
        # search for existant email first
        try:
            emailaddr = self._cache[dn][self.user_rev_attrs['email']]
        except KeyError:
            return
        if isinstance(emailaddr, list):
            emailaddr = emailaddr[0] # XXX consider only the first email in the list
        rset = session.execute('EmailAddress X WHERE X address %(addr)s',
                               {'addr': emailaddr})
        if rset:
            session.execute('SET U primary_email X WHERE U eid %(u)s, X eid %(x)s',
                            {'x': rset[0][0], 'u': entity.eid})
        else:
            # not found, create it
            _insert_email(session, emailaddr, entity.eid)

    def update_entity(self, session, entity):
        """replace an entity in the source"""
        raise RepositoryError('this source is read only')

    def delete_entity(self, session, entity):
        """delete an entity from the source"""
        raise RepositoryError('this source is read only')

def _insert_email(session, emailaddr, ueid):
    session.execute('INSERT EmailAddress X: X address %(addr)s, U primary_email X '
                    'WHERE U eid %(x)s', {'addr': emailaddr, 'x': ueid})

class GotDN(Exception):
    """exception used when a dn localizing the searched user has been found"""
    def __init__(self, dn):
        self.dn = dn


class RQL2LDAPFilter(object):
    """generate an LDAP filter for a rql query"""
    def __init__(self, source, session, args=None, mainvars=()):
        self.source = source
        self.repo = source.repo
        self._ldap_attrs = source.user_rev_attrs
        self._base_filters = source.base_filters
        self._session = session
        if args is None:
            args = {}
        self._args = args
        self.mainvars = mainvars

    def generate(self, selection, mainvarname):
        self._filters = res = self._base_filters[:]
        self._mainvarname = mainvarname
        self._eidfilters = []
        self._done_not = set()
        restriction = selection.where
        if isinstance(restriction, Relation):
            # only a single relation, need to append result here (no AND/OR)
            filter = restriction.accept(self)
            if filter is not None:
                res.append(filter)
        elif restriction:
            restriction.accept(self)
        if len(res) > 1:
            return self._eidfilters, '(&%s)' % ''.join(res)
        return self._eidfilters, res[0]

    def visit_and(self, et):
        """generate filter for a AND subtree"""
        for c in et.children:
            part = c.accept(self)
            if part:
                self._filters.append(part)

    def visit_or(self, ou):
        """generate filter for a OR subtree"""
        res = []
        for c in ou.children:
            part = c.accept(self)
            if part:
                res.append(part)
        if res:
            if len(res) > 1:
                part = '(|%s)' % ''.join(res)
            else:
                part = res[0]
            self._filters.append(part)

    def visit_not(self, node):
        """generate filter for a OR subtree"""
        part = node.children[0].accept(self)
        if part:
            self._filters.append('(!(%s))'% part)

    def visit_relation(self, relation):
        """generate filter for a relation"""
        rtype = relation.r_type
        # don't care of type constraint statement (i.e. relation_type = 'is')
        if rtype == 'is':
            return ''
        lhs, rhs = relation.get_parts()
        # attribute relation
        if self.source.schema.rschema(rtype).final:
            # dunno what to do here, don't pretend anything else
            if lhs.name != self._mainvarname:
                if lhs.name in self.mainvars:
                    # XXX check we don't have variable as rhs
                    return
                raise NotImplementedError
            rhs_vars = rhs.get_nodes(VariableRef)
            if rhs_vars:
                if len(rhs_vars) > 1:
                    raise NotImplementedError
                # selected variable, nothing to do here
                return
            # no variables in the RHS
            if isinstance(rhs.children[0], Function):
                res = rhs.children[0].accept(self)
            elif rtype != 'has_text':
                res = self._visit_attribute_relation(relation)
            else:
                raise NotImplementedError(relation)
        # regular relation XXX todo: in_group
        else:
            raise NotImplementedError(relation)
        return res

    def _visit_attribute_relation(self, relation):
        """generate filter for an attribute relation"""
        lhs, rhs = relation.get_parts()
        lhsvar = lhs.variable
        if relation.r_type == 'eid':
            # XXX hack
            # skip comparison sign
            eid = int(rhs.children[0].accept(self))
            if relation.neged(strict=True):
                self._done_not.add(relation.parent)
                self._eidfilters.append(lambda x: not x == eid)
                return
            if rhs.operator != '=':
                filter = {'>': lambda x: x > eid,
                          '>=': lambda x: x >= eid,
                          '<': lambda x: x < eid,
                          '<=': lambda x: x <= eid,
                          }[rhs.operator]
                self._eidfilters.append(filter)
                return
            dn = self.repo.eid2extid(self.source, eid, self._session)
            raise GotDN(dn)
        try:
            filter = '(%s%s)' % (self._ldap_attrs[relation.r_type],
                                 rhs.accept(self))
        except KeyError:
            # unsupported attribute
            self.source.warning('%s source can\'t handle relation %s, no '
                                'results will be returned from this source',
                                self.source.uri, relation)
            raise UnknownEid # trick to return no result
        return filter

    def visit_comparison(self, cmp):
        """generate filter for a comparaison"""
        return '%s%s'% (cmp.operator, cmp.children[0].accept(self))

    def visit_mathexpression(self, mexpr):
        """generate filter for a mathematic expression"""
        raise NotImplementedError

    def visit_function(self, function):
        """generate filter name for a function"""
        if function.name == 'IN':
            return self.visit_in(function)
        raise NotImplementedError

    def visit_in(self, function):
        grandpapa = function.parent.parent
        ldapattr = self._ldap_attrs[grandpapa.r_type]
        res = []
        for c in function.children:
            part = c.accept(self)
            if part:
                res.append(part)
        if res:
            if len(res) > 1:
                part = '(|%s)' % ''.join('(%s=%s)' % (ldapattr, v) for v in res)
            else:
                part = '(%s=%s)' % (ldapattr, res[0])
        return part

    def visit_constant(self, constant):
        """generate filter name for a constant"""
        value = constant.value
        if constant.type is None:
            raise NotImplementedError
        if constant.type == 'Date':
            raise NotImplementedError
            #value = self.keyword_map[value]()
        elif constant.type == 'Substitute':
            value = self._args[constant.value]
        else:
            value = constant.value
        if isinstance(value, unicode):
            value = value.encode('utf8')
        else:
            value = str(value)
        return escape_filter_chars(value)

    def visit_variableref(self, variableref):
        """get the sql name for a variable reference"""
        pass

