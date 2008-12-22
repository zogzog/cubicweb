"""cubicweb ldap user source

this source is for now limited to a read-only EUser source

:organization: Logilab
:copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr


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

from mx.DateTime import now, DateTimeDelta

from logilab.common.textutils import get_csv
from rql.nodes import Relation, VariableRef, Constant, Function

import ldap
from ldap.ldapobject import ReconnectLDAPObject
from ldap.filter import filter_format, escape_filter_chars
from ldapurl import LDAPUrl

from cubicweb.common import AuthenticationError, UnknownEid, RepositoryError
from cubicweb.server.sources import AbstractSource, TrFunc, GlobTrFunc, ConnectionWrapper
from cubicweb.server.utils import cartesian_product

# search scopes
BASE = ldap.SCOPE_BASE
ONELEVEL = ldap.SCOPE_ONELEVEL
SUBTREE = ldap.SCOPE_SUBTREE

# XXX only for edition ??
## password encryption possibilities
#ENCRYPTIONS = ('SHA', 'CRYPT', 'MD5', 'CLEAR') # , 'SSHA'

# mode identifier : (port, protocol)
MODES = {
    0: (389, 'ldap'),
    1: (636, 'ldaps'),
    2: (0,   'ldapi'),
    }

class TimedCache(dict):
    def __init__(self, ttlm, ttls=0):
        # time to live in minutes
        self.ttl = DateTimeDelta(0, 0, ttlm, ttls)
        
    def __setitem__(self, key, value):
        dict.__setitem__(self, key, (now(), value))
        
    def __getitem__(self, key):
        return dict.__getitem__(self, key)[1]
    
    def clear_expired(self):
        now_ = now()
        ttl = self.ttl
        for key, (timestamp, value) in self.items():
            if now_ - timestamp > ttl:
                del self[key]
                
class LDAPUserSource(AbstractSource):
    """LDAP read-only EUser source"""
    support_entities = {'EUser': False} 

    port = None
    
    cnx_mode = 0
    cnx_dn = ''
    cnx_pwd = ''
    
    options = (
        ('host',
         {'type' : 'string',
          'default': 'ldap',
          'help': 'ldap host',
          'group': 'ldap-source', 'inputlevel': 1,
          }),
        ('user-base-dn',
         {'type' : 'string',
          'default': 'ou=People,dc=logilab,dc=fr',
          'help': 'base DN to lookup for users',
          'group': 'ldap-source', 'inputlevel': 0,
          }),
        ('user-scope',
         {'type' : 'choice',
          'default': 'ONELEVEL',
          'choices': ('BASE', 'ONELEVEL', 'SUBTREE'),
          'help': 'user search scope',
          'group': 'ldap-source', 'inputlevel': 1,
          }),
        ('user-classes',
         {'type' : 'csv',
          'default': ('top', 'posixAccount'),
          'help': 'classes of user',
          'group': 'ldap-source', 'inputlevel': 1,
          }),
        ('user-login-attr',
         {'type' : 'string',
          'default': 'uid',
          'help': 'attribute used as login on authentication',
          'group': 'ldap-source', 'inputlevel': 1,
          }),
        ('user-default-group',
         {'type' : 'csv',
          'default': ('users',),
          'help': 'name of a group in which ldap users will be by default. \
You can set multiple groups by separating them by a comma.',
          'group': 'ldap-source', 'inputlevel': 1,
          }),
        ('user-attrs-map',
         {'type' : 'named',
          'default': {'uid': 'login', 'gecos': 'email'},
          'help': 'map from ldap user attributes to cubicweb attributes',
          'group': 'ldap-source', 'inputlevel': 1,
          }),

        ('synchronization-interval',
         {'type' : 'int',
          'default': 24*60*60,
          'help': 'interval between synchronization with the ldap \
directory (default to once a day).',
          'group': 'ldap-source', 'inputlevel': 2,
          }),
        ('cache-life-time',
         {'type' : 'int',
          'default': 2*60,
          'help': 'life time of query cache in minutes (default to two hours).',
          'group': 'ldap-source', 'inputlevel': 2,
          }),
        
    )
            
    def __init__(self, repo, appschema, source_config, *args, **kwargs):
        AbstractSource.__init__(self, repo, appschema, source_config,
                                *args, **kwargs)
        self.host = source_config['host']
        self.user_base_dn = source_config['user-base-dn']
        self.user_base_scope = globals()[source_config['user-scope']]
        self.user_classes = get_csv(source_config['user-classes'])
        self.user_login_attr = source_config['user-login-attr']
        self.user_default_groups = get_csv(source_config['user-default-group'])
        self.user_attrs = dict(v.split(':', 1) for v in get_csv(source_config['user-attrs-map']))
        self.user_rev_attrs = {'eid': 'dn'}
        for ldapattr, cwattr in self.user_attrs.items():
            self.user_rev_attrs[cwattr] = ldapattr
        self.base_filters = [filter_format('(%s=%s)', ('objectClass', o))
                              for o in self.user_classes]
        self._conn = None
        self._cache = {}
        ttlm = int(source_config.get('cache-life-type', 2*60))
        self._query_cache = TimedCache(ttlm)
        self._interval = int(source_config.get('synchronization-interval',
                                               24*60*60))

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        self._query_cache = TimedCache(2*60)

    def init(self):
        """method called by the repository once ready to handle request"""
        self.repo.looping_task(self._interval, self.synchronize) 
        self.repo.looping_task(self._query_cache.ttl.seconds/10, self._query_cache.clear_expired) 

    def synchronize(self):
        """synchronize content known by this repository with content in the
        external repository
        """
        self.info('synchronizing ldap source %s', self.uri)
        session = self.repo.internal_session()
        try:
            cursor = session.system_sql("SELECT eid, extid FROM entities WHERE "
                                        "source='%s'" % self.uri)
            for eid, extid in cursor.fetchall():
                # if no result found, _search automatically delete entity information
                res = self._search(session, extid, BASE)
                if res: 
                    ldapemailaddr = res[0].get(self.user_rev_attrs['email'])
                    if ldapemailaddr:
                        rset = session.execute('EmailAddress X,A WHERE '
                                               'U use_email X, U eid %(u)s',
                                               {'u': eid})
                        ldapemailaddr = unicode(ldapemailaddr)
                        for emaileid, emailaddr in rset:
                            if emailaddr == ldapemailaddr:
                                break
                        else:
                            self.info('updating email address of user %s to %s',
                                      extid, ldapemailaddr)
                            if rset:
                                session.execute('SET X address %(addr)s WHERE '
                                                'U primary_email X, U eid %(u)s',
                                                {'addr': ldapemailaddr, 'u': eid})
                            else:
                                # no email found, create it
                                _insert_email(session, ldapemailaddr, eid)
        finally:
            session.commit()
            session.close()
            
    def get_connection(self):
        """open and return a connection to the source"""
        if self._conn is None:
            self._connect()
        return ConnectionWrapper(self._conn)
    
    def authenticate(self, session, login, password):
        """return EUser eid for the given login/password if this account is
        defined in this source, else raise `AuthenticationError`

        two queries are needed since passwords are stored crypted, so we have
        to fetch the salt first
        """
        assert login, 'no login!'
        searchfilter = [filter_format('(%s=%s)', (self.user_login_attr, login))]
        searchfilter.extend([filter_format('(%s=%s)', ('objectClass', o))
                             for o in self.user_classes])
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
            self._connect(user['dn'], password)
        except:
            # Something went wrong, most likely bad credentials
            raise AuthenticationError()
        return self.extid2eid(user['dn'], 'EUser', session)

    def ldap_name(self, var):
        if var.stinfo['relations']:
            relname = iter(var.stinfo['relations']).next().r_type
            return self.user_rev_attrs.get(relname)
        return None
        
    def prepare_columns(self, mainvars, rqlst):
        """return two list describin how to build the final results
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
        # XXX not handled : transform/aggregat function, join on multiple users...
        assert len(union.children) == 1, 'union not supported'
        rqlst = union.children[0]
        assert not rqlst.with_, 'subquery not supported'
        rqlkey = rqlst.as_string(kwargs=args)
        try:
            results = self._query_cache[rqlkey]
        except KeyError:
            results = self.rqlst_search(session, rqlst, args)
            self._query_cache[rqlkey] = results
        return results

    def rqlst_search(self, session, rqlst, args):
        mainvars = []
        for varname in rqlst.defined_vars:
            for sol in rqlst.solutions:
                if sol[varname] == 'EUser':
                    mainvars.append(varname)
                    break
        assert mainvars
        columns, globtransforms = self.prepare_columns(mainvars, rqlst)
        eidfilters = []
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
                eid = self.extid2eid(resdict['dn'], 'EUser', session)
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
                
    
    def _connect(self, userdn=None, userpwd=None):
        port, protocol = MODES[self.cnx_mode]
        if protocol == 'ldapi':
            hostport = self.host
        else:
            hostport = '%s:%s' % (self.host, self.port or port)
        self.info('connecting %s://%s as %s', protocol, hostport,
                  userdn or 'anonymous')
        url = LDAPUrl(urlscheme=protocol, hostport=hostport)
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
        if userdn is None:
            assert self._conn is None
            self._conn = conn
            userdn = self.cnx_dn
            userpwd = self.cnx_pwd
        conn.simple_bind_s(userdn, userpwd)
        return conn

    def _search(self, session, base, scope,
                searchstr='(objectClass=*)', attrs=()):
        """make an ldap query"""
        cnx = session.pool.connection(self.uri).cnx
        try:
            res = cnx.search_s(base, scope, searchstr, attrs)
        except ldap.PARTIAL_RESULTS:
            res = cnx.result(all=0)[1]
        except ldap.NO_SUCH_OBJECT:
            eid = self.extid2eid(base, 'EUser', session, insert=False)
            if eid:
                self.warning('deleting ldap user with eid %s and dn %s',
                             eid, base)
                self.repo.delete_info(session, eid)
                self._cache.pop(base, None)
            return []
