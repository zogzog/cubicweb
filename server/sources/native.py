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
"""Adapters for native cubicweb sources.

Notes:
* extid (aka external id, the primary key of an entity in the external source
  from which it comes from) are stored in a varchar column encoded as a base64
  string. This is because it should actually be Bytes but we want an index on
  it for fast querying.
"""
__docformat__ = "restructuredtext en"

try:
    from cPickle import loads, dumps
    import cPickle as pickle
except ImportError:
    from pickle import loads, dumps
    import pickle
from threading import Lock
from datetime import datetime
from base64 import b64decode, b64encode
from contextlib import contextmanager
from os.path import abspath, basename
import re
import itertools
import zipfile
import logging
import sys

from logilab.common.compat import any
from logilab.common.decorators import cached, clear_cache
from logilab.common.configuration import Method
from logilab.common.shellutils import getlogin
from logilab.database import get_db_helper, sqlgen

from yams import schema2sql as y2sql
from yams.schema import role_name

from cubicweb import (UnknownEid, AuthenticationError, ValidationError, Binary,
                      UniqueTogetherError, QueryError, UndoTransactionException)
from cubicweb import transaction as tx, server, neg_role
from cubicweb.utils import QueryCache
from cubicweb.schema import VIRTUAL_RTYPES
from cubicweb.cwconfig import CubicWebNoAppConfiguration
from cubicweb.server import hook
from cubicweb.server.utils import crypt_password, eschema_eid, verify_and_update
from cubicweb.server.sqlutils import SQL_PREFIX, SQLAdapterMixIn
from cubicweb.server.rqlannotation import set_qdata
from cubicweb.server.hook import CleanupDeletedEidsCacheOp
from cubicweb.server.edition import EditedEntity
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
        except Exception as ex:
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

def rdef_table_column(rdef):
    """return table and column used to store the given relation definition in
    the database
    """
    return (SQL_PREFIX + str(rdef.subject),
            SQL_PREFIX + str(rdef.rtype))

def rdef_physical_info(dbhelper, rdef):
    """return backend type and a boolean flag if NULL values should be allowed
    for a given relation definition
    """
    if rdef.object.final:
        ttype = rdef.object
    else:
        ttype = 'Int' # eid type
    coltype = y2sql.type_from_constraints(dbhelper, ttype,
                                          rdef.constraints, creating=False)
    allownull = rdef.cardinality[0] != '1'
    return coltype, allownull


class _UndoException(Exception):
    """something went wrong during undoing"""

    def __unicode__(self):
        """Called by the unicode builtin; should return a Unicode object

        Type of _UndoException message must be `unicode` by design in CubicWeb.
        """
        assert isinstance(self.args[0], unicode)
        return self.args[0]


def _undo_check_relation_target(tentity, rdef, role):
    """check linked entity has not been redirected for this relation"""
    card = rdef.role_cardinality(role)
    if card in '?1' and tentity.related(rdef.rtype, role):
        raise _UndoException(tentity._cw._(
            "Can't restore %(role)s relation %(rtype)s to entity %(eid)s which "
            "is already linked using this relation.")
                            % {'role': neg_role(role),
                               'rtype': rdef.rtype,
                               'eid': tentity.eid})

def _undo_rel_info(session, subj, rtype, obj):
    entities = []
    for role, eid in (('subject', subj), ('object', obj)):
        try:
            entities.append(session.entity_from_eid(eid))
        except UnknownEid:
            raise _UndoException(session._(
                "Can't restore relation %(rtype)s, %(role)s entity %(eid)s"
                " doesn't exist anymore.")
                                % {'role': session._(role),
                                   'rtype': session._(rtype),
                                   'eid': eid})
    sentity, oentity = entities
    try:
        rschema = session.vreg.schema.rschema(rtype)
        rdef = rschema.rdefs[(sentity.cw_etype, oentity.cw_etype)]
    except KeyError:
        raise _UndoException(session._(
            "Can't restore relation %(rtype)s between %(subj)s and "
            "%(obj)s, that relation does not exists anymore in the "
            "schema.")
                            % {'rtype': session._(rtype),
                               'subj': subj,
                               'obj': obj})
    return sentity, oentity, rdef

def _undo_has_later_transaction(session, eid):
    return session.system_sql('''\
SELECT T.tx_uuid FROM transactions AS TREF, transactions AS T
WHERE TREF.tx_uuid='%(txuuid)s' AND T.tx_uuid!='%(txuuid)s'
AND T.tx_time>=TREF.tx_time
AND (EXISTS(SELECT 1 FROM tx_entity_actions AS TEA
            WHERE TEA.tx_uuid=T.tx_uuid AND TEA.eid=%(eid)s)
     OR EXISTS(SELECT 1 FROM tx_relation_actions as TRA
               WHERE TRA.tx_uuid=T.tx_uuid AND (
                   TRA.eid_from=%(eid)s OR TRA.eid_to=%(eid)s))
     )''' % {'txuuid': session.transaction_data['undoing_uuid'],
             'eid': eid}).fetchone()


