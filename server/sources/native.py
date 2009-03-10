"""Adapters for native cubicweb sources.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from threading import Lock
from datetime import datetime

from logilab.common.cache import Cache
from logilab.common.configuration import REQUIRED
from logilab.common.adbh import get_adv_func_helper

from indexer import get_indexer

from cubicweb import UnknownEid, AuthenticationError, Binary, server
from cubicweb.server.utils import crypt_password
from cubicweb.server.sqlutils import SQLAdapterMixIn
from cubicweb.server.rqlannotation import set_qdata
from cubicweb.server.sources import AbstractSource
from cubicweb.server.sources.rql2sql import SQLGenerator


NONSYSTEM_ETYPES = set()
NONSYSTEM_RELATIONS = set()

class LogCursor(object):
    def __init__(self, cursor):
        self.cu = cursor
        
    def execute(self, query, args=None):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        if server.DEBUG:
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
            # assert not schema(ttype).is_final()
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


class NativeSQLSource(SQLAdapterMixIn, AbstractSource):
    """adapter for source using the native cubicweb schema (see below)
    """
    # need default value on class since migration doesn't call init method
    has_deleted_entitites_table = True
    
    passwd_rql = "Any P WHERE X is EUser, X login %(login)s, X upassword P"
    auth_rql = "Any X WHERE X is EUser, X login %(login)s, X upassword %(pwd)s"
    _sols = ({'X': 'EUser', 'P': 'Password'},)
    
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
        ('db-name',
         {'type' : 'string',
          'default': REQUIRED,
          'help': 'database name',
          'group': 'native-source', 'inputlevel': 0,
          }),
        ('db-user',
         {'type' : 'string',
          'default': 'cubicweb',
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
        AbstractSource.__init__(self, repo, appschema, source_config,
                                *args, **kwargs)
        # sql generator
        self._rql_sqlgen = SQLGenerator(appschema, self.dbhelper,
                                        self.encoding)
        # full text index helper
        self.indexer = get_indexer(self.dbdriver, self.encoding)
        # advanced functionality helper
        self.dbhelper.fti_uid_attr = self.indexer.uid_attr
        self.dbhelper.fti_table = self.indexer.table
        self.dbhelper.fti_restriction_sql = self.indexer.restriction_sql
        self.dbhelper.fti_need_distinct_query = self.indexer.need_distinct
        # sql queries cache
        self._cache = Cache(repo.config['rql-cache-size'])
        self._temp_table_data = {}
        self._eid_creation_lock = Lock()

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        self._cache = Cache(self.repo.config['rql-cache-size'])
    
    def clear_eid_cache(self, eid, etype):
        """clear potential caches for the given eid"""
        self._cache.pop('%s X WHERE X eid %s' % (etype, eid), None)
        self._cache.pop('Any X WHERE X eid %s' % eid, None)
        
    def sqlexec(self, session, sql, args=None):
        """execute the query and return its result"""
        cursor = session.pool[self.uri]
        self.doexec(cursor, sql, args)
        return self.process_result(cursor)
    
    def init_creating(self):
        # check full text index availibility
        pool = self.repo._get_pool()
        if not self.indexer.has_fti_table(pool['system']):
            self.error('no text index table')
            self.indexer = None
        self.repo._free_pool(pool)

    def init(self):
        self.init_creating() 
        pool = self.repo._get_pool()
        # XXX cubicweb < 2.42 compat
        if 'deleted_entities' in self.dbhelper.list_tables(pool['system']):
            self.has_deleted_entitites_table = True
        else:
            self.has_deleted_entitites_table = False
        self.repo._free_pool(pool)
        
    # ISource interface #######################################################

    def compile_rql(self, rql):
        rqlst = self.repo.querier._rqlhelper.parse(rql)
        rqlst.restricted_vars = ()
        rqlst.children[0].solutions = self._sols
        self.repo.querier.sqlgen_annotate(rqlst)
        set_qdata(self.schema.rschema, rqlst, ())
        return rqlst
    
    def set_schema(self, schema):
        """set the application'schema"""
        self._cache = Cache(self.repo.config['rql-cache-size'])
        self.cache_hit, self.cache_miss, self.no_cache = 0, 0, 0
        self.schema = schema
        try:
            self._rql_sqlgen.schema = schema
        except AttributeError:
            pass # __init__
        if 'EUser' in schema: # probably an empty schema if not true...
            # rql syntax trees used to authenticate users
            self._passwd_rqlst = self.compile_rql(self.passwd_rql)
            self._auth_rqlst = self.compile_rql(self.auth_rql)
                
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

    def authenticate(self, session, login, password):
        """return EUser eid for the given login/password if this account is
        defined in this source, else raise `AuthenticationError`

        two queries are needed since passwords are stored crypted, so we have
        to fetch the salt first
        """
        args = {'login': login, 'pwd' : password}
        if password is not None:
            rset = self.syntax_tree_search(session, self._passwd_rqlst, args)
            try:
                pwd = rset[0][0]
            except IndexError:
                raise AuthenticationError('bad login')
            # passwords are stored using the bytea type, so we get a StringIO
            if pwd is not None:
                args['pwd'] = crypt_password(password, pwd.getvalue()[:2])
        # get eid from login and (crypted) password
        rset = self.syntax_tree_search(session, self._auth_rqlst, args)
        try:
            return rset[0][0]
        except IndexError:
            raise AuthenticationError('bad password')
    
    def syntax_tree_search(self, session, union, args=None, cachekey=None, 
                           varmap=None):
        """return result from this source for a rql query (actually from
        a rql syntax tree and a solution dictionary mapping each used
        variable to a possible type). If cachekey is given, the query
        necessary to fetch the results (but not the results themselves)
        may be cached using this key.
        """
        if server.DEBUG:
            print 'RQL FOR NATIVE SOURCE', self.uri, cachekey
            if varmap:
                print 'USING VARMAP', varmap
            print union.as_string()
            if args: print 'ARGS', args
            print 'SOLUTIONS', ','.join(str(s.solutions) for s in union.children)
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
        cursor = session.pool[self.uri]
        assert isinstance(sql, basestring), repr(sql)
        try:
            self.doexec(cursor, sql, args)
        except (self.dbapi_module.OperationalError,
                self.dbapi_module.InterfaceError):
            # FIXME: better detection of deconnection pb
            self.info("request failed '%s' ... retry with a new cursor", sql)
            session.pool.reconnect(self)
            cursor = session.pool[self.uri]
            self.doexec(cursor, sql, args)
        res = self.process_result(cursor)
        if server.DEBUG:
            print '------>', res
        return res
                
    def flying_insert(self, table, session, union, args=None, varmap=None):
        """similar as .syntax_tree_search, but inserts data in the
        temporary table (on-the-fly if possible, eg for the system
        source whose the given cursor come from). If not possible,
        inserts all data by calling .executemany().
        """
        if self.uri == 'system':
            if server.DEBUG:
                print 'FLYING RQL FOR SOURCE', self.uri
                if varmap:
                    print 'USING VARMAP', varmap
                print union.as_string()
                print 'SOLUTIONS', ','.join(str(s.solutions) for s in union.children)
            # generate sql queries if we are able to do so
            sql, query_args = self._rql_sqlgen.generate(union, args, varmap)
            query = 'INSERT INTO %s %s' % (table, sql.encode(self.encoding))
            self.doexec(session.pool[self.uri], query,
                        self.merge_args(args, query_args))
