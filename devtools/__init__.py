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
"""Test tools for cubicweb"""

__docformat__ = "restructuredtext en"

import os
import sys
import errno
import logging
import shutil
import pickle
import glob
import random
import subprocess
import warnings
import tempfile
import getpass
from hashlib import sha1 # pylint: disable=E0611
from datetime import timedelta
from os.path import (abspath, realpath, join, exists, split, isabs, isdir)
from functools import partial

from logilab.common.date import strptime
from logilab.common.decorators import cached, clear_cache

from cubicweb import ExecutionError, BadConnectionId
from cubicweb import schema, cwconfig
from cubicweb.server.serverconfig import ServerConfiguration
from cubicweb.etwist.twconfig import WebConfigurationBase

cwconfig.CubicWebConfiguration.cls_adjust_sys_path()

# db auto-population configuration #############################################

SYSTEM_ENTITIES = (schema.SCHEMA_TYPES
                   | schema.INTERNAL_TYPES
                   | schema.WORKFLOW_TYPES
                   | set(('CWGroup', 'CWUser',))
                   )
SYSTEM_RELATIONS = (schema.META_RTYPES
                    | schema.WORKFLOW_RTYPES
                    | schema.WORKFLOW_DEF_RTYPES
                    | schema.SYSTEM_RTYPES
                    | schema.SCHEMA_TYPES
                    | set(('primary_email', # deducted from other relations
                           ))
                    )

# content validation configuration #############################################

# validators are used to validate (XML, DTD, whatever) view's content
# validators availables are :
#  'dtd' : validates XML + declared DTD
#  'xml' : guarantees XML is well formed
#  None : do not try to validate anything

# {'vid': validator}
VIEW_VALIDATORS = {}


# cubicweb test configuration ##################################################

BASE_URL = 'http://testing.fr/cubicweb/'

DEFAULT_SOURCES = {'system': {'adapter' : 'native',
                              'db-encoding' : 'UTF-8', #'ISO-8859-1',
                              'db-user' : u'admin',
                              'db-password' : 'gingkow',
                              'db-name' : 'tmpdb',
                              'db-driver' : 'sqlite',
                              'db-host' : None,
                              },
                   'admin' : {'login': u'admin',
                              'password': u'gingkow',
                              },
                   }
DEFAULT_PSQL_SOURCES = DEFAULT_SOURCES.copy()
DEFAULT_PSQL_SOURCES['system'] = DEFAULT_SOURCES['system'].copy()
DEFAULT_PSQL_SOURCES['system']['db-driver'] = 'postgres'
DEFAULT_PSQL_SOURCES['system']['db-host'] = '/tmp'
DEFAULT_PSQL_SOURCES['system']['db-port'] = str(random.randrange(5432, 2**16))
DEFAULT_PSQL_SOURCES['system']['db-user'] = unicode(getpass.getuser())
DEFAULT_PSQL_SOURCES['system']['db-password'] = None

def turn_repo_off(repo):
    """ Idea: this is less costly than a full re-creation of the repo object.
    off:
    * session are closed,
    * cnxsets are closed
    * system source is shutdown
    """
    if not repo._needs_refresh:
        for sessionid in list(repo._sessions):
            warnings.warn('%s Open session found while turning repository off'
                          %sessionid, RuntimeWarning)
            try:
                repo.close(sessionid)
            except BadConnectionId: #this is strange ? thread issue ?
                print 'XXX unknown session', sessionid
        for cnxset in repo.cnxsets:
            cnxset.close(True)
        repo.system_source.shutdown()
        repo._needs_refresh = True
        repo._has_started = False


def turn_repo_on(repo):
    """Idea: this is less costly than a full re-creation of the repo object.
    on:
    * cnxsets are connected
    * cache are cleared
    """
    if repo._needs_refresh:
        for cnxset in repo.cnxsets:
            cnxset.reconnect()
        repo._type_source_cache = {}
        repo._extid_cache = {}
        repo.querier._rql_cache = {}
        repo.system_source.reset_caches()
        repo._needs_refresh = False


