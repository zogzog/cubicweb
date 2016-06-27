# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""SQL utilities functions and classes."""
from __future__ import print_function

__docformat__ = "restructuredtext en"

import sys
import re
import subprocess
from os.path import abspath
from logging import getLogger
from datetime import time, datetime, timedelta

from six import string_types, text_type
from six.moves import filter

from pytz import utc

from logilab import database as db, common as lgc
from logilab.common.shellutils import ProgressBar, DummyProgressBar
from logilab.common.deprecation import deprecated
from logilab.common.logging_ext import set_log_methods
from logilab.common.date import utctime, utcdatetime, strptime
from logilab.database.sqlgen import SQLGenerator

from cubicweb import Binary, ConfigurationError
from cubicweb.uilib import remove_html_tags
from cubicweb.schema import PURE_VIRTUAL_RTYPES
from cubicweb.server import SQL_CONNECT_HOOKS
from cubicweb.server.utils import crypt_password

lgc.USE_MX_DATETIME = False
SQL_PREFIX = 'cw_'


def _run_command(cmd):
    if isinstance(cmd, string_types):
        print(cmd)
        return subprocess.call(cmd, shell=True)
    else:
        print(' '.join(cmd))
        return subprocess.call(cmd)


def sqlexec(sqlstmts, cursor_or_execute, withpb=True,
            pbtitle='', delimiter=';', cnx=None):
    """execute sql statements ignoring DROP/ CREATE GROUP or USER statements
    error.

    :sqlstmts_as_string: a string or a list of sql statements.
    :cursor_or_execute: sql cursor or a callback used to execute statements
    :cnx: if given, commit/rollback at each statement.

    :withpb: if True, display a progresse bar
    :pbtitle: a string displayed as the progress bar title (if `withpb=True`)

    :delimiter: a string used to split sqlstmts (if it is a string)

    Return the failed statements (same type as sqlstmts)
    """
    if hasattr(cursor_or_execute, 'execute'):
        execute = cursor_or_execute.execute
    else:
        execute = cursor_or_execute
    sqlstmts_as_string = False
    if isinstance(sqlstmts, string_types):
        sqlstmts_as_string = True
        sqlstmts = sqlstmts.split(delimiter)
    if withpb:
        if sys.stdout.isatty():
            pb = ProgressBar(len(sqlstmts), title=pbtitle)
        else:
            pb = DummyProgressBar()
    failed = []
    for sql in sqlstmts:
        sql = sql.strip()
        if withpb:
            pb.update()
        if not sql:
            continue
        try:
            # some dbapi modules doesn't accept unicode for sql string
            execute(str(sql))
        except Exception as ex:
            print(ex, file=sys.stderr)
            if cnx:
                cnx.rollback()
            failed.append(sql)
        else:
            if cnx:
                cnx.commit()
    if withpb:
        print()
    if sqlstmts_as_string:
        failed = delimiter.join(failed)
    return failed


def sqlgrants(schema, driver, user,
              text_index=True, set_owner=True,
              skip_relations=(), skip_entities=()):
    """return sql to give all access privileges to the given user on the system
    schema
    """
    from cubicweb.server.schema2sql import grant_schema
    from cubicweb.server.sources import native
    output = []
    w = output.append
    w(native.grant_schema(user, set_owner))
    w('')
    if text_index:
        dbhelper = db.get_db_helper(driver)
        w(dbhelper.sql_grant_user_on_fti(user))
        w('')
    w(grant_schema(schema, user, set_owner, skip_entities=skip_entities, prefix=SQL_PREFIX))
    return '\n'.join(output)