# XXX commented until it's proved to be necessary
#             # XXX probably inefficient
#             tempdata = self._temp_table_data.setdefault(table, set())
#             cursor = session.pool[self.uri]
#             cursor.execute('select * from %s' % table)
#             for row in cursor.fetchall():
#                 print 'data', row
#                 tempdata.add(tuple(row))
        else:
            super(NativeSQLSource, self).flying_insert(table, session, union,
                                                       args, varmap)
        
    def _manual_insert(self, results, table, session):
        """insert given result into a temporary table on the system source"""
        #print 'manual insert', table, results
        if not results:
            return
        #cursor.execute('select * from %s'%table)
        #assert len(cursor.fetchall())== 0
        encoding = self.encoding
        # added chr to be sqlite compatible
        query_args = ['%%(%s)s' % i for i in xrange(len(results[0]))]
        query = 'INSERT INTO %s VALUES(%s)' % (table, ','.join(query_args))
        kwargs_list = []
#        tempdata = self._temp_table_data.setdefault(table, set())
        for row in results:
            kwargs = {}
            row = tuple(row)
# XXX commented until it's proved to be necessary
#             if row in tempdata:
#                 continue
#             tempdata.add(row)
            for index, cell in enumerate(row):
                if type(cell) is unicode:
                    cell = cell.encode(encoding)
                elif isinstance(cell, Binary):
                    cell = self.binary(cell.getvalue())
                kwargs[str(index)] = cell
            kwargs_list.append(kwargs)
        self.doexecmany(session.pool[self.uri], query, kwargs_list)

    def clean_temp_data(self, session, temptables):
        """remove temporary data, usually associated to temporary tables"""
        if temptables:
            cursor = session.pool[self.uri]
            for table in temptables:
                try:
                    self.doexec(cursor,'DROP TABLE %s' % table)
                except:
                    pass
                try:
                    del self._temp_table_data[table]
                except KeyError:
                    continue
    
    def add_entity(self, session, entity):
        """add a new entity to the source"""
        attrs = self.preprocess_entity(entity)
        sql = self.sqlgen.insert(str(entity.e_schema), attrs)
        self.doexec(session.pool[self.uri], sql, attrs)
        
    def update_entity(self, session, entity):
        """replace an entity in the source"""
        attrs = self.preprocess_entity(entity)
        sql = self.sqlgen.update(str(entity.e_schema), attrs, ['eid'])
        self.doexec(session.pool[self.uri], sql, attrs)

    def delete_entity(self, session, etype, eid):
        """delete an entity from the source"""
        attrs = {'eid': eid}
        sql = self.sqlgen.delete(etype, attrs)
        self.doexec(session.pool[self.uri], sql, attrs)

    def add_relation(self, session, subject, rtype, object):
        """add a relation to the source"""
        attrs = {'eid_from': subject, 'eid_to': object}
        sql = self.sqlgen.insert('%s_relation' % rtype, attrs)
        self.doexec(session.pool[self.uri], sql, attrs)
    
    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        rschema = self.schema.rschema(rtype)
        if rschema.inlined:
            etype = session.describe(subject)[0]
            sql = 'UPDATE %s SET %s=NULL WHERE eid=%%(eid)s' % (etype, rtype)
            attrs = {'eid' : subject}
        else:
            attrs = {'eid_from': subject, 'eid_to': object}
            sql = self.sqlgen.delete('%s_relation' % rtype, attrs)
        self.doexec(session.pool[self.uri], sql, attrs)    

    def doexec(self, cursor, query, args=None):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        #t1 = time()
        if server.DEBUG:
            print 'exec', query, args
        #import sys
        #sys.stdout.flush()
        # str(query) to avoid error if it's an unicode string
        try:
            cursor.execute(str(query), args)
        except Exception, ex:
            self.critical("sql: %r\n args: %s\ndbms message: %r",
                          query, args, ex.args[0])
            raise
        
    def doexecmany(self, cursor, query, args):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        #t1 = time()
        if server.DEBUG:
            print 'execmany', query, 'with', len(args), 'arguments'
        #import sys
        #sys.stdout.flush()
        # str(query) to avoid error if it's an unicode string
        try:
            cursor.executemany(str(query), args)
        except:
            self.critical("sql many: %r\n args: %s", query, args)
            raise
        
    # short cut to method requiring advanced db helper usage ##################
            
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
            res = session.system_sql(sql).fetchone()
        except:
            assert session.pool, 'session has no pool set'
            raise UnknownEid(eid)
        if res is None:
            raise UnknownEid(eid)
        return res

    def extid2eid(self, session, source, lid):
        """get eid from a local id. An eid is attributed if no record is found"""
        cursor = session.system_sql('SELECT eid FROM entities WHERE '
                                    'extid=%(x)s AND source=%(s)s',
                                    # str() necessary with pg 8.3
                                    {'x': str(lid), 's': source.uri})
        # XXX testing rowcount cause strange bug with sqlite, results are there
        #     but rowcount is 0
        #if cursor.rowcount > 0: 
        try:
            result = cursor.fetchone()
            if result:
                eid = result[0]
                return eid            
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
        self.doexec(session.pool[self.uri], sql)
    
    def create_eid(self, session):
        self._eid_creation_lock.acquire()
        try:
            cursor = session.pool[self.uri]
            for sql in self.dbhelper.sqls_increment_sequence('entities_id_seq'):
                self.doexec(cursor, sql)
            return cursor.fetchone()[0]
        finally:
            self._eid_creation_lock.release()

    def add_info(self, session, entity, source, extid=None):
        """add type and source info for an eid into the system table"""
        # begin by inserting eid/type/source/extid into the entities table
        attrs = {'type': str(entity.e_schema), 'eid': entity.eid,
                 'extid': extid, 'source': source.uri, 'mtime': datetime.now()}
        session.system_sql(self.sqlgen.insert('entities', attrs), attrs)

    def delete_info(self, session, eid, etype, uri, extid):
        """delete system information on deletion of an entity by transfering
        record from the entities table to the deleted_entities table
        """
        attrs = {'eid': eid}
        session.system_sql(self.sqlgen.delete('entities', attrs), attrs)
        if self.has_deleted_entitites_table:
            attrs = {'type': etype, 'eid': eid, 'extid': extid,
                     'source': uri, 'dtime': datetime.now()}
            session.system_sql(self.sqlgen.insert('deleted_entities', attrs), attrs)
        
    def fti_unindex_entity(self, session, eid):
        """remove text content for entity with the given eid from the full text
        index
        """
        try:
            self.indexer.cursor_unindex_object(eid, session.pool['system'])
        except:
            if self.indexer is not None:
                self.exception('error while unindexing %s', eid)
        
    def fti_index_entity(self, session, entity):
        """add text content of a created/modified entity to the full text index
        """
        self.info('reindexing %r', entity.eid)
        try:
            self.indexer.cursor_reindex_object(entity.eid, entity,
                                               session.pool['system'])
        except:
            if self.indexer is not None:
                self.exception('error while reindexing %s', entity)
        # update entities.mtime
        attrs = {'eid': entity.eid, 'mtime': datetime.now()}
        session.system_sql(self.sqlgen.update('entities', attrs, ['eid']), attrs)
        
    def modified_entities(self, session, etypes, mtime):
        """return a 2-uple:
        * list of (etype, eid) of entities of the given types which have been
          modified since the given timestamp (actually entities whose full text
          index content has changed)
        * list of (etype, eid) of entities of the given types which have been
          deleted since the given timestamp
        """
        modsql = _modified_sql('entities', etypes)
        cursor = session.system_sql(modsql, {'time': mtime})
        modentities = cursor.fetchall()
        delsql = _modified_sql('deleted_entities', etypes)
        cursor = session.system_sql(delsql, {'time': mtime})
        delentities = cursor.fetchall()
        return modentities, delentities


