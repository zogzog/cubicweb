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
"""Test tools for cubicweb

"""
__docformat__ = "restructuredtext en"

import os
import logging
from datetime import timedelta
from os.path import (abspath, join, exists, basename, dirname, normpath, split,
                     isfile, isabs)

from logilab.common.date import strptime
from cubicweb import CW_SOFTWARE_ROOT, ConfigurationError, schema, cwconfig
from cubicweb.server.serverconfig import ServerConfiguration
from cubicweb.etwist.twconfig import TwistedConfiguration

cwconfig.CubicWebConfiguration.cls_adjust_sys_path()

# db auto-population configuration #############################################

SYSTEM_ENTITIES = schema.SCHEMA_TYPES | set((
    'CWGroup', 'CWUser', 'CWProperty',
    'Workflow', 'State', 'BaseTransition', 'Transition', 'WorkflowTransition',
    'TrInfo', 'SubWorkflowExitPoint',
    ))

SYSTEM_RELATIONS = schema.META_RTYPES | set((
    # workflow related
    'workflow_of', 'state_of', 'transition_of', 'initial_state', 'default_workflow',
    'allowed_transition', 'destination_state', 'from_state', 'to_state',
    'condition', 'subworkflow', 'subworkflow_state', 'subworkflow_exit',
    'custom_workflow', 'in_state', 'wf_info_for',
    # cwproperty
    'for_user',
    # schema definition
    'specializes',
    'relation_type', 'from_entity', 'to_entity',
    'constrained_by', 'cstrtype', 'widget',
    'read_permission', 'update_permission', 'delete_permission', 'add_permission',
    # permission
    'in_group', 'require_group', 'require_permission',
    # deducted from other relations
    'primary_email',
    ))

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
    options = cwconfig.merge_options(ServerConfiguration.options + (
        ('anonymous-user',
         {'type' : 'string',
          'default': None,
          'help': 'login of the CubicWeb user account to use for anonymous user (if you want to allow anonymous)',
          'group': 'main', 'level': 1,
          }),
        ('anonymous-password',
         {'type' : 'string',
          'default': None,
          'help': 'password of the CubicWeb user account matching login',
          'group': 'main', 'level': 1,
          }),
        ))

    def __init__(self, appid, log_threshold=logging.CRITICAL+10):
        ServerConfiguration.__init__(self, appid)
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

    def load_configuration(self):
        super(TestServerConfiguration, self).load_configuration()
        self.global_set_option('anonymous-user', 'anon')
        self.global_set_option('anonymous-password', 'anon')
        # no undo support in tests
        self.global_set_option('undo-support', '')

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


class BaseApptestConfiguration(TestServerConfiguration, TwistedConfiguration):
    repo_method = 'inmemory'
    options = cwconfig.merge_options(TestServerConfiguration.options
                                     + TwistedConfiguration.options)
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


# test database handling #######################################################

def init_test_database(config=None, configdir='data'):
    """init a test database for a specific driver"""
    from cubicweb.dbapi import in_memory_cnx
    config = config or TestServerConfiguration(configdir)
    sources = config.sources()
    driver = sources['system']['db-driver']
    if driver == 'sqlite':
        init_test_database_sqlite(config)
    elif driver == 'postgres':
        init_test_database_postgres(config)
    elif driver == 'sqlserver2005':
        init_test_database_sqlserver2005(config)
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
    driver = config.sources()['system']['db-driver']
    if driver == 'sqlite':
        reset_test_database_sqlite(config)
    elif driver in ('sqlserver2005', 'postgres'):
        # XXX do something with dump/restore ?
        print 'resetting the database is not done for', driver
        print 'you should handle it manually'
    else:
        raise ValueError('no reset function for driver %r' % driver)


### postgres test database handling ############################################

def init_test_database_postgres(config):
    """initialize a fresh postgresql databse used for testing purpose"""
    if config.init_repository:
        from cubicweb.server import init_repository
        init_repository(config, interactive=False, drop=True)

### sqlserver2005 test database handling ############################################

def init_test_database_sqlserver2005(config):
    """initialize a fresh sqlserver databse used for testing purpose"""
    if config.init_repository:
        from cubicweb.server import init_repository
        init_repository(config, interactive=False, drop=True, vreg=vreg)

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
    if not reset_test_database_sqlite(config):
        # initialize the database
        import shutil
        from cubicweb.server import init_repository
        init_repository(config, interactive=False)
        dbfile = config.sources()['system']['db-name']
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