def sqlschema(schema, driver, text_index=True,
              user=None, set_owner=False,
              skip_relations=PURE_VIRTUAL_RTYPES, skip_entities=()):
    """return the system sql schema, according to the given parameters"""
    from cubicweb.server.schema2sql import schema2sql
    from cubicweb.server.sources import native
    if set_owner:
        assert user, 'user is argument required when set_owner is true'
    output = []
    w = output.append
    w(native.sql_schema(driver))
    w('')
    dbhelper = db.get_db_helper(driver)
    if text_index:
        w(dbhelper.sql_init_fti().replace(';', ';;'))
        w('')
    w(schema2sql(dbhelper, schema, prefix=SQL_PREFIX,
                 skip_entities=skip_entities,
                 skip_relations=skip_relations).replace(';', ';;'))
    if dbhelper.users_support and user:
        w('')
        w(sqlgrants(schema, driver, user, text_index, set_owner,
                    skip_relations, skip_entities).replace(';', ';;'))
    return '\n'.join(output)


def sqldropschema(schema, driver, text_index=True,
                  skip_relations=PURE_VIRTUAL_RTYPES, skip_entities=()):
    """return the sql to drop the schema, according to the given parameters"""
    from cubicweb.server.schema2sql import dropschema2sql
    from cubicweb.server.sources import native
    output = []
    w = output.append
    if text_index:
        dbhelper = db.get_db_helper(driver)
        w(dbhelper.sql_drop_fti())
        w('')
    w(dropschema2sql(dbhelper, schema, prefix=SQL_PREFIX,
                     skip_entities=skip_entities,
                     skip_relations=skip_relations))
    w('')
    w(native.sql_drop_schema(driver))
    return '\n'.join(output)


_SQL_DROP_ALL_USER_TABLES_FILTER_FUNCTION = re.compile('^(?!(sql|pg)_)').match
def sql_drop_all_user_tables(driver_or_helper, sqlcursor):
    """Return ths sql to drop all tables found in the database system."""
    if not getattr(driver_or_helper, 'list_tables', None):
        dbhelper = db.get_db_helper(driver_or_helper)
    else:
        dbhelper = driver_or_helper

    cmds = [dbhelper.sql_drop_sequence('entities_id_seq')]
    # for mssql, we need to drop views before tables
    if hasattr(dbhelper, 'list_views'):
        cmds += ['DROP VIEW %s;' % name
                 for name in filter(_SQL_DROP_ALL_USER_TABLES_FILTER_FUNCTION, dbhelper.list_views(sqlcursor))]
    cmds += ['DROP TABLE %s;' % name
             for name in filter(_SQL_DROP_ALL_USER_TABLES_FILTER_FUNCTION, dbhelper.list_tables(sqlcursor))]
    return '\n'.join(cmds)


class ConnectionWrapper(object):
    """handle connection to the system source, at some point associated to a
    :class:`Session`
    """

    # since 3.19, we only have to manage the system source connection
    def __init__(self, system_source):
        # dictionary of (source, connection), indexed by sources'uri
        self._source = system_source
        self.cnx = system_source.get_connection()
        self.cu = self.cnx.cursor()

    def commit(self):
        """commit the current transaction for this user"""
        # let exception propagates
        self.cnx.commit()

    def rollback(self):
        """rollback the current transaction for this user"""
        # catch exceptions, rollback other sources anyway
        try:
            self.cnx.rollback()
        except Exception:
            self._source.critical('rollback error', exc_info=sys.exc_info())
            # error on rollback, the connection is much probably in a really
            # bad state. Replace it by a new one.
            self.reconnect()

    def close(self, i_know_what_i_do=False):
        """close all connections in the set"""
        if i_know_what_i_do is not True: # unexpected closing safety belt
            raise RuntimeError('connections set shouldn\'t be closed')
        try:
            self.cu.close()
            self.cu = None
        except Exception:
            pass
        try:
            self.cnx.close()
            self.cnx = None
        except Exception:
            pass

    # internals ###############################################################

    def cnxset_freed(self):
        """connections set is being freed from a session"""
        pass # no nothing by default

    def reconnect(self):
        """reopen a connection for this source or all sources if none specified
        """
        try:
            # properly close existing connection if any
            self.cnx.close()
        except Exception:
            pass
        self._source.info('trying to reconnect')
        self.cnx = self._source.get_connection()
        self.cu = self.cnx.cursor()

    @deprecated('[3.19] use .cu instead')
    def __getitem__(self, uri):
        assert uri == 'system'
        return self.cu

    @deprecated('[3.19] use repo.system_source instead')
    def source(self, uid):
        assert uid == 'system'
        return self._source

    @deprecated('[3.19] use .cnx instead')
    def connection(self, uid):
        assert uid == 'system'
        return self.cnx