##         except ldap.REFERRAL, e:
##             cnx = self.handle_referral(e)
##             try:
##                 res = cnx.search_s(base, scope, searchstr, attrs)
##             except ldap.PARTIAL_RESULTS:
##                 res_type, res = cnx.result(all=0)
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
                    except:
                        pass
                if isinstance(value, list) and len(value) == 1:
                    rec_dict[key] = value = value[0]
            rec_dict['dn'] = rec_dn
            self._cache[rec_dn] = rec_dict
            result.append(rec_dict)
        #print '--->', result
        return result
    
    def before_entity_insertion(self, session, lid, etype, eid):
        """called by the repository when an eid has been attributed for an
        entity stored here but the entity has not been inserted in the system
        table yet.
        
        This method must return the an Entity instance representation of this
        entity.
        """
        entity = super(LDAPUserSource, self).before_entity_insertion(session, lid, etype, eid)
        res = self._search(session, lid, BASE)[0]
        for attr in entity.e_schema.indexable_attributes():
            entity[attr] = res[self.user_rev_attrs[attr]]
        return entity
    
    def after_entity_insertion(self, session, dn, entity):
        """called by the repository after an entity stored here has been
        inserted in the system table.
        """
        super(LDAPUserSource, self).after_entity_insertion(session, dn, entity)
        for group in self.user_default_groups:
            session.execute('SET X in_group G WHERE X eid %(x)s, G name %(group)s',
                            {'x': entity.eid, 'group': group}, 'x')
        # search for existant email first
        try:
            emailaddr = self._cache[dn][self.user_rev_attrs['email']]
        except KeyError:
            return
        rset = session.execute('EmailAddress X WHERE X address %(addr)s',
                               {'addr': emailaddr})
        if rset:
            session.execute('SET U primary_email X WHERE U eid %(u)s, X eid %(x)s',
                            {'x': rset[0][0], 'u': entity.eid}, 'u')
        else:
            # not found, create it
            _insert_email(session, emailaddr, entity.eid)

    def update_entity(self, session, entity):
        """replace an entity in the source"""
        raise RepositoryError('this source is read only')

    def delete_entity(self, session, etype, eid):
        """delete an entity from the source"""
        raise RepositoryError('this source is read only')

def _insert_email(session, emailaddr, ueid):
    session.execute('INSERT EmailAddress X: X address %(addr)s, U primary_email X '
                    'WHERE U eid %(x)s', {'addr': emailaddr, 'x': ueid}, 'x')
    
class GotDN(Exception):
    """exception used when a dn localizing the searched user has been found"""
    def __init__(self, dn):
        self.dn = dn

        
class RQL2LDAPFilter(object):
    """generate an LDAP filter for a rql query"""
    def __init__(self, source, session, args=None, mainvars=()):
        self.source = source
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
        if self.source.schema.rschema(rtype).is_final():
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
            dn = self.source.eid2extid(eid, self._session)
            raise GotDN(dn)
        try:
            filter = '(%s%s)' % (self._ldap_attrs[relation.r_type],
                                 rhs.accept(self))
        except KeyError:
            assert relation.r_type == 'password' # 2.38 migration
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

