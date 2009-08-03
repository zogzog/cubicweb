"""Test tools for cubicweb

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import os
import logging
from datetime import timedelta
from os.path import (abspath, join, exists, basename, dirname, normpath, split,
                     isfile, isabs)

from cubicweb import CW_SOFTWARE_ROOT, ConfigurationError
from cubicweb.utils import strptime
from cubicweb.toolsutils import read_config
from cubicweb.cwconfig import CubicWebConfiguration, merge_options
from cubicweb.server.serverconfig import ServerConfiguration
from cubicweb.etwist.twconfig import TwistedConfiguration

# validators are used to validate (XML, DTD, whatever) view's content
# validators availables are :
#  'dtd' : validates XML + declared DTD
#  'xml' : guarantees XML is well formed
#  None : do not try to validate anything
VIEW_VALIDATORS = {}
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
    bootstrap_schema = False
    init_repository = True
    options = merge_options(ServerConfiguration.options + (
        ('anonymous-user',
         {'type' : 'string',
          'default': None,
          'help': 'login of the CubicWeb user account to use for anonymous user (if you want to allow anonymous)',
          'group': 'main', 'inputlevel': 1,
          }),
        ('anonymous-password',
         {'type' : 'string',
          'default': None,
          'help': 'password of the CubicWeb user account matching login',
          'group': 'main', 'inputlevel': 1,
          }),
        ))

    if not os.environ.get('APYCOT_ROOT'):
        REGISTRY_DIR = normpath(join(CW_SOFTWARE_ROOT, '../cubes'))

    def __init__(self, appid, log_threshold=logging.CRITICAL+10):
        ServerConfiguration.__init__(self, appid)
        self.global_set_option('log-file', None)
        self.init_log(log_threshold, force=True)
        # need this, usually triggered by cubicweb-ctl
        self.load_cwctl_plugins()

    anonymous_user = TwistedConfiguration.anonymous_user.im_func

    @property
    def apphome(self):
        if exists(self.appid):
            return abspath(self.appid)
        # cube test
        return abspath('..')
    appdatahome = apphome

    def main_config_file(self):
        """return instance's control configuration file"""
        return join(self.apphome, '%s.conf' % self.name)

    def instance_md5_version(self):
        return ''

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
        return sources

    def load_defaults(self):
        super(TestServerConfiguration, self).load_defaults()
        # note: don't call global set option here, OptionManager may not yet be initialized
        # add anonymous user
        self.set_option('anonymous-user', 'anon')
        self.set_option('anonymous-password', 'anon')
        # uncomment the line below if you want rql queries to be logged
        #self.set_option('query-log-file', '/tmp/test_rql_log.' + `os.getpid()`)
        self.set_option('sender-name', 'cubicweb-test')
        self.set_option('sender-addr', 'cubicweb-test@logilab.fr')
        try:
            send_to =  '%s@logilab.fr' % os.getlogin()
        except OSError:
            send_to =  '%s@logilab.fr' % (os.environ.get('USER')
                                          or os.environ.get('USERNAME')
                                          or os.environ.get('LOGNAME'))
        self.set_option('sender-addr', send_to)
        self.set_option('default-dest-addrs', send_to)
        self.set_option('base-url', BASE_URL)


class BaseApptestConfiguration(TestServerConfiguration, TwistedConfiguration):
    repo_method = 'inmemory'
    options = merge_options(TestServerConfiguration.options + TwistedConfiguration.options)
    cubicweb_appobject_path = TestServerConfiguration.cubicweb_appobject_path | TwistedConfiguration.cubicweb_appobject_path
    cube_appobject_path = TestServerConfiguration.cube_appobject_path | TwistedConfiguration.cube_appobject_path

    def available_languages(self, *args):
        return ('en', 'fr', 'de')

    def ext_resources_file(self):
        """return instance's external resources file"""
        return join(self.apphome, 'data', 'external_resources')

    def pyro_enabled(self):
        # but export PYRO_MULTITHREAD=0 or you get problems with sqlite and threads
        return True


class ApptestConfiguration(BaseApptestConfiguration):

    def __init__(self, appid, log_threshold=logging.CRITICAL, sourcefile=None):
        BaseApptestConfiguration.__init__(self, appid, log_threshold=log_threshold)
        self.init_repository = sourcefile is None
        self.sourcefile = sourcefile
        import re
        self.global_set_option('embed-allowed', re.compile('.*'))


