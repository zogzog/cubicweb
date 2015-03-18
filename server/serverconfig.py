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
"""server.serverconfig definition"""

__docformat__ = "restructuredtext en"

import sys
from os.path import join, exists
from StringIO import StringIO

import logilab.common.configuration as lgconfig
from logilab.common.decorators import cached

from cubicweb.toolsutils import read_config, restrict_perms_to_user
from cubicweb.cwconfig import CONFIGURATIONS, CubicWebConfiguration
from cubicweb.server import SOURCE_TYPES


USER_OPTIONS =  (
    ('login', {'type' : 'string',
               'default': 'admin',
               'help': "cubicweb manager account's login "
               '(this user will be created)',
               'level': 0,
               }),
    ('password', {'type' : 'password',
                  'default': lgconfig.REQUIRED,
                  'help': "cubicweb manager account's password",
                  'level': 0,
                  }),
    )

class SourceConfiguration(lgconfig.Configuration):
    def __init__(self, appconfig, options):
        self.appconfig = appconfig # has to be done before super call
        super(SourceConfiguration, self).__init__(options=options)

    # make Method('default_instance_id') usable in db option defs (in native.py)
    def default_instance_id(self):
        return self.appconfig.appid

    def input_option(self, option, optdict, inputlevel):
        try:
            dbdriver = self['db-driver']
        except lgconfig.OptionError:
            pass
        else:
            if dbdriver == 'sqlite':
                if option in ('db-user', 'db-password'):
                    return
                if option == 'db-name':
                    optdict = optdict.copy()
                    optdict['help'] = 'path to the sqlite database'
                    optdict['default'] = join(self.appconfig.appdatahome,
                                              self.appconfig.appid + '.sqlite')
        super(SourceConfiguration, self).input_option(option, optdict, inputlevel)



def ask_source_config(appconfig, type, inputlevel=0):
    options = SOURCE_TYPES[type].options
    sconfig = SourceConfiguration(appconfig, options=options)
    sconfig.input_config(inputlevel=inputlevel)
    return sconfig

def generate_source_config(sconfig, encoding=sys.stdin.encoding):
    """serialize a repository source configuration as text"""
    stream = StringIO()
    optsbysect = list(sconfig.options_by_section())
    assert len(optsbysect) == 1, (
        'all options for a source should be in the same group, got %s'
        % [x[0] for x in optsbysect])
    lgconfig.ini_format(stream, optsbysect[0][1], encoding)
    return stream.getvalue()


