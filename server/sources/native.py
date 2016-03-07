# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cPickle import loads, dumps
import cPickle as pickle
from threading import Lock
from datetime import datetime
from base64 import b64decode, b64encode
from contextlib import contextmanager
from os.path import basename
import re
import itertools
import zipfile
import logging
import sys

from logilab.common.decorators import cached, clear_cache
from logilab.common.configuration import Method
from logilab.common.shellutils import getlogin, ASK
from logilab.database import get_db_helper, sqlgen

from yams import schema2sql as y2sql
from yams.schema import role_name

from cubicweb import (UnknownEid, AuthenticationError, ValidationError, Binary,
                      UniqueTogetherError, UndoTransactionException)
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

def _undo_rel_info(cnx, subj, rtype, obj):
    entities = []
    for role, eid in (('subject', subj), ('object', obj)):
        try:
            entities.append(cnx.entity_from_eid(eid))
        except UnknownEid:
            raise _UndoException(cnx._(
                "Can't restore relation %(rtype)s, %(role)s entity %(eid)s"
                " doesn't exist anymore.")
                                % {'role': cnx._(role),
                                   'rtype': cnx._(rtype),
                                   'eid': eid})
    sentity, oentity = entities
    try:
        rschema = cnx.vreg.schema.rschema(rtype)
        rdef = rschema.rdefs[(sentity.cw_etype, oentity.cw_etype)]
    except KeyError:
        raise _UndoException(cnx._(
            "Can't restore relation %(rtype)s between %(subj)s and "
            "%(obj)s, that relation does not exists anymore in the "
            "schema.")
                            % {'rtype': cnx._(rtype),
                               'subj': subj,
                               'obj': obj})
    return sentity, oentity, rdef

def _undo_has_later_transaction(cnx, eid):
    return cnx.system_sql('''\
SELECT T.tx_uuid FROM transactions AS TREF, transactions AS T
WHERE TREF.tx_uuid='%(txuuid)s' AND T.tx_uuid!='%(txuuid)s'
AND T.tx_time>=TREF.tx_time
AND (EXISTS(SELECT 1 FROM tx_entity_actions AS TEA
            WHERE TEA.tx_uuid=T.tx_uuid AND TEA.eid=%(eid)s)
     OR EXISTS(SELECT 1 FROM tx_relation_actions as TRA
               WHERE TRA.tx_uuid=T.tx_uuid AND (
                   TRA.eid_from=%(eid)s OR TRA.eid_to=%(eid)s))
     )''' % {'txuuid': cnx.transaction_data['undoing_uuid'],
             'eid': eid}).fetchone()


class DefaultEidGenerator(object):
    __slots__ = ('source', 'cnx', 'lock')

    def __init__(self, source):
        self.source = source
        self.cnx = None
        self.lock = Lock()

    def close(self):
        if self.cnx:
            self.cnx.close()
        self.cnx = None

    def create_eid(self, _cnx, count=1):
        # lock needed to prevent 'Connection is busy with results for another
        # command (0)' errors with SQLServer
        assert count > 0
        with self.lock:
            return self._create_eid(count)

    def _create_eid(self, count):
        # internal function doing the eid creation without locking.
        # needed for the recursive handling of disconnections (otherwise we
        # deadlock on self._eid_cnx_lock
        source = self.source
        if self.cnx is None:
            self.cnx = source.get_connection()
        cnx = self.cnx
        try:
            cursor = cnx.cursor()
            for sql in source.dbhelper.sqls_increment_numrange('entities_id_seq', count):
                cursor.execute(sql)
            eid = cursor.fetchone()[0]
        except (source.OperationalError, source.InterfaceError):
            # FIXME: better detection of deconnection pb
            source.warning("trying to reconnect create eid connection")
            self.cnx = None
            return self._create_eid(count)
        except source.DbapiError as exc:
            # We get this one with pyodbc and SQL Server when connection was reset
            if exc.args[0] == '08S01':
                source.warning("trying to reconnect create eid connection")
                self.cnx = None
                return self._create_eid(count)
            else:
                raise
        except Exception: # WTF?
            cnx.rollback()
            self.cnx = None
            source.exception('create eid failed in an unforeseen way on SQL statement %s', sql)
            raise
        else:
            cnx.commit()
            return eid


