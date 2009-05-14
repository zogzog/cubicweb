"""Server subcube of cubicweb : defines objects used only on the server
(repository) side

This module contains functions to initialize a new repository.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
from os.path import join, exists

from logilab.common.modutils import LazyObject

# server debugging flag
DEBUG = False

def init_repository(config, interactive=True, drop=False, vreg=None):
    """initialise a repository database by creating tables add filling them
    with the minimal set of entities (ie at least the schema, base groups and
    a initial user)
    """
    from glob import glob
    from cubicweb.schema import BASEGROUPS
    from cubicweb.dbapi import in_memory_cnx
    from cubicweb.server.repository import Repository
    from cubicweb.server.utils import manager_userpasswd
    from cubicweb.server.sqlutils import sqlexec, sqlschema, sqldropschema
    # configuration to avoid db schema loading and user'state checking
    # on connection
    read_application_schema = config.read_application_schema
    bootstrap_schema = config.bootstrap_schema
    config.read_application_schema = False
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
    print 'creating necessary tables into the system source'
    source = sourcescfg['system']
    driver = source['db-driver']
    sqlcnx = repo.system_source.get_connection()
    sqlcursor = sqlcnx.cursor()
    def execute(sql, args=None):
        repo.system_source.doexec(sqlcursor, sql, args)
    if drop:
        dropsql = sqldropschema(schema, driver)
        try:
            sqlexec(dropsql, execute)
        except Exception, ex:
            print 'drop failed, skipped (%s)' % ex
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
    sqlexec(schemasql, execute)
    # install additional driver specific sql files
    for fpath in glob(join(config.schemas_lib_dir(), '*.sql.%s' % driver)):
        print 'install', fpath
        sqlexec(open(fpath).read(), execute, False, delimiter=';;')
    for directory in config.cubes_path():
        for fpath in glob(join(directory, 'schema', '*.sql.%s' % driver)):
            print 'install', fpath
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
    print 'inserting default user and groups'
    needisfix = []
    for group in BASEGROUPS:
        rset = session.execute('INSERT CWGroup X: X name %(name)s',
                               {'name': unicode(group)})
        needisfix.append( (rset.rows[0][0], rset.description[0][0]) )
    rset = session.execute('INSERT CWUser X: X login %(login)s, X upassword %(pwd)s',
                           {'login': login, 'pwd': pwd})
    needisfix.append( (rset.rows[0][0], rset.description[0][0]) )
    session.execute('SET U in_group G WHERE G name "managers"')
    session.commit()
    # reloging using the admin user
    config._cubes = None # avoid assertion error
    repo, cnx = in_memory_cnx(config, login, pwd)
    assert len(repo.sources) == 1, repo.sources
    handler = config.migration_handler(schema, interactive=False,
                                       cnx=cnx, repo=repo)
    initialize_schema(config, schema, handler)
    # admin user and groups have been added before schema entities, fix the 'is'
    # relation
    for eid, etype in needisfix:
        handler.session.unsafe_execute('SET X is E WHERE X eid %(x)s, E name %(name)s',
                                       {'x': eid, 'name': etype}, 'x')
        handler.session.unsafe_execute('SET X is_instance_of E WHERE X eid %(x)s, E name %(name)s',
                                       {'x': eid, 'name': etype}, 'x')
    # insert versions
    handler.cmd_add_entity('CWProperty', pkey=u'system.version.cubicweb',
                           value=unicode(config.cubicweb_version()))
    for cube in config.cubes():
        handler.cmd_add_entity('CWProperty', 
                               pkey=u'system.version.%s' % cube.lower(),
                               value=unicode(config.cube_version(cube)))
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
    config.read_application_schema = read_application_schema
    config.bootstrap_schema = bootstrap_schema
    config.consider_user_state = True
    config.set_language = True
    print 'application %s initialized' % config.appid


def initialize_schema(config, schema, mhandler, event='create'):
    from cubicweb.server.schemaserial import serialize_schema
    paths = [p for p in config.cubes_path() + [config.apphome]
             if exists(join(p, 'migration'))]
    # execute cubicweb's pre<event> script
    mhandler.exec_event_script('pre%s' % event)
    # execute cubes pre<event> script if any
    for path in reversed(paths):
        mhandler.exec_event_script('pre%s' % event, path)
    # enter application'schema into the database
    serialize_schema(mhandler.rqlcursor, schema)
    # execute cubicweb's post<event> script
    mhandler.exec_event_script('post%s' % event)
    # execute cubes'post<event> script if any
    for path in reversed(paths):
        mhandler.exec_event_script('post%s' % event, path)

def set_debug(debugmode):
    global DEBUG
    DEBUG = debugmode

def debugged(func):
    """decorator to activate debug mode"""
    def wrapped(*args, **kwargs):
        global DEBUG
        DEBUG = True
        try:
            return func(*args, **kwargs)
        finally:
            DEBUG = False
    return wrapped

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
