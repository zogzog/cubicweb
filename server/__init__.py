# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Server subcube of cubicweb : defines objects used only on the server
(repository) side

The server module contains functions to initialize a new repository.
"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

import sys
from os.path import join, exists
from glob import glob

from logilab.common.modutils import LazyObject
from logilab.common.textutils import splitstrip

from yams import BASE_GROUPS

from cubicweb import CW_SOFTWARE_ROOT

class ShuttingDown(BaseException):
    """raised when trying to access some resources while the repository is
    shutting down. Inherit from BaseException so that `except Exception` won't
    catch it.
    """

# server-side debugging #########################################################

# server debugging flags. They may be combined using binary operators.

#:no debug information
DBG_NONE = 0  #: no debug information
#: rql execution information
DBG_RQL  = 1
#: executed sql
DBG_SQL  = 2
#: repository events
DBG_REPO = 4
#: multi-sources
DBG_MS   = 8
#: more verbosity
DBG_MORE = 16
#: all level enabled
DBG_ALL  = DBG_RQL + DBG_SQL + DBG_REPO + DBG_MS + DBG_MORE

#: current debug mode
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
    """Context manager and decorator to help debug the repository.

    It can be used either as a context manager:

    >>> with debugged(server.DBG_RQL | server.DBG_REPO):
    ...     # some code in which you want to debug repository activity,
    ...     # seing information about RQL being executed an repository events.

    or as a function decorator:

    >>> @debugged(server.DBG_RQL | server.DBG_REPO)
    ... def some_function():
    ...     # some code in which you want to debug repository activity,
    ...     # seing information about RQL being executed an repository events

    The debug mode will be reset to its original value when leaving the "with"
    block or the decorated function.
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

def create_user(session, login, pwd, *groups):
    # monkey patch this method if you want to customize admin/anon creation
    # (that maybe necessary if you change CWUser's schema)
    user = session.create_entity('CWUser', login=login, upassword=pwd)
    for group in groups:
        session.execute('SET U in_group G WHERE U eid %(u)s, G name %(group)s',
                        {'u': user.eid, 'group': group})
    return user

def init_repository(config, interactive=True, drop=False, vreg=None):
    """initialise a repository database by creating tables add filling them
    with the minimal set of entities (ie at least the schema, base groups and
    a initial user)
    """
    from cubicweb.dbapi import in_memory_repo_cnx
    from cubicweb.server.repository import Repository
    from cubicweb.server.utils import manager_userpasswd
    from cubicweb.server.sqlutils import sqlexec, sqlschema, sqldropschema
    # configuration to avoid db schema loading and user'state checking
    # on connection
    config.creating = True
    config.consider_user_state = False
    # only enable the system source at initialization time
    repo = Repository(config, vreg=vreg)
    schema = repo.schema
    sourcescfg = config.sources()
    source = sourcescfg['system']
    driver = source['db-driver']
    sqlcnx = repo.system_source.get_connection()
    sqlcursor = sqlcnx.cursor()
    execute = sqlcursor.execute
    if drop:
        _title = '-> drop tables '
        dropsql = sqldropschema(schema, driver)
        try:
            sqlexec(dropsql, execute, pbtitle=_title)
        except Exception, ex:
            print '-> drop failed, skipped (%s).' % ex
            sqlcnx.rollback()
    _title = '-> creating tables '
    print _title,
    # schema entities and relations tables
    # can't skip entities table even if system source doesn't support them,
    # they are used sometimes by generated sql. Keeping them empty is much
    # simpler than fixing this...
    schemasql = sqlschema(schema, driver)
    #skip_entities=[str(e) for e in schema.entities()
    #               if not repo.system_source.support_entity(str(e))])
    sqlexec(schemasql, execute, pbtitle=_title, delimiter=';;')
    sqlcursor.close()
    sqlcnx.commit()
    sqlcnx.close()
    session = repo.internal_session()
    # insert entity representing the system source
    ssource = session.create_entity('CWSource', type=u'native', name=u'system')
    repo.system_source.eid = ssource.eid
    session.execute('SET X cw_source X WHERE X eid %(x)s', {'x': ssource.eid})
    # insert base groups and default admin
    print '-> inserting default user and default groups.'
    try:
        login = unicode(sourcescfg['admin']['login'])
        pwd = sourcescfg['admin']['password']
    except KeyError:
        if interactive:
            msg = 'enter login and password of the initial manager account'
            login, pwd = manager_userpasswd(msg=msg, confirm=True)
        else:
            login, pwd = unicode(source['db-user']), source['db-password']
    # sort for eid predicatability as expected in some server tests
    for group in sorted(BASE_GROUPS):
        session.create_entity('CWGroup', name=unicode(group))
    admin = create_user(session, login, pwd, 'managers')
    session.execute('SET X owned_by U WHERE X is IN (CWGroup,CWSource), U eid %(u)s',
                    {'u': admin.eid})
    session.commit()
    session.close()
    repo.shutdown()
    # reloging using the admin user
    config._cubes = None # avoid assertion error
    repo, cnx = in_memory_repo_cnx(config, login, password=pwd)
    repo.system_source.eid = ssource.eid # redo this manually
    # trigger vreg initialisation of entity classes
    config.cubicweb_appobject_path = set(('entities',))
    config.cube_appobject_path = set(('entities',))
    repo.vreg.set_schema(repo.schema)
    assert len(repo.sources) == 1, repo.sources
    handler = config.migration_handler(schema, interactive=False,
                                       cnx=cnx, repo=repo)
    # install additional driver specific sql files
    handler.cmd_install_custom_sql_scripts()
    for cube in reversed(config.cubes()):
        handler.cmd_install_custom_sql_scripts(cube)
    # serialize the schema
    initialize_schema(config, schema, handler)
    # yoo !
    cnx.commit()
    repo.system_source.init_creating()
    cnx.commit()
    cnx.close()
    repo.shutdown()
    # restore initial configuration
    config.creating = False
    config.consider_user_state = True
    print '-> database for instance %s initialized.' % config.appid


def initialize_schema(config, schema, mhandler, event='create'):
    from cubicweb.server.schemaserial import serialize_schema
    from cubicweb.server.session import hooks_control
    session = mhandler.session
    cubes = config.cubes()
    # deactivate every hooks but those responsible to set metadata
    # so, NO INTEGRITY CHECKS are done, to have quicker db creation.
    # Active integrity is kept else we may pb such as two default
    # workflows for one entity type.
    with hooks_control(session, session.HOOKS_DENY_ALL, 'metadata',
                       'activeintegrity'):
        # execute cubicweb's pre<event> script
        mhandler.cmd_exec_event_script('pre%s' % event)
        # execute cubes pre<event> script if any
        for cube in reversed(cubes):
            mhandler.cmd_exec_event_script('pre%s' % event, cube)
        # execute instance's pre<event> script (useful in tests)
        mhandler.cmd_exec_event_script('pre%s' % event, apphome=True)
        # enter instance'schema into the database
        session.set_cnxset()
        serialize_schema(session, schema)
        # execute cubicweb's post<event> script
        mhandler.cmd_exec_event_script('post%s' % event)
        # execute cubes'post<event> script if any
        for cube in reversed(cubes):
            mhandler.cmd_exec_event_script('post%s' % event, cube)
        # execute instance's post<event> script (useful in tests)
        mhandler.cmd_exec_event_script('post%s' % event, apphome=True)


# sqlite'stored procedures have to be registered at connection opening time
from logilab.database import SQL_CONNECT_HOOKS

# add to this set relations which should have their add security checking done
# *BEFORE* adding the actual relation (done after by default)
BEFORE_ADD_RELATIONS = set(('owned_by',))

# add to this set relations which should have their add security checking done
# *at COMMIT TIME* (done after by default)
ON_COMMIT_ADD_RELATIONS = set(())

# available sources registry
SOURCE_TYPES = {'native': LazyObject('cubicweb.server.sources.native', 'NativeSQLSource'),
                'pyrorql': LazyObject('cubicweb.server.sources.pyrorql', 'PyroRQLSource'),
                'ldapuser': LazyObject('cubicweb.server.sources.ldapuser', 'LDAPUserSource'),
                'datafeed': LazyObject('cubicweb.server.sources.datafeed', 'DataFeedSource'),
                }
