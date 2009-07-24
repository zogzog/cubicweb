"""provide an abstract class for external sources using a sqlite database helper

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"


from os.path import join, exists

from cubicweb import server
from cubicweb.server.sqlutils import (SQL_PREFIX, SQLAdapterMixIn, sqlexec,
                                      sql_source_backup, sql_source_restore)
from cubicweb.server.sources import AbstractSource, native
from cubicweb.server.sources.rql2sql import SQLGenerator

class ConnectionWrapper(object):
    def __init__(self, source=None):
        self.source = source
        self._cnx = None

    @property
    def logged_user(self):
        if self._cnx is None:
            self._cnx = self.source._sqlcnx
        return self._cnx.logged_user

    def cursor(self):
        if self._cnx is None:
            self._cnx = self.source._sqlcnx
        return self._cnx.cursor()

    def commit(self):
        if self._cnx is not None:
            self._cnx.commit()

    def rollback(self):
        if self._cnx is not None:
            self._cnx.rollback()

    def close(self):
        if self._cnx is not None:
            self._cnx.close()
            self._cnx = None


class SQLiteAbstractSource(AbstractSource):
    """an abstract class for external sources using a sqlite database helper
    """
    sqlgen_class = SQLGenerator
    @classmethod
    def set_nonsystem_types(cls):
        # those entities are only in this source, we don't want them in the
        # system source
        for etype in cls.support_entities:
            native.NONSYSTEM_ETYPES.add(etype)
        for rtype in cls.support_relations:
            native.NONSYSTEM_RELATIONS.add(rtype)

    options = (
        ('helper-db-path',
         {'type' : 'string',
          'default': None,
          'help': 'path to the sqlite database file used to do queries on the \
repository.',
          'inputlevel': 2,
          }),
    )

    def __init__(self, repo, appschema, source_config, *args, **kwargs):
        # the helper db is used to easy querying and will store everything but
        # actual file content
        dbpath = source_config.get('helper-db-path')
        if dbpath is None:
            dbpath = join(repo.config.appdatahome,
                          '%(uri)s.sqlite' % source_config)
        self.dbpath = dbpath
        self.sqladapter = SQLAdapterMixIn({'db-driver': 'sqlite',
                                           'db-name': dbpath})
        # those attributes have to be initialized before ancestor's __init__
        # which will call set_schema
        self._need_sql_create = not exists(dbpath)
        self._need_full_import = self._need_sql_create
        AbstractSource.__init__(self, repo, appschema, source_config,
                                *args, **kwargs)

    def backup(self, confirm, backupfile=None, timestamp=None, askconfirm=False):
        """method called to create a backup of source's data"""
        backupfile = self.backup_file(backupfile, timestamp)
        sql_source_backup(self, self.sqladapter, confirm, backupfile,
                          askconfirm)

    def restore(self, confirm, backupfile=None, timestamp=None, drop=True,
               askconfirm=False):
        """method called to restore a backup of source's data"""
        backupfile = self.backup_file(backupfile, timestamp)
        sql_source_restore(self, self.sqladapter, confirm, backupfile, drop,
                           askconfirm)

    @property
    def _sqlcnx(self):
        # XXX: sqlite connections can only be used in the same thread, so
        #      create a new one each time necessary. If it appears to be time
        #      consuming, find another way
        return self.sqladapter.get_connection()

    def _is_schema_complete(self):
        for etype in self.support_entities:
            if not etype in self.schema:
                self.warning('not ready to generate %s database, %s support missing from schema',
                             self.uri, etype)
                return False
        for rtype in self.support_relations:
            if not rtype in self.schema:
                self.warning('not ready to generate %s database, %s support missing from schema',
                             self.uri, rtype)
                return False
        return True

    def _create_database(self):
        from yams.schema2sql import eschema2sql, rschema2sql
        from cubicweb.toolsutils import restrict_perms_to_user
        self.warning('initializing sqlite database for %s source' % self.uri)
        cnx = self._sqlcnx
        cu = cnx.cursor()
        schema = self.schema
        for etype in self.support_entities:
            eschema = schema.eschema(etype)
            createsqls = eschema2sql(self.sqladapter.dbhelper, eschema,
                                     skip_relations=('data',), prefix=SQL_PREFIX)
            sqlexec(createsqls, cu, withpb=False)
        for rtype in self.support_relations:
            rschema = schema.rschema(rtype)
            if not rschema.inlined:
                sqlexec(rschema2sql(rschema), cu, withpb=False)
        cnx.commit()
        cnx.close()
        self._need_sql_create = False
        if self.repo.config['uid']:
            from logilab.common.shellutils import chown
            # database file must be owned by the uid of the server process
            self.warning('set %s as owner of the database file',
                         self.repo.config['uid'])
            chown(self.dbpath, self.repo.config['uid'])
        restrict_perms_to_user(self.dbpath, self.info)

    def set_schema(self, schema):
        super(SQLiteAbstractSource, self).set_schema(schema)
        if self._need_sql_create and self._is_schema_complete() and self.dbpath:
            self._create_database()
        self.rqlsqlgen = self.sqlgen_class(schema, self.sqladapter.dbhelper)

    def get_connection(self):
        return ConnectionWrapper(self)

    def check_connection(self, cnx):
        """check connection validity, return None if the connection is still valid
        else a new connection (called when the pool using the given connection is
        being attached to a session)

        always return the connection to reset eventually cached cursor
        """
        return cnx

    def pool_reset(self, cnx):
        """the pool using the given connection is being reseted from its current
        attached session: release the connection lock if the connection wrapper
        has a connection set
        """
        if cnx._cnx is not None:
            cnx._cnx.close()
            # reset _cnx to ensure next thread using cnx will get a new
            # connection
            cnx._cnx = None

    def syntax_tree_search(self, session, union,
                           args=None, cachekey=None, varmap=None, debug=0):
        """return result from this source for a rql query (actually from a rql
        syntax tree and a solution dictionary mapping each used variable to a
        possible type). If cachekey is given, the query necessary to fetch the
        results (but not the results themselves) may be cached using this key.
        """
        if self._need_sql_create:
            return []
        sql, query_args = self.rqlsqlgen.generate(union, args)
        if server.DEBUG:
            print self.uri, 'SOURCE RQL', union.as_string()
        args = self.sqladapter.merge_args(args, query_args)
        res = self.sqladapter.process_result(self.doexec(session, sql, args))
        if server.DEBUG:
            print '------>', res
        return res

    def local_add_entity(self, session, entity):
        """insert the entity in the local database.

        This is not provided as add_entity implementation since usually source
        don't want to simply do this, so let raise NotImplementedError and the
        source implementor may use this method if necessary
        """
        attrs = self.sqladapter.preprocess_entity(entity)
        sql = self.sqladapter.sqlgen.insert(SQL_PREFIX + str(entity.e_schema), attrs)
        self.doexec(session, sql, attrs)

    def add_entity(self, session, entity):
        """add a new entity to the source"""
        raise NotImplementedError()

    def local_update_entity(self, session, entity, attrs=None):
        """update an entity in the source

        This is not provided as update_entity implementation since usually
        source don't want to simply do this, so let raise NotImplementedError
        and the source implementor may use this method if necessary
        """
        if attrs is None:
            attrs = self.sqladapter.preprocess_entity(entity)
        sql = self.sqladapter.sqlgen.update(SQL_PREFIX + str(entity.e_schema),
                                            attrs, [SQL_PREFIX + 'eid'])
        self.doexec(session, sql, attrs)

    def update_entity(self, session, entity):
        """update an entity in the source"""
        raise NotImplementedError()

    def delete_entity(self, session, etype, eid):
        """delete an entity from the source

        this is not deleting a file in the svn but deleting entities from the
        source. Main usage is to delete repository content when a Repository
        entity is deleted.
        """
        attrs = {SQL_PREFIX + 'eid': eid}
        sql = self.sqladapter.sqlgen.delete(SQL_PREFIX + etype, attrs)
        self.doexec(session, sql, attrs)

    def local_add_relation(self, session, subject, rtype, object):
        """add a relation to the source

        This is not provided as add_relation implementation since usually
        source don't want to simply do this, so let raise NotImplementedError
        and the source implementor may use this method if necessary
        """
        attrs = {'eid_from': subject, 'eid_to': object}
        sql = self.sqladapter.sqlgen.insert('%s_relation' % rtype, attrs)
        self.doexec(session, sql, attrs)

    def add_relation(self, session, subject, rtype, object):
        """add a relation to the source"""
        raise NotImplementedError()

    def delete_relation(self, session, subject, rtype, object):
        """delete a relation from the source"""
        rschema = self.schema.rschema(rtype)
        if rschema.inlined:
            if subject in session.transaction_data.get('pendingeids', ()):
                return
            table = SQL_PREFIX + session.describe(subject)[0]
            column = SQL_PREFIX + rtype
            sql = 'UPDATE %s SET %s=NULL WHERE %seid=%%(eid)s' % (table, column, SQL_PREFIX)
            attrs = {'eid' : subject}
        else:
            attrs = {'eid_from': subject, 'eid_to': object}
            sql = self.sqladapter.sqlgen.delete('%s_relation' % rtype, attrs)
        self.doexec(session, sql, attrs)

    def doexec(self, session, query, args=None):
        """Execute a query.
        it's a function just so that it shows up in profiling
        """
        if server.DEBUG:
            print 'exec', query, args
        cursor = session.pool[self.uri]
        try:
            # str(query) to avoid error if it's an unicode string
            cursor.execute(str(query), args)
        except Exception, ex:
            self.critical("sql: %r\n args: %s\ndbms message: %r",
                          query, args, ex.args[0])
            try:
                session.pool.connection(self.uri).rollback()
                self.critical('transaction has been rollbacked')
            except:
                pass
            raise
        return cursor
