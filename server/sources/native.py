"""Adapters for native cubicweb sources.

Notes:
* extid (aka external id, the primary key of an entity in the external source
  from which it comes from) are stored in a varchar column encoded as a base64
  string. This is because it should actually be Bytes but we want an index on
  it for fast querying.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from __future__ import with_statement

__docformat__ = "restructuredtext en"

from pickle import loads, dumps
from threading import Lock
from datetime import datetime
from base64 import b64decode, b64encode
from contextlib import contextmanager

from logilab.common.compat import any
from logilab.common.cache import Cache
from logilab.common.decorators import cached, clear_cache
from logilab.common.configuration import Method
from logilab.common.shellutils import getlogin
from logilab.database import get_db_helper

from cubicweb import UnknownEid, AuthenticationError, Binary, server, neg_role
from cubicweb import transaction as tx
from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.cwconfig import CubicWebNoAppConfiguration
from cubicweb.server import hook
from cubicweb.server.utils import crypt_password
from cubicweb.server.sqlutils import SQL_PREFIX, SQLAdapterMixIn
from cubicweb.server.rqlannotation import set_qdata
from cubicweb.server.session import hooks_control, security_enabled
from cubicweb.server.sources import AbstractSource, dbg_st_search, dbg_results
from cubicweb.server.sources.rql2sql import SQLGenerator


ATTR_MAP = {}
NONSYSTEM_ETYPES = set()
NONSYSTEM_RELATIONS = set()

class LogCursor(object):
    def __init__(self, cursor):
        self.cu = cursor

    def execute(self, query, args=None):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        if server.DEBUG & server.DBG_SQL:
            print 'exec', query, args
        try:
            self.cu.execute(str(query), args)
        except Exception, ex:
            print "sql: %r\n args: %s\ndbms message: %r" % (
                query, args, ex.args[0])
            raise

    def fetchall(self):
        return self.cu.fetchall()

    def fetchone(self):
        return self.cu.fetchone()


def make_schema(selected, solution, table, typemap):
    """return a sql schema to store RQL query result"""
    sql = []
    varmap = {}
    for i, term in enumerate(selected):
        name = 'C%s' % i
        key = term.as_string()
        varmap[key] = '%s.%s' % (table, name)
        ttype = term.get_type(solution)
        try:
            sql.append('%s %s' % (name, typemap[ttype]))
        except KeyError:
            # assert not schema(ttype).final
            sql.append('%s %s' % (name, typemap['Int']))
    return ','.join(sql), varmap


def _modified_sql(table, etypes):
    # XXX protect against sql injection
    if len(etypes) > 1:
        restr = 'type IN (%s)' % ','.join("'%s'" % etype for etype in etypes)
    else:
        restr = "type='%s'" % etypes[0]
    if table == 'entities':
        attr = 'mtime'
    else:
        attr = 'dtime'
    return 'SELECT type, eid FROM %s WHERE %s AND %s > %%(time)s' % (
        table, restr, attr)


def sql_or_clauses(sql, clauses):
    select, restr = sql.split(' WHERE ', 1)
    restrclauses = restr.split(' AND ')
    for clause in clauses:
        restrclauses.remove(clause)
    if restrclauses:
        restr = '%s AND (%s)' % (' AND '.join(restrclauses),
                                 ' OR '.join(clauses))
    else:
        restr = '(%s)' % ' OR '.join(clauses)
    return '%s WHERE %s' % (select, restr)


class UndoException(Exception):
    """something went wrong during undoing"""


def _undo_check_relation_target(tentity, rdef, role):
    """check linked entity has not been redirected for this relation"""
    card = rdef.role_cardinality(role)
    if card in '?1' and tentity.related(rdef.rtype, role):
        raise UndoException(tentity._cw._(
            "Can't restore %(role)s relation %(rtype)s to entity %(eid)s which "
            "is already linked using this relation.")
                            % {'role': neg_role(role),
                               'rtype': rdef.rtype,
                               'eid': tentity.eid})


class NativeSQLSource(SQLAdapterMixIn, AbstractSource):
    """adapter for source using the native cubicweb schema (see below)
    """
    sqlgen_class = SQLGenerator
    options = (
        ('db-driver',
         {'type' : 'string',
          'default': 'postgres',
          'help': 'database driver (postgres or sqlite)',
          'group': 'native-source', 'inputlevel': 1,
          }),
        ('db-host',
         {'type' : 'string',
          'default': '',
          'help': 'database host',
          'group': 'native-source', 'inputlevel': 1,
          }),
        ('db-port',
         {'type' : 'string',
          'default': '',
          'help': 'database port',
          'group': 'native-source', 'inputlevel': 1,
          }),
        ('db-name',
         {'type' : 'string',
          'default': Method('default_instance_id'),
          'help': 'database name',
          'group': 'native-source', 'inputlevel': 0,
          }),
        ('db-user',
         {'type' : 'string',
          'default': CubicWebNoAppConfiguration.mode == 'user' and getlogin() or 'cubicweb',
          'help': 'database user',
          'group': 'native-source', 'inputlevel': 0,
          }),
        ('db-password',
         {'type' : 'password',
          'default': '',
          'help': 'database password',
          'group': 'native-source', 'inputlevel': 0,
          }),
        ('db-encoding',
         {'type' : 'string',
          'default': 'utf8',
          'help': 'database encoding',
          'group': 'native-source', 'inputlevel': 1,
          }),
    )

    def __init__(self, repo, appschema, source_config, *args, **kwargs):
        SQLAdapterMixIn.__init__(self, source_config)
        self.authentifiers = [LoginPasswordAuthentifier(self)]
        AbstractSource.__init__(self, repo, appschema, source_config,
                                *args, **kwargs)
        # sql generator
        self._rql_sqlgen = self.sqlgen_class(appschema, self.dbhelper,
                                             ATTR_MAP.copy())
        # full text index helper
        self.do_fti = not repo.config['delay-full-text-indexation']
        # sql queries cache
        self._cache = Cache(repo.config['rql-cache-size'])
        self._temp_table_data = {}
        self._eid_creation_lock = Lock()
        # (etype, attr) / storage mapping
        self._storages = {}
        # XXX no_sqlite_wrap trick since we've a sqlite locking pb when
        # running unittest_multisources with the wrapping below
        if self.dbdriver == 'sqlite' and \
               not getattr(repo.config, 'no_sqlite_wrap', False):
            from cubicweb.server.sources.extlite import ConnectionWrapper
            self.get_connection = lambda: ConnectionWrapper(self)
            self.check_connection = lambda cnx: cnx
            def pool_reset(cnx):
                cnx.close()
            self.pool_reset = pool_reset

    @property
    def _sqlcnx(self):
        # XXX: sqlite connections can only be used in the same thread, so
        #      create a new one each time necessary. If it appears to be time
        #      consuming, find another way
        return SQLAdapterMixIn.get_connection(self)

    def add_authentifier(self, authentifier):
        self.authentifiers.append(authentifier)
        authentifier.source = self
        authentifier.set_schema(self.schema)

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        self._cache = Cache(self.repo.config['rql-cache-size'])

    def clear_eid_cache(self, eid, etype):
        """clear potential caches for the given eid"""
        self._cache.pop('Any X WHERE X eid %s, X is %s' % (eid, etype), None)
        self._cache.pop('Any X WHERE X eid %s' % eid, None)
        self._cache.pop('Any %s' % eid, None)

    def sqlexec(self, session, sql, args=None):
        """execute the query and return its result"""
        return self.process_result(self.doexec(session, sql, args))

    def init_creating(self):
        pool = self.repo._get_pool()
        pool.pool_set()
        # check full text index availibility
        if self.do_fti:
            if not self.dbhelper.has_fti_table(pool['system']):
                if not self.repo.config.creating:
                    self.critical('no text index table')
                self.do_fti = False
        pool.pool_reset()
        self.repo._free_pool(pool)

    def backup(self, backupfile, confirm):
        """method called to create a backup of the source's data"""
        self.close_pool_connections()
        try:
            self.backup_to_file(backupfile, confirm)
        finally:
            self.open_pool_connections()

    def restore(self, backupfile, confirm, drop):
        """method called to restore a backup of source's data"""
        if self.repo.config.open_connections_pools:
            self.close_pool_connections()
        try:
            self.restore_from_file(backupfile, confirm, drop=drop)
        finally:
            if self.repo.config.open_connections_pools:
                self.open_pool_connections()

    def init(self):
        self.init_creating()

    def map_attribute(self, etype, attr, cb):
        self._rql_sqlgen.attr_map['%s.%s' % (etype, attr)] = cb

    def unmap_attribute(self, etype, attr):
        self._rql_sqlgen.attr_map.pop('%s.%s' % (etype, attr), None)

    def set_storage(self, etype, attr, storage):
        storage_dict = self._storages.setdefault(etype, {})
        storage_dict[attr] = storage
        self.map_attribute(etype, attr, storage.sqlgen_callback)

    def unset_storage(self, etype, attr):
        self._storages[etype].pop(attr)
        # if etype has no storage left, remove the entry
        if not self._storages[etype]:
            del self._storages[etype]
        self.unmap_attribute(etype, attr)

    # ISource interface #######################################################

    def compile_rql(self, rql, sols):
        rqlst = self.repo.vreg.rqlhelper.parse(rql)
        rqlst.restricted_vars = ()
        rqlst.children[0].solutions = sols
        self.repo.querier.sqlgen_annotate(rqlst)
        set_qdata(self.schema.rschema, rqlst, ())
        return rqlst

    def set_schema(self, schema):
        """set the instance'schema"""
        self._cache = Cache(self.repo.config['rql-cache-size'])
        self.cache_hit, self.cache_miss, self.no_cache = 0, 0, 0
        self.schema = schema
        try:
            self._rql_sqlgen.schema = schema
        except AttributeError:
            pass # __init__
        for authentifier in self.authentifiers:
            authentifier.set_schema(self.schema)
        clear_cache(self, 'need_fti_indexation')

    def support_entity(self, etype, write=False):
        """return true if the given entity's type is handled by this adapter
        if write is true, return true only if it's a RW support
        """
        return not etype in NONSYSTEM_ETYPES

    def support_relation(self, rtype, write=False):
        """return true if the given relation's type is handled by this adapter
        if write is true, return true only if it's a RW support
        """
        if write:
            return not rtype in NONSYSTEM_RELATIONS
        # due to current multi-sources implementation, the system source
        # can't claim not supporting a relation
        return True #not rtype == 'content_for'

    def may_cross_relation(self, rtype):
        return True

    def authenticate(self, session, login, **kwargs):
        """return CWUser eid for the given login and other authentication
        information found in kwargs, else raise `AuthenticationError`
        """
        for authentifier in self.authentifiers:
            try:
                return authentifier.authenticate(session, login, **kwargs)
            except AuthenticationError:
                continue
        raise AuthenticationError()

    def syntax_tree_search(self, session, union, args=None, cachekey=None,
                           varmap=None):
        """return result from this source for a rql query (actually from
        a rql syntax tree and a solution dictionary mapping each used
        variable to a possible type). If cachekey is given, the query
        necessary to fetch the results (but not the results themselves)
        may be cached using this key.
        """
        assert dbg_st_search(self.uri, union, varmap, args, cachekey)
        # remember number of actually selected term (sql generation may append some)
        if cachekey is None:
            self.no_cache += 1
            # generate sql query if we are able to do so (not supported types...)
            sql, query_args = self._rql_sqlgen.generate(union, args, varmap)
        else:
            # sql may be cached
            try:
                sql, query_args = self._cache[cachekey]
                self.cache_hit += 1
            except KeyError:
                self.cache_miss += 1
                sql, query_args = self._rql_sqlgen.generate(union, args, varmap)
                self._cache[cachekey] = sql, query_args
        args = self.merge_args(args, query_args)
        assert isinstance(sql, basestring), repr(sql)
        try:
            cursor = self.doexec(session, sql, args)
        except (self.OperationalError, self.InterfaceError):
            # FIXME: better detection of deconnection pb
            self.info("request failed '%s' ... retry with a new cursor", sql)
            session.pool.reconnect(self)
            cursor = self.doexec(session, sql, args)
        results = self.process_result(cursor)
        assert dbg_results(results)
        return results

    def flying_insert(self, table, session, union, args=None, varmap=None):
        """similar as .syntax_tree_search, but inserts data in the
        temporary table (on-the-fly if possible, eg for the system
        source whose the given cursor come from). If not possible,
        inserts all data by calling .executemany().
        """
        assert dbg_st_search(
            self.uri, union, varmap, args,
            prefix='ON THE FLY temp data insertion into %s from' % table)
        # generate sql queries if we are able to do so
        sql, query_args = self._rql_sqlgen.generate(union, args, varmap)
        query = 'INSERT INTO %s %s' % (table, sql.encode(self._dbencoding))
        self.doexec(session, query, self.merge_args(args, query_args))

    def manual_insert(self, results, table, session):
        """insert given result into a temporary table on the system source"""
        if server.DEBUG & server.DBG_RQL:
            print '  manual insertion of', results, 'into', table
        if not results:
            return
        query_args = ['%%(%s)s' % i for i in xrange(len(results[0]))]
        query = 'INSERT INTO %s VALUES(%s)' % (table, ','.join(query_args))
        kwargs_list = []
        for row in results:
            kwargs = {}
            row = tuple(row)
            for index, cell in enumerate(row):
                if isinstance(cell, Binary):
                    cell = self._binary(cell.getvalue())
                kwargs[str(index)] = cell
            kwargs_list.append(kwargs)
        self.doexecmany(session, query, kwargs_list)

    def clean_temp_data(self, session, temptables):
        """remove temporary data, usually associated to temporary tables"""
        if temptables:
            for table in temptables:
                try:
                    self.doexec(session,'DROP TABLE %s' % table)
                except:
                    pass
                try:
                    del self._temp_table_data[table]
                except KeyError:
                    continue

    @contextmanager
    def _storage_handler(self, entity, event):
        # 1/ memorize values as they are before the storage is called.
        #    For instance, the BFSStorage will replace the `data`
        #    binary value with a Binary containing the destination path
        #    on the filesystem. To make the entity.data usage absolutely
        #    transparent, we'll have to reset entity.data to its binary
        #    value once the SQL query will be executed
        orig_values = {}
        etype = entity.__regid__
        for attr, storage in self._storages.get(etype, {}).items():
            if attr in entity.edited_attributes:
                orig_values[attr] = entity[attr]
                handler = getattr(storage, 'entity_%s' % event)
                handler(entity, attr)
        yield # 2/ execute the source's instructions
        # 3/ restore original values
        for attr, value in orig_values.items():
            entity[attr] = value

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        with self._storage_handler(entity, 'added'):
            attrs = self.preprocess_entity(entity)
            sql = self.sqlgen.insert(SQL_PREFIX + entity.__regid__, attrs)
            self.doexec(session, sql, attrs)
            if session.undoable_action('C', entity.__regid__):
                self._record_tx_action(session, 'tx_entity_actions', 'C',
                                       etype=entity.__regid__, eid=entity.eid)

    def update_entity(self, session, entity):
        """replace an entity in the source"""
        with self._storage_handler(entity, 'updated'):
            attrs = self.preprocess_entity(entity)
            if session.undoable_action('U', entity.__regid__):
                changes = self._save_attrs(session, entity, attrs)
                self._record_tx_action(session, 'tx_entity_actions', 'U',
                                       etype=entity.__regid__, eid=entity.eid,
                                       changes=self._binary(dumps(changes)))
            sql = self.sqlgen.update(SQL_PREFIX + entity.__regid__, attrs,
                                     ['cw_eid'])
            self.doexec(session, sql, attrs)

    def delete_entity(self, session, entity):
        """delete an entity from the source"""
        with self._storage_handler(entity, 'deleted'):
            if session.undoable_action('D', entity.__regid__):
                attrs = [SQL_PREFIX + r.type
                         for r in entity.e_schema.subject_relations()
                         if (r.final or r.inlined) and not r in VIRTUAL_RTYPES]
                changes = self._save_attrs(session, entity, attrs)
                self._record_tx_action(session, 'tx_entity_actions', 'D',
                                       etype=entity.__regid__, eid=entity.eid,
                                       changes=self._binary(dumps(changes)))
            attrs = {'cw_eid': entity.eid}
            sql = self.sqlgen.delete(SQL_PREFIX + entity.__regid__, attrs)
            self.doexec(session, sql, attrs)

    def _add_relation(self, session, subject, rtype, object, inlined=False):
        """add a relation to the source"""
        if inlined is False:
            attrs = {'eid_from': subject, 'eid_to': object}
            sql = self.sqlgen.insert('%s_relation' % rtype, attrs)
        else: # used by data import
            etype = session.describe(subject)[0]
            attrs = {'cw_eid': subject, SQL_PREFIX + rtype: object}
            sql = self.sqlgen.update(SQL_PREFIX + etype, attrs,
                                     ['cw_eid'])
        self.doexec(session, sql, attrs)

    def add_relation(self, session, subject, rtype, object, inlined=False):
        """add a relation to the source"""
        self._add_relation(session, subject, rtype, object, inlined)
        if session.undoable_action('A', rtype):
            self._record_tx_action(session, 'tx_relation_actions', 'A',
                                   eid_from=subject, rtype=rtype, eid_to=object)

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        rschema = self.schema.rschema(rtype)
        if rschema.inlined:
            table = SQL_PREFIX + session.describe(subject)[0]
            column = SQL_PREFIX + rtype
            sql = 'UPDATE %s SET %s=NULL WHERE %seid=%%(eid)s' % (table, column,
                                                                  SQL_PREFIX)
            attrs = {'eid' : subject}
        else:
            attrs = {'eid_from': subject, 'eid_to': object}
            sql = self.sqlgen.delete('%s_relation' % rtype, attrs)
        self.doexec(session, sql, attrs)
        if session.undoable_action('R', rtype):
            self._record_tx_action(session, 'tx_relation_actions', 'R',
                                   eid_from=subject, rtype=rtype, eid_to=object)

    def doexec(self, session, query, args=None, rollback=True):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        cursor = session.pool[self.uri]
        if server.DEBUG & server.DBG_SQL:
            cnx = session.pool.connection(self.uri)
            # getattr to get the actual connection if cnx is a ConnectionWrapper
            # instance
            print 'exec', query, args, getattr(cnx, '_cnx', cnx)
        try:
            # str(query) to avoid error if it's an unicode string
            cursor.execute(str(query), args)
        except Exception, ex:
            if self.repo.config.mode != 'test':
                # during test we get those message when trying to alter sqlite
                # db schema
                self.critical("sql: %r\n args: %s\ndbms message: %r",
                              query, args, ex.args[0])
            if rollback:
                try:
                    session.pool.connection(self.uri).rollback()
                    if self.repo.config.mode != 'test':
                        self.critical('transaction has been rollbacked')
                except:
                    pass
            raise
        return cursor

    def doexecmany(self, session, query, args):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        if server.DEBUG & server.DBG_SQL:
            print 'execmany', query, 'with', len(args), 'arguments'
        cursor = session.pool[self.uri]
        try:
            # str(query) to avoid error if it's an unicode string
            cursor.executemany(str(query), args)
        except Exception, ex:
            if self.repo.config.mode != 'test':
                # during test we get those message when trying to alter sqlite
                # db schema
                self.critical("sql many: %r\n args: %s\ndbms message: %r",
                              query, args, ex.args[0])
            try:
                session.pool.connection(self.uri).rollback()
                if self.repo.config.mode != 'test':
                    self.critical('transaction has been rollbacked')
            except:
                pass
            raise

    # short cut to method requiring advanced db helper usage ##################

    def binary_to_str(self, value):
        return self.dbhelper.dbapi_module.binary_to_str(value)

    def create_index(self, session, table, column, unique=False):
        cursor = LogCursor(session.pool[self.uri])
        self.dbhelper.create_index(cursor, table, column, unique)

    def drop_index(self, session, table, column, unique=False):
        cursor = LogCursor(session.pool[self.uri])
        self.dbhelper.drop_index(cursor, table, column, unique)

    # system source interface #################################################

    def eid_type_source(self, session, eid):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        sql = 'SELECT type, source, extid FROM entities WHERE eid=%s' % eid
        try:
            res = self.doexec(session, sql).fetchone()
        except:
            assert session.pool, 'session has no pool set'
            raise UnknownEid(eid)
        if res is None:
            raise UnknownEid(eid)
        if res[-1] is not None:
            if not isinstance(res, list):
                res = list(res)
            res[-1] = b64decode(res[-1])
        return res

    def extid2eid(self, session, source, extid):
        """get eid from an external id. Return None if no record found."""
        assert isinstance(extid, str)
        cursor = self.doexec(session,
                             'SELECT eid FROM entities '
                             'WHERE extid=%(x)s AND source=%(s)s',
                             {'x': b64encode(extid), 's': source.uri})
        # XXX testing rowcount cause strange bug with sqlite, results are there
        #     but rowcount is 0
        #if cursor.rowcount > 0:
        try:
            result = cursor.fetchone()
            if result:
                return result[0]
        except:
            pass
        return None

    def temp_table_def(self, selected, sol, table):
        return make_schema(selected, sol, table, self.dbhelper.TYPE_MAPPING)

    def create_temp_table(self, session, table, schema):
        # we don't want on commit drop, this may cause problem when
        # running with an ldap source, and table will be deleted manually any way
        # on commit
        sql = self.dbhelper.sql_temporary_table(table, schema, False)
        self.doexec(session, sql)

    def create_eid(self, session):
        self._eid_creation_lock.acquire()
        try:
            for sql in self.dbhelper.sqls_increment_sequence('entities_id_seq'):
                cursor = self.doexec(session, sql)
            return cursor.fetchone()[0]
        finally:
            self._eid_creation_lock.release()

    def add_info(self, session, entity, source, extid, complete):
        """add type and source info for an eid into the system table"""
        # begin by inserting eid/type/source/extid into the entities table
        if extid is not None:
            assert isinstance(extid, str)
            extid = b64encode(extid)
        attrs = {'type': entity.__regid__, 'eid': entity.eid, 'extid': extid,
                 'source': source.uri, 'mtime': datetime.now()}
        self.doexec(session, self.sqlgen.insert('entities', attrs), attrs)
        # now we can update the full text index
        if self.do_fti and self.need_fti_indexation(entity.__regid__):
            if complete:
                entity.complete(entity.e_schema.indexable_attributes())
            FTIndexEntityOp(session, entity=entity)

    def update_info(self, session, entity, need_fti_update):
        """mark entity as being modified, fulltext reindex if needed"""
        if self.do_fti and need_fti_update:
            # reindex the entity only if this query is updating at least
            # one indexable attribute
            FTIndexEntityOp(session, entity=entity)
        # update entities.mtime
        attrs = {'eid': entity.eid, 'mtime': datetime.now()}
        self.doexec(session, self.sqlgen.update('entities', attrs, ['eid']), attrs)

    def delete_info(self, session, entity, uri, extid):
        """delete system information on deletion of an entity by transfering
        record from the entities table to the deleted_entities table
        """
        attrs = {'eid': entity.eid}
        self.doexec(session, self.sqlgen.delete('entities', attrs), attrs)
        if extid is not None:
            assert isinstance(extid, str), type(extid)
            extid = b64encode(extid)
        attrs = {'type': entity.__regid__, 'eid': entity.eid, 'extid': extid,
                 'source': uri, 'dtime': datetime.now(),
                 }
        self.doexec(session, self.sqlgen.insert('deleted_entities', attrs), attrs)

    def modified_entities(self, session, etypes, mtime):
        """return a 2-uple:
        * list of (etype, eid) of entities of the given types which have been
          modified since the given timestamp (actually entities whose full text
          index content has changed)
        * list of (etype, eid) of entities of the given types which have been
          deleted since the given timestamp
        """
        modsql = _modified_sql('entities', etypes)
        cursor = self.doexec(session, modsql, {'time': mtime})
        modentities = cursor.fetchall()
        delsql = _modified_sql('deleted_entities', etypes)
        cursor = self.doexec(session, delsql, {'time': mtime})
        delentities = cursor.fetchall()
        return modentities, delentities

    # undo support #############################################################

    def undoable_transactions(self, session, ueid=None, **actionfilters):
        """See :class:`cubicweb.dbapi.Connection.undoable_transactions`"""
        # force filtering to session's user if not a manager
        if not session.user.is_in_group('managers'):
            ueid = session.user.eid
        restr = {}
        if ueid is not None:
            restr['tx_user'] = ueid
        sql = self.sqlgen.select('transactions', restr, ('tx_uuid', 'tx_time', 'tx_user'))
        if actionfilters:
            # we will need subqueries to filter transactions according to
            # actions done
            tearestr = {} # filters on the tx_entity_actions table
            trarestr = {} # filters on the tx_relation_actions table
            genrestr = {} # generic filters, appliyable to both table
            # unless public explicitly set to false, we only consider public
            # actions
            if actionfilters.pop('public', True):
                genrestr['txa_public'] = True
            # put additional filters in trarestr and/or tearestr
            for key, val in actionfilters.iteritems():
                if key == 'etype':
                    # filtering on etype implies filtering on entity actions
                    # only, and with no eid specified
                    assert actionfilters.get('action', 'C') in 'CUD'
                    assert not 'eid' in actionfilters
                    tearestr['etype'] = val
                elif key == 'eid':
                    # eid filter may apply to 'eid' of tx_entity_actions or to
                    # 'eid_from' OR 'eid_to' of tx_relation_actions
                    if actionfilters.get('action', 'C') in 'CUD':
                        tearestr['eid'] = val
                    if actionfilters.get('action', 'A') in 'AR':
                        trarestr['eid_from'] = val
                        trarestr['eid_to'] = val
                elif key == 'action':
                    if val in 'CUD':
                        tearestr['txa_action'] = val
                    else:
                        assert val in 'AR'
                        trarestr['txa_action'] = val
                else:
                    raise AssertionError('unknow filter %s' % key)
            assert trarestr or tearestr, "can't only filter on 'public'"
            subqsqls = []
            # append subqueries to the original query, using EXISTS()
            if trarestr or (genrestr and not tearestr):
                trarestr.update(genrestr)
                trasql = self.sqlgen.select('tx_relation_actions', trarestr, ('1',))
                if 'eid_from' in trarestr:
                    # replace AND by OR between eid_from/eid_to restriction
                    trasql = sql_or_clauses(trasql, ['eid_from = %(eid_from)s',
                                                     'eid_to = %(eid_to)s'])
                trasql += ' AND transactions.tx_uuid=tx_relation_actions.tx_uuid'
                subqsqls.append('EXISTS(%s)' % trasql)
            if tearestr or (genrestr and not trarestr):
                tearestr.update(genrestr)
                teasql = self.sqlgen.select('tx_entity_actions', tearestr, ('1',))
                teasql += ' AND transactions.tx_uuid=tx_entity_actions.tx_uuid'
                subqsqls.append('EXISTS(%s)' % teasql)
            if restr:
                sql += ' AND %s' % ' OR '.join(subqsqls)
            else:
                sql += ' WHERE %s' % ' OR '.join(subqsqls)
            restr.update(trarestr)
            restr.update(tearestr)
        # we want results ordered by transaction's time descendant
        sql += ' ORDER BY tx_time DESC'
        cu = self.doexec(session, sql, restr)
        # turn results into transaction objects
        return [tx.Transaction(*args) for args in cu.fetchall()]

    def tx_info(self, session, txuuid):
        """See :class:`cubicweb.dbapi.Connection.transaction_info`"""
        return tx.Transaction(txuuid, *self._tx_info(session, txuuid))

    def tx_actions(self, session, txuuid, public):
        """See :class:`cubicweb.dbapi.Connection.transaction_actions`"""
        self._tx_info(session, txuuid)
        restr = {'tx_uuid': txuuid}
        if public:
            restr['txa_public'] = True
        sql = self.sqlgen.select('tx_entity_actions', restr,
                                 ('txa_action', 'txa_public', 'txa_order',
                                  'etype', 'eid', 'changes'))
        cu = self.doexec(session, sql, restr)
        actions = [tx.EntityAction(a,p,o,et,e,c and loads(self.binary_to_str(c)))
                   for a,p,o,et,e,c in cu.fetchall()]
        sql = self.sqlgen.select('tx_relation_actions', restr,
                                 ('txa_action', 'txa_public', 'txa_order',
                                  'rtype', 'eid_from', 'eid_to'))
        cu = self.doexec(session, sql, restr)
        actions += [tx.RelationAction(*args) for args in cu.fetchall()]
        return sorted(actions, key=lambda x: x.order)

    def undo_transaction(self, session, txuuid):
        """See :class:`cubicweb.dbapi.Connection.undo_transaction`"""
        # set mode so pool isn't released subsquently until commit/rollback
        session.mode = 'write'
        errors = []
        with hooks_control(session, session.HOOKS_DENY_ALL, 'integrity'):
            with security_enabled(session, read=False):
                for action in reversed(self.tx_actions(session, txuuid, False)):
                    undomethod = getattr(self, '_undo_%s' % action.action.lower())
                    errors += undomethod(session, action)
        # remove the transactions record
        self.doexec(session,
                    "DELETE FROM transactions WHERE tx_uuid='%s'" % txuuid)
        return errors

    def start_undoable_transaction(self, session, uuid):
        """session callback to insert a transaction record in the transactions
        table when some undoable transaction is started
        """
        ueid = session.user.eid
        attrs = {'tx_uuid': uuid, 'tx_user': ueid, 'tx_time': datetime.now()}
        self.doexec(session, self.sqlgen.insert('transactions', attrs), attrs)

    def _save_attrs(self, session, entity, attrs):
        """return a pickleable dictionary containing current values for given
        attributes of the entity
        """
        restr = {'cw_eid': entity.eid}
        sql = self.sqlgen.select(SQL_PREFIX + entity.__regid__, restr, attrs)
        cu = self.doexec(session, sql, restr)
        values = dict(zip(attrs, cu.fetchone()))
        # ensure backend specific binary are converted back to string
        eschema = entity.e_schema
        for column in attrs:
            # [3:] remove 'cw_' prefix
            attr = column[3:]
            if not eschema.subjrels[attr].final:
                continue
            if eschema.destination(attr) in ('Password', 'Bytes'):
                value = values[column]
                if value is not None:
                    values[column] = self.binary_to_str(value)
        return values

    def _record_tx_action(self, session, table, action, **kwargs):
        """record a transaction action in the given table (either
        'tx_entity_actions' or 'tx_relation_action')
        """
        kwargs['tx_uuid'] = session.transaction_uuid()
        kwargs['txa_action'] = action
        kwargs['txa_order'] = session.transaction_inc_action_counter()
        kwargs['txa_public'] = session.running_dbapi_query
        self.doexec(session, self.sqlgen.insert(table, kwargs), kwargs)

    def _tx_info(self, session, txuuid):
        """return transaction's time and user of the transaction with the given uuid.

        raise `NoSuchTransaction` if there is no such transaction of if the
        session's user isn't allowed to see it.
        """
        restr = {'tx_uuid': txuuid}
        sql = self.sqlgen.select('transactions', restr, ('tx_time', 'tx_user'))
        cu = self.doexec(session, sql, restr)
        try:
            time, ueid = cu.fetchone()
        except TypeError:
            raise tx.NoSuchTransaction()
        if not (session.user.is_in_group('managers')
                or session.user.eid == ueid):
            raise tx.NoSuchTransaction()
        return time, ueid

    def _undo_d(self, session, action):
        """undo an entity deletion"""
        errors = []
        err = errors.append
        eid = action.eid
        etype = action.etype
        _ = session._
        # get an entity instance
        try:
            entity = self.repo.vreg['etypes'].etype_class(etype)(session)
        except Exception:
            err("can't restore entity %s of type %s, type no more supported"
                % (eid, etype))
            return errors
        # check for schema changes, entities linked through inlined relation
        # still exists, rewrap binary values
        eschema = entity.e_schema
        getrschema = eschema.subjrels
        for column, value in action.changes.items():
            rtype = column[3:] # remove cw_ prefix
            try:
                rschema = getrschema[rtype]
            except KeyError:
                err(_("Can't restore relation %(rtype)s of entity %(eid)s, "
                      "this relation does not exists anymore in the schema.")
                    % {'rtype': rtype, 'eid': eid})
            if not rschema.final:
                assert value is None
                    # try:
                    #     tentity = session.entity_from_eid(eid)
                    # except UnknownEid:
                    #     err(_("Can't restore %(role)s relation %(rtype)s to "
                    #           "entity %(eid)s which doesn't exist anymore.")
                    #         % {'role': _('subject'),
                    #            'rtype': _(rtype),
                    #            'eid': eid})
                    #     continue
                    # rdef = rdefs[(eschema, tentity.__regid__)]
                    # try:
                    #     _undo_check_relation_target(tentity, rdef, 'object')
                    # except UndoException, ex:
                    #     err(unicode(ex))
                    #     continue
                    # if rschema.inlined:
                    #     entity[rtype] = value
                    # else:
                    #     # restore relation where inlined changed since the deletion
                    #     del action.changes[column]
                    #     self._add_relation(session, subject, rtype, object)
                    # # set related cache
                    # session.update_rel_cache_add(eid, rtype, value,
                    #                              rschema.symmetric)
            elif eschema.destination(rtype) in ('Bytes', 'Password'):
                action.changes[column] = self._binary(value)
                entity[rtype] = Binary(value)
            elif isinstance(value, str):
                entity[rtype] = unicode(value, session.encoding, 'replace')
            else:
                entity[rtype] = value
        entity.set_eid(eid)
        entity.edited_attributes = set(entity)
        entity.check()
        self.repo.hm.call_hooks('before_add_entity', session, entity=entity)
        # restore the entity
        action.changes['cw_eid'] = eid
        sql = self.sqlgen.insert(SQL_PREFIX + etype, action.changes)
        self.doexec(session, sql, action.changes)
        # restore record in entities (will update fti if needed)
        self.add_info(session, entity, self, None, True)
        # remove record from deleted_entities
        self.doexec(session, 'DELETE FROM deleted_entities WHERE eid=%s' % eid)
        self.repo.hm.call_hooks('after_add_entity', session, entity=entity)
        return errors

    def _undo_r(self, session, action):
        """undo a relation removal"""
        errors = []
        err = errors.append
        _ = session._
        subj, rtype, obj = action.eid_from, action.rtype, action.eid_to
        entities = []
        for role, eid in (('subject', subj), ('object', obj)):
            try:
                entities.append(session.entity_from_eid(eid))
            except UnknownEid:
                err(_("Can't restore relation %(rtype)s, %(role)s entity %(eid)s"
                      " doesn't exist anymore.")
                    % {'role': _(role),
                       'rtype': _(rtype),
                       'eid': eid})
        if not len(entities) == 2:
            return errors
        sentity, oentity = entities
        try:
            rschema = self.schema.rschema(rtype)
            rdef = rschema.rdefs[(sentity.__regid__, oentity.__regid__)]
        except KeyError:
            err(_("Can't restore relation %(rtype)s between %(subj)s and "
                  "%(obj)s, that relation does not exists anymore in the "
                  "schema.")
                % {'rtype': rtype,
                   'subj': subj,
                   'obj': obj})
        else:
            for role, entity in (('subject', sentity),
                                 ('object', oentity)):
                try:
                    _undo_check_relation_target(entity, rdef, role)
                except UndoException, ex:
                    err(unicode(ex))
                    continue
        if not errors:
            self.repo.hm.call_hooks('before_add_relation', session,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
            # add relation in the database
            self._add_relation(session, subj, rtype, obj, rschema.inlined)
            # set related cache
            session.update_rel_cache_add(subj, rtype, obj, rschema.symmetric)
            self.repo.hm.call_hooks('after_add_relation', session,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
        return errors

    def _undo_c(self, session, action):
        """undo an entity creation"""
        return ['undoing of entity creation not yet supported.']

    def _undo_u(self, session, action):
        """undo an entity update"""
        return ['undoing of entity updating not yet supported.']

    def _undo_a(self, session, action):
        """undo a relation addition"""
        return ['undoing of relation addition not yet supported.']

    # full text index handling #################################################

    @cached
    def need_fti_indexation(self, etype):
        eschema = self.schema.eschema(etype)
        if any(eschema.indexable_attributes()):
            return True
        if any(eschema.fulltext_containers()):
            return True
        return False

    def index_entity(self, session, entity):
        """create an operation to [re]index textual content of the given entity
        on commit
        """
        FTIndexEntityOp(session, entity=entity)

    def fti_unindex_entity(self, session, eid):
        """remove text content for entity with the given eid from the full text
        index
        """
        try:
            self.dbhelper.cursor_unindex_object(eid, session.pool['system'])
        except Exception: # let KeyboardInterrupt / SystemExit propagate
            self.exception('error while unindexing %s', eid)

    def fti_index_entity(self, session, entity):
        """add text content of a created/modified entity to the full text index
        """
        self.debug('reindexing %r', entity.eid)
        try:
            # use cursor_index_object, not cursor_reindex_object since
            # unindexing done in the FTIndexEntityOp
            self.dbhelper.cursor_index_object(entity.eid, entity,
                                              session.pool['system'])
        except Exception: # let KeyboardInterrupt / SystemExit propagate
            self.exception('error while reindexing %s', entity)


class FTIndexEntityOp(hook.LateOperation):
    """operation to delay entity full text indexation to commit

    since fti indexing may trigger discovery of other entities, it should be
    triggered on precommit, not commit, and this should be done after other
    precommit operation which may add relations to the entity
    """

    def precommit_event(self):
        session = self.session
        entity = self.entity
        if entity.eid in session.transaction_data.get('pendingeids', ()):
            return # entity added and deleted in the same transaction
        alreadydone = session.transaction_data.setdefault('indexedeids', set())
        if entity.eid in alreadydone:
            self.debug('skipping reindexation of %s, already done', entity.eid)
            return
        alreadydone.add(entity.eid)
        source = session.repo.system_source
        for container in entity.fti_containers():
            source.fti_unindex_entity(session, container.eid)
            source.fti_index_entity(session, container)

    def commit_event(self):
        pass


def sql_schema(driver):
    helper = get_db_helper(driver)
    typemap = helper.TYPE_MAPPING
    schema = """
/* Create the repository's system database */

%s

CREATE TABLE entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  source VARCHAR(64) NOT NULL,
  mtime %s NOT NULL,
  extid VARCHAR(256)
);;
CREATE INDEX entities_type_idx ON entities(type);;
CREATE INDEX entities_mtime_idx ON entities(mtime);;
CREATE INDEX entities_extid_idx ON entities(extid);;

CREATE TABLE deleted_entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  source VARCHAR(64) NOT NULL,
  dtime %s NOT NULL,
  extid VARCHAR(256)
);;
CREATE INDEX deleted_entities_type_idx ON deleted_entities(type);;
CREATE INDEX deleted_entities_dtime_idx ON deleted_entities(dtime);;
CREATE INDEX deleted_entities_extid_idx ON deleted_entities(extid);;

CREATE TABLE transactions (
  tx_uuid CHAR(32) PRIMARY KEY NOT NULL,
  tx_user INTEGER NOT NULL,
  tx_time %s NOT NULL
);;
CREATE INDEX transactions_tx_user_idx ON transactions(tx_user);;

CREATE TABLE tx_entity_actions (
  tx_uuid CHAR(32) REFERENCES transactions(tx_uuid) ON DELETE CASCADE,
  txa_action CHAR(1) NOT NULL,
  txa_public %s NOT NULL,
  txa_order INTEGER,
  eid INTEGER NOT NULL,
  etype VARCHAR(64) NOT NULL,
  changes %s
);;
CREATE INDEX tx_entity_actions_txa_action_idx ON tx_entity_actions(txa_action);;
CREATE INDEX tx_entity_actions_txa_public_idx ON tx_entity_actions(txa_public);;
CREATE INDEX tx_entity_actions_eid_idx ON tx_entity_actions(eid);;
CREATE INDEX tx_entity_actions_etype_idx ON tx_entity_actions(etype);;

CREATE TABLE tx_relation_actions (
  tx_uuid CHAR(32) REFERENCES transactions(tx_uuid) ON DELETE CASCADE,
  txa_action CHAR(1) NOT NULL,
  txa_public %s NOT NULL,
  txa_order INTEGER,
  eid_from INTEGER NOT NULL,
  eid_to INTEGER NOT NULL,
  rtype VARCHAR(256) NOT NULL
);;
CREATE INDEX tx_relation_actions_txa_action_idx ON tx_relation_actions(txa_action);;
CREATE INDEX tx_relation_actions_txa_public_idx ON tx_relation_actions(txa_public);;
CREATE INDEX tx_relation_actions_eid_from_idx ON tx_relation_actions(eid_from);;
CREATE INDEX tx_relation_actions_eid_to_idx ON tx_relation_actions(eid_to);;
""" % (helper.sql_create_sequence('entities_id_seq').replace(';', ';;'),
       typemap['Datetime'], typemap['Datetime'], typemap['Datetime'],
       typemap['Boolean'], typemap['Bytes'], typemap['Boolean'])
    if helper.backend_name == 'sqlite':
        # sqlite support the ON DELETE CASCADE syntax but do nothing
        schema += '''
CREATE TRIGGER fkd_transactions
BEFORE DELETE ON transactions
FOR EACH ROW BEGIN
    DELETE FROM tx_entity_actions WHERE tx_uuid=OLD.tx_uuid;
    DELETE FROM tx_relation_actions WHERE tx_uuid=OLD.tx_uuid;
END;;
'''
    return schema


def sql_drop_schema(driver):
    helper = get_db_helper(driver)
    return """
%s
DROP TABLE entities;
DROP TABLE deleted_entities;
DROP TABLE transactions;
DROP TABLE tx_entity_actions;
DROP TABLE tx_relation_actions;
""" % helper.sql_drop_sequence('entities_id_seq')


def grant_schema(user, set_owner=True):
    result = ''
    for table in ('entities', 'deleted_entities', 'entities_id_seq',
                  'transactions', 'tx_entity_actions', 'tx_relation_actions'):
        if set_owner:
            result = 'ALTER TABLE %s OWNER TO %s;\n' % (table, user)
        result += 'GRANT ALL ON %s TO %s;\n' % (table, user)
    return result


class BaseAuthentifier(object):

    def __init__(self, source=None):
        self.source = source

    def set_schema(self, schema):
        """set the instance'schema"""
        pass

class LoginPasswordAuthentifier(BaseAuthentifier):
    passwd_rql = "Any P WHERE X is CWUser, X login %(login)s, X upassword P"
    auth_rql = "Any X WHERE X is CWUser, X login %(login)s, X upassword %(pwd)s"
    _sols = ({'X': 'CWUser', 'P': 'Password'},)

    def set_schema(self, schema):
        """set the instance'schema"""
        if 'CWUser' in schema: # probably an empty schema if not true...
            # rql syntax trees used to authenticate users
            self._passwd_rqlst = self.source.compile_rql(self.passwd_rql, self._sols)
            self._auth_rqlst = self.source.compile_rql(self.auth_rql, self._sols)

    def authenticate(self, session, login, password=None, **kwargs):
        """return CWUser eid for the given login/password if this account is
        defined in this source, else raise `AuthenticationError`

        two queries are needed since passwords are stored crypted, so we have
        to fetch the salt first
        """
        args = {'login': login, 'pwd' : password}
        if password is not None:
            rset = self.source.syntax_tree_search(session, self._passwd_rqlst, args)
            try:
                pwd = rset[0][0]
            except IndexError:
                raise AuthenticationError('bad login')
            # passwords are stored using the Bytes type, so we get a StringIO
            if pwd is not None:
                args['pwd'] = Binary(crypt_password(password, pwd.getvalue()[:2]))
        # get eid from login and (crypted) password
        rset = self.source.syntax_tree_search(session, self._auth_rqlst, args)
        try:
            return rset[0][0]
        except IndexError:
            raise AuthenticationError('bad password')