class SqliteConnectionWrapper(ConnectionWrapper):
    """Sqlite specific connection wrapper: close the connection each time it's
    freed (and reopen it later when needed)
    """
    def __init__(self, system_source):
        # don't call parent's __init__, we don't want to initiate the connection
        self._source = system_source

    _cnx = None

    def cnxset_freed(self):
        self.cu.close()
        self.cnx.close()
        self.cnx = self.cu = None

    @property
    def cnx(self):
        if self._cnx is None:
            self._cnx = self._source.get_connection()
            self._cu = self._cnx.cursor()
        return self._cnx
    @cnx.setter
    def cnx(self, value):
        self._cnx = value

    @property
    def cu(self):
        if self._cnx is None:
            self._cnx = self._source.get_connection()
            self._cu = self._cnx.cursor()
        return self._cu
    @cu.setter
    def cu(self, value):
        self._cu = value


class SQLAdapterMixIn(object):
    """Mixin for SQL data sources, getting a connection from a configuration
    dictionary and handling connection locking
    """
    cnx_wrap = ConnectionWrapper

    def __init__(self, source_config, repairing=False):
        try:
            self.dbdriver = source_config['db-driver'].lower()
            dbname = source_config['db-name']
        except KeyError:
            raise ConfigurationError('missing some expected entries in sources file')
        dbhost = source_config.get('db-host')
        port = source_config.get('db-port')
        dbport = port and int(port) or None
        dbuser = source_config.get('db-user')
        dbpassword = source_config.get('db-password')
        dbencoding = source_config.get('db-encoding', 'UTF-8')
        dbextraargs = source_config.get('db-extra-arguments')
        dbnamespace = source_config.get('db-namespace')
        self.dbhelper = db.get_db_helper(self.dbdriver)
        self.dbhelper.record_connection_info(dbname, dbhost, dbport, dbuser,
                                             dbpassword, dbextraargs,
                                             dbencoding, dbnamespace)
        self.sqlgen = SQLGenerator()
        # copy back some commonly accessed attributes
        dbapi_module = self.dbhelper.dbapi_module
        self.OperationalError = dbapi_module.OperationalError
        self.InterfaceError = dbapi_module.InterfaceError
        self.DbapiError = dbapi_module.Error
        self._binary = self.dbhelper.binary_value
        self._process_value = dbapi_module.process_value
        self._dbencoding = dbencoding
        if self.dbdriver == 'sqlite':
            self.cnx_wrap = SqliteConnectionWrapper
            self.dbhelper.dbname = abspath(self.dbhelper.dbname)
        if not repairing:
            statement_timeout = int(source_config.get('db-statement-timeout', 0))
            if statement_timeout > 0:
                def set_postgres_timeout(cnx):
                    cnx.cursor().execute('SET statement_timeout to %d' % statement_timeout)
                    cnx.commit()
                postgres_hooks = SQL_CONNECT_HOOKS['postgres']
                postgres_hooks.append(set_postgres_timeout)

    def wrapped_connection(self):
        """open and return a connection to the database, wrapped into a class
        handling reconnection and all
        """
        return self.cnx_wrap(self)

    def get_connection(self):
        """open and return a connection to the database"""
        return self.dbhelper.get_connection()

    def backup_to_file(self, backupfile, confirm):
        for cmd in self.dbhelper.backup_commands(backupfile,
                                                 keepownership=False):
            if _run_command(cmd):
                if not confirm('   [Failed] Continue anyway?', default='n'):
                    raise Exception('Failed command: %s' % cmd)

    def restore_from_file(self, backupfile, confirm, drop=True):
        for cmd in self.dbhelper.restore_commands(backupfile,
                                                  keepownership=False,
                                                  drop=drop):
            if _run_command(cmd):
                if not confirm('   [Failed] Continue anyway?', default='n'):
                    raise Exception('Failed command: %s' % cmd)

    def merge_args(self, args, query_args):
        if args is not None:
            newargs = {}
            for key, val in args.items():
                # convert cubicweb binary into db binary
                if isinstance(val, Binary):
                    val = self._binary(val.getvalue())
                # convert timestamp to utc.
                # expect SET TiME ZONE to UTC at connection opening time.
                # This shouldn't change anything for datetime without TZ.
                elif isinstance(val, datetime) and val.tzinfo is not None:
                    val = utcdatetime(val)
                elif isinstance(val, time) and val.tzinfo is not None:
                    val = utctime(val)
                newargs[key] = val
            # should not collide
            assert not (frozenset(newargs) & frozenset(query_args)), \
                'unexpected collision: %s' % (frozenset(newargs) & frozenset(query_args))
            newargs.update(query_args)
            return newargs
        return query_args

    def process_result(self, cursor, cnx=None, column_callbacks=None):
        """return a list of CubicWeb compliant values from data in the given cursor
        """
        return list(self.iter_process_result(cursor, cnx, column_callbacks))

    def iter_process_result(self, cursor, cnx, column_callbacks=None):
        """return a iterator on tuples of CubicWeb compliant values from data
        in the given cursor
        """
        # use two different implementations to avoid paying the price of
        # callback lookup for each *cell* in results when there is nothing to
        # lookup
        if not column_callbacks:
            return self.dbhelper.dbapi_module.process_cursor(cursor, self._dbencoding,
                                                             Binary)
        assert cnx
        return self._cb_process_result(cursor, column_callbacks, cnx)

    def _cb_process_result(self, cursor, column_callbacks, cnx):
        # begin bind to locals for optimization
        descr = cursor.description
        encoding = self._dbencoding
        process_value = self._process_value
        binary = Binary
        # /end
        cursor.arraysize = 100
        while True:
            results = cursor.fetchmany()
            if not results:
                break
            for line in results:
                result = []
                for col, value in enumerate(line):
                    if value is None:
                        result.append(value)
                        continue
                    cbstack = column_callbacks.get(col, None)
                    if cbstack is None:
                        value = process_value(value, descr[col], encoding, binary)
                    else:
                        for cb in cbstack:
                            value = cb(self, cnx, value)
                    result.append(value)
                yield result

    def preprocess_entity(self, entity):
        """return a dictionary to use as extra argument to cursor.execute
        to insert/update an entity into a SQL database
        """
        attrs = {}
        eschema = entity.e_schema
        converters = getattr(self.dbhelper, 'TYPE_CONVERTERS', {})
        for attr, value in entity.cw_edited.items():
            if value is not None and eschema.subjrels[attr].final:
                atype = str(entity.e_schema.destination(attr))
                if atype in converters:
                    # It is easier to modify preprocess_entity rather
                    # than add_entity (native) as this behavior
                    # may also be used for update.
                    value = converters[atype](value)
                elif atype == 'Password': # XXX could be done using a TYPE_CONVERTERS callback
                    # if value is a Binary instance, this mean we got it
                    # from a query result and so it is already encrypted
                    if isinstance(value, Binary):
                        value = value.getvalue()
                    else:
                        value = crypt_password(value)
                    value = self._binary(value)
                elif isinstance(value, Binary):
                    value = self._binary(value.getvalue())
            attrs[SQL_PREFIX+str(attr)] = value
        attrs[SQL_PREFIX+'eid'] = entity.eid
        return attrs

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

