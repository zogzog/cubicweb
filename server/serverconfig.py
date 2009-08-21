"""server.serverconfig definition

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import os
from os.path import join, exists

from logilab.common.configuration import REQUIRED, Method, Configuration, \
     ini_format_section
from logilab.common.decorators import wproperty, cached, clear_cache

from cubicweb import CW_SOFTWARE_ROOT, RegistryNotFound
from cubicweb.toolsutils import env_path, read_config, restrict_perms_to_user
from cubicweb.cwconfig import CubicWebConfiguration, merge_options
from cubicweb.server import SOURCE_TYPES


USER_OPTIONS =  (
    ('login', {'type' : 'string',
               'default': REQUIRED,
               'help': "cubicweb manager account's login "
               '(this user will be created)',
               'inputlevel': 0,
               }),
    ('password', {'type' : 'password',
                  'help': "cubicweb manager account's password",
                  'inputlevel': 0,
                  }),
    )

def generate_sources_file(sourcesfile, sourcescfg, keys=None):
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
            _sconfig = Configuration(options=options)
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
    if os.environ.get('APYCOT_ROOT'):
        root = os.environ['APYCOT_ROOT']
    elif CubicWebConfiguration.mode == 'dev':
        BACKUP_DIR = CubicWebConfiguration.RUNTIME_DIR
    else:
        BACKUP_DIR = '/var/lib/cubicweb/backup/'

    cubicweb_appobject_path = CubicWebConfiguration.cubicweb_appobject_path | set(['sobjects'])
    cube_appobject_path = CubicWebConfiguration.cube_appobject_path | set(['sobjects', 'hooks'])

    options = merge_options((
        # ctl configuration
        ('host',
         {'type' : 'string',
          'default': None,
          'help': 'host name if not correctly detectable through gethostname',
          'group': 'main', 'inputlevel': 1,
          }),
        ('pid-file',
         {'type' : 'string',
          'default': Method('default_pid_file'),
          'help': 'repository\'s pid file',
          'group': 'main', 'inputlevel': 2,
          }),
        ('uid',
         {'type' : 'string',
          'default': None,
          'help': 'if this option is set, use the specified user to start \
the repository rather than the user running the command',
          'group': 'main', 'inputlevel': (CubicWebConfiguration.mode == 'installed') and 0 or 1,
          }),
        ('session-time',
         {'type' : 'int',
          'default': 30*60,
          'help': 'session expiration time, default to 30 minutes',
          'group': 'main', 'inputlevel': 1,
          }),
        ('connections-pool-size',
         {'type' : 'int',
          'default': 4,
          'help': 'size of the connections pools. Each source supporting multiple \
connections will have this number of opened connections.',
          'group': 'main', 'inputlevel': 1,
          }),
        ('rql-cache-size',
         {'type' : 'int',
          'default': 300,
          'help': 'size of the parsed rql cache size.',
          'group': 'main', 'inputlevel': 1,
          }),
        ('delay-full-text-indexation',
         {'type' : 'yn', 'default': False,
          'help': 'When full text indexation of entity has a too important cost'
          ' to be done when entity are added/modified by users, activate this '
          'option and setup a job using cubicweb-ctl db-rebuild-fti on your '
          'system (using cron for instance).',
          'group': 'main', 'inputlevel': 1,
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
          'group': 'email', 'inputlevel': 1,
          }),
        ('default-dest-addrs',
         {'type' : 'csv',
          'default': (),
          'help': 'comma separated list of email addresses that will be used \
as default recipient when an email is sent and the notification has no \
specific recipient rules.',
          'group': 'email', 'inputlevel': 1,
          }),
        ('supervising-addrs',
         {'type' : 'csv',
          'default': (),
          'help': 'comma separated list of email addresses that will be \
notified of every changes.',
          'group': 'email', 'inputlevel': 2,
          }),
        # pyro server.serverconfig
        ('pyro-host',
         {'type' : 'int',
          'default': None,
          'help': 'Pyro server host, if not detectable correctly through \
gethostname(). It may contains port information using <host>:<port> notation, \
and if not set, it will be choosen randomly',
          'group': 'pyro-server', 'inputlevel': 2,
          }),
        ('pyro-id', # XXX reuse pyro-instance-id
         {'type' : 'string',
          'default': None,
          'help': 'identifier of the repository in the pyro name server',
          'group': 'pyro-server', 'inputlevel': 2,
          }),
        ) + CubicWebConfiguration.options)

    # should we open connections pools (eg connect to sources). This is usually
    # necessary...
    open_connections_pools = True

    # read the schema from the database
    read_instance_schema = True
    bootstrap_schema = True

    # check user's state at login time
    consider_user_state = True

    # hooks registration configuration
    # all hooks should be activated during normal execution
    core_hooks = True
    usergroup_hooks = True
    schema_hooks = True
    notification_hooks = True
    security_hooks = True
    instance_hooks = True

    # should some hooks be deactivated during [pre|post]create script execution
    free_wheel = False

    # list of enables sources when sources restriction is necessary
    # (eg repository initialization at least)
    _enabled_sources = None
    @wproperty
    def enabled_sources(self, sourceuris=None):
        self._enabled_sources = sourceuris
        clear_cache(self, 'sources')

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
        allsources = self.read_sources_file()
        if self._enabled_sources is None:
            return allsources
        return dict((uri, config) for uri, config in allsources.items()
                    if uri in self._enabled_sources or uri == 'admin')

    def write_sources_file(self, sourcescfg):
        sourcesfile = self.sources_file()
        if exists(sourcesfile):
            import shutil
            shutil.copy(sourcesfile, sourcesfile + '.bak')
        generate_sources_file(sourcesfile, sourcescfg, ['admin', 'system'])
        restrict_perms_to_user(sourcesfile)

    def pyro_enabled(self):
        """pyro is always enabled in standalone repository configuration"""
        return True

    def load_hooks(self, vreg):
        hooks = {}
        try:
            apphookdefs = vreg['hooks'].all_objects()
        except RegistryNotFound:
            return hooks
        for hookdef in apphookdefs:
            for event, ertype in hookdef.register_to():
                if ertype == 'Any':
                    ertype = ''
                cb = hookdef.make_callback(event)
                hooks.setdefault(event, {}).setdefault(ertype, []).append(cb)
        return hooks

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
        self._enabled_sources = enabled_sources
        clear_cache(self, 'sources')

    def migration_handler(self, schema=None, interactive=True,
                          cnx=None, repo=None, connect=True, verbosity=None):
        """return a migration handler instance"""
        from cubicweb.server.migractions import ServerMigrationHelper
        if verbosity is None:
            verbosity = getattr(self, 'verbosity', 0)
        return ServerMigrationHelper(self, schema, interactive=interactive,
                                     cnx=cnx, repo=repo, connect=connect,
                                     verbosity=verbosity)