class TestServerConfiguration(ServerConfiguration):
    mode = 'test'
    read_instance_schema = False
    init_repository = True
    skip_db_create_and_restore = False
    default_sources = DEFAULT_SOURCES

    def __init__(self, appid='data', apphome=None, log_threshold=logging.CRITICAL+10):
        # must be set before calling parent __init__
        if apphome is None:
            if exists(appid):
                apphome = abspath(appid)
            else: # cube test
                apphome = abspath('..')
        self._apphome = apphome
        ServerConfiguration.__init__(self, appid)
        self.init_log(log_threshold, force=True)
        # need this, usually triggered by cubicweb-ctl
        self.load_cwctl_plugins()

    # By default anonymous login are allow but some test need to deny of to
    # change the default user. Set it to None to prevent anonymous login.
    anonymous_credential = ('anon', 'anon')

    def anonymous_user(self):
        if not self.anonymous_credential:
            return None, None
        return self.anonymous_credential

    def set_anonymous_allowed(self, allowed, anonuser='anon'):
        if allowed:
            self.anonymous_credential = (anonuser, anonuser)
        else:
            self.anonymous_credential = None

    @property
    def apphome(self):
        return self._apphome
    appdatahome = apphome

    def load_configuration(self):
        super(TestServerConfiguration, self).load_configuration()
        # no undo support in tests
        self.global_set_option('undo-enabled', 'n')

    def main_config_file(self):
        """return instance's control configuration file"""
        return join(self.apphome, '%s.conf' % self.name)

    def bootstrap_cubes(self):
        try:
            super(TestServerConfiguration, self).bootstrap_cubes()
        except IOError:
            # no cubes
            self.init_cubes( () )

    sourcefile = None
    def sources_file(self):
        """define in subclasses self.sourcefile if necessary"""
        if self.sourcefile:
            print 'Reading sources from', self.sourcefile
            sourcefile = self.sourcefile
            if not isabs(sourcefile):
                sourcefile = join(self.apphome, sourcefile)
        else:
            sourcefile = super(TestServerConfiguration, self).sources_file()
        return sourcefile

    def read_sources_file(self):
        """By default, we run tests with the sqlite DB backend.  One may use its
        own configuration by just creating a 'sources' file in the test
        directory from which tests are launched or by specifying an alternative
        sources file using self.sourcefile.
        """
        try:
            sources = super(TestServerConfiguration, self).read_sources_file()
        except ExecutionError:
            sources = {}
        if not sources:
            sources = self.default_sources
        if 'admin' not in sources:
            sources['admin'] = self.default_sources['admin']
        return sources

    # web config methods needed here for cases when we use this config as a web
    # config

    def default_base_url(self):
        return BASE_URL


class BaseApptestConfiguration(TestServerConfiguration, WebConfigurationBase):
    name = 'all-in-one' # so it search for all-in-one.conf, not repository.conf
    options = cwconfig.merge_options(TestServerConfiguration.options
                                     + WebConfigurationBase.options)
    cubicweb_appobject_path = TestServerConfiguration.cubicweb_appobject_path | WebConfigurationBase.cubicweb_appobject_path
    cube_appobject_path = TestServerConfiguration.cube_appobject_path | WebConfigurationBase.cube_appobject_path

    def available_languages(self, *args):
        return self.cw_languages()

    def pyro_enabled(self):
        # but export PYRO_MULTITHREAD=0 or you get problems with sqlite and
        # threads
        return True

# XXX merge with BaseApptestConfiguration ?
class ApptestConfiguration(BaseApptestConfiguration):
    # `skip_db_create_and_restore` controls wether or not the test database
    # should be created / backuped / restored. If set to True, those
    # steps are completely skipped, the database is used as is and is
    # considered initialized
    skip_db_create_and_restore = False

    def __init__(self, appid, apphome=None,
                 log_threshold=logging.CRITICAL, sourcefile=None):
        BaseApptestConfiguration.__init__(self, appid, apphome,
                                          log_threshold=log_threshold)
        self.init_repository = sourcefile is None
        self.sourcefile = sourcefile


class PostgresApptestConfiguration(ApptestConfiguration):
    default_sources = DEFAULT_PSQL_SOURCES


class RealDatabaseConfiguration(ApptestConfiguration):
    """configuration class for tests to run on a real database.

    The intialization is done by specifying a source file path.

    Important note: init_test_database / reset_test_database steps are
    skipped. It's thus up to the test developer to implement setUp/tearDown
    accordingly.

    Example usage::

      class MyTests(CubicWebTC):
          _config = RealDatabaseConfiguration('myapp',
                                              sourcefile='/path/to/sources')

          def test_something(self):
              with self.admin_access.web_request() as req:
                  rset = req.execute('Any X WHERE X is CWUser')
                  self.view('foaf', rset, req=req)

    """
    skip_db_create_and_restore = True
    read_instance_schema = True # read schema from database