set_log_methods(SQLAdapterMixIn, getLogger('cubicweb.sqladapter'))


# connection initialization functions ##########################################

def _install_sqlite_querier_patch():
    """This monkey-patch hotfixes a bug sqlite causing some dates to be returned as strings rather than
    date objects (http://www.sqlite.org/cvstrac/tktview?tn=1327,33)
    """
    from cubicweb.server.querier import QuerierHelper

    if hasattr(QuerierHelper, '_sqlite_patched'):
        return  # already monkey patched

    def wrap_execute(base_execute):
        def new_execute(*args, **kwargs):
            rset = base_execute(*args, **kwargs)
            if rset.description:
                found_date = False
                for row, rowdesc in zip(rset, rset.description):
                    for cellindex, (value, vtype) in enumerate(zip(row, rowdesc)):
                        if vtype in ('TZDatetime', 'Date', 'Datetime') \
                           and isinstance(value, text_type):
                            found_date = True
                            value = value.rsplit('.', 1)[0]
                            try:
                                row[cellindex] = strptime(value, '%Y-%m-%d %H:%M:%S')
                            except Exception:
                                row[cellindex] = strptime(value, '%Y-%m-%d')
                            if vtype == 'TZDatetime':
                                row[cellindex] = row[cellindex].replace(tzinfo=utc)
                        if vtype == 'Time' and isinstance(value, text_type):
                            found_date = True
                            try:
                                row[cellindex] = strptime(value, '%H:%M:%S')
                            except Exception:
                                # DateTime used as Time?
                                row[cellindex] = strptime(value, '%Y-%m-%d %H:%M:%S')
                        if vtype == 'Interval' and isinstance(value, int):
                            found_date = True
                            # XXX value is in number of seconds?
                            row[cellindex] = timedelta(0, value, 0)
                    if not found_date:
                        break
            return rset
        return new_execute

    QuerierHelper.execute = wrap_execute(QuerierHelper.execute)
    QuerierHelper._sqlite_patched = True


