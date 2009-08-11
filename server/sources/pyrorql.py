"""Source to query another RQL repository using pyro

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import threading
from os.path import join
from time import mktime
from datetime import datetime
from base64 import b64decode

from Pyro.errors import PyroError, ConnectionClosedError

from logilab.common.configuration import REQUIRED

from rql.nodes import Constant
from rql.utils import rqlvar_maker

from cubicweb import dbapi, server
from cubicweb import BadConnectionId, UnknownEid, ConnectionError
from cubicweb.cwconfig import register_persistent_options
from cubicweb.server.sources import (AbstractSource, ConnectionWrapper,
                                     TimedCache, dbg_st_search, dbg_results)

class ReplaceByInOperator(Exception):
    def __init__(self, eids):
        self.eids = eids

class PyroRQLSource(AbstractSource):
    """External repository source, using Pyro connection"""

    # boolean telling if modification hooks should be called when something is
    # modified in this source
    should_call_hooks = False
    # boolean telling if the repository should connect to this source during
    # migration
    connect_for_migration = False

    support_entities = None

    options = (
        # XXX pyro-ns host/port
        ('pyro-ns-id',
         {'type' : 'string',
          'default': REQUIRED,
          'help': 'identifier of the repository in the pyro name server',
          'group': 'pyro-source', 'inputlevel': 0,
          }),
        ('mapping-file',
         {'type' : 'string',
          'default': REQUIRED,
          'help': 'path to a python file with the schema mapping definition',
          'group': 'pyro-source', 'inputlevel': 1,
          }),
        ('cubicweb-user',
         {'type' : 'string',
          'default': REQUIRED,
          'help': 'user to use for connection on the distant repository',
          'group': 'pyro-source', 'inputlevel': 0,
          }),
        ('cubicweb-password',
         {'type' : 'password',
          'default': '',
          'help': 'user to use for connection on the distant repository',
          'group': 'pyro-source', 'inputlevel': 0,
          }),
        ('base-url',
         {'type' : 'string',
          'default': '',
          'help': 'url of the web site for the distant repository, if you want '
          'to generate external link to entities from this repository',
          'group': 'pyro-source', 'inputlevel': 1,
          }),
        ('pyro-ns-host',
         {'type' : 'string',
          'default': None,
          'help': 'Pyro name server\'s host. If not set, default to the value \
from all_in_one.conf. It may contains port information using <host>:<port> notation.',
          'group': 'pyro-source', 'inputlevel': 1,
          }),
        ('pyro-ns-group',
         {'type' : 'string',
          'default': None,
          'help': 'Pyro name server\'s group where the repository will be \
registered. If not set, default to the value from all_in_one.conf.',
          'group': 'pyro-source', 'inputlevel': 1,
          }),
        ('synchronization-interval',
         {'type' : 'int',
          'default': 5*60,
          'help': 'interval between synchronization with the external \
repository (default to 5 minutes).',
          'group': 'pyro-source', 'inputlevel': 2,
          }),

    )

    PUBLIC_KEYS = AbstractSource.PUBLIC_KEYS + ('base-url',)
    _conn = None

    def __init__(self, repo, appschema, source_config, *args, **kwargs):
        AbstractSource.__init__(self, repo, appschema, source_config,
                                *args, **kwargs)
        mappingfile = source_config['mapping-file']
        if not mappingfile[0] == '/':
            mappingfile = join(repo.config.apphome, mappingfile)
        mapping = {}
        execfile(mappingfile, mapping)
        self.support_entities = mapping['support_entities']
        self.support_relations = mapping.get('support_relations', {})
        self.dont_cross_relations = mapping.get('dont_cross_relations', ())
        self.cross_relations = mapping.get('cross_relations', ())
        baseurl = source_config.get('base-url')
        if baseurl and not baseurl.endswith('/'):
            source_config['base-url'] += '/'
        self.config = source_config
        myoptions = (('%s.latest-update-time' % self.uri,
                      {'type' : 'int', 'sitewide': True,
                       'default': 0,
                       'help': _('timestamp of the latest source synchronization.'),
                       'group': 'sources',
                       }),)
        register_persistent_options(myoptions)
        self._query_cache = TimedCache(30)

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        self._query_cache = TimedCache(30)

    def last_update_time(self):
        pkey = u'sources.%s.latest-update-time' % self.uri
        rql = 'Any V WHERE X is CWProperty, X value V, X pkey %(k)s'
        session = self.repo.internal_session()
        try:
            rset = session.execute(rql, {'k': pkey})
            if not rset:
                # insert it
                session.execute('INSERT CWProperty X: X pkey %(k)s, X value %(v)s',
                                {'k': pkey, 'v': u'0'})
                session.commit()
                timestamp = 0
            else:
                assert len(rset) == 1
                timestamp = int(rset[0][0])
            return datetime.fromtimestamp(timestamp)
        finally:
            session.close()

    def init(self):
        """method called by the repository once ready to handle request"""
        interval = int(self.config.get('synchronization-interval', 5*60))
        self.repo.looping_task(interval, self.synchronize)
        self.repo.looping_task(self._query_cache.ttl.seconds/10, self._query_cache.clear_expired)

    def synchronize(self, mtime=None):
        """synchronize content known by this repository with content in the
        external repository
        """
        self.info('synchronizing pyro source %s', self.uri)
        cnx = self.get_connection()
        try:
            extrepo = cnx._repo
        except AttributeError:
            # fake connection wrapper returned when we can't connect to the
            # external source (hence we've no chance to synchronize...)
            return
        etypes = self.support_entities.keys()
        if mtime is None:
            mtime = self.last_update_time()
        updatetime, modified, deleted = extrepo.entities_modified_since(etypes,
                                                                        mtime)
        self._query_cache.clear()
        repo = self.repo
        session = repo.internal_session()
        try:
            for etype, extid in modified:
                try:
                    exturi = cnx.describe(extid)[1]
                    if exturi == 'system' or not exturi in repo.sources_by_uri:
                        eid = self.extid2eid(str(extid), etype, session)
                        rset = session.eid_rset(eid, etype)
                        entity = rset.get_entity(0, 0)
                        entity.complete(entity.e_schema.indexable_attributes())
                        repo.index_entity(session, entity)
                except:
                    self.exception('while updating %s with external id %s of source %s',
                                   etype, extid, self.uri)
                    continue
            for etype, extid in deleted:
                try:
                    eid = self.extid2eid(str(extid), etype, session,
                                         insert=False)
                    # entity has been deleted from external repository but is not known here
                    if eid is not None:
                        repo.delete_info(session, eid)
                except:
                    self.exception('while updating %s with external id %s of source %s',
                                   etype, extid, self.uri)
                    continue
            session.execute('SET X value %(v)s WHERE X pkey %(k)s',
                            {'k': u'sources.%s.latest-update-time' % self.uri,
                             'v': unicode(int(mktime(updatetime.timetuple())))})
            session.commit()
        finally:
            session.close()

    def _get_connection(self):
        """open and return a connection to the source"""
        nshost = self.config.get('pyro-ns-host') or self.repo.config['pyro-ns-host']
        nsgroup = self.config.get('pyro-ns-group') or self.repo.config['pyro-ns-group']
        #cnxprops = ConnectionProperties(cnxtype=self.config['cnx-type'])
        return dbapi.connect(database=self.config['pyro-ns-id'],
                             login=self.config['cubicweb-user'],
                             password=self.config['cubicweb-password'],
                             host=nshost, group=nsgroup,
                             setvreg=False) #cnxprops=cnxprops)

    def get_connection(self):
        try:
            return self._get_connection()
        except (ConnectionError, PyroError):
            self.critical("can't get connection to source %s", self.uri,
                          exc_info=1)
            return ConnectionWrapper()

    def check_connection(self, cnx):
        """check connection validity, return None if the connection is still valid
        else a new connection
        """
        # we have to transfer manually thread ownership. This can be done safely
        # since the pool to which belong the connection is affected to one
        # session/thread and can't be called simultaneously
        try:
            cnx._repo._transferThread(threading.currentThread())
        except AttributeError:
            # inmemory connection
            pass
        if not isinstance(cnx, ConnectionWrapper):
            try:
                cnx.check()
                return # ok
            except (BadConnectionId, ConnectionClosedError):
                pass
        # try to reconnect
        return self.get_connection()

    def syntax_tree_search(self, session, union, args=None, cachekey=None,
                           varmap=None):
        assert dbg_st_search(self.uri, union, varmap, args, cachekey)
        rqlkey = union.as_string(kwargs=args)
        try:
            results = self._query_cache[rqlkey]
        except KeyError:
            results = self._syntax_tree_search(session, union, args)
            self._query_cache[rqlkey] = results
        assert dbg_results(results)
        return results

    def _syntax_tree_search(self, session, union, args):
        """return result from this source for a rql query (actually from a rql
        syntax tree and a solution dictionary mapping each used variable to a
        possible type). If cachekey is given, the query necessary to fetch the
        results (but not the results themselves) may be cached using this key.
        """
        if not args is None:
            args = args.copy()
        # get cached cursor anyway
        cu = session.pool[self.uri]
        if cu is None:
            # this is a ConnectionWrapper instance
            msg = session._("can't connect to source %s, some data may be missing")
            session.set_shared_data('sources_error', msg % self.uri)
            return []
        try:
            rql, cachekey = RQL2RQL(self).generate(session, union, args)
        except UnknownEid, ex:
            if server.DEBUG:
                print '  unknown eid', ex, 'no results'
            return []
        if server.DEBUG & server.DBG_RQL:
            print '  translated rql', rql
        try:
            rset = cu.execute(rql, args, cachekey)
        except Exception, ex:
            self.exception(str(ex))
            msg = session._("error while querying source %s, some data may be missing")
            session.set_shared_data('sources_error', msg % self.uri)
            return []
        descr = rset.description
        if rset:
            needtranslation = []
            rows = rset.rows
            for i, etype in enumerate(descr[0]):
                if (etype is None or not self.schema.eschema(etype).is_final() or
                    getattr(union.locate_subquery(i, etype, args).selection[i], 'uidtype', None)):
                    needtranslation.append(i)
            if needtranslation:
                cnx = session.pool.connection(self.uri)
                for rowindex in xrange(rset.rowcount - 1, -1, -1):
                    row = rows[rowindex]
                    for colindex in needtranslation:
                        if row[colindex] is not None: # optional variable
                            etype = descr[rowindex][colindex]
                            exttype, exturi, extid = cnx.describe(row[colindex])
                            if exturi == 'system' or not exturi in self.repo.sources_by_uri:
                                eid = self.extid2eid(str(row[colindex]), etype,
                                                     session)
                                row[colindex] = eid
                            else:
                                # skip this row
                                del rows[rowindex]
                                del descr[rowindex]
                                break
            results = rows
        else:
            results = []
        return results

    def _entity_relations_and_kwargs(self, session, entity):
        relations = []
        kwargs = {'x': self.eid2extid(entity.eid, session)}
        for key, val in entity.iteritems():
            relations.append('X %s %%(%s)s' % (key, key))
            kwargs[key] = val
        return relations, kwargs

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        raise NotImplementedError()

    def update_entity(self, session, entity):
        """update an entity in the source"""
        relations, kwargs = self._entity_relations_and_kwargs(session, entity)
        cu = session.pool[self.uri]
        cu.execute('SET %s WHERE X eid %%(x)s' % ','.join(relations),
                   kwargs, 'x')
        self._query_cache.clear()

    def delete_entity(self, session, etype, eid):
        """delete an entity from the source"""
        cu = session.pool[self.uri]
        cu.execute('DELETE %s X WHERE X eid %%(x)s' % etype,
                   {'x': self.eid2extid(eid, session)}, 'x')
        self._query_cache.clear()

    def add_relation(self, session, subject, rtype, object):
        """add a relation to the source"""
        cu = session.pool[self.uri]
        cu.execute('SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype,
                   {'x': self.eid2extid(subject, session),
                    'y': self.eid2extid(object, session)}, ('x', 'y'))
        self._query_cache.clear()

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        cu = session.pool[self.uri]
        cu.execute('DELETE X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype,
                   {'x': self.eid2extid(subject, session),
                    'y': self.eid2extid(object, session)}, ('x', 'y'))
        self._query_cache.clear()


class RQL2RQL(object):
    """translate a local rql query to be executed on a distant repository"""
    def __init__(self, source):
        self.source = source
        self.current_operator = None

    def _accept_children(self, node):
        res = []
        for child in node.children:
            rql = child.accept(self)
            if rql is not None:
                res.append(rql)
        return res

    def generate(self, session, rqlst, args):
        self._session = session
        self.kwargs = args
        self.cachekey = []
        self.need_translation = False
        return self.visit_union(rqlst), self.cachekey

    def visit_union(self, node):
        s = self._accept_children(node)
        if len(s) > 1:
            return ' UNION '.join('(%s)' % q for q in s)
        return s[0]

    def visit_select(self, node):
        """return the tree as an encoded rql string"""
        self._varmaker = rqlvar_maker(defined=node.defined_vars.copy())
        self._const_var = {}
        if node.distinct:
            base = 'DISTINCT Any'
        else:
            base = 'Any'
        s = ['%s %s' % (base, ','.join(v.accept(self) for v in node.selection))]
        if node.groupby:
            s.append('GROUPBY %s' % ', '.join(group.accept(self)
                                              for group in node.groupby))
        if node.orderby:
            s.append('ORDERBY %s' % ', '.join(self.visit_sortterm(term)
                                              for term in node.orderby))
        if node.limit is not None:
            s.append('LIMIT %s' % node.limit)
        if node.offset:
            s.append('OFFSET %s' % node.offset)
        restrictions = []
        if node.where is not None:
            nr = node.where.accept(self)
            if nr is not None:
                restrictions.append(nr)
        if restrictions:
            s.append('WHERE %s' % ','.join(restrictions))

        if node.having:
            s.append('HAVING %s' % ', '.join(term.accept(self)
                                             for term in node.having))
        subqueries = []
        for subquery in node.with_:
            subqueries.append('%s BEING (%s)' % (','.join(ca.name for ca in subquery.aliases),
                                                 self.visit_union(subquery.query)))
        if subqueries:
            s.append('WITH %s' % (','.join(subqueries)))
        return ' '.join(s)

    def visit_and(self, node):
        res = self._accept_children(node)
        if res:
            return ', '.join(res)
        return

    def visit_or(self, node):
        res = self._accept_children(node)
        if len(res) > 1:
            return ' OR '.join('(%s)' % rql for rql in res)
        elif res:
            return res[0]
        return

    def visit_not(self, node):
        rql = node.children[0].accept(self)
        if rql:
            return 'NOT (%s)' % rql
        return

    def visit_exists(self, node):
        return 'EXISTS(%s)' % node.children[0].accept(self)

    def visit_relation(self, node):
        try:
            if isinstance(node.children[0], Constant):
                # simplified rqlst, reintroduce eid relation
                try:
                    restr, lhs = self.process_eid_const(node.children[0])
                except UnknownEid:
                    # can safely skip not relation with an unsupported eid
                    if node.neged(strict=True):
                        return
                    raise
            else:
                lhs = node.children[0].accept(self)
                restr = None
        except UnknownEid:
            # can safely skip not relation with an unsupported eid
            if node.neged(strict=True):
                return
            # XXX what about optional relation or outer NOT EXISTS()
            raise
        if node.optional in ('left', 'both'):
            lhs += '?'
        if node.r_type == 'eid' or not self.source.schema.rschema(node.r_type).is_final():
            self.need_translation = True
            self.current_operator = node.operator()
            if isinstance(node.children[0], Constant):
                self.current_etypes = (node.children[0].uidtype,)
            else:
                self.current_etypes = node.children[0].variable.stinfo['possibletypes']
        try:
            rhs = node.children[1].accept(self)
        except UnknownEid:
            # can safely skip not relation with an unsupported eid
            if node.neged(strict=True):
                return
            # XXX what about optional relation or outer NOT EXISTS()
            raise
        except ReplaceByInOperator, ex:
            rhs = 'IN (%s)' % ','.join(eid for eid in ex.eids)
        self.need_translation = False
        self.current_operator = None
        if node.optional in ('right', 'both'):
            rhs += '?'
        if restr is not None:
            return '%s %s %s, %s' % (lhs, node.r_type, rhs, restr)
        return '%s %s %s' % (lhs, node.r_type, rhs)

    def visit_comparison(self, node):
        if node.operator in ('=', 'IS'):
            return node.children[0].accept(self)
        return '%s %s' % (node.operator.encode(),
                          node.children[0].accept(self))

    def visit_mathexpression(self, node):
        return '(%s %s %s)' % (node.children[0].accept(self),
                               node.operator.encode(),
                               node.children[1].accept(self))

    def visit_function(self, node):
        #if node.name == 'IN':
        res = []
        for child in node.children:
            try:
                rql = child.accept(self)
            except UnknownEid, ex:
                continue
            res.append(rql)
        if not res:
            raise ex
        return '%s(%s)' % (node.name, ', '.join(res))

    def visit_constant(self, node):
        if self.need_translation or node.uidtype:
            if node.type == 'Int':
                return str(self.eid2extid(node.value))
            if node.type == 'Substitute':
                key = node.value
                # ensure we have not yet translated the value...
                if not key in self._const_var:
                    self.kwargs[key] = self.eid2extid(self.kwargs[key])
                    self.cachekey.append(key)
                    self._const_var[key] = None
        return node.as_string()

    def visit_variableref(self, node):
        """get the sql name for a variable reference"""
        return node.name

    def visit_sortterm(self, node):
        if node.asc:
            return node.term.accept(self)
        return '%s DESC' % node.term.accept(self)

    def process_eid_const(self, const):
        value = const.eval(self.kwargs)
        try:
            return None, self._const_var[value]
        except:
            var = self._varmaker.next()
            self.need_translation = True
            restr = '%s eid %s' % (var, self.visit_constant(const))
            self.need_translation = False
            self._const_var[value] = var
            return restr, var

    def eid2extid(self, eid):
        try:
            return self.source.eid2extid(eid, self._session)
        except UnknownEid:
            operator = self.current_operator
            if operator is not None and operator != '=':
                # deal with query like "X eid > 12"
                #
                # The problem is that eid order in the external source may
                # differ from the local source
                #
                # So search for all eids from this source matching the condition
                # locally and then to replace the "> 12" branch by "IN (eids)"
                #
                # XXX we may have to insert a huge number of eids...)
                sql = "SELECT extid FROM entities WHERE source='%s' AND type IN (%s) AND eid%s%s"
                etypes = ','.join("'%s'" % etype for etype in self.current_etypes)
                cu = self._session.system_sql(sql % (self.source.uri, etypes,
                                                      operator, eid))
                # XXX buggy cu.rowcount which may be zero while there are some
                # results
                rows = cu.fetchall()
                if rows:
                    raise ReplaceByInOperator((b64decode(r[0]) for r in rows))
            raise

