# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Source to query another RQL remote repository"""

__docformat__ = "restructuredtext en"
_ = unicode

from os.path import join
from base64 import b64decode

from logilab.common.configuration import REQUIRED

from yams.schema import role_name

from rql.nodes import Constant
from rql.utils import rqlvar_maker

from cubicweb import dbapi, server
from cubicweb import ValidationError, BadConnectionId, UnknownEid
from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.server.sources import (AbstractSource, ConnectionWrapper,
                                     TimedCache, dbg_st_search, dbg_results)
from cubicweb.server.msplanner import neged_relation

def uidtype(union, col, etype, args):
    select, col = union.locate_subquery(col, etype, args)
    return getattr(select.selection[col], 'uidtype', None)


class ReplaceByInOperator(Exception):
    def __init__(self, eids):
        self.eids = eids

class RemoteSource(AbstractSource):
    """Generic external repository source"""

    # boolean telling if modification hooks should be called when something is
    # modified in this source
    should_call_hooks = False
    # boolean telling if the repository should connect to this source during
    # migration
    connect_for_migration = False

    options = (

        ('cubicweb-user',
         {'type' : 'string',
          'default': REQUIRED,
          'help': 'user to use for connection on the distant repository',
          'group': 'remote-source', 'level': 0,
          }),
        ('cubicweb-password',
         {'type' : 'password',
          'default': '',
          'help': 'user to use for connection on the distant repository',
          'group': 'remote-source', 'level': 0,
          }),
        ('base-url',
         {'type' : 'string',
          'default': '',
          'help': 'url of the web site for the distant repository, if you want '
          'to generate external link to entities from this repository',
          'group': 'remote-source', 'level': 1,
          }),
        ('skip-external-entities',
         {'type' : 'yn',
          'default': False,
          'help': 'should entities not local to the source be considered or not',
          'group': 'remote-source', 'level': 0,
          }),
        ('synchronization-interval',
         {'type' : 'time',
          'default': '5min',
          'help': 'interval between synchronization with the external \
repository (default to 5 minutes).',
          'group': 'remote-source', 'level': 2,
          }))

    PUBLIC_KEYS = AbstractSource.PUBLIC_KEYS + ('base-url',)

    _conn = None

    def __init__(self, repo, source_config, eid=None):
        super(RemoteSource, self).__init__(repo, source_config, eid)
        self._query_cache = TimedCache(1800)

    def update_config(self, source_entity, processed_config):
        """update configuration from source entity"""
        super(RemoteSource, self).update_config(source_entity, processed_config)
        baseurl = processed_config.get('base-url')
        if baseurl and not baseurl.endswith('/'):
            processed_config['base-url'] += '/'
        self.config = processed_config
        self._skip_externals = processed_config['skip-external-entities']
        if source_entity is not None:
            self.latest_retrieval = source_entity.latest_retrieval

    def _entity_update(self, source_entity):
        super(RemoteSource, self)._entity_update(source_entity)
        if self.urls and len(self.urls) > 1:
            raise ValidationError(source_entity.eid, {'url': _('can only have one url')})

    def get_connection(self):
        try:
            return self._get_connection()
        except ConnectionError as ex:
            self.critical("can't get connection to source %s: %s", self.uri, ex)
            return ConnectionWrapper()

    def _get_connection(self):
        """open and return a connection to the source"""
        self.info('connecting to source %s as user %s',
                  self.urls[0], self.config['cubicweb-user'])
        # XXX check protocol according to source type (zmq / pyro)
        return dbapi.connect(self.urls[0], login=self.config['cubicweb-user'],
                             password=self.config['cubicweb-password'])

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        self._query_cache = TimedCache(1800)

    def init(self, activated, source_entity):
        """method called by the repository once ready to handle request"""
        super(RemoteSource, self).init(activated, source_entity)
        self.load_mapping(source_entity._cw)
        if activated:
            interval = self.config['synchronization-interval']
            self.repo.looping_task(interval, self.synchronize)
            self.repo.looping_task(self._query_cache.ttl.seconds/10,
                                   self._query_cache.clear_expired)
            self.latest_retrieval = source_entity.latest_retrieval

    def load_mapping(self, session=None):
        self.support_entities = {}
        self.support_relations = {}
        self.dont_cross_relations = set(('owned_by', 'created_by'))
        self.cross_relations = set()
        assert self.eid is not None
        self._schemacfg_idx = {}
        self._load_mapping(session)

    etype_options = set(('write',))
    rtype_options = set(('maycross', 'dontcross', 'write',))

    def _check_options(self, schemacfg, allowedoptions):
        if schemacfg.options:
            options = set(w.strip() for w in schemacfg.options.split(':'))
        else:
            options = set()
        if options - allowedoptions:
            options = ', '.join(sorted(options - allowedoptions))
            msg = _('unknown option(s): %s' % options)
            raise ValidationError(schemacfg.eid, {role_name('options', 'subject'): msg})
        return options

    def add_schema_config(self, schemacfg, checkonly=False):
        """added CWSourceSchemaConfig, modify mapping accordingly"""
        try:
            ertype = schemacfg.schema.name
        except AttributeError:
            msg = schemacfg._cw._("attribute/relation can't be mapped, only "
                                  "entity and relation types")
            raise ValidationError(schemacfg.eid, {role_name('cw_for_schema', 'subject'): msg})
        if schemacfg.schema.__regid__ == 'CWEType':
            options = self._check_options(schemacfg, self.etype_options)
            if not checkonly:
                self.support_entities[ertype] = 'write' in options
        else: # CWRType
            if ertype in ('is', 'is_instance_of', 'cw_source') or ertype in VIRTUAL_RTYPES:
                msg = schemacfg._cw._('%s relation should not be in mapped') % ertype
                raise ValidationError(schemacfg.eid, {role_name('cw_for_schema', 'subject'): msg})
            options = self._check_options(schemacfg, self.rtype_options)
            if 'dontcross' in options:
                if 'maycross' in options:
                    msg = schemacfg._("can't mix dontcross and maycross options")
                    raise ValidationError(schemacfg.eid, {role_name('options', 'subject'): msg})
                if 'write' in options:
                    msg = schemacfg._("can't mix dontcross and write options")
                    raise ValidationError(schemacfg.eid, {role_name('options', 'subject'): msg})
                if not checkonly:
                    self.dont_cross_relations.add(ertype)
            elif not checkonly:
                self.support_relations[ertype] = 'write' in options
                if 'maycross' in options:
                    self.cross_relations.add(ertype)
        if not checkonly:
            # add to an index to ease deletion handling
            self._schemacfg_idx[schemacfg.eid] = ertype

    def del_schema_config(self, schemacfg, checkonly=False):
        """deleted CWSourceSchemaConfig, modify mapping accordingly"""
        if checkonly:
            return
        try:
            ertype = self._schemacfg_idx[schemacfg.eid]
            if ertype[0].isupper():
                del self.support_entities[ertype]
            else:
                if ertype in self.support_relations:
                    del self.support_relations[ertype]
                    if ertype in self.cross_relations:
                        self.cross_relations.remove(ertype)
                else:
                    self.dont_cross_relations.remove(ertype)
        except Exception:
            self.error('while updating mapping consequently to removal of %s',
                       schemacfg)

    def local_eid(self, cnx, extid, session):
        etype, dexturi, dextid = cnx.describe(extid)
        if dexturi == 'system' or not (
            dexturi in self.repo.sources_by_uri or self._skip_externals):
            assert etype in self.support_entities, etype
            eid = self.repo.extid2eid(self, str(extid), etype, session)
            if eid > 0:
                return eid, True
        elif dexturi in self.repo.sources_by_uri:
            source = self.repo.sources_by_uri[dexturi]
            cnx = session.cnxset.connection(source.uri)
            eid = source.local_eid(cnx, dextid, session)[0]
            return eid, False
        return None, None

    def synchronize(self, mtime=None):
        """synchronize content known by this repository with content in the
        external repository
        """
        self.info('synchronizing remote source %s', self.uri)
        cnx = self.get_connection()
        try:
            extrepo = cnx._repo
        except AttributeError:
            # fake connection wrapper returned when we can't connect to the
            # external source (hence we've no chance to synchronize...)
            return
        etypes = list(self.support_entities)
        if mtime is None:
            mtime = self.latest_retrieval
        updatetime, modified, deleted = extrepo.entities_modified_since(etypes, mtime)
        self._query_cache.clear()
        repo = self.repo
        session = repo.internal_session()
        source = repo.system_source
        try:
            for etype, extid in modified:
                try:
                    eid = self.local_eid(cnx, extid, session)[0]
                    if eid is not None:
                        rset = session.eid_rset(eid, etype)
                        entity = rset.get_entity(0, 0)
                        entity.complete(entity.e_schema.indexable_attributes())
                        source.index_entity(session, entity)
                except Exception:
                    self.exception('while updating %s with external id %s of source %s',
                                   etype, extid, self.uri)
                    continue
            for etype, extid in deleted:
                try:
                    eid = self.repo.extid2eid(self, str(extid), etype, session,
                                              insert=False)
                    # entity has been deleted from external repository but is not known here
                    if eid is not None:
                        entity = session.entity_from_eid(eid, etype)
                        repo.delete_info(session, entity, self.uri,
                                         scleanup=self.eid)
                except Exception:
                    if self.repo.config.mode == 'test':
                        raise
                    self.exception('while updating %s with external id %s of source %s',
                                   etype, extid, self.uri)
                    continue
            self.latest_retrieval = updatetime
            session.execute('SET X latest_retrieval %(date)s WHERE X eid %(x)s',
                            {'x': self.eid, 'date': self.latest_retrieval})
            session.commit()
        finally:
            session.close()

    def get_connection(self):
        raise NotImplementedError()

    def check_connection(self, cnx):
        """check connection validity, return None if the connection is still valid
        else a new connection
        """
        if not isinstance(cnx, ConnectionWrapper):
            try:
                cnx.check()
                return # ok
            except BadConnectionId:
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
        cu = session.cnxset[self.uri]
        if cu is None:
            # this is a ConnectionWrapper instance
            msg = session._("can't connect to source %s, some data may be missing")
            session.set_shared_data('sources_error', msg % self.uri, txdata=True)
            return []
        translator = RQL2RQL(self)
        try:
            rql = translator.generate(session, union, args)
        except UnknownEid as ex:
            if server.DEBUG:
                print '  unknown eid', ex, 'no results'
            return []
        if server.DEBUG & server.DBG_RQL:
            print '  translated rql', rql
        try:
            rset = cu.execute(rql, args)
        except Exception as ex:
            self.exception(str(ex))
            msg = session._("error while querying source %s, some data may be missing")
            session.set_shared_data('sources_error', msg % self.uri, txdata=True)
            return []
        descr = rset.description
        if rset:
            needtranslation = []
            rows = rset.rows
            for i, etype in enumerate(descr[0]):
                if (etype is None or not self.schema.eschema(etype).final
                    or uidtype(union, i, etype, args)):
                    needtranslation.append(i)
            if needtranslation:
                cnx = session.cnxset.connection(self.uri)
                for rowindex in xrange(rset.rowcount - 1, -1, -1):
                    row = rows[rowindex]
                    localrow = False
                    for colindex in needtranslation:
                        if row[colindex] is not None: # optional variable
                            eid, local = self.local_eid(cnx, row[colindex], session)
                            if local:
                                localrow = True
                            if eid is not None:
                                row[colindex] = eid
                            else:
                                # skip this row
                                del rows[rowindex]
                                del descr[rowindex]
                                break
                    else:
                        # skip row if it only contains eids of entities which
                        # are actually from a source we also know locally,
                        # except if some args specified (XXX should actually
                        # check if there are some args local to the source)
                        if not (translator.has_local_eid or localrow):
                            del rows[rowindex]
                            del descr[rowindex]
            results = rows
        else:
            results = []
        return results

    def _entity_relations_and_kwargs(self, session, entity):
        relations = []
        kwargs = {'x': self.repo.eid2extid(self, entity.eid, session)}
        for key, val in entity.cw_attr_cache.iteritems():
            relations.append('X %s %%(%s)s' % (key, key))
            kwargs[key] = val
        return relations, kwargs

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        raise NotImplementedError()

    def update_entity(self, session, entity):
        """update an entity in the source"""
        relations, kwargs = self._entity_relations_and_kwargs(session, entity)
        cu = session.cnxset[self.uri]
        cu.execute('SET %s WHERE X eid %%(x)s' % ','.join(relations), kwargs)
        self._query_cache.clear()
        entity.cw_clear_all_caches()

    def delete_entity(self, session, entity):
        """delete an entity from the source"""
        if session.deleted_in_transaction(self.eid):
            # source is being deleted, don't propagate
            self._query_cache.clear()
            return
        cu = session.cnxset[self.uri]
        cu.execute('DELETE %s X WHERE X eid %%(x)s' % entity.cw_etype,
                   {'x': self.repo.eid2extid(self, entity.eid, session)})
        self._query_cache.clear()

    def add_relation(self, session, subject, rtype, object):
        """add a relation to the source"""
        cu = session.cnxset[self.uri]
        cu.execute('SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype,
                   {'x': self.repo.eid2extid(self, subject, session),
                    'y': self.repo.eid2extid(self, object, session)})
        self._query_cache.clear()
        session.entity_from_eid(subject).cw_clear_all_caches()
        session.entity_from_eid(object).cw_clear_all_caches()

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        if session.deleted_in_transaction(self.eid):
            # source is being deleted, don't propagate
            self._query_cache.clear()
            return
        cu = session.cnxset[self.uri]
        cu.execute('DELETE X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype,
                   {'x': self.repo.eid2extid(self, subject, session),
                    'y': self.repo.eid2extid(self, object, session)})
        self._query_cache.clear()
        session.entity_from_eid(subject).cw_clear_all_caches()
        session.entity_from_eid(object).cw_clear_all_caches()