# test database handling #######################################################

DEFAULT_EMPTY_DB_ID = '__default_empty_db__'

class TestDataBaseHandler(object):
    DRIVER = None

    db_cache = {}
    explored_glob = set()

    def __init__(self, config, init_config=None):
        self.config = config
        self.init_config = init_config
        self._repo = None
        # pure consistency check
        assert self.system_source['db-driver'] == self.DRIVER

    def _ensure_test_backup_db_dir(self):
        """Return path of directory for database backup.

        The function create it if necessary"""
        backupdir = join(self.config.apphome, 'database')
        try:
            os.makedirs(backupdir)
        except:
            if not isdir(backupdir):
                raise
        return backupdir

    def config_path(self, db_id):
        """Path for config backup of a given database id"""
        return self.absolute_backup_file(db_id, 'config')

    def absolute_backup_file(self, db_id, suffix):
        """Path for config backup of a given database id"""
        # in case db name is an absolute path, we don't want to replace anything
        # in parent directories
        directory, basename = split(self.dbname)
        dbname = basename.replace('-', '_')
        assert '.' not in db_id
        filename = join(directory, '%s-%s.%s' % (dbname, db_id, suffix))
        return join(self._ensure_test_backup_db_dir(), filename)

    def db_cache_key(self, db_id, dbname=None):
        """Build a database cache key for a db_id with the current config

        This key is meant to be used in the cls.db_cache mapping"""
        if dbname is None:
            dbname = self.dbname
        dbname = os.path.basename(dbname)
        dbname = dbname.replace('-', '_')
        return (self.config.apphome, dbname, db_id)

    def backup_database(self, db_id):
        """Store the content of the current database as <db_id>

        The config used are also stored."""
        backup_data = self._backup_database(db_id)
        config_path = self.config_path(db_id)
        # XXX we dump a dict of the config
        # This is an experimental to help config dependant setup (like BFSS) to
        # be propertly restored
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(config_path), delete=False) as conf_file:
            conf_file.write(pickle.dumps(dict(self.config)))
        os.rename(conf_file.name, config_path)
        self.db_cache[self.db_cache_key(db_id)] = (backup_data, config_path)

    def _backup_database(self, db_id):
        """Actual backup the current database.

        return a value to be stored in db_cache to allow restoration"""
        raise NotImplementedError()

    def restore_database(self, db_id):
        """Restore a database.

        takes as argument value stored in db_cache by self._backup_database"""
        # XXX set a clearer error message ???
        backup_coordinates, config_path = self.db_cache[self.db_cache_key(db_id)]
        # reload the config used to create the database.
        config = pickle.loads(open(config_path, 'rb').read())
        # shutdown repo before changing database content
        if self._repo is not None:
            self._repo.turn_repo_off()
        self._restore_database(backup_coordinates, config)

    def _restore_database(self, backup_coordinates, config):
        """Actual restore of the current database.

        Use the value stored in db_cache as input """
        raise NotImplementedError()

    def get_repo(self, startup=False):
        """ return Repository object on the current database.

        (turn the current repo object "on" if there is one or recreate one)
        if startup is True, server startup server hooks will be called if needed
        """
        if self._repo is None:
            self._repo = self._new_repo(self.config)
        # config has now been bootstrapped, call init_config if specified
        if self.init_config is not None:
            self.init_config(self.config)
        repo = self._repo
        repo.turn_repo_on()
        if startup and not repo._has_started:
            repo.hm.call_hooks('server_startup', repo=repo)
            repo._has_started = True
        return repo

    def _new_repo(self, config):
        """Factory method to create a new Repository Instance"""
        from cubicweb.dbapi import in_memory_repo
        config._cubes = None
        repo = in_memory_repo(config)
        config.repository = lambda x=None: repo
        # extending Repository class
        repo._has_started = False
        repo._needs_refresh = False
        repo.turn_repo_on = partial(turn_repo_on, repo)
        repo.turn_repo_off = partial(turn_repo_off, repo)
        return repo

    def get_cnx(self):
        """return Connection object on the current repository"""
        from cubicweb.repoapi import connect
        repo = self.get_repo()
        sources = self.config.read_sources_file()
        login  = unicode(sources['admin']['login'])
        password = sources['admin']['password'] or 'xxx'
        cnx = connect(repo, login, password=password)
        return cnx

    def get_repo_and_cnx(self, db_id=DEFAULT_EMPTY_DB_ID):
        """Reset database with the current db_id and return (repo, cnx)

        A database *MUST* have been build with the current <db_id> prior to
        call this method. See the ``build_db_cache`` method. The returned
        repository have it's startup hooks called and the connection is
        establised as admin."""

        self.restore_database(db_id)
        repo = self.get_repo(startup=True)
        cnx  = self.get_cnx()
        return repo, cnx

    @property
    def system_source(self):
        return self.config.system_source_config

    @property
    def dbname(self):
        return self.system_source['db-name']

    def init_test_database(self):
        """actual initialisation of the database"""
        raise ValueError('no initialization function for driver %r' % self.DRIVER)

    def has_cache(self, db_id):
        """Check if a given database id exist in cb cache for the current config"""
        cache_glob = self.absolute_backup_file('*', '*')
        if cache_glob not in self.explored_glob:
            self.discover_cached_db()
        return self.db_cache_key(db_id) in self.db_cache

    def discover_cached_db(self):
        """Search available db_if for the current config"""
        cache_glob = self.absolute_backup_file('*', '*')
        directory = os.path.dirname(cache_glob)
        entries={}
        candidates = glob.glob(cache_glob)
        for filepath in candidates:
            data = os.path.basename(filepath)
            # database backup are in the forms are <dbname>-<db_id>.<backtype>
            dbname, data = data.split('-', 1)
            db_id, filetype = data.split('.', 1)
            entries.setdefault((dbname, db_id), {})[filetype] = filepath
        for (dbname, db_id), entry in entries.iteritems():
            # apply necessary transformation from the driver
            value = self.process_cache_entry(directory, dbname, db_id, entry)
            assert 'config' in entry
            if value is not None: # None value means "not handled by this driver
                                  # XXX Ignored value are shadowed to other Handler if cache are common.
                key = self.db_cache_key(db_id, dbname=dbname)
                self.db_cache[key] = value, entry['config']
        self.explored_glob.add(cache_glob)

    def process_cache_entry(self, directory, dbname, db_id, entry):
        """Transforms potential cache entry to proper backup coordinate

        entry argument is a "filetype" -> "filepath" mapping
        Return None if an entry should be ignored."""
        return None

    def build_db_cache(self, test_db_id=DEFAULT_EMPTY_DB_ID, pre_setup_func=None):
        """Build Database cache for ``test_db_id`` if a cache doesn't exist

        if ``test_db_id is DEFAULT_EMPTY_DB_ID`` self.init_test_database is
        called. otherwise, DEFAULT_EMPTY_DB_ID is build/restored and
        ``pre_setup_func`` to setup the database.

        This function backup any database it build"""
        if self.has_cache(test_db_id):
            return #test_db_id, 'already in cache'
        if test_db_id is DEFAULT_EMPTY_DB_ID:
            self.init_test_database()
        else:
            print 'Building %s for database %s' % (test_db_id, self.dbname)
            self.build_db_cache(DEFAULT_EMPTY_DB_ID)
            self.restore_database(DEFAULT_EMPTY_DB_ID)
            repo = self.get_repo(startup=True)
            cnx = self.get_cnx()
            with cnx:
                pre_setup_func(cnx._cnx, self.config)
                cnx.commit()
        self.backup_database(test_db_id)


