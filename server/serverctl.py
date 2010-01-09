"""cubicweb-ctl commands and command handlers specific to the server.serverconfig

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = 'restructuredtext en'

import sys
import os

from logilab.common.configuration import Configuration
from logilab.common.clcommands import register_commands, cmd_run, pop_arg
from logilab.common.shellutils import ASK

from cubicweb import (AuthenticationError, ExecutionError, ConfigurationError,
                      underline_title)
from cubicweb.toolsutils import Command, CommandHandler
from cubicweb.server import SOURCE_TYPES
from cubicweb.server.utils import ask_source_config
from cubicweb.server.serverconfig import (USER_OPTIONS, ServerConfiguration,
                                          SourceConfiguration)

# utility functions ###########################################################

def source_cnx(source, dbname=None, special_privs=False, verbose=True):
    """open and return a connection to the system database defined in the
    given server.serverconfig
    """
    from getpass import getpass
    from logilab.common.db import get_connection
    dbhost = source.get('db-host')
    if dbname is None:
        dbname = source['db-name']
    driver = source['db-driver']
    print '-> connecting to %s database' % driver,
    if dbhost:
        print '%s@%s' % (dbname, dbhost),
    else:
        print dbname,
    if not verbose or (not special_privs and source.get('db-user')):
        user = source['db-user']
        print 'as', user
        if source.get('db-password'):
            password = source['db-password']
        else:
            password = getpass('password: ')
    else:
        print
        if special_privs:
            print 'WARNING'
            print 'the user will need the following special access rights on the database:'
            print special_privs
            print
        default_user = source.get('db-user', os.environ.get('USER', ''))
        user = raw_input('Connect as user ? [%r]: ' % default_user)
        user = user or default_user
        if user == source.get('db-user') and source.get('db-password'):
            password = source['db-password']
        else:
            password = getpass('password: ')
    extra_args = source.get('db-extra-arguments')
    extra = extra_args and {'extra_args': extra_args} or {}
    return get_connection(driver, dbhost, dbname, user, password=password,
                          port=source.get('db-port'),
                          **extra)

def system_source_cnx(source, dbms_system_base=False,
                      special_privs='CREATE/DROP DATABASE', verbose=True):
    """shortcut to get a connextion to the instance system database
    defined in the given config. If <dbms_system_base> is True,
    connect to the dbms system database instead (for task such as
    create/drop the instance database)
    """
    if dbms_system_base:
        from logilab.common.adbh import get_adv_func_helper
        system_db = get_adv_func_helper(source['db-driver']).system_database()
        return source_cnx(source, system_db, special_privs=special_privs, verbose=verbose)
    return source_cnx(source, special_privs=special_privs, verbose=verbose)

def _db_sys_cnx(source, what, db=None, user=None, verbose=True):
    """return a connection on the RDMS system table (to create/drop a user
    or a database
    """
    import logilab.common as lgp
    from logilab.common.adbh import get_adv_func_helper
    lgp.USE_MX_DATETIME = False
    special_privs = ''
    driver = source['db-driver']
    helper = get_adv_func_helper(driver)
    if user is not None and helper.users_support:
        special_privs += '%s USER' % what
    if db is not None:
        special_privs += ' %s DATABASE' % what
    # connect on the dbms system base to create our base
    cnx = system_source_cnx(source, True, special_privs=special_privs, verbose=verbose)
    # disable autocommit (isolation_level(1)) because DROP and
    # CREATE DATABASE can't be executed in a transaction
    try:
        cnx.set_isolation_level(0)
    except AttributeError:
        # set_isolation_level() is psycopg specific
        pass
    return cnx

def repo_cnx(config):
    """return a in-memory repository and a db api connection it"""
    from cubicweb.dbapi import in_memory_cnx
    from cubicweb.server.utils import manager_userpasswd
    try:
        login = config.sources()['admin']['login']
        pwd = config.sources()['admin']['password']
    except KeyError:
        login, pwd = manager_userpasswd()
    while True:
        try:
            return in_memory_cnx(config, login, pwd)
        except AuthenticationError:
            print '-> Error: wrong user/password.'
            # reset cubes else we'll have an assertion error on next retry
            config._cubes = None
        login, pwd = manager_userpasswd()


# repository specific command handlers ########################################

class RepositoryCreateHandler(CommandHandler):
    cmdname = 'create'
    cfgname = 'repository'

    def bootstrap(self, cubes, inputlevel=0):
        """create an instance by copying files from the given cube and by
        asking information necessary to build required configuration files
        """
        config = self.config
        print underline_title('Configuring the repository')
        config.input_config('email', inputlevel)
        # ask for pyro configuration if pyro is activated and we're not using a
        # all-in-one config, in which case this is done by the web side command
        # handler
        if config.pyro_enabled() and config.name != 'all-in-one':
            config.input_config('pyro', inputlevel)
        print '\n'+underline_title('Configuring the sources')
        sourcesfile = config.sources_file()
        # XXX hack to make Method('default_instance_id') usable in db option
        # defs (in native.py)
        sconfig = SourceConfiguration(config.appid,
                                      options=SOURCE_TYPES['native'].options)
        sconfig.adapter = 'native'
        sconfig.input_config(inputlevel=inputlevel)
        sourcescfg = {'system': sconfig}
        for cube in cubes:
            # if a source is named as the cube containing it, we need the
            # source to use the cube, so add it.
            if cube in SOURCE_TYPES:
                sourcescfg[cube] = ask_source_config(cube, inputlevel)
        print
        while ASK.confirm('Enter another source ?', default_is_yes=False):
            available = sorted(stype for stype in SOURCE_TYPES
                               if not stype in cubes)
            while True:
                sourcetype = raw_input('source type (%s): ' % ', '.join(available))
                if sourcetype in available:
                    break
                print '-> unknown source type, use one of the available types.'
            while True:
                sourceuri = raw_input('source uri: ').strip()
                if sourceuri != 'admin' and sourceuri not in sourcescfg:
                    break
                print '-> uri already used, choose another one.'
            sourcescfg[sourceuri] = ask_source_config(sourcetype)
            sourcemodule = SOURCE_TYPES[sourcetype].module
            if not sourcemodule.startswith('cubicweb.'):
                # module names look like cubes.mycube.themodule
                sourcecube = SOURCE_TYPES[sourcetype].module.split('.', 2)[1]
                # if the source adapter is coming from an external component,
                # ensure it's specified in used cubes
                if not sourcecube in cubes:
                    cubes.append(sourcecube)
        sconfig = Configuration(options=USER_OPTIONS)
        sconfig.input_config(inputlevel=inputlevel)
        sourcescfg['admin'] = sconfig
        config.write_sources_file(sourcescfg)
        # remember selected cubes for later initialization of the database
        config.write_bootstrap_cubes_file(cubes)

    def postcreate(self):
        if ASK.confirm('Run db-create to create the system database ?'):
            verbosity = (self.config.mode == 'installed') and 'y' or 'n'
            cmd_run('db-create', self.config.appid, '--verbose=%s' % verbosity)
        else:
            print ('-> nevermind, you can do it later with '
                   '"cubicweb-ctl db-create %s".' % self.config.appid)


class RepositoryDeleteHandler(CommandHandler):
    cmdname = 'delete'
    cfgname = 'repository'

    def cleanup(self):
        """remove instance's configuration and database"""
        from logilab.common.adbh import get_adv_func_helper
        source = self.config.sources()['system']
        dbname = source['db-name']
        helper = get_adv_func_helper(source['db-driver'])
        if ASK.confirm('Delete database %s ?' % dbname):
            user = source['db-user'] or None
            cnx = _db_sys_cnx(source, 'DROP DATABASE', user=user)
            cursor = cnx.cursor()
            try:
                cursor.execute('DROP DATABASE %s' % dbname)
                print '-> database %s dropped.' % dbname
                # XXX should check we are not connected as user
                if user and helper.users_support and \
                       ASK.confirm('Delete user %s ?' % user, default_is_yes=False):
                    cursor.execute('DROP USER %s' % user)
                    print '-> user %s dropped.' % user
                cnx.commit()
            except:
                cnx.rollback()
                raise


class RepositoryStartHandler(CommandHandler):
    cmdname = 'start'
    cfgname = 'repository'

    def start_server(self, ctlconf, debug):
        command = ['cubicweb-ctl start-repository ']
        if debug:
            command.append('--debug')
        command.append(self.config.appid)
        os.system(' '.join(command))


class RepositoryStopHandler(CommandHandler):
    cmdname = 'stop'
    cfgname = 'repository'

    def poststop(self):
        """if pyro is enabled, ensure the repository is correctly
        unregistered
        """
        if self.config.pyro_enabled():
            from cubicweb.server.repository import pyro_unregister
            pyro_unregister(self.config)


# repository specific commands ################################################

class CreateInstanceDBCommand(Command):
    """Create the system database of an instance (run after 'create').

    You will be prompted for a login / password to use to connect to
    the system database.  The given user should have almost all rights
    on the database (ie a super user on the dbms allowed to create
    database, users, languages...).

    <instance>
      the identifier of the instance to initialize.
    """
    name = 'db-create'
    arguments = '<instance>'

    options = (
        ('create-db',
         {'short': 'c', 'type': 'yn', 'metavar': '<y or n>',
          'default': True,
          'help': 'create the database (yes by default)'}),
        ('verbose',
         {'short': 'v', 'type' : 'yn', 'metavar': '<verbose>',
          'default': 'n',
          'help': 'verbose mode: will ask all possible configuration questions',
          }
         ),
        ('automatic',
         {'short': 'a', 'type' : 'yn', 'metavar': '<auto>',
          'default': 'n',
          'help': 'automatic mode: never ask and use default answer to every question',
          }
         ),
        )
    def run(self, args):
        """run the command with its specific arguments"""
        from logilab.common.adbh import get_adv_func_helper
        from indexer import get_indexer
        verbose = self.get('verbose')
        automatic = self.get('automatic')
        appid = pop_arg(args, msg='No instance specified !')
        config = ServerConfiguration.config_for(appid)
        source = config.sources()['system']
        dbname = source['db-name']
        driver = source['db-driver']
        create_db = self.config.create_db
        helper = get_adv_func_helper(driver)
        if driver == 'sqlite':
            if os.path.exists(dbname) and automatic or \
                   ASK.confirm('Database %s already exists -- do you want to drop it ?' % dbname):
                os.unlink(dbname)
        elif create_db:
            print '\n'+underline_title('Creating the system database')
            # connect on the dbms system base to create our base
            dbcnx = _db_sys_cnx(source, 'CREATE DATABASE and / or USER', verbose=verbose)
            cursor = dbcnx.cursor()
            try:
                if helper.users_support:
                    user = source['db-user']
                    if not helper.user_exists(cursor, user) and (automatic or \
                           ASK.confirm('Create db user %s ?' % user, default_is_yes=False)):
                        helper.create_user(source['db-user'], source['db-password'])
                        print '-> user %s created.' % user
                if dbname in helper.list_databases(cursor):
                    if automatic or ASK.confirm('Database %s already exists -- do you want to drop it ?' % dbname):
                        cursor.execute('DROP DATABASE %s' % dbname)
                    else:
                        return
                if dbcnx.logged_user != source['db-user']:
                    helper.create_database(cursor, dbname, source['db-user'],
                                           source['db-encoding'])
                else:
                    helper.create_database(cursor, dbname,
                                           encoding=source['db-encoding'])
                dbcnx.commit()
                print '-> database %s created.' % dbname
            except:
                dbcnx.rollback()
                raise
        cnx = system_source_cnx(source, special_privs='LANGUAGE C', verbose=verbose)
        cursor = cnx.cursor()
        indexer = get_indexer(driver)
        indexer.init_extensions(cursor)
        # postgres specific stuff
        if driver == 'postgres':
            # install plpythonu/plpgsql language if not installed by the cube
            langs = sys.platform == 'win32' and ('plpgsql',) or ('plpythonu', 'plpgsql')
            for extlang in langs:
                helper.create_language(cursor, extlang)
        cursor.close()
        cnx.commit()
        print '-> database for instance %s created and necessary extensions installed.' % appid
        print
        if automatic or ASK.confirm('Run db-init to initialize the system database ?'):
            cmd_run('db-init', config.appid)
        else:
            print ('-> nevermind, you can do it later with '
                   '"cubicweb-ctl db-init %s".' % config.appid)


class InitInstanceCommand(Command):
    """Initialize the system database of an instance (run after 'db-create').

    You will be prompted for a login / password to use to connect to
    the system database.  The given user should have the create tables,
    and grant permissions.

    <instance>
      the identifier of the instance to initialize.
    """
    name = 'db-init'
    arguments = '<instance>'

    options = (
        ('drop',
         {'short': 'd', 'action': 'store_true',
          'default': False,
          'help': 'insert drop statements to remove previously existant \
tables, indexes... (no by default)'}),
        )

    def run(self, args):
        print '\n'+underline_title('Initializing the system database')
        from cubicweb.server import init_repository
        from logilab.common.db import get_connection
        appid = pop_arg(args, msg='No instance specified !')
        config = ServerConfiguration.config_for(appid)
        try:
            system = config.sources()['system']
            extra_args=system.get('db-extra-arguments')
            extra = extra_args and {'extra_args': extra_args} or {}
            get_connection(
                system['db-driver'], database=system['db-name'],
                host=system.get('db-host'), port=system.get('db-port'),
                user=system.get('db-user'), password=system.get('db-password'), 
                **extra)
        except Exception, ex:
            raise ConfigurationError(
                'You seem to have provided wrong connection information in '\
                'the %s file. Resolve this first (error: %s).'
                % (config.sources_file(), str(ex).strip()))
        init_repository(config, drop=self.config.drop)


class GrantUserOnInstanceCommand(Command):
    """Grant a database user on a repository system database.

    <instance>
      the identifier of the instance
    <user>
      the database's user requiring grant access
    """
    name = 'db-grant-user'
    arguments = '<instance> <user>'

    options = (
        ('set-owner',
         {'short': 'o', 'type' : 'yn', 'metavar' : '<yes or no>',
          'default' : False,
          'help': 'Set the user as tables owner if yes (no by default).'}
         ),
        )
    def run(self, args):
        """run the command with its specific arguments"""
        from cubicweb.server.sqlutils import sqlexec, sqlgrants
        appid = pop_arg(args, 1, msg='No instance specified !')
        user = pop_arg(args, msg='No user specified !')
        config = ServerConfiguration.config_for(appid)
        source = config.sources()['system']
        set_owner = self.config.set_owner
        cnx = system_source_cnx(source, special_privs='GRANT')
        cursor = cnx.cursor()
        schema = config.load_schema()
        try:
            sqlexec(sqlgrants(schema, source['db-driver'], user,
                              set_owner=set_owner), cursor)
        except Exception, ex:
            cnx.rollback()
            import traceback
            traceback.print_exc()
            print '-> an error occured:', ex
        else:
            cnx.commit()
            print '-> rights granted to %s on instance %s.' % (appid, user)


class ResetAdminPasswordCommand(Command):
    """Reset the administrator password.

    <instance>
      the identifier of the instance
    """
    name = 'reset-admin-pwd'
    arguments = '<instance>'

    def run(self, args):
        """run the command with its specific arguments"""
        from cubicweb.server.sqlutils import sqlexec, SQL_PREFIX
        from cubicweb.server.utils import crypt_password, manager_userpasswd
        appid = pop_arg(args, 1, msg='No instance specified !')
        config = ServerConfiguration.config_for(appid)
        sourcescfg = config.read_sources_file()
        try:
            adminlogin = sourcescfg['admin']['login']
        except KeyError:
            print '-> Error: could not get cubicweb administrator login.'
            sys.exit(1)
        cnx = source_cnx(sourcescfg['system'])
        cursor = cnx.cursor()
        _, passwd = manager_userpasswd(adminlogin, confirm=True,
                                       passwdmsg='new password for %s' % adminlogin)
        try:
            sqlexec("UPDATE %(sp)sCWUser SET %(sp)supassword='%(p)s' WHERE %(sp)slogin='%(l)s'"
                    % {'sp': SQL_PREFIX,
                       'p': crypt_password(passwd), 'l': adminlogin},
                    cursor, withpb=False)
            sconfig = Configuration(options=USER_OPTIONS)
            sconfig['login'] = adminlogin
            sconfig['password'] = passwd
            sourcescfg['admin'] = sconfig
            config.write_sources_file(sourcescfg)
        except Exception, ex:
            cnx.rollback()
            import traceback
            traceback.print_exc()
            print '-> an error occured:', ex
        else:
            cnx.commit()
            print '-> password reset, sources file regenerated.'


class StartRepositoryCommand(Command):
    """Start an CubicWeb RQL server for a given instance.

    The server will be accessible through pyro

    <instance>
      the identifier of the instance to initialize.
    """
    name = 'start-repository'
    arguments = '<instance>'

    options = (
        ('debug',
         {'short': 'D', 'action' : 'store_true',
          'help': 'start server in debug mode.'}),
        )

    def run(self, args):
        from cubicweb.server.server import RepositoryServer
        appid = pop_arg(args, msg='No instance specified !')
        config = ServerConfiguration.config_for(appid)
        if sys.platform == 'win32':
            if not self.config.debug:
                from logging import getLogger
                logger = getLogger('cubicweb.ctl')
                logger.info('Forcing debug mode on win32 platform')
                self.config.debug = True
        debug = self.config.debug
        # create the server
        server = RepositoryServer(config, debug)
        # go ! (don't daemonize in debug mode)
        pidfile = config['pid-file']
        # ensure the directory where the pid-file should be set exists (for
        # instance /var/run/cubicweb may be deleted on computer restart)
        piddir = os.path.dirname(pidfile)
        if not os.path.exists(piddir):
            os.makedirs(piddir)
        if not debug and server.daemonize(pidfile) == -1:
            return
        uid = config['uid']
        if uid is not None:
            try:
                uid = int(uid)
            except ValueError:
                from pwd import getpwnam
                uid = getpwnam(uid).pw_uid
            os.setuid(uid)
        server.install_sig_handlers()
        server.connect(config['host'], 0)
        server.run()


def _remote_dump(host, appid, output, sudo=False):
    # XXX generate unique/portable file name
    from datetime import date
    filename = '%s-%s.tgz' % (appid, date.today().strftime('%Y-%m-%d'))
    dmpcmd = 'cubicweb-ctl db-dump -o /tmp/%s %s' % (filename, appid)
    if sudo:
        dmpcmd = 'sudo %s' % (dmpcmd)
    dmpcmd = 'ssh -t %s "%s"' % (host, dmpcmd)
    print dmpcmd
    if os.system(dmpcmd):
        raise ExecutionError('Error while dumping the database')
    if output is None:
        output = filename
    cmd = 'scp %s:/tmp/%s %s' % (host, filename, output)
    print cmd
    if os.system(cmd):
        raise ExecutionError('Error while retrieving the dump at /tmp/%s' % filename)
    rmcmd = 'ssh -t %s "rm -f /tmp/%s"' % (host, filename)
    print rmcmd
    if os.system(rmcmd) and not ASK.confirm(
        'An error occured while deleting remote dump at /tmp/%s. '
        'Continue anyway?' % filename):
        raise ExecutionError('Error while deleting remote dump at /tmp/%s' % filename)

def _local_dump(appid, output):
    config = ServerConfiguration.config_for(appid)
    # schema=1 to avoid unnecessary schema loading
    mih = config.migration_handler(connect=False, schema=1, verbosity=1)
    mih.backup_database(output, askconfirm=False)
    mih.shutdown()

def _local_restore(appid, backupfile, drop, systemonly=True):
    config = ServerConfiguration.config_for(appid)
    config.verbosity = 1 # else we won't be asked for confirmation on problems
    config.repairing = 1 # don't check versions
    # schema=1 to avoid unnecessary schema loading
    mih = config.migration_handler(connect=False, schema=1, verbosity=1)
    mih.restore_database(backupfile, drop, systemonly, askconfirm=False)
    repo = mih.repo_connect()
    # version of the database
    dbversions = repo.get_versions()
    mih.shutdown()
    if not dbversions:
        print "bad or missing version information in the database, don't upgrade file system"
        return
    # version of installed software
    eversion = dbversions['cubicweb']
    status = instance_status(config, eversion, dbversions)
    # * database version > installed software
    if status == 'needsoftupgrade':
        print "** The database of %s is more recent than the installed software!" % config.appid
        print "** Upgrade your software, then migrate the database by running the command"
        print "** 'cubicweb-ctl upgrade %s'" % config.appid
        return
    # * database version < installed software, an upgrade will be necessary
    #   anyway, just rewrite vc.conf and warn user he has to upgrade
    elif status == 'needapplupgrade':
        print "** The database of %s is older than the installed software." % config.appid
        print "** Migrate the database by running the command"
        print "** 'cubicweb-ctl upgrade %s'" % config.appid
        return
    # * database version = installed software, database version = instance fs version
    #   ok!

def instance_status(config, cubicwebapplversion, vcconf):
    cubicwebversion = config.cubicweb_version()
    if cubicwebapplversion > cubicwebversion:
        return 'needsoftupgrade'
    if cubicwebapplversion < cubicwebversion:
        return 'needapplupgrade'
    for cube in config.cubes():
        try:
            softversion = config.cube_version(cube)
        except ConfigurationError:
            print '-> Error: no cube version information for %s, please check that the cube is installed.' % cube
            continue
        try:
            applversion = vcconf[cube]
        except KeyError:
            print '-> Error: no cube version information for %s in version configuration.' % cube
            continue
        if softversion == applversion:
            continue
        if softversion > applversion:
            return 'needsoftupgrade'
        elif softversion < applversion:
            return 'needapplupgrade'
    return None


class DBDumpCommand(Command):
    """Backup the system database of an instance.

    <instance>
      the identifier of the instance to backup
      format [[user@]host:]appname
    """
    name = 'db-dump'
    arguments = '<instance>'

    options = (
        ('output',
         {'short': 'o', 'type' : 'string', 'metavar' : '<file>',
          'default' : None,
          'help': 'Specify the backup file where the backup will be stored.'}
         ),
        ('sudo',
         {'short': 's', 'action' : 'store_true',
          'default' : False,
          'help': 'Use sudo on the remote host.'}
         ),
        )

    def run(self, args):
        appid = pop_arg(args, 1, msg='No instance specified !')
        if ':' in appid:
            host, appid = appid.split(':')
            _remote_dump(host, appid, self.config.output, self.config.sudo)
        else:
            _local_dump(appid, self.config.output)


class DBRestoreCommand(Command):
    """Restore the system database of an instance.

    <instance>
      the identifier of the instance to restore
    """
    name = 'db-restore'
    arguments = '<instance> <backupfile>'

    options = (
        ('no-drop',
         {'short': 'n', 'action' : 'store_true', 'default' : False,
          'help': 'for some reason the database doesn\'t exist and so '
          'should not be dropped.'}
         ),
        ('restore-all',
         {'short': 'r', 'action' : 'store_true', 'default' : False,
          'help': 'restore everything, eg not only the system source database '
          'but also data for all sources supporting backup/restore and custom '
          'instance data. In that case, <backupfile> is expected to be the '
          'timestamp of the backup to restore, not a file'}
         ),
        )

    def run(self, args):
        appid = pop_arg(args, 1, msg='No instance specified !')
        backupfile = pop_arg(args, msg='No backup file or timestamp specified !')
        _local_restore(appid, backupfile,
                       drop=not self.config.no_drop,
                       systemonly=not self.config.restore_all)


class DBCopyCommand(Command):
    """Copy the system database of an instance (backup and restore).

    <src-instance>
      the identifier of the instance to backup
      format [[user@]host:]appname

    <dest-instance>
      the identifier of the instance to restore
    """
    name = 'db-copy'
    arguments = '<src-instance> <dest-instance>'

    options = (
        ('no-drop',
         {'short': 'n', 'action' : 'store_true',
          'default' : False,
          'help': 'For some reason the database doesn\'t exist and so '
          'should not be dropped.'}
         ),
        ('keep-dump',
         {'short': 'k', 'action' : 'store_true',
          'default' : False,
          'help': 'Specify that the dump file should not be automatically removed.'}
         ),
        ('sudo',
         {'short': 's', 'action' : 'store_true',
          'default' : False,
          'help': 'Use sudo on the remote host.'}
         ),
        )

    def run(self, args):
        import tempfile
        srcappid = pop_arg(args, 1, msg='No source instance specified !')
        destappid = pop_arg(args, msg='No destination instance specified !')
        fd, output = tempfile.mkstemp()
        os.close(fd)
        if ':' in srcappid:
            host, srcappid = srcappid.split(':')
            _remote_dump(host, srcappid, output, self.config.sudo)
        else:
            _local_dump(srcappid, output)
        _local_restore(destappid, output, not self.config.no_drop)
        if self.config.keep_dump:
            print '-> you can get the dump file at', output
        else:
            os.remove(output)


class CheckRepositoryCommand(Command):
    """Check integrity of the system database of an instance.

    <instance>
      the identifier of the instance to check
    """
    name = 'db-check'
    arguments = '<instance>'

    options = (
        ('checks',
         {'short': 'c', 'type' : 'csv', 'metavar' : '<check list>',
          'default' : ('entities', 'relations', 'metadata', 'schema', 'text_index'),
          'help': 'Comma separated list of check to run. By default run all \
checks, i.e. entities, relations, text_index and metadata.'}
         ),

        ('autofix',
         {'short': 'a', 'type' : 'yn', 'metavar' : '<yes or no>',
          'default' : False,
          'help': 'Automatically correct integrity problems if this option \
is set to "y" or "yes", else only display them'}
         ),
        ('reindex',
         {'short': 'r', 'type' : 'yn', 'metavar' : '<yes or no>',
          'default' : False,
          'help': 're-indexes the database for full text search if this \
option is set to "y" or "yes" (may be long for large database).'}
         ),
        ('force',
         {'short': 'f', 'action' : 'store_true',
          'default' : False,
          'help': 'don\'t check instance is up to date.'}
         ),

        )

    def run(self, args):
        from cubicweb.server.checkintegrity import check
        appid = pop_arg(args, 1, msg='No instance specified !')
        config = ServerConfiguration.config_for(appid)
        config.repairing = self.config.force
        repo, cnx = repo_cnx(config)
        check(repo, cnx,
              self.config.checks, self.config.reindex, self.config.autofix)


class RebuildFTICommand(Command):
    """Rebuild the full-text index of the system database of an instance.

    <instance>
      the identifier of the instance to rebuild
    """
    name = 'db-rebuild-fti'
    arguments = '<instance>'

    options = ()

    def run(self, args):
        from cubicweb.server.checkintegrity import reindex_entities
        appid = pop_arg(args, 1, msg='No instance specified !')
        config = ServerConfiguration.config_for(appid)
        repo, cnx = repo_cnx(config)
        session = repo._get_session(cnx.sessionid, setpool=True)
        reindex_entities(repo.schema, session)
        cnx.commit()


class SynchronizeInstanceSchemaCommand(Command):
    """Synchronize persistent schema with cube schema.

    Will synchronize common stuff between the cube schema and the
    actual persistent schema, but will not add/remove any entity or relation.

    <instance>
      the identifier of the instance to synchronize.
    """
    name = 'schema-sync'
    arguments = '<instance>'

    def run(self, args):
        appid = pop_arg(args, msg='No instance specified !')
        config = ServerConfiguration.config_for(appid)
        mih = config.migration_handler()
        mih.cmd_synchronize_schema()


register_commands( (CreateInstanceDBCommand,
                    InitInstanceCommand,
                    GrantUserOnInstanceCommand,
                    ResetAdminPasswordCommand,
                    StartRepositoryCommand,
                    DBDumpCommand,
                    DBRestoreCommand,
                    DBCopyCommand,
                    CheckRepositoryCommand,
                    RebuildFTICommand,
                    SynchronizeInstanceSchemaCommand,
                    ) )