def _init_sqlite_connection(cnx):
    """Internal function that will be called to init a sqlite connection"""
    _install_sqlite_querier_patch()

    class group_concat(object):
        def __init__(self):
            self.values = set()
        def step(self, value):
            if value is not None:
                self.values.add(value)
        def finalize(self):
            return ', '.join(text_type(v) for v in self.values)

    cnx.create_aggregate("GROUP_CONCAT", 1, group_concat)

    def _limit_size(text, maxsize, format='text/plain'):
        if len(text) < maxsize:
            return text
        if format in ('text/html', 'text/xhtml', 'text/xml'):
            text = remove_html_tags(text)
        if len(text) > maxsize:
            text = text[:maxsize] + '...'
        return text

    def limit_size3(text, format, maxsize):
        return _limit_size(text, maxsize, format)
    cnx.create_function("LIMIT_SIZE", 3, limit_size3)

    def limit_size2(text, maxsize):
        return _limit_size(text, maxsize)
    cnx.create_function("TEXT_LIMIT_SIZE", 2, limit_size2)

    from logilab.common.date import strptime
    def weekday(ustr):
        try:
            dt = strptime(ustr, '%Y-%m-%d %H:%M:%S')
        except:
            dt =  strptime(ustr, '%Y-%m-%d')
        # expect sunday to be 1, saturday 7 while weekday method return 0 for
        # monday
        return (dt.weekday() + 1) % 7
    cnx.create_function("WEEKDAY", 1, weekday)

    cnx.cursor().execute("pragma foreign_keys = on")

    import yams.constraints
    yams.constraints.patch_sqlite_decimal()

sqlite_hooks = SQL_CONNECT_HOOKS.setdefault('sqlite', [])
sqlite_hooks.append(_init_sqlite_connection)


def _init_postgres_connection(cnx):
    """Internal function that will be called to init a postgresql connection"""
    cnx.cursor().execute('SET TIME ZONE UTC')
    # commit is needed, else setting are lost if the connection is first
    # rolled back
    cnx.commit()

postgres_hooks = SQL_CONNECT_HOOKS.setdefault('postgres', [])
postgres_hooks.append(_init_postgres_connection)
