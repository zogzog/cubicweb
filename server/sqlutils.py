"""SQL utilities functions and classes.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import os
from os.path import exists
from warnings import warn
from datetime import datetime, date, timedelta

import logilab.common as lgc
from logilab.common.shellutils import ProgressBar
from logilab.common import db
from logilab.common.adbh import get_adv_func_helper
from logilab.common.sqlgen import SQLGenerator

from indexer import get_indexer

from cubicweb import Binary, ConfigurationError
from cubicweb.utils import todate, todatetime
from cubicweb.common.uilib import remove_html_tags
from cubicweb.toolsutils import restrict_perms_to_user
from cubicweb.server import SQL_CONNECT_HOOKS
from cubicweb.server.utils import crypt_password


lgc.USE_MX_DATETIME = False
SQL_PREFIX = 'cw_'


def sqlexec(sqlstmts, cursor_or_execute, withpb=True, pbtitle='', delimiter=';'):
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
        indexer = get_indexer(driver)
        w(indexer.sql_grant_user(user))
        w('')
    w(grant_schema(schema, user, set_owner, skip_entities=skip_entities, prefix=SQL_PREFIX))
    return '\n'.join(output)


def sqlschema(schema, driver, text_index=True,
              user=None, set_owner=False,
              skip_relations=('has_text', 'identity'), skip_entities=()):
    """return the system sql schema, according to the given parameters"""
    from yams.schema2sql import schema2sql
    from cubicweb.server.sources import native
    if set_owner:
        assert user, 'user is argument required when set_owner is true'
    output = []
    w = output.append
    w(native.sql_schema(driver))
    w('')
    if text_index:
        indexer = get_indexer(driver)
        w(indexer.sql_init_fti())
        w('')
    dbhelper = get_adv_func_helper(driver)
    w(schema2sql(dbhelper, schema, prefix=SQL_PREFIX,
                 skip_entities=skip_entities, skip_relations=skip_relations))
    if dbhelper.users_support and user:
        w('')
        w(sqlgrants(schema, driver, user, text_index, set_owner,
                    skip_relations, skip_entities))
    return '\n'.join(output)


def sqldropschema(schema, driver, text_index=True,
                  skip_relations=('has_text', 'identity'), skip_entities=()):
    """return the sql to drop the schema, according to the given parameters"""
    from yams.schema2sql import dropschema2sql
    from cubicweb.server.sources import native
    output = []
    w = output.append
    w(native.sql_drop_schema(driver))
    w('')
    if text_index:
        indexer = get_indexer(driver)
        w(indexer.sql_drop_fti())
        w('')
    w(dropschema2sql(schema, prefix=SQL_PREFIX,
                     skip_entities=skip_entities,
                     skip_relations=skip_relations))
    return '\n'.join(output)


def sql_source_backup(source, sqladapter, confirm, backupfile,
                      askconfirm=False):
    if exists(backupfile):
        if not confirm('Backup file %s exists, overwrite it?' % backupfile):
            return
    elif askconfirm and not confirm('Backup %s database?'
                                    % source.repo.config.appid):
        print '-> no backup done.'
        return
    # should close opened connection before backuping
    source.close_pool_connections()
    try:
        sqladapter.backup_to_file(backupfile, confirm)
    finally:
        source.open_pool_connections()

def sql_source_restore(source, sqladapter, confirm, backupfile, drop=True,
                       askconfirm=False):
    if not exists(backupfile):
        raise Exception("backup file %s doesn't exist" % backupfile)
    app = source.repo.config.appid
    if askconfirm and not confirm('Restore %s %s database from %s ?'
                                  % (app, source.uri, backupfile)):
        return
    # should close opened connection before restoring
    source.close_pool_connections()
    try:
        sqladapter.restore_from_file(backupfile, confirm, drop=drop)
    finally:
        source.open_pool_connections()


try:
    from mx.DateTime import DateTimeType, DateTimeDeltaType
except ImportError:
    DateTimeType = DateTimeDeltaType = None

class SQLAdapterMixIn(object):
    """Mixin for SQL data sources, getting a connection from a configuration
    dictionary and handling connection locking
    """

    def __init__(self, source_config):
        try:
            self.dbdriver = source_config['db-driver'].lower()
            self.dbname = source_config['db-name']
        except KeyError:
            raise ConfigurationError('missing some expected entries in sources file')
        self.dbhost = source_config.get('db-host')
        port = source_config.get('db-port')
        self.dbport = port and int(port) or None
        self.dbuser = source_config.get('db-user')
        self.dbpasswd = source_config.get('db-password')
        self.encoding = source_config.get('db-encoding', 'UTF-8')
        self.dbapi_module = db.get_dbapi_compliant_module(self.dbdriver)
        self.binary = self.dbapi_module.Binary
        self.dbhelper = self.dbapi_module.adv_func_helper
        self.sqlgen = SQLGenerator()

    def get_connection(self, user=None, password=None):
        """open and return a connection to the database"""
        if user or self.dbuser:
            self.info('connecting to %s@%s for user %s', self.dbname,
                      self.dbhost or 'localhost', user or self.dbuser)
        else:
            self.info('connecting to %s@%s', self.dbname,
                      self.dbhost or 'localhost')
        cnx = self.dbapi_module.connect(self.dbhost, self.dbname,
                                        user or self.dbuser,
                                        password or self.dbpasswd,
                                        port=self.dbport)
        init_cnx(self.dbdriver, cnx)
        #self.dbapi_module.type_code_test(cnx.cursor())
        return cnx

    def backup_to_file(self, backupfile, confirm):
        cmd = self.dbhelper.backup_command(self.dbname, self.dbhost,
                                           self.dbuser, backupfile,
                                           keepownership=False)
        backupdir = os.path.dirname(backupfile)
        if not os.path.exists(backupdir):
            if confirm('%s does not exist. Create it?' % backupdir,
                       abort=False, shell=False):
                os.mkdir(backupdir)
            else:
                print '-> failed to backup instance'
                return
        if os.system(cmd):
            print '-> error trying to backup with command', cmd
            if not confirm('Continue anyway?', default_is_yes=False):
                raise SystemExit(1)
        else:
            print '-> backup file',  backupfile
            restrict_perms_to_user(backupfile, self.info)

    def restore_from_file(self, backupfile, confirm, drop=True):
        for cmd in self.dbhelper.restore_commands(self.dbname, self.dbhost,
                                                  self.dbuser, backupfile,
                                                  self.encoding,
                                                  keepownership=False,
                                                  drop=drop):
            while True:
                print cmd
                if os.system(cmd):
                    print '-> error while restoring the base'
                    answer = confirm('Continue anyway?',
                                     shell=False, abort=False, retry=True)
                    if not answer:
                        raise SystemExit(1)
                    if answer == 1: # 1: continue, 2: retry
                        break
                else:
                    break
        print '-> database restored.'

    def merge_args(self, args, query_args):
        if args is not None:
            args = dict(args)
            for key, val in args.items():
                # convert cubicweb binary into db binary
                if isinstance(val, Binary):
                    val = self.binary(val.getvalue())
                # XXX <3.2 bw compat
                elif type(val) is DateTimeType:
                    warn('found mx date time instance, please update to use datetime',
                         DeprecationWarning)
                    val = datetime(val.year, val.month, val.day,
                                   val.hour, val.minute, int(val.second))
                elif type(val) is DateTimeDeltaType:
                    warn('found mx date time instance, please update to use datetime',
                         DeprecationWarning)
                    val = timedelta(0, int(val.seconds), 0)
                args[key] = val
            # should not collide
            args.update(query_args)
            return args
        return query_args

    def process_result(self, cursor):
        """return a list of CubicWeb compliant values from data in the given cursor
        """
        descr = cursor.description
        encoding = self.encoding
        process_value = self.dbapi_module.process_value
        binary = Binary
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


    def preprocess_entity(self, entity):
        """return a dictionary to use as extra argument to cursor.execute
        to insert/update an entity into a SQL database
        """
        attrs = {}
        eschema = entity.e_schema
        for attr, value in entity.items():
            rschema = eschema.subject_relation(attr)
            if rschema.is_final():
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
                # XXX needed for sqlite but I don't think it is for other backends
                elif atype == 'Datetime' and isinstance(value, date):
                    value = todatetime(value)
                elif atype == 'Date' and isinstance(value, datetime):
                    value = todate(value)
                elif isinstance(value, Binary):
                    value = self.binary(value.getvalue())
                # XXX <3.2 bw compat
                elif type(value) is DateTimeType:
                    warn('found mx date time instance, please update to use datetime',
                         DeprecationWarning)
                    value = datetime(value.year, value.month, value.day,
                                   value.hour, value.minute, int(value.second))
                elif type(value) is DateTimeDeltaType:
                    warn('found mx date time instance, please update to use datetime',
                         DeprecationWarning)
                    value = timedelta(0, int(value.seconds), 0)
            attrs[SQL_PREFIX+str(attr)] = value
        return attrs


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(SQLAdapterMixIn, getLogger('cubicweb.sqladapter'))

def init_sqlite_connexion(cnx):
    # XXX should not be publicly exposed
    #def comma_join(strings):
    #    return ', '.join(strings)
    #cnx.create_function("COMMA_JOIN", 1, comma_join)

    class concat_strings(object):
        def __init__(self):
            self.values = []
        def step(self, value):
            if value is not None:
                self.values.append(value)
        def finalize(self):
            return ', '.join(self.values)
    # renamed to GROUP_CONCAT in cubicweb 2.45, keep old name for bw compat for
    # some time
    cnx.create_aggregate("CONCAT_STRINGS", 1, concat_strings)
    cnx.create_aggregate("GROUP_CONCAT", 1, concat_strings)

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
    if hasattr(yams.constraints, 'patch_sqlite_decimal'):
        yams.constraints.patch_sqlite_decimal()


sqlite_hooks = SQL_CONNECT_HOOKS.setdefault('sqlite', [])
sqlite_hooks.append(init_sqlite_connexion)

def init_cnx(driver, cnx):
    for hook in SQL_CONNECT_HOOKS.get(driver, ()):
        hook(cnx)