def sql_schema(driver):
    helper = get_adv_func_helper(driver)
    schema = """
/* Create the repository's system database */

%s

CREATE TABLE entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  source VARCHAR(64) NOT NULL,
  mtime TIMESTAMP NOT NULL,
  extid VARCHAR(256)
);
CREATE INDEX entities_type_idx ON entities(type);
CREATE INDEX entities_mtime_idx ON entities(mtime);
CREATE INDEX entities_extid_idx ON entities(extid);

CREATE TABLE deleted_entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  source VARCHAR(64) NOT NULL,
  dtime TIMESTAMP NOT NULL,
  extid VARCHAR(256)
);
CREATE INDEX deleted_entities_type_idx ON deleted_entities(type);
CREATE INDEX deleted_entities_dtime_idx ON deleted_entities(dtime);
CREATE INDEX deleted_entities_extid_idx ON deleted_entities(extid);
""" % helper.sql_create_sequence('entities_id_seq')
    return schema


def sql_drop_schema(driver):
    helper = get_adv_func_helper(driver)
    return """
%s
DROP TABLE entities;
DROP TABLE deleted_entities;
""" % helper.sql_drop_sequence('entities_id_seq')


def grant_schema(user, set_owner=True):
    result = ''
    if set_owner:
        result = 'ALTER TABLE entities OWNER TO %s;\n' % user
        result += 'ALTER TABLE deleted_entities OWNER TO %s;\n' % user
        result += 'ALTER TABLE entities_id_seq OWNER TO %s;\n' % user
    result += 'GRANT ALL ON entities TO %s;\n' % user
    result += 'GRANT ALL ON deleted_entities TO %s;\n' % user
    result += 'GRANT ALL ON entities_id_seq TO %s;\n' % user
    return result