class NoCreateDropDatabaseHandler(TestDataBaseHandler):
    """This handler is used if config.skip_db_create_and_restore is True

    This is typically the case with RealDBConfig. In that case,
    we explicitely want to skip init / backup / restore phases.

    This handler redefines the three corresponding methods and delegates
    to original handler for any other method / attribute
    """

    def __init__(self, base_handler):
        self.base_handler = base_handler

    # override init / backup / restore methods
    def init_test_database(self):
        pass

    def backup_database(self, db_id):
        pass

    def restore_database(self, db_id):
        pass

    # delegate to original handler in all other cases
    def __getattr__(self, attrname):
        return getattr(self.base_handler, attrname)


### postgres test database handling ############################################

class PostgresTestDataBaseHandler(TestDataBaseHandler):
    DRIVER = 'postgres'

    # Separate db_cache for PG databases, to avoid collisions with sqlite dbs
    db_cache = {}
    explored_glob = set()

    __CTL = set()

    @classmethod
    def killall(cls):
        for datadir in cls.__CTL:
            subprocess.call(['pg_ctl', 'stop', '-D', datadir, '-m', 'fast'])

    def __init__(self, *args, **kwargs):
        super(PostgresTestDataBaseHandler, self).__init__(*args, **kwargs)
        datadir = realpath(join(self.config.apphome, 'pgdb'))
        if datadir in self.__CTL:
            return
        if not exists(datadir):
            try:
                subprocess.check_call(['initdb', '-D', datadir, '-E', 'utf-8', '--locale=C'])

            except OSError, err:
                if err.errno == errno.ENOENT:
                    raise OSError('"initdb" could not be found. '
                                  'You should add the postgresql bin folder to your PATH '
                                  '(/usr/lib/postgresql/9.1/bin for example).')
                raise
        port = self.system_source['db-port']
        directory = self.system_source['db-host']
        env = os.environ.copy()
        env['PGPORT'] = str(port)
        env['PGHOST'] = str(directory)
        options = '-h "" -k %s -p %s' % (directory, port)
        options += ' -c fsync=off -c full_page_writes=off'
        options += ' -c synchronous_commit=off'
        try:
            subprocess.check_call(['pg_ctl', 'start', '-w', '-D', datadir,
                                   '-o', options],
                                  env=env)
        except OSError, err:
            if err.errno == errno.ENOENT:
                raise OSError('"pg_ctl" could not be found. '
                              'You should add the postgresql bin folder to your PATH '
                              '(/usr/lib/postgresql/9.1/bin for example).')
            raise
        self.__CTL.add(datadir)

    @property
    @cached
    def helper(self):
        from logilab.database import get_db_helper
        return get_db_helper('postgres')

    @property
    def dbcnx(self):
        try:
            return self._cnx
        except AttributeError:
            from cubicweb.server.serverctl import _db_sys_cnx
            try:
                self._cnx = _db_sys_cnx(
                    self.system_source, 'CREATE DATABASE and / or USER',
                    interactive=False)
                return self._cnx
            except Exception:
                self._cnx = None
                raise

    @property
    @cached
    def cursor(self):
        return self.dbcnx.cursor()

    def process_cache_entry(self, directory, dbname, db_id, entry):
        backup_name = self._backup_name(db_id)
        if backup_name in self.helper.list_databases(self.cursor):
            return backup_name
        return None

    def init_test_database(self):
        """initialize a fresh postgresql database used for testing purpose"""
        from cubicweb.server import init_repository
        from cubicweb.server.serverctl import system_source_cnx, createdb
        # connect on the dbms system base to create our base
        try:
            self._drop(self.dbname)
            createdb(self.helper, self.system_source, self.dbcnx, self.cursor)
            self.dbcnx.commit()
            cnx = system_source_cnx(self.system_source, special_privs='LANGUAGE C',
                                    interactive=False)
            templcursor = cnx.cursor()
            try:
                # XXX factorize with db-create code
                self.helper.init_fti_extensions(templcursor)
                # install plpythonu/plpgsql language if not installed by the cube
                langs = sys.platform == 'win32' and ('plpgsql',) or ('plpythonu', 'plpgsql')
                for extlang in langs:
                    self.helper.create_language(templcursor, extlang)
                cnx.commit()
            finally:
                templcursor.close()
                cnx.close()
            init_repository(self.config, interactive=False,
                            init_config=self.init_config)
        except BaseException:
            if self.dbcnx is not None:
                self.dbcnx.rollback()
            sys.stderr.write('building %s failed\n' % self.dbname)
            #self._drop(self.dbname)
            raise

    def helper_clear_cache(self):
        if self.dbcnx is not None:
            self.dbcnx.commit()
            self.dbcnx.close()
            del self._cnx
            clear_cache(self, 'cursor')
        clear_cache(self, 'helper')

    def __del__(self):
        self.helper_clear_cache()

    @property
    def _config_id(self):
        return sha1(self.config.apphome).hexdigest()[:10]

    def _backup_name(self, db_id): # merge me with parent
        backup_name = '_'.join(('cache', self._config_id, self.dbname, db_id))
        return backup_name.lower()

    def _drop(self, db_name):
        if db_name in self.helper.list_databases(self.cursor):
            self.cursor.execute('DROP DATABASE %s' % db_name)
            self.dbcnx.commit()

    def _backup_database(self, db_id):
        """Actual backup the current database.

        return a value to be stored in db_cache to allow restoration
        """
        from cubicweb.server.serverctl import createdb
        orig_name = self.system_source['db-name']
        try:
            backup_name = self._backup_name(db_id)
            self._drop(backup_name)
            self.system_source['db-name'] = backup_name
            if self._repo:
                self._repo.turn_repo_off()
            try:
                createdb(self.helper, self.system_source, self.dbcnx, self.cursor, template=orig_name)
                self.dbcnx.commit()
            finally:
                if self._repo:
                    self._repo.turn_repo_on()
            return backup_name
        finally:
            self.system_source['db-name'] = orig_name

    def _restore_database(self, backup_coordinates, config):
        from cubicweb.server.serverctl import createdb
        """Actual restore of the current database.

        Use the value tostored in db_cache as input """
        self._drop(self.dbname)
        createdb(self.helper, self.system_source, self.dbcnx, self.cursor,
                 template=backup_coordinates)
        self.dbcnx.commit()