class RQL2RQL(object):
    """translate a local rql query to be executed on a distant repository"""
    def __init__(self, source):
        self.source = source
        self.repo = source.repo
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
        self.need_translation = False
        self.has_local_eid = False
        return self.visit_union(rqlst)

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
        rql = node.children[0].accept(self)
        if rql:
            return 'EXISTS(%s)' % rql
        return

    def visit_relation(self, node):
        try:
            if isinstance(node.children[0], Constant):
                # simplified rqlst, reintroduce eid relation
                try:
                    restr, lhs = self.process_eid_const(node.children[0])
                except UnknownEid:
                    # can safely skip not relation with an unsupported eid
                    if neged_relation(node):
                        return
                    raise
            else:
                lhs = node.children[0].accept(self)
                restr = None
        except UnknownEid:
            # can safely skip not relation with an unsupported eid
            if neged_relation(node):
                return
            # XXX what about optional relation or outer NOT EXISTS()
            raise
        if node.optional in ('left', 'both'):
            lhs += '?'
        if node.r_type == 'eid' or not self.source.schema.rschema(node.r_type).final:
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
            if neged_relation(node):
                return
            # XXX what about optional relation or outer NOT EXISTS()
            raise
        except ReplaceByInOperator as ex:
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
            except UnknownEid as ex:
                continue
            res.append(rql)
        if not res:
            raise ex
        return '%s(%s)' % (node.name, ', '.join(res))

    def visit_constant(self, node):
        if self.need_translation or node.uidtype:
            if node.type == 'Int':
                self.has_local_eid = True
                return str(self.eid2extid(node.value))
            if node.type == 'Substitute':
                key = node.value
                # ensure we have not yet translated the value...
                if not key in self._const_var:
                    self.kwargs[key] = self.eid2extid(self.kwargs[key])
                    self._const_var[key] = None
                    self.has_local_eid = True
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
        except Exception:
            var = self._varmaker.next()
            self.need_translation = True
            restr = '%s eid %s' % (var, self.visit_constant(const))
            self.need_translation = False
            self._const_var[value] = var
            return restr, var

    def eid2extid(self, eid):
        try:
            return self.repo.eid2extid(self.source, eid, self._session)
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

