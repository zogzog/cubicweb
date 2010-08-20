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
"""server.serverconfig definition"""

__docformat__ = "restructuredtext en"

from os.path import join, exists

from logilab.common.configuration import REQUIRED, Method, Configuration, \
     ini_format_section
from logilab.common.decorators import wproperty, cached

from cubicweb.toolsutils import read_config, restrict_perms_to_user
from cubicweb.cwconfig import CubicWebConfiguration, merge_options
from cubicweb.server import SOURCE_TYPES


USER_OPTIONS =  (
    ('login', {'type' : 'string',
               'default': 'admin',
               'help': "cubicweb manager account's login "
               '(this user will be created)',
               'level': 0,
               }),
    ('password', {'type' : 'password',
                  'default': REQUIRED,
                  'help': "cubicweb manager account's password",
                  'level': 0,
                  }),
    )

class SourceConfiguration(Configuration):
    def __init__(self, appid, options):
        self.appid = appid # has to be done before super call
        super(SourceConfiguration, self).__init__(options=options)

    # make Method('default_instance_id') usable in db option defs (in native.py)
    def default_instance_id(self):
        return self.appid

def generate_sources_file(appid, sourcesfile, sourcescfg, keys=None):
    """serialize repository'sources configuration into a INI like file

    the `keys` parameter may be used to sort sections
    """
    if keys is None:
        keys = sourcescfg.keys()
    else:
        for key in sourcescfg:
            if not key in keys:
                keys.append(key)
    stream = open(sourcesfile, 'w')
    for uri in keys:
        sconfig = sourcescfg[uri]
        if isinstance(sconfig, dict):
            # get a Configuration object
            if uri == 'admin':
                options = USER_OPTIONS
            else:
                options = SOURCE_TYPES[sconfig['adapter']].options
            _sconfig = SourceConfiguration(appid, options=options)
            for attr, val in sconfig.items():
                if attr == 'uri':
                    continue
                if attr == 'adapter':
                    _sconfig.adapter = val
                else:
                    _sconfig.set_option(attr, val)
            sconfig = _sconfig
        optsbysect = list(sconfig.options_by_section())
        assert len(optsbysect) == 1, 'all options for a source should be in the same group'
        ini_format_section(stream, uri, optsbysect[0][1])
        if hasattr(sconfig, 'adapter'):
            print >> stream
            print >> stream, '# adapter for this source (YOU SHOULD NOT CHANGE THIS)'
            print >> stream, 'adapter=%s' % sconfig.adapter
        print >> stream


class ServerConfiguration(CubicWebConfiguration):
    """standalone RQL server"""
    name = 'repository'

    cubicweb_appobject_path = CubicWebConfiguration.cubicweb_appobject_path | set(['sobjects', 'hooks'])
    cube_appobject_path = CubicWebConfiguration.cube_appobject_path | set(['sobjects', 'hooks'])

    options = merge_options((
        # ctl configuration
        ('host',
         {'type' : 'string',
          'default': None,
          'help': 'host name if not correctly detectable through gethostname',
          'group': 'main', 'level': 1,
          }),
        ('pid-file',
         {'type' : 'string',
          'default': Method('default_pid_file'),
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
        ('session-time',
         {'type' : 'time',
          'default': '30min',
          'help': 'session expiration time, default to 30 minutes',
          'group': 'main', 'level': 3,
          }),
        ('connections-pool-size',
         {'type' : 'int',
          'default': 4,
          'help': 'size of the connections pools. Each source supporting multiple \
connections will have this number of opened connections.',
          'group': 'main', 'level': 3,
          }),
        ('rql-cache-size',
         {'type' : 'int',
          'default': 300,
          'help': 'size of the parsed rql cache size.',
          'group': 'main', 'level': 3,
          }),
        ('undo-support',
         {'type' : 'string', 'default': '',
          'help': 'string defining actions that will have undo support: \
[C]reate [U]pdate [D]elete entities / [A]dd [R]emove relation. Leave it empty \
for no undo support, set it to CUDAR for full undo support, or to DR for \
support undoing of deletion only.',
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
        # pyro server.serverconfig
        ('pyro-host',
         {'type' : 'string',
          'default': None,
          'help': 'Pyro server host, if not detectable correctly through \
gethostname(). It may contains port information using <host>:<port> notation, \
and if not set, it will be choosen randomly',
          'group': 'pyro', 'level': 3,
          }),
        ) + CubicWebConfiguration.options)

    # should we open connections pools (eg connect to sources). This is usually
    # necessary...
    open_connections_pools = True

    # read the schema from the database
    read_instance_schema = True
    # set to true while creating an instance
    creating = False
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
        return read_config(self.sources_file())

    def sources(self):
        """return a dictionnaries containing sources definitions indexed by
        sources'uri
        """
        return self.read_sources_file()

    def source_enabled(self, uri):
        return not self.enabled_sources or uri in self.enabled_sources

    def write_sources_file(self, sourcescfg):
        sourcesfile = self.sources_file()
        if exists(sourcesfile):
            import shutil
            shutil.copy(sourcesfile, sourcesfile + '.bak')
        generate_sources_file(self.appid, sourcesfile, sourcescfg,
                              ['admin', 'system'])
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
            # restaure original value
            self._cubes = origcubes
        return schema

    def load_bootstrap_schema(self):
        from cubicweb.schema import BootstrapSchemaLoader
        schema = BootstrapSchemaLoader().load(self)
        schema.name = 'bootstrap'
        return schema

    def set_sources_mode(self, sources):
        if 'migration' in sources:
            from cubicweb.server.sources import source_adapter
            assert len(sources) == 1
            enabled_sources = []
            for uri, config in self.sources().iteritems():
                if uri == 'admin':
                    continue
                if source_adapter(config).connect_for_migration:
                    enabled_sources.append(uri)
                else:
                    print 'not connecting to source', uri, 'during migration'
        elif 'all' in sources:
            assert len(sources) == 1
            enabled_sources = None
        else:
            known_sources = self.sources()
            for uri in sources:
                assert uri in known_sources, uri
            enabled_sources = sources
        self.enabled_sources = enabled_sources

    def migration_handler(self, schema=None, interactive=True,
                          cnx=None, repo=None, connect=True, verbosity=None):
        """return a migration handler instance"""
        from cubicweb.server.migractions import ServerMigrationHelper
        if verbosity is None:
            verbosity = getattr(self, 'verbosity', 0)
        return ServerMigrationHelper(self, schema, interactive=interactive,
                                     cnx=cnx, repo=repo, connect=connect,
                                     verbosity=verbosity)