class NativeSQLSource(SQLAdapterMixIn, AbstractSource):
    """adapter for source using the native cubicweb schema (see below)
    """
    sqlgen_class = SQLGenerator
    options = (
        ('db-driver',
         {'type' : 'string',
          'default': 'postgres',
          # XXX use choice type
          'help': 'database driver (postgres, mysql, sqlite, sqlserver2005)',
          'group': 'native-source', 'level': 0,
          }),
        ('db-host',
         {'type' : 'string',
          'default': '',
          'help': 'database host',
          'group': 'native-source', 'level': 1,
          }),
        ('db-port',
         {'type' : 'string',
          'default': '',
          'help': 'database port',
          'group': 'native-source', 'level': 1,
          }),
        ('db-name',
         {'type' : 'string',
          'default': Method('default_instance_id'),
          'help': 'database name',
          'group': 'native-source', 'level': 0,
          }),
        ('db-user',
         {'type' : 'string',
          'default': CubicWebNoAppConfiguration.mode == 'user' and getlogin() or 'cubicweb',
          'help': 'database user',
          'group': 'native-source', 'level': 0,
          }),
        ('db-password',
         {'type' : 'password',
          'default': '',
          'help': 'database password',
          'group': 'native-source', 'level': 0,
          }),
        ('db-encoding',
         {'type' : 'string',
          'default': 'utf8',
          'help': 'database encoding',
          'group': 'native-source', 'level': 1,
          }),
        ('db-extra-arguments',
         {'type' : 'string',
          'default': '',
          'help': 'set to "Trusted_Connection" if you are using SQLServer and '
                  'want trusted authentication for the database connection',
          'group': 'native-source', 'level': 2,
          }),
    )

    def __init__(self, repo, source_config, *args, **kwargs):
        SQLAdapterMixIn.__init__(self, source_config)
        self.authentifiers = [LoginPasswordAuthentifier(self)]
        if repo.config['allow-email-login']:
            self.authentifiers.insert(0, EmailPasswordAuthentifier(self))
        AbstractSource.__init__(self, repo, source_config, *args, **kwargs)
        # sql generator
        self._rql_sqlgen = self.sqlgen_class(self.schema, self.dbhelper,
                                             ATTR_MAP.copy())
        # full text index helper
        self.do_fti = not repo.config['delay-full-text-indexation']
        # sql queries cache
        self._cache = QueryCache(repo.config['rql-cache-size'])
        self._temp_table_data = {}
        # we need a lock to protect eid attribution function (XXX, really?
        # explain)
        self._eid_cnx_lock = Lock()
        self._eid_creation_cnx = None
        # (etype, attr) / storage mapping
        self._storages = {}
        # entity types that may be used by other multi-sources instances
        self.multisources_etypes = set(repo.config['multi-sources-etypes'])
        # XXX no_sqlite_wrap trick since we've a sqlite locking pb when
        # running unittest_multisources with the wrapping below
        if self.dbdriver == 'sqlite' and \
               not getattr(repo.config, 'no_sqlite_wrap', False):
            from cubicweb.server.sources.extlite import ConnectionWrapper
            self.dbhelper.dbname = abspath(self.dbhelper.dbname)
            self.get_connection = lambda: ConnectionWrapper(self)
            self.check_connection = lambda cnx: cnx
            def cnxset_freed(cnx):
                cnx.close()
            self.cnxset_freed = cnxset_freed
        if self.dbdriver == 'sqlite':
            self._create_eid = None
            self.create_eid = self._create_eid_sqlite
        self.binary_to_str = self.dbhelper.dbapi_module.binary_to_str


    @property
    def _sqlcnx(self):
        # XXX: sqlite connections can only be used in the same thread, so
        #      create a new one each time necessary. If it appears to be time
        #      consuming, find another way
        return SQLAdapterMixIn.get_connection(self)

    def check_config(self, source_entity):
        """check configuration of source entity"""
        if source_entity.host_config:
            msg = source_entity._cw._('the system source has its configuration '
                                      'stored on the file-system')
            raise ValidationError(source_entity.eid, {role_name('config', 'subject'): msg})

    def add_authentifier(self, authentifier):
        self.authentifiers.append(authentifier)
        authentifier.source = self
        authentifier.set_schema(self.schema)

    def reset_caches(self):
        """method called during test to reset potential source caches"""
        self._cache = QueryCache(self.repo.config['rql-cache-size'])

    def clear_eid_cache(self, eid, etype):
        """clear potential caches for the given eid"""
        self._cache.pop('Any X WHERE X eid %s, X is %s' % (eid, etype), None)
        self._cache.pop('Any X WHERE X eid %s' % eid, None)
        self._cache.pop('Any %s' % eid, None)

    def sqlexec(self, session, sql, args=None):
        """execute the query and return its result"""
        return self.process_result(self.doexec(session, sql, args))

    def init_creating(self, cnxset=None):
        # check full text index availibility
        if self.do_fti:
            if cnxset is None:
                _cnxset = self.repo._get_cnxset()
                _cnxset.cnxset_set()
            else:
                _cnxset = cnxset
            if not self.dbhelper.has_fti_table(_cnxset['system']):
                if not self.repo.config.creating:
                    self.critical('no text index table')
                self.do_fti = False
            if cnxset is None:
                _cnxset.cnxset_freed()
                self.repo._free_cnxset(_cnxset)

    def backup(self, backupfile, confirm, format='native'):
        """method called to create a backup of the source's data"""
        if format == 'portable':
            # ensure the schema is the one stored in the database: if repository
            # started in quick_start mode, the file system's one has been loaded
            # so force reload
            if self.repo.config.quick_start:
                self.repo.set_schema(self.repo.deserialize_schema(),
                                     resetvreg=False)
            helper = DatabaseIndependentBackupRestore(self)
            self.close_source_connections()
            try:
                helper.backup(backupfile)
            finally:
                self.open_source_connections()
        elif format == 'native':
            self.close_source_connections()
            try:
                self.backup_to_file(backupfile, confirm)
            finally:
                self.open_source_connections()
        else:
            raise ValueError('Unknown format %r' % format)


    def restore(self, backupfile, confirm, drop, format='native'):
        """method called to restore a backup of source's data"""
        if self.repo.config.init_cnxset_pool:
            self.close_source_connections()
        try:
            if format == 'portable':
                helper = DatabaseIndependentBackupRestore(self)
                helper.restore(backupfile)
            elif format == 'native':
                self.restore_from_file(backupfile, confirm, drop=drop)
            else:
                raise ValueError('Unknown format %r' % format)
        finally:
            if self.repo.config.init_cnxset_pool:
                self.open_source_connections()


    def init(self, activated, source_entity):
        try:
            # test if 'asource' column exists
            query = self.dbhelper.sql_add_limit_offset('SELECT asource FROM entities', 1)
            source_entity._cw.system_sql(query)
        except Exception as ex:
            self.eid_type_source = self.eid_type_source_pre_131
        super(NativeSQLSource, self).init(activated, source_entity)
        self.init_creating(source_entity._cw.cnxset)

    def shutdown(self):
        if self._eid_creation_cnx:
            self._eid_creation_cnx.close()
            self._eid_creation_cnx = None

    # XXX deprecates [un]map_attribute ?
    def map_attribute(self, etype, attr, cb, sourcedb=True):
        self._rql_sqlgen.attr_map['%s.%s' % (etype, attr)] = (cb, sourcedb)

    def unmap_attribute(self, etype, attr):
        self._rql_sqlgen.attr_map.pop('%s.%s' % (etype, attr), None)

    def set_storage(self, etype, attr, storage):
        storage_dict = self._storages.setdefault(etype, {})
        storage_dict[attr] = storage
        self.map_attribute(etype, attr,
                           storage.callback, storage.is_source_callback)

    def unset_storage(self, etype, attr):
        self._storages[etype].pop(attr)
        # if etype has no storage left, remove the entry
        if not self._storages[etype]:
            del self._storages[etype]
        self.unmap_attribute(etype, attr)

    def storage(self, etype, attr):
        """return the storage for the given entity type / attribute
        """
        try:
            return self._storages[etype][attr]
        except KeyError:
            raise Exception('no custom storage set for %s.%s' % (etype, attr))

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
        self._cache = QueryCache(self.repo.config['rql-cache-size'])
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
            sql, qargs, cbs = self._rql_sqlgen.generate(union, args, varmap)
        else:
            # sql may be cached
            try:
                sql, qargs, cbs = self._cache[cachekey]
                self.cache_hit += 1
            except KeyError:
                self.cache_miss += 1
                sql, qargs, cbs = self._rql_sqlgen.generate(union, args, varmap)
                self._cache[cachekey] = sql, qargs, cbs
        args = self.merge_args(args, qargs)
        assert isinstance(sql, basestring), repr(sql)
        try:
            cursor = self.doexec(session, sql, args)
        except (self.OperationalError, self.InterfaceError):
            if session.mode == 'write':
                # do not attempt to reconnect if there has been some write
                # during the transaction
                raise
            # FIXME: better detection of deconnection pb
            self.warning("trying to reconnect")
            session.cnxset.reconnect(self)
            cursor = self.doexec(session, sql, args)
        except self.DbapiError as exc:
            # We get this one with pyodbc and SQL Server when connection was reset
            if exc.args[0] == '08S01' and session.mode != 'write':
                self.warning("trying to reconnect")
                session.cnxset.reconnect(self)
                cursor = self.doexec(session, sql, args)
            else:
                raise
        results = self.process_result(cursor, cbs, session=session)
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
        sql, qargs, cbs = self._rql_sqlgen.generate(union, args, varmap)
        query = 'INSERT INTO %s %s' % (table, sql.encode(self._dbencoding))
        self.doexec(session, query, self.merge_args(args, qargs))

    def manual_insert(self, results, table, session):
        """insert given result into a temporary table on the system source"""
        if server.DEBUG & server.DBG_RQL:
            print '  manual insertion of', len(results), 'results into', table
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
                except Exception:
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
        restore_values = []
        if isinstance(entity, list):
            entities = entity
        else:
            entities = [entity]
        etype = entities[0].__regid__
        for attr, storage in self._storages.get(etype, {}).items():
            for entity in entities:
                if event == 'deleted':
                    storage.entity_deleted(entity, attr)
                else:
                    edited = entity.cw_edited
                    if attr in edited:
                        handler = getattr(storage, 'entity_%s' % event)
                        to_restore = handler(entity, attr)
                        restore_values.append((entity, attr, to_restore))
        try:
            yield # 2/ execute the source's instructions
        finally:
            # 3/ restore original values
            for entity, attr, value in restore_values:
                entity.cw_edited.edited_attribute(attr, value)

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        with self._storage_handler(entity, 'added'):
            attrs = self.preprocess_entity(entity)
            sql = self.sqlgen.insert(SQL_PREFIX + entity.cw_etype, attrs)
            self.doexec(session, sql, attrs)
            if session.ertype_supports_undo(entity.cw_etype):
                self._record_tx_action(session, 'tx_entity_actions', 'C',
                                       etype=entity.cw_etype, eid=entity.eid)

    def update_entity(self, session, entity):
        """replace an entity in the source"""
        with self._storage_handler(entity, 'updated'):
            attrs = self.preprocess_entity(entity)
            if session.ertype_supports_undo(entity.cw_etype):
                changes = self._save_attrs(session, entity, attrs)
                self._record_tx_action(session, 'tx_entity_actions', 'U',
                                       etype=entity.cw_etype, eid=entity.eid,
                                       changes=self._binary(dumps(changes)))
            sql = self.sqlgen.update(SQL_PREFIX + entity.cw_etype, attrs,
                                     ['cw_eid'])
            self.doexec(session, sql, attrs)

    def delete_entity(self, session, entity):
        """delete an entity from the source"""
        with self._storage_handler(entity, 'deleted'):
            if session.ertype_supports_undo(entity.cw_etype):
                attrs = [SQL_PREFIX + r.type
                         for r in entity.e_schema.subject_relations()
                         if (r.final or r.inlined) and not r in VIRTUAL_RTYPES]
                changes = self._save_attrs(session, entity, attrs)
                self._record_tx_action(session, 'tx_entity_actions', 'D',
                                       etype=entity.cw_etype, eid=entity.eid,
                                       changes=self._binary(dumps(changes)))
            attrs = {'cw_eid': entity.eid}
            sql = self.sqlgen.delete(SQL_PREFIX + entity.cw_etype, attrs)
            self.doexec(session, sql, attrs)

    def add_relation(self, session, subject, rtype, object, inlined=False):
        """add a relation to the source"""
        self._add_relations(session,  rtype, [(subject, object)], inlined)
        if session.ertype_supports_undo(rtype):
            self._record_tx_action(session, 'tx_relation_actions', 'A',
                                   eid_from=subject, rtype=rtype, eid_to=object)

    def add_relations(self, session,  rtype, subj_obj_list, inlined=False):
        """add a relations to the source"""
        self._add_relations(session, rtype, subj_obj_list, inlined)
        if session.ertype_supports_undo(rtype):
            for subject, object in subj_obj_list:
                self._record_tx_action(session, 'tx_relation_actions', 'A',
                                       eid_from=subject, rtype=rtype, eid_to=object)

    def _add_relations(self, session, rtype, subj_obj_list, inlined=False):
        """add a relation to the source"""
        sql = []
        if inlined is False:
            attrs = [{'eid_from': subject, 'eid_to': object}
                     for subject, object in subj_obj_list]
            sql.append((self.sqlgen.insert('%s_relation' % rtype, attrs[0]), attrs))
        else: # used by data import
            etypes = {}
            for subject, object in subj_obj_list:
                etype = session.describe(subject)[0]
                if etype in etypes:
                    etypes[etype].append((subject, object))
                else:
                    etypes[etype] = [(subject, object)]
            for subj_etype, subj_obj_list in etypes.iteritems():
                attrs = [{'cw_eid': subject, SQL_PREFIX + rtype: object}
                         for subject, object in subj_obj_list]
                sql.append((self.sqlgen.update(SQL_PREFIX + etype, attrs[0],
                                     ['cw_eid']),
                            attrs))
        for statement, attrs in sql:
            self.doexecmany(session, statement, attrs)

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        rschema = self.schema.rschema(rtype)
        self._delete_relation(session, subject, rtype, object, rschema.inlined)
        if session.ertype_supports_undo(rtype):
            self._record_tx_action(session, 'tx_relation_actions', 'R',
                                   eid_from=subject, rtype=rtype, eid_to=object)

    def _delete_relation(self, session, subject, rtype, object, inlined=False):
        """delete a relation from the source"""
        if inlined:
            table = SQL_PREFIX + session.describe(subject)[0]
            column = SQL_PREFIX + rtype
            sql = 'UPDATE %s SET %s=NULL WHERE %seid=%%(eid)s' % (table, column,
                                                                  SQL_PREFIX)
            attrs = {'eid' : subject}
        else:
            attrs = {'eid_from': subject, 'eid_to': object}
            sql = self.sqlgen.delete('%s_relation' % rtype, attrs)
        self.doexec(session, sql, attrs)

    def doexec(self, session, query, args=None, rollback=True):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        cursor = session.cnxset[self.uri]
        if server.DEBUG & server.DBG_SQL:
            cnx = session.cnxset.connection(self.uri)
            # getattr to get the actual connection if cnx is a ConnectionWrapper
            # instance
            print 'exec', query, args, getattr(cnx, '_cnx', cnx)
        try:
            # str(query) to avoid error if it's an unicode string
            cursor.execute(str(query), args)
        except Exception as ex:
            if self.repo.config.mode != 'test':
                # during test we get those message when trying to alter sqlite
                # db schema
                self.critical("sql: %r\n args: %s\ndbms message: %r",
                              query, args, ex.args[0])
            if rollback:
                try:
                    session.cnxset.connection(self.uri).rollback()
                    if self.repo.config.mode != 'test':
                        self.critical('transaction has been rolled back')
                except Exception as ex:
                    pass
            if ex.__class__.__name__ == 'IntegrityError':
                # need string comparison because of various backends
                for arg in ex.args:
                    if 'SQL Server' in arg:
                        mo = re.search("'unique_cw_[^ ]+'", arg)
                    else: # postgres
                        mo = re.search('"unique_cw_[^ ]+"', arg)
                    if mo is not None:
                        index_name = mo.group(0)[1:-1] # eat the surrounding " pair
                        elements = index_name.split('_cw_')[1:]
                        etype = elements[0]
                        rtypes = elements[1:]
                        raise UniqueTogetherError(etype, rtypes)
                    # sqlite
                    mo = re.search('columns (.*) are not unique', arg)
                    if mo is not None: # sqlite in use
                        # we left chop the 'cw_' prefix of attribute names
                        rtypes = [c.strip()[3:]
                                  for c in mo.group(1).split(',')]
                        etype = '???'
                        raise UniqueTogetherError(etype, rtypes)
            raise
        return cursor

    def doexecmany(self, session, query, args):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        if server.DEBUG & server.DBG_SQL:
            print 'execmany', query, 'with', len(args), 'arguments'
        cursor = session.cnxset[self.uri]
        try:
            # str(query) to avoid error if it's an unicode string
            cursor.executemany(str(query), args)
        except Exception as ex:
            if self.repo.config.mode != 'test':
                # during test we get those message when trying to alter sqlite
                # db schema
                self.critical("sql many: %r\n args: %s\ndbms message: %r",
                              query, args, ex.args[0])
            try:
                session.cnxset.connection(self.uri).rollback()
                if self.repo.config.mode != 'test':
                    self.critical('transaction has been rolled back')
            except Exception:
                pass
            raise

    # short cut to method requiring advanced db helper usage ##################

    def update_rdef_column(self, session, rdef):
        """update physical column for a relation definition (final or inlined)
        """
        table, column = rdef_table_column(rdef)
        coltype, allownull = rdef_physical_info(self.dbhelper, rdef)
        if not self.dbhelper.alter_column_support:
            self.error("backend can't alter %s.%s to %s%s", table, column, coltype,
                       not allownull and 'NOT NULL' or '')
            return
        self.dbhelper.change_col_type(LogCursor(session.cnxset[self.uri]),
                                      table, column, coltype, allownull)
        self.info('altered %s.%s: now %s%s', table, column, coltype,
                  not allownull and 'NOT NULL' or '')

    def update_rdef_null_allowed(self, session, rdef):
        """update NULL / NOT NULL of physical column for a relation definition
        (final or inlined)
        """
        if not self.dbhelper.alter_column_support:
            # not supported (and NOT NULL not set by yams in that case, so no
            # worry)
            return
        table, column = rdef_table_column(rdef)
        coltype, allownull = rdef_physical_info(self.dbhelper, rdef)
        self.dbhelper.set_null_allowed(LogCursor(session.cnxset[self.uri]),
                                       table, column, coltype, allownull)

    def update_rdef_indexed(self, session, rdef):
        table, column = rdef_table_column(rdef)
        if rdef.indexed:
            self.create_index(session, table, column)
        else:
            self.drop_index(session, table, column)

    def update_rdef_unique(self, session, rdef):
        table, column = rdef_table_column(rdef)
        if rdef.constraint_by_type('UniqueConstraint'):
            self.create_index(session, table, column, unique=True)
        else:
            self.drop_index(session, table, column, unique=True)

    def create_index(self, session, table, column, unique=False):
        cursor = LogCursor(session.cnxset[self.uri])
        self.dbhelper.create_index(cursor, table, column, unique)

    def drop_index(self, session, table, column, unique=False):
        cursor = LogCursor(session.cnxset[self.uri])
        self.dbhelper.drop_index(cursor, table, column, unique)

    # system source interface #################################################

    def _eid_type_source(self, session, eid, sql, _retry=True):
        try:
            res = self.doexec(session, sql).fetchone()
            if res is not None:
                return res
        except (self.OperationalError, self.InterfaceError):
            if session.mode == 'read' and _retry:
                self.warning("trying to reconnect (eid_type_source())")
                session.cnxset.reconnect(self)
                return self._eid_type_source(session, eid, sql, _retry=False)
        except Exception:
            assert session.cnxset, 'session has no connections set'
            self.exception('failed to query entities table for eid %s', eid)
        raise UnknownEid(eid)

    def eid_type_source(self, session, eid): # pylint: disable=E0202
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        sql = 'SELECT type, source, extid, asource FROM entities WHERE eid=%s' % eid
        res = self._eid_type_source(session, eid, sql)
        if res[-2] is not None:
            if not isinstance(res, list):
                res = list(res)
            res[-2] = b64decode(res[-2])
        return res

    def eid_type_source_pre_131(self, session, eid):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        sql = 'SELECT type, source, extid FROM entities WHERE eid=%s' % eid
        res = self._eid_type_source(session, eid, sql)
        if not isinstance(res, list):
            res = list(res)
        if res[-1] is not None:
            res[-1] = b64decode(res[-1])
        res.append(res[1])
        return res

    def extid2eid(self, session, source_uri, extid):
        """get eid from an external id. Return None if no record found."""
        assert isinstance(extid, str)
        cursor = self.doexec(session,
                             'SELECT eid FROM entities '
                             'WHERE extid=%(x)s AND source=%(s)s',
                             {'x': b64encode(extid), 's': source_uri})
        # XXX testing rowcount cause strange bug with sqlite, results are there
        #     but rowcount is 0
        #if cursor.rowcount > 0:
        try:
            result = cursor.fetchone()
            if result:
                return result[0]
        except Exception:
            pass
        return None

    def make_temp_table_name(self, table):
        return self.dbhelper.temporary_table_name(table)

    def temp_table_def(self, selected, sol, table):
        return make_schema(selected, sol, table, self.dbhelper.TYPE_MAPPING)

    def create_temp_table(self, session, table, schema):
        # we don't want on commit drop, this may cause problem when
        # running with an ldap source, and table will be deleted manually any way
        # on commit
        sql = self.dbhelper.sql_temporary_table(table, schema, False)
        self.doexec(session, sql)

    def _create_eid_sqlite(self, session):
        with self._eid_cnx_lock:
            for sql in self.dbhelper.sqls_increment_sequence('entities_id_seq'):
                cursor = self.doexec(session, sql)
            return cursor.fetchone()[0]


    def create_eid(self, session): # pylint: disable=E0202
        # lock needed to prevent 'Connection is busy with results for another
        # command (0)' errors with SQLServer
        with self._eid_cnx_lock:
            return self._create_eid() # pylint: disable=E1102

    def _create_eid(self): # pylint: disable=E0202
        # internal function doing the eid creation without locking.
        # needed for the recursive handling of disconnections (otherwise we
        # deadlock on self._eid_cnx_lock
        if self._eid_creation_cnx is None:
            self._eid_creation_cnx = self.get_connection()
        cnx = self._eid_creation_cnx
        try:
            cursor = cnx.cursor()
            for sql in self.dbhelper.sqls_increment_sequence('entities_id_seq'):
                cursor.execute(sql)
            eid = cursor.fetchone()[0]
        except (self.OperationalError, self.InterfaceError):
            # FIXME: better detection of deconnection pb
            self.warning("trying to reconnect create eid connection")
            self._eid_creation_cnx = None
            return self._create_eid() # pylint: disable=E1102
        except self.DbapiError as exc:
            # We get this one with pyodbc and SQL Server when connection was reset
            if exc.args[0] == '08S01':
                self.warning("trying to reconnect create eid connection")
                self._eid_creation_cnx = None
                return self._create_eid() # pylint: disable=E1102
            else:
                raise
        except Exception: # WTF?
            cnx.rollback()
            self._eid_creation_cnx = None
            self.exception('create eid failed in an unforeseen way on SQL statement %s', sql)
            raise
        else:
            cnx.commit()
            return eid

    def _handle_is_relation_sql(self, session, sql, attrs):
        """ Handler for specific is_relation sql that may be
        overwritten in some stores"""
        self.doexec(session, sql % attrs)

    _handle_insert_entity_sql = doexec
    _handle_is_instance_of_sql = _handle_source_relation_sql = _handle_is_relation_sql

    def add_info(self, session, entity, source, extid, complete):
        """add type and source info for an eid into the system table"""
        # begin by inserting eid/type/source/extid into the entities table
        if extid is not None:
            assert isinstance(extid, str)
            extid = b64encode(extid)
        uri = 'system' if source.copy_based_source else source.uri
        attrs = {'type': entity.cw_etype, 'eid': entity.eid, 'extid': extid,
                 'source': uri, 'asource': source.uri, 'mtime': datetime.utcnow()}
        self._handle_insert_entity_sql(session, self.sqlgen.insert('entities', attrs), attrs)
        # insert core relations: is, is_instance_of and cw_source
        try:
            self._handle_is_relation_sql(session, 'INSERT INTO is_relation(eid_from,eid_to) VALUES (%s,%s)',
                                         (entity.eid, eschema_eid(session, entity.e_schema)))
        except IndexError:
            # during schema serialization, skip
            pass
        else:
            for eschema in entity.e_schema.ancestors() + [entity.e_schema]:
                self._handle_is_relation_sql(session,
                                             'INSERT INTO is_instance_of_relation(eid_from,eid_to) VALUES (%s,%s)',
                                             (entity.eid, eschema_eid(session, eschema)))
        if 'CWSource' in self.schema and source.eid is not None: # else, cw < 3.10
            self._handle_is_relation_sql(session, 'INSERT INTO cw_source_relation(eid_from,eid_to) VALUES (%s,%s)',
                                         (entity.eid, source.eid))
        # now we can update the full text index
        if self.do_fti and self.need_fti_indexation(entity.cw_etype):
            if complete:
                entity.complete(entity.e_schema.indexable_attributes())
            self.index_entity(session, entity=entity)

    def update_info(self, session, entity, need_fti_update):
        """mark entity as being modified, fulltext reindex if needed"""
        if self.do_fti and need_fti_update:
            # reindex the entity only if this query is updating at least
            # one indexable attribute
            self.index_entity(session, entity=entity)
        # update entities.mtime.
        # XXX Only if entity.cw_etype in self.multisources_etypes?
        attrs = {'eid': entity.eid, 'mtime': datetime.utcnow()}
        self.doexec(session, self.sqlgen.update('entities', attrs, ['eid']), attrs)

    def delete_info_multi(self, session, entities, uri):
        """delete system information on deletion of a list of entities with the
        same etype and belinging to the same source

        * update the fti
        * remove record from the `entities` table
        * transfer it to the `deleted_entities`
        """
        self.fti_unindex_entities(session, entities)
        attrs = {'eid': '(%s)' % ','.join([str(_e.eid) for _e in entities])}
        self.doexec(session, self.sqlgen.delete_many('entities', attrs), attrs)
        if entities[0].__regid__ not in self.multisources_etypes:
            return
        attrs = {'type': entities[0].__regid__,
                 'source': uri, 'dtime': datetime.utcnow()}
        for entity in entities:
            extid = entity.cw_metainformation()['extid']
            if extid is not None:
                assert isinstance(extid, str), type(extid)
                extid = b64encode(extid)
            attrs.update({'eid': entity.eid, 'extid': extid})
            self.doexec(session, self.sqlgen.insert('deleted_entities', attrs), attrs)

    def modified_entities(self, session, etypes, mtime):
        """return a 2-uple:
        * list of (etype, eid) of entities of the given types which have been
          modified since the given timestamp (actually entities whose full text
          index content has changed)
        * list of (etype, eid) of entities of the given types which have been
          deleted since the given timestamp
        """
        for etype in etypes:
            if not etype in self.multisources_etypes:
                self.error('%s not listed as a multi-sources entity types. '
                              'Modify your configuration' % etype)
                self.multisources_etypes.add(etype)
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
        # XXX use generator to avoid loading everything in memory?
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
        """See :class:`cubicweb.dbapi.Connection.undo_transaction`

        important note: while undoing of a transaction, only hooks in the
        'integrity', 'activeintegrity' and 'undo' categories are called.
        """
        # set mode so connections set isn't released subsquently until commit/rollback
        session.mode = 'write'
        errors = []
        session.transaction_data['undoing_uuid'] = txuuid
        with session.deny_all_hooks_but('integrity', 'activeintegrity', 'undo'):
            with session.security_enabled(read=False):
                for action in reversed(self.tx_actions(session, txuuid, False)):
                    undomethod = getattr(self, '_undo_%s' % action.action.lower())
                    errors += undomethod(session, action)
        # remove the transactions record
        self.doexec(session,
                    "DELETE FROM transactions WHERE tx_uuid='%s'" % txuuid)
        if errors:
            raise UndoTransactionException(txuuid, errors)
        else:
            return

    def start_undoable_transaction(self, session, uuid):
        """session callback to insert a transaction record in the transactions
        table when some undoable transaction is started
        """
        ueid = session.user.eid
        attrs = {'tx_uuid': uuid, 'tx_user': ueid, 'tx_time': datetime.utcnow()}
        self.doexec(session, self.sqlgen.insert('transactions', attrs), attrs)

    def _save_attrs(self, session, entity, attrs):
        """return a pickleable dictionary containing current values for given
        attributes of the entity
        """
        restr = {'cw_eid': entity.eid}
        sql = self.sqlgen.select(SQL_PREFIX + entity.cw_etype, restr, attrs)
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
            raise tx.NoSuchTransaction(txuuid)
        if not (session.user.is_in_group('managers')
                or session.user.eid == ueid):
            raise tx.NoSuchTransaction(txuuid)
        return time, ueid

    def _reedit_entity(self, entity, changes, err):
        session = entity._cw
        eid = entity.eid
        entity.cw_edited = edited = EditedEntity(entity)
        # check for schema changes, entities linked through inlined relation
        # still exists, rewrap binary values
        eschema = entity.e_schema
        getrschema = eschema.subjrels
        for column, value in changes.items():
            rtype = column[len(SQL_PREFIX):]
            if rtype == "eid":
                continue # XXX should even `eid` be stored in action changes?
            try:
                rschema = getrschema[rtype]
            except KeyError:
                err(session._("can't restore relation %(rtype)s of entity %(eid)s, "
                              "this relation does not exist in the schema anymore.")
                    % {'rtype': rtype, 'eid': eid})
            if not rschema.final:
                if not rschema.inlined:
                    assert value is None
                # rschema is an inlined relation
                elif value is not None:
                    # not a deletion: we must put something in edited
                    try:
                        entity._cw.entity_from_eid(value) # check target exists
                        edited[rtype] = value
                    except UnknownEid:
                        err(session._("can't restore entity %(eid)s of type %(eschema)s, "
                                      "target of %(rtype)s (eid %(value)s) does not exist any longer")
                            % locals())
            elif eschema.destination(rtype) in ('Bytes', 'Password'):
                changes[column] = self._binary(value)
                edited[rtype] = Binary(value)
            elif isinstance(value, str):
                edited[rtype] = unicode(value, session.encoding, 'replace')
            else:
                edited[rtype] = value
        # This must only be done after init_entitiy_caches : defered in calling functions
        # edited.check()

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
        self._reedit_entity(entity, action.changes, err)
        entity.eid = eid
        session.repo.init_entity_caches(session, entity, self)
        entity.cw_edited.check()
        self.repo.hm.call_hooks('before_add_entity', session, entity=entity)
        # restore the entity
        action.changes['cw_eid'] = eid
        sql = self.sqlgen.insert(SQL_PREFIX + etype, action.changes)
        self.doexec(session, sql, action.changes)
        # restore record in entities (will update fti if needed)
        self.add_info(session, entity, self, None, True)
        # remove record from deleted_entities if entity's type is multi-sources
        if entity.cw_etype in self.multisources_etypes:
            self.doexec(session,
                        'DELETE FROM deleted_entities WHERE eid=%s' % eid)
        self.repo.hm.call_hooks('after_add_entity', session, entity=entity)
        return errors

    def _undo_r(self, session, action):
        """undo a relation removal"""
        errors = []
        subj, rtype, obj = action.eid_from, action.rtype, action.eid_to
        try:
            sentity, oentity, rdef = _undo_rel_info(session, subj, rtype, obj)
        except _UndoException as ex:
            errors.append(unicode(ex))
        else:
            for role, entity in (('subject', sentity),
                                 ('object', oentity)):
                try:
                    _undo_check_relation_target(entity, rdef, role)
                except _UndoException as ex:
                    errors.append(unicode(ex))
                    continue
        if not errors:
            self.repo.hm.call_hooks('before_add_relation', session,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
            # add relation in the database
            self._add_relations(session, rtype, [(subj, obj)], rdef.rtype.inlined)
            # set related cache
            session.update_rel_cache_add(subj, rtype, obj, rdef.rtype.symmetric)
            self.repo.hm.call_hooks('after_add_relation', session,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
        return errors

    def _undo_c(self, session, action):
        """undo an entity creation"""
        eid = action.eid
        # XXX done to avoid fetching all remaining relation for the entity
        # we should find an efficient way to do this (keeping current veolidf
        # massive deletion performance)
        if _undo_has_later_transaction(session, eid):
            msg = session._('some later transaction(s) touch entity, undo them '
                            'first')
            raise ValidationError(eid, {None: msg})
        etype = action.etype
        # get an entity instance
        try:
            entity = self.repo.vreg['etypes'].etype_class(etype)(session)
        except Exception:
            return [session._(
                "Can't undo creation of entity %(eid)s of type %(etype)s, type "
                "no more supported" % {'eid': eid, 'etype': etype})]
        entity.eid = eid
        # for proper eid/type cache update
        CleanupDeletedEidsCacheOp.get_instance(session).add_data(eid)
        self.repo.hm.call_hooks('before_delete_entity', session, entity=entity)
        # remove is / is_instance_of which are added using sql by hooks, hence
        # unvisible as transaction action
        self.doexec(session, 'DELETE FROM is_relation WHERE eid_from=%s' % eid)
        self.doexec(session, 'DELETE FROM is_instance_of_relation WHERE eid_from=%s' % eid)
        self.doexec(session, 'DELETE FROM cw_source_relation WHERE eid_from=%s' % self.eid)
        # XXX check removal of inlined relation?
        # delete the entity
        attrs = {'cw_eid': eid}
        sql = self.sqlgen.delete(SQL_PREFIX + entity.cw_etype, attrs)
        self.doexec(session, sql, attrs)
        # remove record from entities (will update fti if needed)
        self.delete_info_multi(session, [entity], self.uri)
        self.repo.hm.call_hooks('after_delete_entity', session, entity=entity)
        return ()

    def _undo_u(self, session, action):
        """undo an entity update"""
        errors = []
        err = errors.append
        try:
            entity = session.entity_from_eid(action.eid)
        except UnknownEid:
            err(session._("can't restore state of entity %s, it has been "
                          "deleted inbetween") % action.eid)
            return errors
        self._reedit_entity(entity, action.changes, err)
        entity.cw_edited.check()
        self.repo.hm.call_hooks('before_update_entity', session, entity=entity)
        sql = self.sqlgen.update(SQL_PREFIX + entity.cw_etype, action.changes,
                                 ['cw_eid'])
        self.doexec(session, sql, action.changes)
        self.repo.hm.call_hooks('after_update_entity', session, entity=entity)
        return errors

    def _undo_a(self, session, action):
        """undo a relation addition"""
        errors = []
        subj, rtype, obj = action.eid_from, action.rtype, action.eid_to
        try:
            sentity, oentity, rdef = _undo_rel_info(session, subj, rtype, obj)
        except _UndoException as ex:
            errors.append(unicode(ex))
        else:
            rschema = rdef.rtype
            if rschema.inlined:
                sql = 'SELECT 1 FROM cw_%s WHERE cw_eid=%s and cw_%s=%s'\
                      % (sentity.cw_etype, subj, rtype, obj)
            else:
                sql = 'SELECT 1 FROM %s_relation WHERE eid_from=%s and eid_to=%s'\
                      % (rtype, subj, obj)
            cu = self.doexec(session, sql)
            if cu.fetchone() is None:
                errors.append(session._(
                    "Can't undo addition of relation %(rtype)s from %(subj)s to"
                    " %(obj)s, doesn't exist anymore" % locals()))
        if not errors:
            self.repo.hm.call_hooks('before_delete_relation', session,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
            # delete relation from the database
            self._delete_relation(session, subj, rtype, obj, rschema.inlined)
            # set related cache
            session.update_rel_cache_del(subj, rtype, obj, rschema.symmetric)
            self.repo.hm.call_hooks('after_delete_relation', session,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
        return errors

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
        FTIndexEntityOp.get_instance(session).add_data(entity.eid)

    def fti_unindex_entities(self, session, entities):
        """remove text content for entities from the full text index
        """
        cursor = session.cnxset['system']
        cursor_unindex_object = self.dbhelper.cursor_unindex_object
        try:
            for entity in entities:
                cursor_unindex_object(entity.eid, cursor)
        except Exception: # let KeyboardInterrupt / SystemExit propagate
            self.exception('error while unindexing %s', entity)


    def fti_index_entities(self, session, entities):
        """add text content of created/modified entities to the full text index
        """
        cursor_index_object = self.dbhelper.cursor_index_object
        cursor = session.cnxset['system']
        try:
            # use cursor_index_object, not cursor_reindex_object since
            # unindexing done in the FTIndexEntityOp
            for entity in entities:
                cursor_index_object(entity.eid,
                                    entity.cw_adapt_to('IFTIndexable'),
                                    cursor)
        except Exception: # let KeyboardInterrupt / SystemExit propagate
            self.exception('error while indexing %s', entity)


class FTIndexEntityOp(hook.DataOperationMixIn, hook.LateOperation):
    """operation to delay entity full text indexation to commit

    since fti indexing may trigger discovery of other entities, it should be
    triggered on precommit, not commit, and this should be done after other
    precommit operation which may add relations to the entity
    """

    def precommit_event(self):
        session = self.session
        source = session.repo.system_source
        pendingeids = session.transaction_data.get('pendingeids', ())
        done = session.transaction_data.setdefault('indexedeids', set())
        to_reindex = set()
        for eid in self.get_data():
            if eid in pendingeids or eid in done:
                # entity added and deleted in the same transaction or already
                # processed
                continue
            done.add(eid)
            iftindexable = session.entity_from_eid(eid).cw_adapt_to('IFTIndexable')
            to_reindex |= set(iftindexable.fti_containers())
        source.fti_unindex_entities(session, to_reindex)
        source.fti_index_entities(session, to_reindex)

def sql_schema(driver):
    helper = get_db_helper(driver)
    typemap = helper.TYPE_MAPPING
    schema = """
/* Create the repository's system database */

%s

CREATE TABLE entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  source VARCHAR(128) NOT NULL,
  asource VARCHAR(128) NOT NULL,
  mtime %s NOT NULL,
  extid VARCHAR(256)
);;
CREATE INDEX entities_type_idx ON entities(type);;
CREATE INDEX entities_mtime_idx ON entities(mtime);;
CREATE INDEX entities_extid_idx ON entities(extid);;

CREATE TABLE deleted_entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  source VARCHAR(128) NOT NULL,
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
CREATE INDEX transactions_tx_time_idx ON transactions(tx_time);;

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
CREATE INDEX tx_entity_actions_tx_uuid_idx ON tx_entity_actions(tx_uuid);;

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
CREATE INDEX tx_relation_actions_tx_uuid_idx ON tx_relation_actions(tx_uuid);;
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
DROP TABLE tx_entity_actions;
DROP TABLE tx_relation_actions;
DROP TABLE transactions;
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
    passwd_rql = 'Any P WHERE X is CWUser, X login %(login)s, X upassword P'
    auth_rql = ('Any X WHERE X is CWUser, X login %(login)s, X upassword %(pwd)s, '
                'X cw_source S, S name "system"')
    _sols = ({'X': 'CWUser', 'P': 'Password', 'S': 'CWSource'},)

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
        args = {'login': login, 'pwd' : None}
        if password is not None:
            rset = self.source.syntax_tree_search(session, self._passwd_rqlst, args)
            try:
                pwd = rset[0][0]
            except IndexError:
                raise AuthenticationError('bad login')
            if pwd is None:
                # if pwd is None but a password is provided, something is wrong
                raise AuthenticationError('bad password')
            # passwords are stored using the Bytes type, so we get a StringIO
            args['pwd'] = Binary(crypt_password(password, pwd.getvalue()))
        # get eid from login and (crypted) password
        rset = self.source.syntax_tree_search(session, self._auth_rqlst, args)
        try:
            user = rset[0][0]
            # If the stored hash uses a deprecated scheme (e.g. DES or MD5 used
            # before 3.14.7), update with a fresh one
            if pwd.getvalue():
                verify, newhash = verify_and_update(password, pwd.getvalue())
                if not verify: # should not happen, but...
                    raise AuthenticationError('bad password')
                if newhash:
                    session.system_sql("UPDATE %s SET %s=%%(newhash)s WHERE %s=%%(login)s" % (
                                        SQL_PREFIX + 'CWUser',
                                        SQL_PREFIX + 'upassword',
                                        SQL_PREFIX + 'login'),
                                       {'newhash': self.source._binary(newhash),
                                        'login': login})
                    session.commit(free_cnxset=False)
            return user
        except IndexError:
            raise AuthenticationError('bad password')


class EmailPasswordAuthentifier(BaseAuthentifier):
    def authenticate(self, session, login, **authinfo):
        # email_auth flag prevent from infinite recursion (call to
        # repo.check_auth_info at the end of this method may lead us here again)
        if not '@' in login or authinfo.pop('email_auth', None):
            raise AuthenticationError('not an email')
        rset = session.execute('Any L WHERE U login L, U primary_email M, '
                               'M address %(login)s', {'login': login},
                               build_descr=False)
        if rset.rowcount != 1:
            raise AuthenticationError('unexisting email')
        login = rset.rows[0][0]
        authinfo['email_auth'] = True
        return self.source.repo.check_auth_info(session, login, authinfo)

class DatabaseIndependentBackupRestore(object):
    """Helper class to perform db backend agnostic backup and restore

    The backup and restore methods are used to dump / restore the
    system database in a database independent format. The file is a
    Zip archive containing the following files:

    * format.txt: the format of the archive. Currently '1.0'
    * tables.txt: list of filenames in the archive tables/ directory
    * sequences.txt: list of filenames in the archive sequences/ directory
    * versions.txt: the list of cube versions from CWProperty
    * tables/<tablename>.<chunkno>: pickled data
    * sequences/<sequencename>: pickled data

    The pickled data format for tables and sequences is a tuple of 3 elements:
    * the table name
    * a tuple of column names
    * a list of rows (as tuples with one element per column)

    Tables are saved in chunks in different files in order to prevent
    a too high memory consumption.
    """
    def __init__(self, source):
        """
        :param: source an instance of the system source
        """
        self._source = source
        self.logger = logging.getLogger('cubicweb.ctl')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(logging.StreamHandler(sys.stdout))
        self.schema = self._source.schema
        self.dbhelper = self._source.dbhelper
        self.cnx = None
        self.cursor = None
        self.sql_generator = sqlgen.SQLGenerator()

    def get_connection(self):
        return self._source.get_connection()

    def backup(self, backupfile):
        archive = zipfile.ZipFile(backupfile, 'w', allowZip64=True)
        self.cnx = self.get_connection()
        try:
            self.cursor = self.cnx.cursor()
            self.cursor.arraysize=100
            self.logger.info('writing metadata')
            self.write_metadata(archive)
            for seq in self.get_sequences():
                self.logger.info('processing sequence %s', seq)
                self.write_sequence(archive, seq)
            for table in self.get_tables():
                self.logger.info('processing table %s', table)
                self.write_table(archive, table)
        finally:
            archive.close()
            self.cnx.close()
        self.logger.info('done')

    def get_tables(self):
        non_entity_tables = ['entities',
                             'deleted_entities',
                             'transactions',
                             'tx_entity_actions',
                             'tx_relation_actions',
                             ]
        etype_tables = []
        relation_tables = []
        prefix = 'cw_'
        for etype in self.schema.entities():
            eschema = self.schema.eschema(etype)
            if eschema.final:
                continue
            etype_tables.append('%s%s'%(prefix, etype))
        for rtype in self.schema.relations():
            rschema = self.schema.rschema(rtype)
            if rschema.final or rschema.inlined or rschema in VIRTUAL_RTYPES:
                continue
            relation_tables.append('%s_relation' % rtype)
        return non_entity_tables + etype_tables + relation_tables

    def get_sequences(self):
        return ['entities_id_seq']

    def write_metadata(self, archive):
        archive.writestr('format.txt', '1.0')
        archive.writestr('tables.txt', '\n'.join(self.get_tables()))
        archive.writestr('sequences.txt', '\n'.join(self.get_sequences()))
        versions = self._get_versions()
        versions_str = '\n'.join('%s %s' % (k,v)
                                 for k,v in versions)
        archive.writestr('versions.txt', versions_str)

    def write_sequence(self, archive, seq):
        sql = self.dbhelper.sql_sequence_current_state(seq)
        columns, rows_iterator = self._get_cols_and_rows(sql)
        rows = list(rows_iterator)
        serialized = self._serialize(seq, columns, rows)
        archive.writestr('sequences/%s' % seq, serialized)

    def write_table(self, archive, table):
        nb_lines_sql = 'SELECT COUNT(*) FROM %s' % table
        self.cursor.execute(nb_lines_sql)
        rowcount = self.cursor.fetchone()[0]
        sql = 'SELECT * FROM %s' % table
        columns, rows_iterator = self._get_cols_and_rows(sql)
        self.logger.info('number of rows: %d', rowcount)
        if table.startswith('cw_'): # entities
            blocksize = 2000
        else: # relations and metadata
            blocksize = 10000
        if rowcount > 0:
            for i, start in enumerate(xrange(0, rowcount, blocksize)):
                rows = list(itertools.islice(rows_iterator, blocksize))
                serialized = self._serialize(table, columns, rows)
                archive.writestr('tables/%s.%04d' % (table, i), serialized)
                self.logger.debug('wrote rows %d to %d (out of %d) to %s.%04d',
                                  start, start+len(rows)-1,
                                  rowcount,
                                  table, i)
        else:
            rows = []
            serialized = self._serialize(table, columns, rows)
            archive.writestr('tables/%s.%04d' % (table, 0), serialized)

    def _get_cols_and_rows(self, sql):
        process_result = self._source.iter_process_result
        self.cursor.execute(sql)
        columns = (d[0] for d in self.cursor.description)
        rows = process_result(self.cursor)
        return tuple(columns), rows

    def _serialize(self, name, columns, rows):
        return dumps((name, columns, rows), pickle.HIGHEST_PROTOCOL)

    def restore(self, backupfile):
        archive = zipfile.ZipFile(backupfile, 'r', allowZip64=True)
        self.cnx = self.get_connection()
        self.cursor = self.cnx.cursor()
        sequences, tables, table_chunks = self.read_metadata(archive, backupfile)
        for seq in sequences:
            self.logger.info('restoring sequence %s', seq)
            self.read_sequence(archive, seq)
        for table in tables:
            self.logger.info('restoring table %s', table)
            self.read_table(archive, table, sorted(table_chunks[table]))
        self.cnx.close()
        archive.close()
        self.logger.info('done')

    def read_metadata(self, archive, backupfile):
        formatinfo = archive.read('format.txt')
        self.logger.info('checking metadata')
        if formatinfo.strip() != "1.0":
            self.logger.critical('Unsupported format in archive: %s', formatinfo)
            raise ValueError('Unknown format in %s: %s' % (backupfile, formatinfo))
        tables = archive.read('tables.txt').splitlines()
        sequences = archive.read('sequences.txt').splitlines()
        file_versions = self._parse_versions(archive.read('versions.txt'))
        versions = set(self._get_versions())
        if file_versions != versions:
            self.logger.critical('Unable to restore : versions do not match')
            self.logger.critical('Expected:\n%s', '\n'.join('%s : %s' % (cube, ver)
                                                            for cube, ver in sorted(versions)))
            self.logger.critical('Found:\n%s', '\n'.join('%s : %s' % (cube, ver)
                                                         for cube, ver in sorted(file_versions)))
            raise ValueError('Unable to restore : versions do not match')
        table_chunks = {}
        for name in archive.namelist():
            if not name.startswith('tables/'):
                continue
            filename = basename(name)
            tablename, _ext = filename.rsplit('.', 1)
            table_chunks.setdefault(tablename, []).append(name)
        return sequences, tables, table_chunks

    def read_sequence(self, archive, seq):
        seqname, columns, rows = loads(archive.read('sequences/%s' % seq))
        assert seqname == seq
        assert len(rows) == 1
        assert len(rows[0]) == 1
        value = rows[0][0]
        sql = self.dbhelper.sql_restart_sequence(seq, value)
        self.cursor.execute(sql)
        self.cnx.commit()

    def read_table(self, archive, table, filenames):
        merge_args = self._source.merge_args
        self.cursor.execute('DELETE FROM %s' % table)
        self.cnx.commit()
        row_count = 0
        for filename in filenames:
            tablename, columns, rows = loads(archive.read(filename))
            assert tablename == table
            if not rows:
                continue
            insert = self.sql_generator.insert(table,
                                               dict(zip(columns, rows[0])))
            for row in rows:
                self.cursor.execute(insert, merge_args(dict(zip(columns, row)), {}))
            row_count += len(rows)
            self.cnx.commit()
        self.logger.info('inserted %d rows', row_count)


    def _parse_versions(self, version_str):
        versions = set()
        for line in version_str.splitlines():
            versions.add(tuple(line.split()))
        return versions

    def _get_versions(self):
        version_sql = 'SELECT cw_pkey, cw_value FROM cw_CWProperty'
        versions = []
        self.cursor.execute(version_sql)
        for pkey, value in self.cursor.fetchall():
            if pkey.startswith(u'system.version'):
                versions.append((pkey, value))
        return versions