### sqlserver2005 test database handling #######################################

class SQLServerTestDataBaseHandler(TestDataBaseHandler):
    DRIVER = 'sqlserver'

    # XXX complete me

    def init_test_database(self):
        """initialize a fresh sqlserver databse used for testing purpose"""
        if self.config.init_repository:
            from cubicweb.server import init_repository
            init_repository(self.config, interactive=False, drop=True,
                            init_config=self.init_config)

### sqlite test database handling ##############################################

class SQLiteTestDataBaseHandler(TestDataBaseHandler):
    DRIVER = 'sqlite'

    __TMPDB = set()

    @classmethod
    def _cleanup_all_tmpdb(cls):
        for dbpath in cls.__TMPDB:
            cls._cleanup_database(dbpath)



    def __init__(self, *args, **kwargs):
        super(SQLiteTestDataBaseHandler, self).__init__(*args, **kwargs)
        # use a dedicated base for each process.
        if 'global-db-name' not in self.system_source:
            self.system_source['global-db-name'] = self.system_source['db-name']
            process_db = self.system_source['db-name'] + str(os.getpid())
            self.system_source['db-name'] = process_db
        process_db = self.absolute_dbfile() # update db-name to absolute path
        self.__TMPDB.add(process_db)

    @staticmethod
    def _cleanup_database(dbfile):
        try:
            os.remove(dbfile)
            os.remove('%s-journal' % dbfile)
        except OSError:
            pass

    @property
    def dbname(self):
        return self.system_source['global-db-name']

    def absolute_dbfile(self):
        """absolute path of current database file"""
        dbfile = join(self._ensure_test_backup_db_dir(),
                      self.system_source['db-name'])
        self.system_source['db-name'] = dbfile
        return dbfile

    def process_cache_entry(self, directory, dbname, db_id, entry):
        return entry.get('sqlite')

    def _backup_database(self, db_id=DEFAULT_EMPTY_DB_ID):
        # XXX remove database file if it exists ???
        dbfile = self.absolute_dbfile()
        backup_file = self.absolute_backup_file(db_id, 'sqlite')
        shutil.copy(dbfile, backup_file)
        # Usefull to debug WHO write a database
        # backup_stack = self.absolute_backup_file(db_id, '.stack')
        #with open(backup_stack, 'w') as backup_stack_file:
        #    import traceback
        #    traceback.print_stack(file=backup_stack_file)
        return backup_file

    def _new_repo(self, config):
        repo = super(SQLiteTestDataBaseHandler, self)._new_repo(config)
        install_sqlite_patch(repo.querier)
        return repo

    def _restore_database(self, backup_coordinates, _config):
        # remove database file if it exists ?
        dbfile = self.absolute_dbfile()
        self._cleanup_database(dbfile)
        shutil.copy(backup_coordinates, dbfile)
        self.get_repo()

    def init_test_database(self):
        """initialize a fresh sqlite databse used for testing purpose"""
        # initialize the database
        from cubicweb.server import init_repository
        self._cleanup_database(self.absolute_dbfile())
        init_repository(self.config, interactive=False,
                        init_config=self.init_config)