class ServerConfiguration(CubicWebConfiguration):
    """standalone RQL server"""
    name = 'repository'

    cubicweb_appobject_path = CubicWebConfiguration.cubicweb_appobject_path | set(['sobjects', 'hooks'])
    cube_appobject_path = CubicWebConfiguration.cube_appobject_path | set(['sobjects', 'hooks'])

    options = lgconfig.merge_options((
        # ctl configuration
        ('host',
         {'type' : 'string',
          'default': None,
          'help': 'host name if not correctly detectable through gethostname',
          'group': 'main', 'level': 1,
          }),
        ('pid-file',
         {'type' : 'string',
          'default': lgconfig.Method('default_pid_file'),
          'help': 'repository\'s pid file',
          'group': 'main', 'level': 2,
          }),
        ('uid',
         {'type' : 'string',
          'default': None,
          'help': 'if this option is set, use the specified user to start \
the repository rather than the user running the command',
          'group': 'main', 'level': (CubicWebConfiguration.mode == 'installed') and 0 or 1,
          }),
        ('cleanup-session-time',
         {'type' : 'time',
          'default': '24h',
          'help': 'duration of inactivity after which a session '
          'will be closed, to limit memory consumption (avoid sessions that '
          'never expire and cause memory leak when http-session-time is 0, or '
          'because of bad client that never closes their connection). '
          'So notice that even if http-session-time is 0 and the user don\'t '
          'close his browser, he will have to reauthenticate after this time '
          'of inactivity. Default to 24h.',
          'group': 'main', 'level': 3,
          }),
        ('connections-pool-size',
         {'type' : 'int',
          'default': 4,
          'help': 'size of the connections pool. Each source supporting multiple \
connections will have this number of opened connections.',
          'group': 'main', 'level': 3,
          }),
        ('rql-cache-size',
         {'type' : 'int',
          'default': 3000,
          'help': 'size of the parsed rql cache size.',
          'group': 'main', 'level': 3,
          }),
        ('undo-enabled',
         {'type' : 'yn', 'default': False,
          'help': 'enable undo support',
          'group': 'main', 'level': 3,
          }),
        ('keep-transaction-lifetime',
         {'type' : 'int', 'default': 7,
          'help': 'number of days during which transaction records should be \
kept (hence undoable).',
          'group': 'main', 'level': 3,
          }),
        ('multi-sources-etypes',
         {'type' : 'csv', 'default': (),
          'help': 'defines which entity types from this repository are used \
by some other instances. You should set this properly for these instances to \
detect updates / deletions.',
          'group': 'main', 'level': 3,
          }),

        ('delay-full-text-indexation',
         {'type' : 'yn', 'default': False,
          'help': 'When full text indexation of entity has a too important cost'
          ' to be done when entity are added/modified by users, activate this '
          'option and setup a job using cubicweb-ctl db-rebuild-fti on your '
          'system (using cron for instance).',
          'group': 'main', 'level': 3,
          }),

        # email configuration
        ('default-recipients-mode',
         {'type' : 'choice',
          'choices' : ('default-dest-addrs', 'users', 'none'),
          'default': 'default-dest-addrs',
          'help': 'when a notification should be sent with no specific rules \
to find recipients, recipients will be found according to this mode. Available \
modes are "default-dest-addrs" (emails specified in the configuration \
variable with the same name), "users" (every users which has activated \
account with an email set), "none" (no notification).',
          'group': 'email', 'level': 2,
          }),
        ('default-dest-addrs',
         {'type' : 'csv',
          'default': (),
          'help': 'comma separated list of email addresses that will be used \
as default recipient when an email is sent and the notification has no \
specific recipient rules.',
          'group': 'email', 'level': 2,
          }),
        ('supervising-addrs',
         {'type' : 'csv',
          'default': (),
          'help': 'comma separated list of email addresses that will be \
notified of every changes.',
          'group': 'email', 'level': 2,
          }),
        # pyro services config
        ('pyro-host',
         {'type' : 'string',
          'default': None,
          'help': 'Pyro server host, if not detectable correctly through \
gethostname(). It may contains port information using <host>:<port> notation, \
and if not set, it will be choosen randomly',
          'group': 'pyro', 'level': 3,
          }),
        ('pyro-instance-id',
         {'type' : 'string',
          'default': lgconfig.Method('default_instance_id'),
          'help': 'identifier of the CubicWeb instance in the Pyro name server',
          'group': 'pyro', 'level': 1,
          }),
        ('pyro-ns-host',
         {'type' : 'string',
          'default': '',
          'help': 'Pyro name server\'s host. If not set, will be detected by a \
broadcast query. It may contains port information using <host>:<port> notation. \
Use "NO_PYRONS" to create a Pyro server but not register to a pyro nameserver',
          'group': 'pyro', 'level': 1,
          }),
        ('pyro-ns-group',
         {'type' : 'string',
          'default': 'cubicweb',
          'help': 'Pyro name server\'s group where the repository will be \
registered.',
          'group': 'pyro', 'level': 1,
          }),
        # zmq services config
        ('zmq-repository-address',
         {'type' : 'string',
          'default': None,
          'help': ('ZMQ URI on which the repository will be bound '
                   'to (of the form `zmqpickle-tcp://<ipaddr>:<port>`).'),
          'group': 'zmq', 'level': 3,
          }),
         ('zmq-address-sub',
          {'type' : 'csv',
           'default' : (),
           'help': ('List of ZMQ addresses to subscribe to (requires pyzmq) '
                    '(of the form `tcp://<ipaddr>:<port>`)'),
           'group': 'zmq', 'level': 1,
           }),
         ('zmq-address-pub',
          {'type' : 'string',
           'default' : None,
           'help': ('ZMQ address to use for publishing (requires pyzmq) '
                    '(of the form `tcp://<ipaddr>:<port>`)'),
           'group': 'zmq', 'level': 1,
           }),
        ) + CubicWebConfiguration.options)

    # should we init the connections pool (eg connect to sources). This is
    # usually necessary...
    init_cnxset_pool = True

    # read the schema from the database
    read_instance_schema = True
    # set this to true to get a minimal repository, for instance to get cubes
    # information on commands such as i18ninstance, db-restore, etc...
    quick_start = False
    # check user's state at login time
    consider_user_state = True

    # should some hooks be deactivated during [pre|post]create script execution
    free_wheel = False

    # list of enables sources when sources restriction is necessary
    # (eg repository initialization at least)
    enabled_sources = None

    def bootstrap_cubes(self):
        from logilab.common.textutils import splitstrip
        for line in file(join(self.apphome, 'bootstrap_cubes')):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            self.init_cubes(self.expand_cubes(splitstrip(line)))
            break
        else:
            # no cubes
            self.init_cubes(())

    def write_bootstrap_cubes_file(self, cubes):
        stream = file(join(self.apphome, 'bootstrap_cubes'), 'w')
        stream.write('# this is a generated file only used for bootstraping\n')
        stream.write('# you should not have to edit this\n')
        stream.write('%s\n' % ','.join(cubes))
        stream.close()

    def sources_file(self):
        return join(self.apphome, 'sources')

    # this method has to be cached since when the server is running using a
    # restricted user, this user usually don't have access to the sources
    # configuration file (#16102)
    @cached
    def read_sources_file(self):
        """return a dictionary of values found in the sources file"""
        return read_config(self.sources_file(), raise_if_unreadable=True)

    @property
    def system_source_config(self):
        return self.read_sources_file()['system']

    @property
    def default_admin_config(self):
        return self.read_sources_file()['admin']

    def source_enabled(self, source):
        if self.sources_mode is not None:
            if 'migration' in self.sources_mode:
                assert len(self.sources_mode) == 1
                if source.connect_for_migration:
                    return True
                print 'not connecting to source', source.uri, 'during migration'
                return False
            if 'all' in self.sources_mode:
                assert len(self.sources_mode) == 1
                return True
            return source.uri in self.sources_mode
        if self.quick_start:
            return source.uri == 'system'
        return (not source.disabled and (
            not self.enabled_sources or source.uri in self.enabled_sources))

    def write_sources_file(self, sourcescfg):
        """serialize repository'sources configuration into a INI like file"""
        sourcesfile = self.sources_file()
        if exists(sourcesfile):
            import shutil
            shutil.copy(sourcesfile, sourcesfile + '.bak')
        stream = open(sourcesfile, 'w')
        for section in ('admin', 'system'):
            sconfig = sourcescfg[section]
            if isinstance(sconfig, dict):
                # get a Configuration object
                assert section == 'system', '%r is not system' % section
                _sconfig = SourceConfiguration(
                    self, options=SOURCE_TYPES['native'].options)
                for attr, val in sconfig.items():
                    try:
                        _sconfig.set_option(attr, val)
                    except lgconfig.OptionError:
                        # skip adapter, may be present on pre 3.10 instances
                        if attr != 'adapter':
                            self.error('skip unknown option %s in sources file' % attr)
                sconfig = _sconfig
            stream.write('[%s]\n%s\n' % (section, generate_source_config(sconfig)))
        restrict_perms_to_user(sourcesfile)

    def pyro_enabled(self):
        """pyro is always enabled in standalone repository configuration"""
        return True

    def load_schema(self, expand_cubes=False, **kwargs):
        from cubicweb.schema import CubicWebSchemaLoader
        if expand_cubes:
            # in case some new dependencies have been introduced, we have to
            # reinitialize cubes so the full filesystem schema is read
            origcubes = self.cubes()
            self._cubes = None
            self.init_cubes(self.expand_cubes(origcubes))
        schema = CubicWebSchemaLoader().load(self, **kwargs)
        if expand_cubes:
            # restore original value
            self._cubes = origcubes
        return schema

    def load_bootstrap_schema(self):
        from cubicweb.schema import BootstrapSchemaLoader
        schema = BootstrapSchemaLoader().load(self)
        schema.name = 'bootstrap'
        return schema

    sources_mode = None
    def set_sources_mode(self, sources):
        self.sources_mode = sources

    def migration_handler(self, schema=None, interactive=True,
                          cnx=None, repo=None, connect=True, verbosity=None):
        """return a migration handler instance"""
        from cubicweb.server.migractions import ServerMigrationHelper
        if verbosity is None:
            verbosity = getattr(self, 'verbosity', 0)
        return ServerMigrationHelper(self, schema, interactive=interactive,
                                     cnx=cnx, repo=repo, connect=connect,
                                     verbosity=verbosity)


CONFIGURATIONS.append(ServerConfiguration)
