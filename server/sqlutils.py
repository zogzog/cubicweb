# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""SQL utilities functions and classes.

"""
__docformat__ = "restructuredtext en"

import os
import subprocess
from datetime import datetime, date

from logilab import database as db, common as lgc
from logilab.common.shellutils import ProgressBar
from logilab.common.date import todate, todatetime
from logilab.database.sqlgen import SQLGenerator

from cubicweb import Binary, ConfigurationError
from cubicweb.uilib import remove_html_tags
from cubicweb.schema import PURE_VIRTUAL_RTYPES
from cubicweb.server import SQL_CONNECT_HOOKS
from cubicweb.server.utils import crypt_password
from rql.utils import RQL_FUNCTIONS_REGISTRY

lgc.USE_MX_DATETIME = False
SQL_PREFIX = 'cw_'

def _run_command(cmd):
    """backup/restore command are string w/ lgc < 0.47, lists with earlier versions
    """
    if isinstance(cmd, basestring):
        print '->', cmd
        return subprocess.call(cmd, shell=True)
    print ' '.join(cmd)
    return subprocess.call(cmd)


def sqlexec(sqlstmts, cursor_or_execute, withpb=not os.environ.get('APYCOT_ROOT'),
            pbtitle='', delimiter=';'):
    """execute sql statements ignoring DROP/ CREATE GROUP or USER statements
    error. If a cnx is given, commit at each statement
    """
    if hasattr(cursor_or_execute, 'execute'):
        execute = cursor_or_execute.execute
    else:
        execute = cursor_or_execute
    sqlstmts = sqlstmts.split(delimiter)
    if withpb:
        pb = ProgressBar(len(sqlstmts), title=pbtitle)
    for sql in sqlstmts:
        sql = sql.strip()
        if withpb:
            pb.update()
        if not sql:
            continue
        # some dbapi modules doesn't accept unicode for sql string
        execute(str(sql))
    if withpb:
        print


def sqlgrants(schema, driver, user,
              text_index=True, set_owner=True,
              skip_relations=(), skip_entities=()):
    """return sql to give all access privileges to the given user on the system
    schema
    """
    from yams.schema2sql import grant_schema
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
    from yams.schema2sql import schema2sql
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
    from yams.schema2sql import dropschema2sql
    from cubicweb.server.sources import native
    output = []
    w = output.append
    if text_index:
        dbhelper = db.get_db_helper(driver)
        w(dbhelper.sql_drop_fti())
        w('')
    w(dropschema2sql(schema, prefix=SQL_PREFIX,
                     skip_entities=skip_entities,
                     skip_relations=skip_relations))
    w('')
    w(native.sql_drop_schema(driver))
    return '\n'.join(output)


class SQLAdapterMixIn(object):
    """Mixin for SQL data sources, getting a connection from a configuration
    dictionary and handling connection locking
    """

    def __init__(self, source_config):
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
        self.dbhelper = db.get_db_helper(self.dbdriver)
        self.dbhelper.record_connection_info(dbname, dbhost, dbport, dbuser,
                                             dbpassword, dbextraargs,
                                             dbencoding)
        self.sqlgen = SQLGenerator()
        # copy back some commonly accessed attributes
        dbapi_module = self.dbhelper.dbapi_module
        self.OperationalError = dbapi_module.OperationalError
        self.InterfaceError = dbapi_module.InterfaceError
        self._binary = dbapi_module.Binary
        self._process_value = dbapi_module.process_value
        self._dbencoding = dbencoding

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
            for key, val in args.iteritems():
                # convert cubicweb binary into db binary
                if isinstance(val, Binary):
                    val = self._binary(val.getvalue())
                newargs[key] = val
            # should not collide
            newargs.update(query_args)
            return newargs
        return query_args

    def process_result(self, cursor, column_callbacks=None):
        """return a list of CubicWeb compliant values from data in the given cursor
        """
        # use two different implementations to avoid paying the price of
        # callback lookup for each *cell* in results when there is nothing to
        # lookup
        if not column_callbacks:
            return self._process_result(cursor)
        return self._cb_process_result(cursor, column_callbacks)

    def _process_result(self, cursor, column_callbacks=None):
        # begin bind to locals for optimization
        descr = cursor.description
        encoding = self._dbencoding
        process_value = self._process_value
        binary = Binary
        # /end
        results = cursor.fetchall()
        for i, line in enumerate(results):
            result = []
            for col, value in enumerate(line):
                if value is None:
                    result.append(value)
                    continue
                result.append(process_value(value, descr[col], encoding, binary))
            results[i] = result
        return results

    def _cb_process_result(self, cursor, column_callbacks):
        # begin bind to locals for optimization
        descr = cursor.description
        encoding = self._dbencoding
        process_value = self._process_value
        binary = Binary
        # /end
        results = cursor.fetchall()
        for i, line in enumerate(results):
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
                        value = cb(self, value)
                result.append(value)
            results[i] = result
        return results

    def preprocess_entity(self, entity):
        """return a dictionary to use as extra argument to cursor.execute
        to insert/update an entity into a SQL database
        """
        attrs = {}
        eschema = entity.e_schema
        for attr in entity.edited_attributes:
            value = entity[attr]
            rschema = eschema.subjrels[attr]
            if rschema.final:
                atype = str(entity.e_schema.destination(attr))
                if atype == 'Boolean':
                    value = self.dbhelper.boolean_value(value)
                elif atype == 'Password':
                    # if value is a Binary instance, this mean we got it
                    # from a query result and so it is already encrypted
                    if isinstance(value, Binary):
                        value = value.getvalue()
                    else:
                        value = crypt_password(value)
                    value = self._binary(value)
                # XXX needed for sqlite but I don't think it is for other backends
                elif atype == 'Datetime' and isinstance(value, date):
                    value = todatetime(value)
                elif atype == 'Date' and isinstance(value, datetime):
                    value = todate(value)
                elif isinstance(value, Binary):
                    value = self._binary(value.getvalue())
            attrs[SQL_PREFIX+str(attr)] = value
        attrs[SQL_PREFIX+'eid'] = entity.eid
        return attrs


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(SQLAdapterMixIn, getLogger('cubicweb.sqladapter'))

def init_sqlite_connexion(cnx):

    class group_concat(object):
        def __init__(self):
            self.values = []
        def step(self, value):
            if value is not None:
                self.values.append(value)
        def finalize(self):
            return ', '.join(self.values)
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

    import yams.constraints
    yams.constraints.patch_sqlite_decimal()

sqlite_hooks = SQL_CONNECT_HOOKS.setdefault('sqlite', [])
sqlite_hooks.append(init_sqlite_connexion)