import atexit
atexit.register(SQLiteTestDataBaseHandler._cleanup_all_tmpdb)
atexit.register(PostgresTestDataBaseHandler.killall)


def install_sqlite_patch(querier):
    """This patch hotfixes the following sqlite bug :
       - http://www.sqlite.org/cvstrac/tktview?tn=1327,33
       (some dates are returned as strings rather thant date objects)
    """
    if hasattr(querier.__class__, '_devtools_sqlite_patched'):
        return # already monkey patched
    def wrap_execute(base_execute):
        def new_execute(*args, **kwargs):
            rset = base_execute(*args, **kwargs)
            if rset.description:
                found_date = False
                for row, rowdesc in zip(rset, rset.description):
                    for cellindex, (value, vtype) in enumerate(zip(row, rowdesc)):
                        if vtype in ('Date', 'Datetime') and type(value) is unicode:
                            found_date = True
                            value = value.rsplit('.', 1)[0]
                            try:
                                row[cellindex] = strptime(value, '%Y-%m-%d %H:%M:%S')
                            except Exception:
                                row[cellindex] = strptime(value, '%Y-%m-%d')
                        if vtype == 'Time' and type(value) is unicode:
                            found_date = True
                            try:
                                row[cellindex] = strptime(value, '%H:%M:%S')
                            except Exception:
                                # DateTime used as Time?
                                row[cellindex] = strptime(value, '%Y-%m-%d %H:%M:%S')
                        if vtype == 'Interval' and type(value) is int:
                            found_date = True
                            row[cellindex] = timedelta(0, value, 0) # XXX value is in number of seconds?
                    if not found_date:
                        break
            return rset
        return new_execute
    querier.__class__.execute = wrap_execute(querier.__class__.execute)
    querier.__class__._devtools_sqlite_patched = True



