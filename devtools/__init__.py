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
"""Test tools for cubicweb"""

__docformat__ = "restructuredtext en"

import os
import sys
import logging
from datetime import timedelta
from os.path import (abspath, join, exists, basename, dirname, normpath, split,
                     isfile, isabs, splitext)

from logilab.common.date import strptime
from cubicweb import CW_SOFTWARE_ROOT, ConfigurationError, schema, cwconfig
from cubicweb.server.serverconfig import ServerConfiguration
from cubicweb.etwist.twconfig import TwistedConfiguration

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


class TestServerConfiguration(ServerConfiguration):
    mode = 'test'
    set_language = False
    read_instance_schema = False
    init_repository = True
    db_require_setup = True
    options = cwconfig.merge_options(
        ServerConfiguration.options +
        tuple((opt, optdict) for opt, optdict in TwistedConfiguration.options
              if opt in ('anonymous-user', 'anonymous-password')))

    def __init__(self, appid, apphome=None, log_threshold=logging.CRITICAL+10):
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

    anonymous_user = TwistedConfiguration.anonymous_user.im_func

    @property
    def apphome(self):
        return self._apphome
    appdatahome = apphome

    def load_configuration(self):
        super(TestServerConfiguration, self).load_configuration()
        self.global_set_option('anonymous-user', 'anon')
        self.global_set_option('anonymous-password', 'anon')
        # no undo support in tests
        self.global_set_option('undo-support', '')

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

    def sources(self):
        """By default, we run tests with the sqlite DB backend.  One may use its
        own configuration by just creating a 'sources' file in the test
        directory from wich tests are launched or by specifying an alternative
        sources file using self.sourcefile.
        """
        sources = super(TestServerConfiguration, self).sources()
        if not sources:
            sources = DEFAULT_SOURCES
        if 'admin' not in sources:
            sources['admin'] = DEFAULT_SOURCES['admin']
        return sources

    # web config methods needed here for cases when we use this config as a web
    # config

    def instance_md5_version(self):
        return ''

    def default_base_url(self):
        return BASE_URL


class BaseApptestConfiguration(TestServerConfiguration, TwistedConfiguration):
    repo_method = 'inmemory'
    name = 'all-in-one' # so it search for all-in-one.conf, not repository.conf
    options = cwconfig.merge_options(TestServerConfiguration.options
                                     + TwistedConfiguration.options)
    cubicweb_appobject_path = TestServerConfiguration.cubicweb_appobject_path | TwistedConfiguration.cubicweb_appobject_path
    cube_appobject_path = TestServerConfiguration.cube_appobject_path | TwistedConfiguration.cube_appobject_path

    def available_languages(self, *args):
        return self.cw_languages()

    def pyro_enabled(self):
        # but export PYRO_MULTITHREAD=0 or you get problems with sqlite and
        # threads
        return True

# XXX merge with BaseApptestConfiguration ?
class ApptestConfiguration(BaseApptestConfiguration):

    def __init__(self, appid, apphome=None,
                 log_threshold=logging.CRITICAL, sourcefile=None):
        BaseApptestConfiguration.__init__(self, appid, apphome,
                                          log_threshold=log_threshold)
        self.init_repository = sourcefile is None
        self.sourcefile = sourcefile


class RealDatabaseConfiguration(ApptestConfiguration):
    """configuration class for tests to run on a real database.

    The intialization is done by specifying a source file path.

    Important note: init_test_database / reset_test_database steps are
    skipped. It's thus up to the test developer to implement setUp/tearDown
    accordingly.

    Example usage::

      class MyTests(CubicWebTC):
          _config = RealDatabseConfiguration('myapp',
                                             sourcefile='/path/to/sources')
          def test_something(self):
              rset = self.execute('Any X WHERE X is CWUser')
              self.view('foaf', rset)

    """
    db_require_setup = False    # skip init_db / reset_db steps
    read_instance_schema = True # read schema from database


# test database handling #######################################################