class RealDatabaseConfiguration(ApptestConfiguration):
    init_repository = False
    sourcesdef =  {'system': {'adapter' : 'native',
                              'db-encoding' : 'UTF-8', #'ISO-8859-1',
                              'db-user' : u'admin',
                              'db-password' : 'gingkow',
                              'db-name' : 'seotest',
                              'db-driver' : 'postgres',
                              'db-host' : None,
                              },
                   'admin' : {'login': u'admin',
                              'password': u'gingkow',
                              },
                   }

    def __init__(self, appid, log_threshold=logging.CRITICAL, sourcefile=None):
        ApptestConfiguration.__init__(self, appid)
        self.init_repository = False


    def sources(self):
        """
        By default, we run tests with the sqlite DB backend.
        One may use its own configuration by just creating a
        'sources' file in the test directory from wich tests are
        launched.
        """
        self._sources = self.sourcesdef
        return self._sources


def buildconfig(dbuser, dbpassword, dbname, adminuser, adminpassword, dbhost=None):
    """convenience function that builds a real-db configuration class"""
    sourcesdef =  {'system': {'adapter' : 'native',
                              'db-encoding' : 'UTF-8', #'ISO-8859-1',
                              'db-user' : dbuser,
                              'db-password' : dbpassword,
                              'db-name' : dbname,
                              'db-driver' : 'postgres',
                              'db-host' : dbhost,
                              },
                   'admin' : {'login': adminuser,
                              'password': adminpassword,
                              },
                   }
    return type('MyRealDBConfig', (RealDatabaseConfiguration,),
                {'sourcesdef': sourcesdef})

def loadconfig(filename):
    """convenience function that builds a real-db configuration class
    from a file
    """
    return type('MyRealDBConfig', (RealDatabaseConfiguration,),
                {'sourcesdef': read_config(filename)})


class LivetestConfiguration(BaseApptestConfiguration):
    init_repository = False

    def __init__(self, cube=None, sourcefile=None, pyro_name=None,
                 log_threshold=logging.CRITICAL):
        TestServerConfiguration.__init__(self, cube, log_threshold=log_threshold)
        self.appid = pyro_name or cube
        # don't change this, else some symlink problems may arise in some
        # environment (e.g. mine (syt) ;o)
        # XXX I'm afraid this test will prevent to run test from a production
        # environment
        self._sources = None
        # instance cube test
        if cube is not None:
            self.apphome = self.cube_dir(cube)
        elif 'web' in os.getcwd().split(os.sep):
            # web test
            self.apphome = join(normpath(join(dirname(__file__), '..')), 'web')
        else:
            # cube test
            self.apphome = abspath('..')
        self.sourcefile = sourcefile
        self.global_set_option('realm', '')
        self.use_pyro = pyro_name is not None

    def pyro_enabled(self):
        if self.use_pyro:
            return True
        else:
            return False

CubicWebConfiguration.cls_adjust_sys_path()

def install_sqlite_path(querier):
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

def init_test_database(driver='sqlite', configdir='data', config=None,
                       vreg=None):
    """init a test database for a specific driver"""
    from cubicweb.dbapi import in_memory_cnx
    if vreg and not config:
        config = vreg.config
    config = config or TestServerConfiguration(configdir)
    source = config.sources()
    if driver == 'sqlite':
        init_test_database_sqlite(config, source)
    elif driver == 'postgres':
        init_test_database_postgres(config, source)
    else:
        raise ValueError('no initialization function for driver %r' % driver)
    config._cubes = None # avoid assertion error
    repo, cnx = in_memory_cnx(vreg or config, unicode(source['admin']['login']),
                              source['admin']['password'] or 'xxx')
    if driver == 'sqlite':
        install_sqlite_path(repo.querier)
    return repo, cnx

def init_test_database_postgres(config, source, vreg=None):
    """initialize a fresh sqlite databse used for testing purpose"""
    if config.init_repository:
        from cubicweb.server import init_repository
        init_repository(config, interactive=False, drop=True, vreg=vreg)

def cleanup_sqlite(dbfile, removecube=False):
    try:
        os.remove(dbfile)
        os.remove('%s-journal' % dbfile)
    except OSError:
        pass
    if removecube:
        try:
            os.remove('%s-template' % dbfile)
        except OSError:
            pass

def init_test_database_sqlite(config, source, vreg=None):
    """initialize a fresh sqlite databse used for testing purpose"""
    import shutil
    # remove database file if it exists (actually I know driver == 'sqlite' :)
    dbfile = source['system']['db-name']
    cleanup_sqlite(dbfile)
    template = '%s-template' % dbfile
    if exists(template):
        shutil.copy(template, dbfile)
    else:
        # initialize the database
        from cubicweb.server import init_repository
        init_repository(config, interactive=False, vreg=vreg)
        shutil.copy(dbfile, template)