HANDLERS = {}

def register_handler(handlerkls, overwrite=False):
    assert handlerkls is not None
    if overwrite or handlerkls.DRIVER not in HANDLERS:
        HANDLERS[handlerkls.DRIVER] = handlerkls
    else:
        msg = "%s: Handler already exists use overwrite if it's intended\n"\
              "(existing handler class is %r)"
        raise ValueError(msg % (handlerkls.DRIVER, HANDLERS[handlerkls.DRIVER]))

register_handler(PostgresTestDataBaseHandler)
register_handler(SQLiteTestDataBaseHandler)
register_handler(SQLServerTestDataBaseHandler)


class HCache(object):
    """Handler cache object: store database handler for a given configuration.

    We only keep one repo in cache to prevent too much objects to stay alive
    (database handler holds a reference to a repository). As at the moment a new
    handler is created for each TestCase class and all test methods are executed
    sequentialy whithin this class, there should not have more cache miss that
    if we had a wider cache as once a Handler stop being used it won't be used
    again.
    """

    def __init__(self):
        self.config = None
        self.handler = None

    def get(self, config):
        if config is self.config:
            return self.handler
        else:
            return None

    def set(self, config, handler):
        self.config = config
        self.handler = handler

HCACHE = HCache()


# XXX a class method on Test ?

_CONFIG = None
def get_test_db_handler(config, init_config=None):
    global _CONFIG
    if _CONFIG is not None and config is not _CONFIG:
        from logilab.common.modutils import cleanup_sys_modules
        # cleanup all dynamically loaded modules and everything in the instance
        # directory
        apphome = _CONFIG.apphome
        if apphome: # may be unset in tests
            cleanup_sys_modules([apphome])
        # also cleanup sys.path
        if apphome in sys.path:
            sys.path.remove(apphome)
    _CONFIG = config
    config.adjust_sys_path()
    handler = HCACHE.get(config)
    if handler is not None:
        return handler
    driver = config.system_source_config['db-driver']
    key = (driver, config)
    handlerkls = HANDLERS.get(driver, None)
    if handlerkls is not None:
        handler = handlerkls(config, init_config)
        if config.skip_db_create_and_restore:
            handler = NoCreateDropDatabaseHandler(handler)
        HCACHE.set(config, handler)
        return handler
    else:
        raise ValueError('no initialization function for driver %r' % driver)

### compatibility layer ##############################################
from logilab.common.deprecation import deprecated

@deprecated("please use the new DatabaseHandler mecanism")
def init_test_database(config=None, configdir='data', apphome=None):
    """init a test database for a specific driver"""
    if config is None:
        config = TestServerConfiguration(apphome=apphome)
    handler = get_test_db_handler(config)
    handler.build_db_cache()
    return handler.get_repo_and_cnx()