class SQLITEEidGenerator(object):
    __slots__ = ('source', 'lock')

    def __init__(self, source):
        self.source = source
        self.lock = Lock()

    def close(self):
        pass

    def create_eid(self, cnx, count=1):
        assert count > 0
        source = self.source
        with self.lock:
            for sql in source.dbhelper.sqls_increment_numrange('entities_id_seq', count):
                cursor = source.doexec(cnx, sql)
            return cursor.fetchone()[0]


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
        ('db-namespace',
         {'type' : 'string',
          'default': '',
          'help': 'database namespace (schema) name',
          'group': 'native-source', 'level': 1,
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
        ('db-statement-timeout',
         {'type': 'int',
          'default': 0,
          'help': 'sql statement timeout, in milliseconds (postgres only)',
          'group': 'native-source', 'level': 2,
          }),
    )

    def __init__(self, repo, source_config, *args, **kwargs):
        SQLAdapterMixIn.__init__(self, source_config, repairing=repo.config.repairing)
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
        # (etype, attr) / storage mapping
        self._storages = {}
        self.binary_to_str = self.dbhelper.dbapi_module.binary_to_str
        if self.dbdriver == 'sqlite':
            self.eid_generator = SQLITEEidGenerator(self)
        else:
            self.eid_generator = DefaultEidGenerator(self)
        self.create_eid = self.eid_generator.create_eid

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

    def sqlexec(self, cnx, sql, args=None):
        """execute the query and return its result"""
        return self.process_result(self.doexec(cnx, sql, args))

    def init_creating(self, cnxset=None):
        # check full text index availibility
        if self.do_fti:
            if cnxset is None:
                _cnxset = self.repo._get_cnxset()
            else:
                _cnxset = cnxset
            if not self.dbhelper.has_fti_table(_cnxset.cu):
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
        self.eid_generator.close()

    # XXX deprecates [un]map_attribute?
    def map_attribute(self, etype, attr, cb, sourcedb=True):
        self._rql_sqlgen.attr_map[u'%s.%s' % (etype, attr)] = (cb, sourcedb)

    def unmap_attribute(self, etype, attr):
        self._rql_sqlgen.attr_map.pop(u'%s.%s' % (etype, attr), None)

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

    def authenticate(self, cnx, login, **kwargs):
        """return CWUser eid for the given login and other authentication
        information found in kwargs, else raise `AuthenticationError`
        """
        for authentifier in self.authentifiers:
            try:
                return authentifier.authenticate(cnx, login, **kwargs)
            except AuthenticationError:
                continue
        raise AuthenticationError()

    def syntax_tree_search(self, cnx, union, args=None, cachekey=None,
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
            cursor = self.doexec(cnx, sql, args)
        except (self.OperationalError, self.InterfaceError):
            if cnx.mode == 'write':
                # do not attempt to reconnect if there has been some write
                # during the transaction
                raise
            # FIXME: better detection of deconnection pb
            self.warning("trying to reconnect")
            cnx.cnxset.reconnect()
            cursor = self.doexec(cnx, sql, args)
        except self.DbapiError as exc:
            # We get this one with pyodbc and SQL Server when connection was reset
            if exc.args[0] == '08S01' and cnx.mode != 'write':
                self.warning("trying to reconnect")
                cnx.cnxset.reconnect()
                cursor = self.doexec(cnx, sql, args)
            else:
                raise
        results = self.process_result(cursor, cnx, cbs)
        assert dbg_results(results)
        return results

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

    def add_entity(self, cnx, entity):
        """add a new entity to the source"""
        with self._storage_handler(entity, 'added'):
            attrs = self.preprocess_entity(entity)
            sql = self.sqlgen.insert(SQL_PREFIX + entity.cw_etype, attrs)
            self.doexec(cnx, sql, attrs)
            if cnx.ertype_supports_undo(entity.cw_etype):
                self._record_tx_action(cnx, 'tx_entity_actions', 'C',
                                       etype=entity.cw_etype, eid=entity.eid)

    def update_entity(self, cnx, entity):
        """replace an entity in the source"""
        with self._storage_handler(entity, 'updated'):
            attrs = self.preprocess_entity(entity)
            if cnx.ertype_supports_undo(entity.cw_etype):
                changes = self._save_attrs(cnx, entity, attrs)
                self._record_tx_action(cnx, 'tx_entity_actions', 'U',
                                       etype=entity.cw_etype, eid=entity.eid,
                                       changes=self._binary(dumps(changes)))
            sql = self.sqlgen.update(SQL_PREFIX + entity.cw_etype, attrs,
                                     ['cw_eid'])
            self.doexec(cnx, sql, attrs)

    def delete_entity(self, cnx, entity):
        """delete an entity from the source"""
        with self._storage_handler(entity, 'deleted'):
            if cnx.ertype_supports_undo(entity.cw_etype):
                attrs = [SQL_PREFIX + r.type
                         for r in entity.e_schema.subject_relations()
                         if (r.final or r.inlined) and not r in VIRTUAL_RTYPES]
                changes = self._save_attrs(cnx, entity, attrs)
                self._record_tx_action(cnx, 'tx_entity_actions', 'D',
                                       etype=entity.cw_etype, eid=entity.eid,
                                       changes=self._binary(dumps(changes)))
            attrs = {'cw_eid': entity.eid}
            sql = self.sqlgen.delete(SQL_PREFIX + entity.cw_etype, attrs)
            self.doexec(cnx, sql, attrs)

    def add_relation(self, cnx, subject, rtype, object, inlined=False):
        """add a relation to the source"""
        self._add_relations(cnx,  rtype, [(subject, object)], inlined)
        if cnx.ertype_supports_undo(rtype):
            self._record_tx_action(cnx, 'tx_relation_actions', 'A',
                                   eid_from=subject, rtype=rtype, eid_to=object)

    def add_relations(self, cnx,  rtype, subj_obj_list, inlined=False):
        """add a relations to the source"""
        self._add_relations(cnx, rtype, subj_obj_list, inlined)
        if cnx.ertype_supports_undo(rtype):
            for subject, object in subj_obj_list:
                self._record_tx_action(cnx, 'tx_relation_actions', 'A',
                                       eid_from=subject, rtype=rtype, eid_to=object)

    def _add_relations(self, cnx, rtype, subj_obj_list, inlined=False):
        """add a relation to the source"""
        sql = []
        if inlined is False:
            attrs = [{'eid_from': subject, 'eid_to': object}
                     for subject, object in subj_obj_list]
            sql.append((self.sqlgen.insert('%s_relation' % rtype, attrs[0]), attrs))
        else: # used by data import
            etypes = {}
            for subject, object in subj_obj_list:
                etype = cnx.entity_metas(subject)['type']
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
            self.doexecmany(cnx, statement, attrs)

    def delete_relation(self, cnx, subject, rtype, object):
        """delete a relation from the source"""
        rschema = self.schema.rschema(rtype)
        self._delete_relation(cnx, subject, rtype, object, rschema.inlined)
        if cnx.ertype_supports_undo(rtype):
            self._record_tx_action(cnx, 'tx_relation_actions', 'R',
                                   eid_from=subject, rtype=rtype, eid_to=object)

    def _delete_relation(self, cnx, subject, rtype, object, inlined=False):
        """delete a relation from the source"""
        if inlined:
            table = SQL_PREFIX + cnx.entity_metas(subject)['type']
            column = SQL_PREFIX + rtype
            sql = 'UPDATE %s SET %s=NULL WHERE %seid=%%(eid)s' % (table, column,
                                                                  SQL_PREFIX)
            attrs = {'eid' : subject}
        else:
            attrs = {'eid_from': subject, 'eid_to': object}
            sql = self.sqlgen.delete('%s_relation' % rtype, attrs)
        self.doexec(cnx, sql, attrs)

    def doexec(self, cnx, query, args=None, rollback=True):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        cursor = cnx.cnxset.cu
        if server.DEBUG & server.DBG_SQL:
            print 'exec', query, args, cnx.cnxset.cnx
        try:
            # str(query) to avoid error if it's a unicode string
            cursor.execute(str(query), args)
        except Exception as ex:
            if self.repo.config.mode != 'test':
                # during test we get those message when trying to alter sqlite
                # db schema
                self.info("sql: %r\n args: %s\ndbms message: %r",
                              query, args, ex.args[0])
            if rollback:
                try:
                    cnx.cnxset.rollback()
                    if self.repo.config.mode != 'test':
                        self.debug('transaction has been rolled back')
                except Exception as ex:
                    pass
            if ex.__class__.__name__ == 'IntegrityError':
                # need string comparison because of various backends
                for arg in ex.args:
                    # postgres, sqlserver
                    mo = re.search("unique_[a-z0-9]{32}", arg)
                    if mo is not None:
                        raise UniqueTogetherError(cnx, cstrname=mo.group(0))
                    # old sqlite
                    mo = re.search('columns? (.*) (?:is|are) not unique', arg)
                    if mo is not None: # sqlite in use
                        # we left chop the 'cw_' prefix of attribute names
                        rtypes = [c.strip()[3:]
                                  for c in mo.group(1).split(',')]
                        raise UniqueTogetherError(cnx, rtypes=rtypes)
                    # sqlite after http://www.sqlite.org/cgi/src/info/c80e229dd9c1230a
                    if arg.startswith('UNIQUE constraint failed:'):
                        # message looks like: "UNIQUE constraint failed: foo.cw_bar, foo.cw_baz"
                        # so drop the prefix, split on comma, drop the tablenames, and drop "cw_"
                        columns = arg.split(':', 1)[1].split(',')
                        rtypes = [c.split('.', 1)[1].strip()[3:] for c in columns]
                        raise UniqueTogetherError(cnx, rtypes=rtypes)
            raise
        return cursor

    def doexecmany(self, cnx, query, args):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        if server.DEBUG & server.DBG_SQL:
            print 'execmany', query, 'with', len(args), 'arguments'
        cursor = cnx.cnxset.cu
        try:
            # str(query) to avoid error if it's a unicode string
            cursor.executemany(str(query), args)
        except Exception as ex:
            if self.repo.config.mode != 'test':
                # during test we get those message when trying to alter sqlite
                # db schema
                self.critical("sql many: %r\n args: %s\ndbms message: %r",
                              query, args, ex.args[0])
            try:
                cnx.cnxset.rollback()
                if self.repo.config.mode != 'test':
                    self.critical('transaction has been rolled back')
            except Exception:
                pass
            raise

    # short cut to method requiring advanced db helper usage ##################

    def update_rdef_column(self, cnx, rdef):
        """update physical column for a relation definition (final or inlined)
        """
        table, column = rdef_table_column(rdef)
        coltype, allownull = rdef_physical_info(self.dbhelper, rdef)
        if not self.dbhelper.alter_column_support:
            self.error("backend can't alter %s.%s to %s%s", table, column, coltype,
                       not allownull and 'NOT NULL' or '')
            return
        self.dbhelper.change_col_type(LogCursor(cnx.cnxset.cu),
                                      table, column, coltype, allownull)
        self.info('altered %s.%s: now %s%s', table, column, coltype,
                  not allownull and 'NOT NULL' or '')

    def update_rdef_null_allowed(self, cnx, rdef):
        """update NULL / NOT NULL of physical column for a relation definition
        (final or inlined)
        """
        if not self.dbhelper.alter_column_support:
            # not supported (and NOT NULL not set by yams in that case, so no
            # worry)
            return
        table, column = rdef_table_column(rdef)
        coltype, allownull = rdef_physical_info(self.dbhelper, rdef)
        self.dbhelper.set_null_allowed(LogCursor(cnx.cnxset.cu),
                                       table, column, coltype, allownull)

    def update_rdef_indexed(self, cnx, rdef):
        table, column = rdef_table_column(rdef)
        if rdef.indexed:
            self.create_index(cnx, table, column)
        else:
            self.drop_index(cnx, table, column)

    def update_rdef_unique(self, cnx, rdef):
        table, column = rdef_table_column(rdef)
        if rdef.constraint_by_type('UniqueConstraint'):
            self.create_index(cnx, table, column, unique=True)
        else:
            self.drop_index(cnx, table, column, unique=True)

    def create_index(self, cnx, table, column, unique=False):
        cursor = LogCursor(cnx.cnxset.cu)
        self.dbhelper.create_index(cursor, table, column, unique)

    def drop_index(self, cnx, table, column, unique=False):
        cursor = LogCursor(cnx.cnxset.cu)
        self.dbhelper.drop_index(cursor, table, column, unique)

    # system source interface #################################################

    def _eid_type_source(self, cnx, eid, sql, _retry=True):
        try:
            res = self.doexec(cnx, sql).fetchone()
            if res is not None:
                return res
        except (self.OperationalError, self.InterfaceError):
            if cnx.mode == 'read' and _retry:
                self.warning("trying to reconnect (eid_type_source())")
                cnx.cnxset.reconnect()
                return self._eid_type_source(cnx, eid, sql, _retry=False)
        except Exception:
            assert cnx.cnxset, 'connection has no connections set'
            self.exception('failed to query entities table for eid %s', eid)
        raise UnknownEid(eid)

    def eid_type_source(self, cnx, eid): # pylint: disable=E0202
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        sql = 'SELECT type, extid, asource FROM entities WHERE eid=%s' % eid
        res = self._eid_type_source(cnx, eid, sql)
        if res[-2] is not None:
            if not isinstance(res, list):
                res = list(res)
            res[-2] = b64decode(res[-2])
        return res

    def eid_type_source_pre_131(self, cnx, eid):
        """return a tuple (type, source, extid) for the entity with id <eid>"""
        sql = 'SELECT type, extid FROM entities WHERE eid=%s' % eid
        res = self._eid_type_source(cnx, eid, sql)
        if not isinstance(res, list):
            res = list(res)
        if res[-1] is not None:
            res[-1] = b64decode(res[-1])
        res.append("system")
        return res

    def extid2eid(self, cnx, extid):
        """get eid from an external id. Return None if no record found."""
        assert isinstance(extid, str)
        cursor = self.doexec(cnx,
                             'SELECT eid FROM entities WHERE extid=%(x)s',
                             {'x': b64encode(extid)})
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

    def _handle_is_relation_sql(self, cnx, sql, attrs):
        """ Handler for specific is_relation sql that may be
        overwritten in some stores"""
        self.doexec(cnx, sql % attrs)

    _handle_insert_entity_sql = doexec
    _handle_is_instance_of_sql = _handle_source_relation_sql = _handle_is_relation_sql

    def add_info(self, cnx, entity, source, extid):
        """add type and source info for an eid into the system table"""
        assert cnx.cnxset is not None
        # begin by inserting eid/type/source/extid into the entities table
        if extid is not None:
            assert isinstance(extid, str)
            extid = b64encode(extid)
        attrs = {'type': entity.cw_etype, 'eid': entity.eid, 'extid': extid and unicode(extid),
                 'asource': unicode(source.uri)}
        self._handle_insert_entity_sql(cnx, self.sqlgen.insert('entities', attrs), attrs)
        # insert core relations: is, is_instance_of and cw_source
        try:
            self._handle_is_relation_sql(cnx, 'INSERT INTO is_relation(eid_from,eid_to) VALUES (%s,%s)',
                                         (entity.eid, eschema_eid(cnx, entity.e_schema)))
        except IndexError:
            # during schema serialization, skip
            pass
        else:
            for eschema in entity.e_schema.ancestors() + [entity.e_schema]:
                self._handle_is_relation_sql(cnx,
                                             'INSERT INTO is_instance_of_relation(eid_from,eid_to) VALUES (%s,%s)',
                                             (entity.eid, eschema_eid(cnx, eschema)))
        if 'CWSource' in self.schema and source.eid is not None: # else, cw < 3.10
            self._handle_is_relation_sql(cnx, 'INSERT INTO cw_source_relation(eid_from,eid_to) VALUES (%s,%s)',
                                         (entity.eid, source.eid))
        # now we can update the full text index
        if self.need_fti_indexation(entity.cw_etype):
            self.index_entity(cnx, entity=entity)

    def update_info(self, cnx, entity, need_fti_update):
        """mark entity as being modified, fulltext reindex if needed"""
        if need_fti_update:
            # reindex the entity only if this query is updating at least
            # one indexable attribute
            self.index_entity(cnx, entity=entity)

    def delete_info_multi(self, cnx, entities):
        """delete system information on deletion of a list of entities with the
        same etype and belinging to the same source

        * update the fti
        * remove record from the `entities` table
        """
        self.fti_unindex_entities(cnx, entities)
        attrs = {'eid': '(%s)' % ','.join([str(_e.eid) for _e in entities])}
        self.doexec(cnx, self.sqlgen.delete_many('entities', attrs), attrs)

    # undo support #############################################################

    def undoable_transactions(self, cnx, ueid=None, **actionfilters):
        """See :class:`cubicweb.repoapi.ClientConnection.undoable_transactions`"""
        # force filtering to connection's user if not a manager
        if not cnx.user.is_in_group('managers'):
            ueid = cnx.user.eid
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
        with cnx.ensure_cnx_set:
            cu = self.doexec(cnx, sql, restr)
            # turn results into transaction objects
            return [tx.Transaction(*args) for args in cu.fetchall()]

    def tx_info(self, cnx, txuuid):
        """See :class:`cubicweb.repoapi.ClientConnection.transaction_info`"""
        return tx.Transaction(txuuid, *self._tx_info(cnx, txuuid))

    def tx_actions(self, cnx, txuuid, public):
        """See :class:`cubicweb.repoapi.ClientConnection.transaction_actions`"""
        self._tx_info(cnx, txuuid)
        restr = {'tx_uuid': txuuid}
        if public:
            restr['txa_public'] = True
        # XXX use generator to avoid loading everything in memory?
        sql = self.sqlgen.select('tx_entity_actions', restr,
                                 ('txa_action', 'txa_public', 'txa_order',
                                  'etype', 'eid', 'changes'))
        with cnx.ensure_cnx_set:
            cu = self.doexec(cnx, sql, restr)
            actions = [tx.EntityAction(a,p,o,et,e,c and loads(self.binary_to_str(c)))
                       for a,p,o,et,e,c in cu.fetchall()]
        sql = self.sqlgen.select('tx_relation_actions', restr,
                                 ('txa_action', 'txa_public', 'txa_order',
                                  'rtype', 'eid_from', 'eid_to'))
        with cnx.ensure_cnx_set:
            cu = self.doexec(cnx, sql, restr)
            actions += [tx.RelationAction(*args) for args in cu.fetchall()]
        return sorted(actions, key=lambda x: x.order)

    def undo_transaction(self, cnx, txuuid):
        """See :class:`cubicweb.repoapi.ClientConnection.undo_transaction`

        important note: while undoing of a transaction, only hooks in the
        'integrity', 'activeintegrity' and 'undo' categories are called.
        """
        # set mode so connections set isn't released subsquently until commit/rollback
        cnx.mode = 'write'
        errors = []
        cnx.transaction_data['undoing_uuid'] = txuuid
        with cnx.deny_all_hooks_but('integrity', 'activeintegrity', 'undo'):
            with cnx.security_enabled(read=False):
                for action in reversed(self.tx_actions(cnx, txuuid, False)):
                    undomethod = getattr(self, '_undo_%s' % action.action.lower())
                    errors += undomethod(cnx, action)
        # remove the transactions record
        self.doexec(cnx,
                    "DELETE FROM transactions WHERE tx_uuid='%s'" % txuuid)
        if errors:
            raise UndoTransactionException(txuuid, errors)
        else:
            return

    def start_undoable_transaction(self, cnx, uuid):
        """connection callback to insert a transaction record in the transactions
        table when some undoable transaction is started
        """
        ueid = cnx.user.eid
        attrs = {'tx_uuid': uuid, 'tx_user': ueid, 'tx_time': datetime.utcnow()}
        self.doexec(cnx, self.sqlgen.insert('transactions', attrs), attrs)

    def _save_attrs(self, cnx, entity, attrs):
        """return a pickleable dictionary containing current values for given
        attributes of the entity
        """
        restr = {'cw_eid': entity.eid}
        sql = self.sqlgen.select(SQL_PREFIX + entity.cw_etype, restr, attrs)
        cu = self.doexec(cnx, sql, restr)
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

    def _record_tx_action(self, cnx, table, action, **kwargs):
        """record a transaction action in the given table (either
        'tx_entity_actions' or 'tx_relation_action')
        """
        kwargs['tx_uuid'] = cnx.transaction_uuid()
        kwargs['txa_action'] = action
        kwargs['txa_order'] = cnx.transaction_inc_action_counter()
        kwargs['txa_public'] = cnx.running_dbapi_query
        self.doexec(cnx, self.sqlgen.insert(table, kwargs), kwargs)

    def _tx_info(self, cnx, txuuid):
        """return transaction's time and user of the transaction with the given uuid.

        raise `NoSuchTransaction` if there is no such transaction of if the
        connection's user isn't allowed to see it.
        """
        with cnx.ensure_cnx_set:
            restr = {'tx_uuid': txuuid}
            sql = self.sqlgen.select('transactions', restr,
                                     ('tx_time', 'tx_user'))
            cu = self.doexec(cnx, sql, restr)
            try:
                time, ueid = cu.fetchone()
            except TypeError:
                raise tx.NoSuchTransaction(txuuid)
            if not (cnx.user.is_in_group('managers')
                    or cnx.user.eid == ueid):
                raise tx.NoSuchTransaction(txuuid)
            return time, ueid

    def _reedit_entity(self, entity, changes, err):
        cnx = entity._cw
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
                err(cnx._("can't restore relation %(rtype)s of entity %(eid)s, "
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
                        err(cnx._("can't restore entity %(eid)s of type %(eschema)s, "
                                      "target of %(rtype)s (eid %(value)s) does not exist any longer")
                            % locals())
            elif eschema.destination(rtype) in ('Bytes', 'Password'):
                changes[column] = self._binary(value)
                edited[rtype] = Binary(value)
            elif isinstance(value, str):
                edited[rtype] = unicode(value, cnx.encoding, 'replace')
            else:
                edited[rtype] = value
        # This must only be done after init_entitiy_caches : defered in calling functions
        # edited.check()

    def _undo_d(self, cnx, action):
        """undo an entity deletion"""
        errors = []
        err = errors.append
        eid = action.eid
        etype = action.etype
        _ = cnx._
        # get an entity instance
        try:
            entity = self.repo.vreg['etypes'].etype_class(etype)(cnx)
        except Exception:
            err("can't restore entity %s of type %s, type no more supported"
                % (eid, etype))
            return errors
        self._reedit_entity(entity, action.changes, err)
        entity.eid = eid
        cnx.repo.init_entity_caches(cnx, entity, self)
        entity.cw_edited.check()
        self.repo.hm.call_hooks('before_add_entity', cnx, entity=entity)
        # restore the entity
        action.changes['cw_eid'] = eid
        sql = self.sqlgen.insert(SQL_PREFIX + etype, action.changes)
        self.doexec(cnx, sql, action.changes)
        # restore record in entities (will update fti if needed)
        self.add_info(cnx, entity, self, None)
        self.repo.hm.call_hooks('after_add_entity', cnx, entity=entity)
        return errors

    def _undo_r(self, cnx, action):
        """undo a relation removal"""
        errors = []
        subj, rtype, obj = action.eid_from, action.rtype, action.eid_to
        try:
            sentity, oentity, rdef = _undo_rel_info(cnx, subj, rtype, obj)
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
            self.repo.hm.call_hooks('before_add_relation', cnx,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
            # add relation in the database
            self._add_relations(cnx, rtype, [(subj, obj)], rdef.rtype.inlined)
            # set related cache
            cnx.update_rel_cache_add(subj, rtype, obj, rdef.rtype.symmetric)
            self.repo.hm.call_hooks('after_add_relation', cnx,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
        return errors

    def _undo_c(self, cnx, action):
        """undo an entity creation"""
        eid = action.eid
        # XXX done to avoid fetching all remaining relation for the entity
        # we should find an efficient way to do this (keeping current veolidf
        # massive deletion performance)
        if _undo_has_later_transaction(cnx, eid):
            msg = cnx._('some later transaction(s) touch entity, undo them '
                            'first')
            raise ValidationError(eid, {None: msg})
        etype = action.etype
        # get an entity instance
        try:
            entity = self.repo.vreg['etypes'].etype_class(etype)(cnx)
        except Exception:
            return [cnx._(
                "Can't undo creation of entity %(eid)s of type %(etype)s, type "
                "no more supported" % {'eid': eid, 'etype': etype})]
        entity.eid = eid
        # for proper eid/type cache update
        CleanupDeletedEidsCacheOp.get_instance(cnx).add_data(eid)
        self.repo.hm.call_hooks('before_delete_entity', cnx, entity=entity)
        # remove is / is_instance_of which are added using sql by hooks, hence
        # unvisible as transaction action
        self.doexec(cnx, 'DELETE FROM is_relation WHERE eid_from=%s' % eid)
        self.doexec(cnx, 'DELETE FROM is_instance_of_relation WHERE eid_from=%s' % eid)
        self.doexec(cnx, 'DELETE FROM cw_source_relation WHERE eid_from=%s' % eid)
        # XXX check removal of inlined relation?
        # delete the entity
        attrs = {'cw_eid': eid}
        sql = self.sqlgen.delete(SQL_PREFIX + entity.cw_etype, attrs)
        self.doexec(cnx, sql, attrs)
        # remove record from entities (will update fti if needed)
        self.delete_info_multi(cnx, [entity])
        self.repo.hm.call_hooks('after_delete_entity', cnx, entity=entity)
        return ()

    def _undo_u(self, cnx, action):
        """undo an entity update"""
        errors = []
        err = errors.append
        try:
            entity = cnx.entity_from_eid(action.eid)
        except UnknownEid:
            err(cnx._("can't restore state of entity %s, it has been "
                          "deleted inbetween") % action.eid)
            return errors
        self._reedit_entity(entity, action.changes, err)
        entity.cw_edited.check()
        self.repo.hm.call_hooks('before_update_entity', cnx, entity=entity)
        sql = self.sqlgen.update(SQL_PREFIX + entity.cw_etype, action.changes,
                                 ['cw_eid'])
        self.doexec(cnx, sql, action.changes)
        self.repo.hm.call_hooks('after_update_entity', cnx, entity=entity)
        return errors

    def _undo_a(self, cnx, action):
        """undo a relation addition"""
        errors = []
        subj, rtype, obj = action.eid_from, action.rtype, action.eid_to
        try:
            sentity, oentity, rdef = _undo_rel_info(cnx, subj, rtype, obj)
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
            cu = self.doexec(cnx, sql)
            if cu.fetchone() is None:
                errors.append(cnx._(
                    "Can't undo addition of relation %(rtype)s from %(subj)s to"
                    " %(obj)s, doesn't exist anymore" % locals()))
        if not errors:
            self.repo.hm.call_hooks('before_delete_relation', cnx,
                                    eidfrom=subj, rtype=rtype, eidto=obj)
            # delete relation from the database
            self._delete_relation(cnx, subj, rtype, obj, rschema.inlined)
            # set related cache
            cnx.update_rel_cache_del(subj, rtype, obj, rschema.symmetric)
            self.repo.hm.call_hooks('after_delete_relation', cnx,
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

    def index_entity(self, cnx, entity):
        """create an operation to [re]index textual content of the given entity
        on commit
        """
        if self.do_fti:
            FTIndexEntityOp.get_instance(cnx).add_data(entity.eid)

    def fti_unindex_entities(self, cnx, entities):
        """remove text content for entities from the full text index
        """
        cursor = cnx.cnxset.cu
        cursor_unindex_object = self.dbhelper.cursor_unindex_object
        try:
            for entity in entities:
                cursor_unindex_object(entity.eid, cursor)
        except Exception: # let KeyboardInterrupt / SystemExit propagate
            self.exception('error while unindexing %s', entity)


    def fti_index_entities(self, cnx, entities):
        """add text content of created/modified entities to the full text index
        """
        cursor_index_object = self.dbhelper.cursor_index_object
        cursor = cnx.cnxset.cu
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
        cnx = self.cnx
        source = cnx.repo.system_source
        pendingeids = cnx.transaction_data.get('pendingeids', ())
        done = cnx.transaction_data.setdefault('indexedeids', set())
        to_reindex = set()
        for eid in self.get_data():
            if eid in pendingeids or eid in done:
                # entity added and deleted in the same transaction or already
                # processed
                continue
            done.add(eid)
            iftindexable = cnx.entity_from_eid(eid).cw_adapt_to('IFTIndexable')
            to_reindex |= set(iftindexable.fti_containers())
        source.fti_unindex_entities(cnx, to_reindex)
        source.fti_index_entities(cnx, to_reindex)

def sql_schema(driver):
    helper = get_db_helper(driver)
    typemap = helper.TYPE_MAPPING
    schema = """
/* Create the repository's system database */

%s

CREATE TABLE entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  type VARCHAR(64) NOT NULL,
  asource VARCHAR(128) NOT NULL,
  extid VARCHAR(256)
);;
CREATE INDEX entities_type_idx ON entities(type);;
CREATE INDEX entities_extid_idx ON entities(extid);;

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
""" % (helper.sql_create_numrange('entities_id_seq').replace(';', ';;'),
       typemap['Datetime'],
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
DROP TABLE tx_entity_actions;
DROP TABLE tx_relation_actions;
DROP TABLE transactions;
""" % helper.sql_drop_numrange('entities_id_seq')


def grant_schema(user, set_owner=True):
    result = ''
    for table in ('entities', 'entities_id_seq',
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
    auth_rql = (u'Any X WHERE X is CWUser, X login %(login)s, X upassword %(pwd)s, '
                'X cw_source S, S name "system"')
    _sols = ({'X': 'CWUser', 'P': 'Password', 'S': 'CWSource'},)

    def set_schema(self, schema):
        """set the instance'schema"""
        if 'CWUser' in schema: # probably an empty schema if not true...
            # rql syntax trees used to authenticate users
            self._passwd_rqlst = self.source.compile_rql(self.passwd_rql, self._sols)
            if 'CWSource' in schema:
                self._auth_rqlst = self.source.compile_rql(self.auth_rql, self._sols)
            else:
                self._auth_rqlst = self.source.compile_rql(
                        u'Any X WHERE X is CWUser, X login %(login)s, X upassword %(pwd)s',
                        ({'X': 'CWUser', 'P': 'Password'},))

    def authenticate(self, cnx, login, password=None, **kwargs):
        """return CWUser eid for the given login/password if this account is
        defined in this source, else raise `AuthenticationError`

        two queries are needed since passwords are stored crypted, so we have
        to fetch the salt first
        """
        args = {'login': login, 'pwd' : None}
        if password is not None:
            rset = self.source.syntax_tree_search(cnx, self._passwd_rqlst, args)
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
        rset = self.source.syntax_tree_search(cnx, self._auth_rqlst, args)
        pwd = args['pwd']
        try:
            user = rset[0][0]
            # If the stored hash uses a deprecated scheme (e.g. DES or MD5 used
            # before 3.14.7), update with a fresh one
            if pwd is not None and pwd.getvalue():
                verify, newhash = verify_and_update(password, pwd.getvalue())
                if not verify: # should not happen, but...
                    raise AuthenticationError('bad password')
                if newhash:
                    cnx.system_sql("UPDATE %s SET %s=%%(newhash)s WHERE %s=%%(login)s" % (
                                        SQL_PREFIX + 'CWUser',
                                        SQL_PREFIX + 'upassword',
                                        SQL_PREFIX + 'login'),
                                       {'newhash': self.source._binary(newhash),
                                        'login': login})
                    cnx.commit(free_cnxset=False)
            return user
        except IndexError:
            raise AuthenticationError('bad password')


class EmailPasswordAuthentifier(BaseAuthentifier):
    def authenticate(self, cnx, login, **authinfo):
        # email_auth flag prevent from infinite recursion (call to
        # repo.check_auth_info at the end of this method may lead us here again)
        if not '@' in login or authinfo.pop('email_auth', None):
            raise AuthenticationError('not an email')
        rset = cnx.execute('Any L WHERE U login L, U primary_email M, '
                               'M address %(login)s', {'login': login},
                               build_descr=False)
        if rset.rowcount != 1:
            raise AuthenticationError('unexisting email')
        login = rset.rows[0][0]
        authinfo['email_auth'] = True
        return self.source.repo.check_auth_info(cnx, login, authinfo)


class DatabaseIndependentBackupRestore(object):
    """Helper class to perform db backend agnostic backup and restore

    The backup and restore methods are used to dump / restore the
    system database in a database independent format. The file is a
    Zip archive containing the following files:

    * format.txt: the format of the archive. Currently '1.1'
    * tables.txt: list of filenames in the archive tables/ directory
    * sequences.txt: list of filenames in the archive sequences/ directory
    * numranges.txt: list of filenames in the archive numrange/ directory
    * versions.txt: the list of cube versions from CWProperty
    * tables/<tablename>.<chunkno>: pickled data
    * sequences/<sequencename>: pickled data

    The pickled data format for tables, numranges and sequences is a tuple of 3 elements:
    * the table name
    * a tuple of column names
    * a list of rows (as tuples with one element per column)

    Tables are saved in chunks in different files in order to prevent
    a too high memory consumption.
    """
    blocksize = 100

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
            self.cursor.arraysize = 100
            self.logger.info('writing metadata')
            self.write_metadata(archive)
            for seq in self.get_sequences():
                self.logger.info('processing sequence %s', seq)
                self.write_sequence(archive, seq)
            for numrange in self.get_numranges():
                self.logger.info('processing numrange %s', numrange)
                self.write_numrange(archive, numrange)
            for table in self.get_tables():
                self.logger.info('processing table %s', table)
                self.write_table(archive, table)
        finally:
            archive.close()
            self.cnx.close()
        self.logger.info('done')

    def get_tables(self):
        non_entity_tables = ['entities',
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
        return []

    def get_numranges(self):
        return ['entities_id_seq']

    def write_metadata(self, archive):
        archive.writestr('format.txt', '1.1')
        archive.writestr('tables.txt', '\n'.join(self.get_tables()))
        archive.writestr('sequences.txt', '\n'.join(self.get_sequences()))
        archive.writestr('numranges.txt', '\n'.join(self.get_numranges()))
        versions = self._get_versions()
        versions_str = '\n'.join('%s %s' % (k, v)
                                 for k, v in versions)
        archive.writestr('versions.txt', versions_str)

    def write_sequence(self, archive, seq):
        sql = self.dbhelper.sql_sequence_current_state(seq)
        columns, rows_iterator = self._get_cols_and_rows(sql)
        rows = list(rows_iterator)
        serialized = self._serialize(seq, columns, rows)
        archive.writestr('sequences/%s' % seq, serialized)

    def write_numrange(self, archive, numrange):
        sql = self.dbhelper.sql_numrange_current_state(numrange)
        columns, rows_iterator = self._get_cols_and_rows(sql)
        rows = list(rows_iterator)
        serialized = self._serialize(numrange, columns, rows)
        archive.writestr('numrange/%s' % numrange, serialized)

    def write_table(self, archive, table):
        nb_lines_sql = 'SELECT COUNT(*) FROM %s' % table
        self.cursor.execute(nb_lines_sql)
        rowcount = self.cursor.fetchone()[0]
        sql = 'SELECT * FROM %s' % table
        columns, rows_iterator = self._get_cols_and_rows(sql)
        self.logger.info('number of rows: %d', rowcount)
        blocksize = self.blocksize
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
        sequences, numranges, tables, table_chunks = self.read_metadata(archive, backupfile)
        for seq in sequences:
            self.logger.info('restoring sequence %s', seq)
            self.read_sequence(archive, seq)
        for numrange in numranges:
            self.logger.info('restoring numrange %s', numrange)
            self.read_numrange(archive, numrange)
        for table in tables:
            self.logger.info('restoring table %s', table)
            self.read_table(archive, table, sorted(table_chunks[table]))
        self.cnx.close()
        archive.close()
        self.logger.info('done')

    def read_metadata(self, archive, backupfile):
        formatinfo = archive.read('format.txt')
        self.logger.info('checking metadata')
        if formatinfo.strip() != "1.1":
            self.logger.critical('Unsupported format in archive: %s', formatinfo)
            raise ValueError('Unknown format in %s: %s' % (backupfile, formatinfo))
        tables = archive.read('tables.txt').splitlines()
        sequences = archive.read('sequences.txt').splitlines()
        numranges = archive.read('numranges.txt').splitlines()
        archive_versions = self._parse_versions(archive.read('versions.txt'))
        db_versions = set(self._get_versions())
        if archive_versions != db_versions:
            self.logger.critical('Restore warning: versions do not match')
            new_cubes = db_versions - archive_versions
            if new_cubes:
                self.logger.critical('In the db:\n%s', '\n'.join('%s: %s' % (cube, ver)
                                                            for cube, ver in sorted(new_cubes)))
            old_cubes = archive_versions - db_versions
            if old_cubes:
                self.logger.critical('In the archive:\n%s', '\n'.join('%s: %s' % (cube, ver)
                                                            for cube, ver in sorted(old_cubes)))
            if not ASK.confirm('Versions mismatch: continue anyway ?', False):
                raise ValueError('Unable to restore: versions do not match')
        table_chunks = {}
        for name in archive.namelist():
            if not name.startswith('tables/'):
                continue
            filename = basename(name)
            tablename, _ext = filename.rsplit('.', 1)
            table_chunks.setdefault(tablename, []).append(name)
        return sequences, numranges, tables, table_chunks

    def read_sequence(self, archive, seq):
        seqname, columns, rows = loads(archive.read('sequences/%s' % seq))
        assert seqname == seq
        assert len(rows) == 1
        assert len(rows[0]) == 1
        value = rows[0][0]
        sql = self.dbhelper.sql_restart_sequence(seq, value)
        self.cursor.execute(sql)
        self.cnx.commit()

    def read_numrange(self, archive, numrange):
        rangename, columns, rows = loads(archive.read('numrange/%s' % numrange))
        assert rangename == numrange
        assert len(rows) == 1
        assert len(rows[0]) == 1
        value = rows[0][0]
        sql = self.dbhelper.sql_restart_numrange(numrange, value)
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
