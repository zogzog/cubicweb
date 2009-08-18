"""Server subcube of cubicweb : defines objects used only on the server
(repository) side

This module contains functions to initialize a new repository.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
from os.path import join, exists
from glob import glob

from logilab.common.modutils import LazyObject
from logilab.common.textutils import splitstrip

from yams import BASE_GROUPS

from cubicweb import CW_SOFTWARE_ROOT

# server-side debugging #########################################################

# server debugging flags. They may be combined using binary operators.
DBG_NONE = 0  # no debug information
DBG_RQL = 1   # rql execution information
DBG_SQL = 2   # executed sql
DBG_REPO = 4  # repository events
DBG_MS = 8    # multi-sources
DBG_MORE = 16 # repository events

# current debug mode
DEBUG = 0

def set_debug(debugmode):
    """change the repository debugging mode"""
    global DEBUG
    if not debugmode:
        DEBUG = 0
        return
    if isinstance(debugmode, basestring):
        for mode in splitstrip(debugmode, sep='|'):
            DEBUG |= globals()[mode]
    else:
        DEBUG |= debugmode


class debugged(object):
    """repository debugging context manager / decorator

    Can be used either as a context manager:

    >>> with debugged(server.DBG_RQL | server.DBG_REPO):
    ...     # some code in which you want to debug repository activity,
    ...     # seing information about RQL being executed an repository events.

    or as a function decorator:

    >>> @debugged(server.DBG_RQL | server.DBG_REPO)
    ... def some_function():
    ...     # some code in which you want to debug repository activity,
    ...     # seing information about RQL being executed an repository events

    debug mode will be reseted at its original value when leaving the "with"
    block or the decorated function
    """
    def __init__(self, debugmode):
        self.debugmode = debugmode
        self._clevel = None

    def __enter__(self):
        """enter with block"""
        self._clevel = DEBUG
        set_debug(self.debugmode)

    def __exit__(self, exctype, exc, traceback):
        """leave with block"""
        set_debug(self._clevel)
        return traceback is None

    def __call__(self, func):
        """decorate function"""
        def wrapped(*args, **kwargs):
            _clevel = DEBUG
            set_debug(self.debugmode)
            try:
                return func(*args, **kwargs)
            finally:
                set_debug(self._clevel)
        return wrapped

# database initialization ######################################################

def init_repository(config, interactive=True, drop=False, vreg=None):
    """initialise a repository database by creating tables add filling them
    with the minimal set of entities (ie at least the schema, base groups and
    a initial user)
    """
    from cubicweb.dbapi import in_memory_cnx
    from cubicweb.server.repository import Repository
    from cubicweb.server.utils import manager_userpasswd
    from cubicweb.server.sqlutils import sqlexec, sqlschema, sqldropschema
    # configuration to avoid db schema loading and user'state checking
    # on connection
    read_instance_schema = config.read_instance_schema
    bootstrap_schema = config.bootstrap_schema
    config.read_instance_schema = False
    config.creating = True
    config.bootstrap_schema = True
    config.consider_user_state = False
    config.set_language = False
    # only enable the system source at initialization time + admin which is not
    # an actual source but contains initial manager account information
    config.enabled_sources = ('system', 'admin')
    repo = Repository(config, vreg=vreg)
    assert len(repo.sources) == 1, repo.sources
    schema = repo.schema
    sourcescfg = config.sources()
    _title = '-> creating tables '
    print _title,
    source = sourcescfg['system']
    driver = source['db-driver']
    sqlcnx = repo.system_source.get_connection()
    sqlcursor = sqlcnx.cursor()
    execute = sqlcursor.execute
    if drop:
        dropsql = sqldropschema(schema, driver)
        try:
            sqlexec(dropsql, execute)
        except Exception, ex:
            print '-> drop failed, skipped (%s).' % ex
            sqlcnx.rollback()
    # schema entities and relations tables
    # can't skip entities table even if system source doesn't support them,
    # they are used sometimes by generated sql. Keeping them empty is much
    # simpler than fixing this...
    if sqlcnx.logged_user != source['db-user']:
        schemasql = sqlschema(schema, driver, user=source['db-user'])
    else:
        schemasql = sqlschema(schema, driver)
        #skip_entities=[str(e) for e in schema.entities()
        #               if not repo.system_source.support_entity(str(e))])
    sqlexec(schemasql, execute, pbtitle=_title)
    # install additional driver specific sql files
    for fpath in glob(join(CW_SOFTWARE_ROOT, 'schemas', '*.sql.%s' % driver)):
        print '-> installing', fpath
        sqlexec(open(fpath).read(), execute, False, delimiter=';;')
    for directory in config.cubes_path():
        for fpath in glob(join(directory, 'schema', '*.sql.%s' % driver)):
            print '-> installing', fpath
            sqlexec(open(fpath).read(), execute, False, delimiter=';;')
    sqlcursor.close()
    sqlcnx.commit()
    sqlcnx.close()
    session = repo.internal_session()
    try:
        login = unicode(sourcescfg['admin']['login'])
        pwd = sourcescfg['admin']['password']
    except KeyError:
        if interactive:
            msg = 'enter login and password of the initial manager account'
            login, pwd = manager_userpasswd(msg=msg, confirm=True)
        else:
            login, pwd = unicode(source['db-user']), source['db-password']
    print '-> inserting default user and default groups.'
    # sort for eid predicatability as expected in some server tests
    for group in sorted(BASE_GROUPS):
        session.execute('INSERT CWGroup X: X name %(name)s',
                        {'name': unicode(group)})
    session.execute('INSERT CWUser X: X login %(login)s, X upassword %(pwd)s',
                    {'login': login, 'pwd': pwd})
    session.execute('SET U in_group G WHERE G name "managers"')
    session.commit()
    # reloging using the admin user
    config._cubes = None # avoid assertion error
    repo, cnx = in_memory_cnx(config, login, pwd)
    assert len(repo.sources) == 1, repo.sources
    handler = config.migration_handler(schema, interactive=False,
                                       cnx=cnx, repo=repo)
    initialize_schema(config, schema, handler)
    # insert versions
    handler.cmd_add_entity('CWProperty', pkey=u'system.version.cubicweb',
                           value=unicode(config.cubicweb_version()))
    for cube in config.cubes():
        handler.cmd_add_entity('CWProperty',
                               pkey=u'system.version.%s' % cube.lower(),
                               value=unicode(config.cube_version(cube)))
    # some entities have been added before schema entities, fix the 'is' and
    # 'is_instance_of' relations
    for rtype in ('is', 'is_instance_of'):
        handler.sqlexec(
            'INSERT INTO %s_relation '
            'SELECT X.eid, ET.cw_eid FROM entities as X, cw_CWEType as ET '
            'WHERE X.type=ET.cw_name AND NOT EXISTS('
            '      SELECT 1 from is_relation '
            '      WHERE eid_from=X.eid AND eid_to=ET.cw_eid)' % rtype)
    # yoo !
    cnx.commit()
    config.enabled_sources = None
    for uri, source_config in config.sources().items():
        if uri in ('admin', 'system'):
            # not an actual source or init_creating already called
            continue
        source = repo.get_source(uri, source_config)
        source.init_creating()
    cnx.commit()
    cnx.close()
    session.close()
    # restore initial configuration
    config.creating = False
    config.read_instance_schema = read_instance_schema
    config.bootstrap_schema = bootstrap_schema
    config.consider_user_state = True
    config.set_language = True
    print '-> database for instance %s initialized.' % config.appid


def initialize_schema(config, schema, mhandler, event='create'):
    from cubicweb.server.schemaserial import serialize_schema
    paths = [p for p in config.cubes_path() + [config.apphome]
             if exists(join(p, 'migration'))]
    # execute cubicweb's pre<event> script
    mhandler.exec_event_script('pre%s' % event)
    # execute cubes pre<event> script if any
    for path in reversed(paths):
        mhandler.exec_event_script('pre%s' % event, path)
    # enter instance'schema into the database
    serialize_schema(mhandler.session, schema)
    # execute cubicweb's post<event> script
    mhandler.exec_event_script('post%s' % event)
    # execute cubes'post<event> script if any
    for path in reversed(paths):
        mhandler.exec_event_script('post%s' % event, path)


# sqlite'stored procedures have to be registered at connexion opening time
SQL_CONNECT_HOOKS = {}

# add to this set relations which should have their add security checking done
# *BEFORE* adding the actual relation (done after by default)
BEFORE_ADD_RELATIONS = set(('owned_by',))

# add to this set relations which should have their add security checking done
# *at COMMIT TIME* (done after by default)
ON_COMMIT_ADD_RELATIONS = set(())

# available sources registry
SOURCE_TYPES = {'native': LazyObject('cubicweb.server.sources.native', 'NativeSQLSource'),
                # XXX private sources installed by an external cube
                'pyrorql': LazyObject('cubicweb.server.sources.pyrorql', 'PyroRQLSource'),
                'ldapuser': LazyObject('cubicweb.server.sources.ldapuser', 'LDAPUserSource'),
                }