def init_test_database(config=None, appid='data', apphome=None):
    """init a test database for a specific driver"""
    from cubicweb.dbapi import in_memory_cnx
    config = config or TestServerConfiguration(appid, apphome=apphome)
    sources = config.sources()
    driver = sources['system']['db-driver']
    if config.db_require_setup:
        if driver == 'sqlite':
            init_test_database_sqlite(config)
        elif driver == 'postgres':
            init_test_database_postgres(config)
        else:
            raise ValueError('no initialization function for driver %r' % driver)
    config._cubes = None # avoid assertion error
    repo, cnx = in_memory_cnx(config, unicode(sources['admin']['login']),
                              password=sources['admin']['password'] or 'xxx')
    if driver == 'sqlite':
        install_sqlite_patch(repo.querier)
    return repo, cnx

def reset_test_database(config):
    """init a test database for a specific driver"""
    if not config.db_require_setup:
        return
    driver = config.sources()['system']['db-driver']
    if driver == 'sqlite':
        reset_test_database_sqlite(config)
    elif driver == 'postgres':
        init_test_database_postgres(config)
    else:
        raise ValueError('no reset function for driver %r' % driver)


### postgres test database handling ############################################

def init_test_database_postgres(config):
    """initialize a fresh postgresql databse used for testing purpose"""
    from logilab.database import get_db_helper
    from cubicweb.server import init_repository
    from cubicweb.server.serverctl import (createdb, system_source_cnx,
                                           _db_sys_cnx)
    source = config.sources()['system']
    dbname = source['db-name']
    templdbname = dbname + '_template'
    helper = get_db_helper('postgres')
    # connect on the dbms system base to create our base
    dbcnx = _db_sys_cnx(source, 'CREATE DATABASE and / or USER', verbose=0)
    cursor = dbcnx.cursor()
    try:
        if dbname in helper.list_databases(cursor):
            cursor.execute('DROP DATABASE %s' % dbname)
        if not templdbname in helper.list_databases(cursor):
            source['db-name'] = templdbname
            createdb(helper, source, dbcnx, cursor)
            dbcnx.commit()
            cnx = system_source_cnx(source, special_privs='LANGUAGE C', verbose=0)
            templcursor = cnx.cursor()
            # XXX factorize with db-create code
            helper.init_fti_extensions(templcursor)
            # install plpythonu/plpgsql language if not installed by the cube
            langs = sys.platform == 'win32' and ('plpgsql',) or ('plpythonu', 'plpgsql')
            for extlang in langs:
                helper.create_language(templcursor, extlang)
            cnx.commit()
            templcursor.close()
            cnx.close()
            init_repository(config, interactive=False)
            source['db-name'] = dbname
    except:
        dbcnx.rollback()
        # XXX drop template
        raise
    createdb(helper, source, dbcnx, cursor, template=templdbname)
    dbcnx.commit()
    dbcnx.close()

### sqlserver2005 test database handling #######################################

def init_test_database_sqlserver2005(config):
    """initialize a fresh sqlserver databse used for testing purpose"""
    if config.init_repository:
        from cubicweb.server import init_repository
        init_repository(config, interactive=False, drop=True)

### sqlite test database handling ##############################################

def cleanup_sqlite(dbfile, removetemplate=False):
    try:
        os.remove(dbfile)
        os.remove('%s-journal' % dbfile)
    except OSError:
        pass
    if removetemplate:
        try:
            os.remove('%s-template' % dbfile)
        except OSError:
            pass

def reset_test_database_sqlite(config):
    import shutil
    dbfile = config.sources()['system']['db-name']
    cleanup_sqlite(dbfile)
    template = '%s-template' % dbfile
    if exists(template):
        shutil.copy(template, dbfile)
        return True
    return False

def init_test_database_sqlite(config):
    """initialize a fresh sqlite databse used for testing purpose"""
    # remove database file if it exists
    dbfile = join(config.apphome, config.sources()['system']['db-name'])
    config.sources()['system']['db-name'] = dbfile
    if not reset_test_database_sqlite(config):
        # initialize the database
        import shutil
        from cubicweb.server import init_repository
        init_repository(config, interactive=False)
        shutil.copy(dbfile, '%s-template' % dbfile)

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
                            except:
                                row[cellindex] = strptime(value, '%Y-%m-%d')
                        if vtype == 'Time' and type(value) is unicode:
                            found_date = True
                            try:
                                row[cellindex] = strptime(value, '%H:%M:%S')
                            except:
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
