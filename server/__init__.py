# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

__docformat__ = "restructuredtext en"

import sys
from os.path import join, exists
from glob import glob
from contextlib import contextmanager

from logilab.common.modutils import LazyObject
from logilab.common.textutils import splitstrip
from logilab.common.registry import yes
from logilab import database

from yams import BASE_GROUPS

from cubicweb import CW_SOFTWARE_ROOT
from cubicweb.appobject import AppObject

class ShuttingDown(BaseException):
    """raised when trying to access some resources while the repository is
    shutting down. Inherit from BaseException so that `except Exception` won't
    catch it.
    """

# server-side services #########################################################

class Service(AppObject):
    """Base class for services.

    A service is a selectable object that performs an action server-side.
    Use :class:`cubicweb.dbapi.Connection.call_service` to call them from
    the web-side.

    When inheriting this class, do not forget to define at least the __regid__
    attribute (and probably __select__ too).
    """
    __registry__ = 'services'
    __select__ = yes()

    def call(self, **kwargs):
        raise NotImplementedError


# server-side debugging ########################################################

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
#: hooks
DBG_HOOKS = 16
#: operations
DBG_OPS = 32
#: security
DBG_SEC = 64
#: more verbosity
DBG_MORE = 128
#: all level enabled
DBG_ALL  = DBG_RQL + DBG_SQL + DBG_REPO + DBG_MS + DBG_HOOKS + DBG_OPS + DBG_SEC + DBG_MORE

_SECURITY_ITEMS = []
_SECURITY_CAPS = ['read', 'add', 'update', 'delete', 'transition']

#: current debug mode
DEBUG = 0

@contextmanager
def tunesecurity(items=(), capabilities=()):
    """Context manager to use in conjunction with DBG_SEC.

    This allows some tuning of:
    * the monitored capabilities ('read', 'add', ....)
    * the object being checked by the security checkers

    When no item is given, all of them will be watched.
    By default all capabilities are monitored, unless specified.

    Example use::

      from cubicweb.server import debugged, DBG_SEC, tunesecurity
      with debugged(DBG_SEC):
          with tunesecurity(items=('Elephant', 'trumps'),
                            capabilities=('update', 'delete')):
              babar.cw_set(trumps=celeste)
              flore.cw_delete()

      ==>

      check_perm: 'update' 'relation Elephant.trumps.Elephant'
       [(ERQLExpression(Any X WHERE U has_update_permission X, X eid %(x)s, U eid %(u)s),
       {'eid': 2167}, True)]
      check_perm: 'delete' 'Elephant'
       [(ERQLExpression(Any X WHERE U has_delete_permission X, X eid %(x)s, U eid %(u)s),
       {'eid': 2168}, True)]

    """
    olditems = _SECURITY_ITEMS[:]
    _SECURITY_ITEMS.extend(list(items))
    oldactions = _SECURITY_CAPS[:]
    _SECURITY_CAPS[:] = capabilities
    yield
    _SECURITY_ITEMS[:] = olditems
    _SECURITY_CAPS[:] = oldactions

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

    >>> with debugged('DBG_RQL | DBG_REPO'):
    ...     # some code in which you want to debug repository activity,
    ...     # seing information about RQL being executed an repository events.

    or as a function decorator:

    >>> @debugged('DBG_RQL | DBG_REPO')
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
                        {'u': user.eid, 'group': unicode(group)})
    return user

def init_repository(config, interactive=True, drop=False, vreg=None,
                    init_config=None):
    """initialise a repository database by creating tables add filling them
    with the minimal set of entities (ie at least the schema, base groups and
    a initial user)
    """
    from cubicweb.repoapi import get_repository, connect
    from cubicweb.server.repository import Repository
    from cubicweb.server.utils import manager_userpasswd
    from cubicweb.server.sqlutils import sqlexec, sqlschema, sql_drop_all_user_tables
    from cubicweb.server.sqlutils import _SQL_DROP_ALL_USER_TABLES_FILTER_FUNCTION as drop_filter
    # configuration to avoid db schema loading and user'state checking
    # on connection
    config.creating = True
    config.consider_user_state = False
    config.cubicweb_appobject_path = set(('hooks', 'entities'))
    config.cube_appobject_path = set(('hooks', 'entities'))
    # only enable the system source at initialization time
    repo = Repository(config, vreg=vreg)
    if init_config is not None:
        # further config initialization once it has been bootstrapped
        init_config(config)
    schema = repo.schema
    sourcescfg = config.read_sources_file()
    source = sourcescfg['system']
    driver = source['db-driver']
    sqlcnx = repo.system_source.get_connection()
    sqlcursor = sqlcnx.cursor()
    execute = sqlcursor.execute
    if drop:
        helper = database.get_db_helper(driver)
        dropsql = sql_drop_all_user_tables(helper, sqlcursor)
        # We may fail dropping some tables because of table dependencies, in a first pass.
        # So, we try a second drop sequence to drop remaining tables if needed.
        # Note that 2 passes is an arbitrary choice as it seems enougth for our usecases.
        # (looping may induce infinite recursion when user have no right for example)
        # Here we try to keep code simple and backend independant. That why we don't try to
        # distinguish remaining tables (wrong right, dependencies, ...).
        failed = sqlexec(dropsql, execute, cnx=sqlcnx,
                         pbtitle='-> dropping tables (first pass)')
        if failed:
            failed = sqlexec(failed, execute, cnx=sqlcnx,
                             pbtitle='-> dropping tables (second pass)')
            remainings = filter(drop_filter, helper.list_tables(sqlcursor))
            assert not remainings, 'Remaining tables: %s' % ', '.join(remainings)
    _title = '-> creating tables '
    print _title,
    # schema entities and relations tables
    # can't skip entities table even if system source doesn't support them,
    # they are used sometimes by generated sql. Keeping them empty is much
    # simpler than fixing this...
    schemasql = sqlschema(schema, driver)
    #skip_entities=[str(e) for e in schema.entities()
    #               if not repo.system_source.support_entity(str(e))])
    failed = sqlexec(schemasql, execute, pbtitle=_title, delimiter=';;')
    if failed:
        print 'The following SQL statements failed. You should check your schema.'
        print failed
        raise Exception('execution of the sql schema failed, you should check your schema')
    sqlcursor.close()
    sqlcnx.commit()
    sqlcnx.close()
    with repo.internal_cnx() as cnx:
        # insert entity representing the system source
        ssource = cnx.create_entity('CWSource', type=u'native', name=u'system')
        repo.system_source.eid = ssource.eid
        cnx.execute('SET X cw_source X WHERE X eid %(x)s', {'x': ssource.eid})
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
            cnx.create_entity('CWGroup', name=unicode(group))
        admin = create_user(cnx, login, pwd, 'managers')
        cnx.execute('SET X owned_by U WHERE X is IN (CWGroup,CWSource), U eid %(u)s',
                        {'u': admin.eid})
        cnx.commit()
    repo.shutdown()
    # reloging using the admin user
    config._cubes = None # avoid assertion error
    repo = get_repository(config=config)
    with connect(repo, login, password=pwd) as cnx:
        with cnx.security_enabled(False, False):
            repo.system_source.eid = ssource.eid # redo this manually
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
    repo.shutdown()
    # restore initial configuration
    config.creating = False
    config.consider_user_state = True
    # (drop instance attribute to get back to class attribute)
    del config.cubicweb_appobject_path
    del config.cube_appobject_path
    print '-> database for instance %s initialized.' % config.appid


def initialize_schema(config, schema, mhandler, event='create'):
    from cubicweb.server.schemaserial import serialize_schema
    cnx = mhandler.cnx
    cubes = config.cubes()
    # deactivate every hooks but those responsible to set metadata
    # so, NO INTEGRITY CHECKS are done, to have quicker db creation.
    # Active integrity is kept else we may pb such as two default
    # workflows for one entity type.
    with cnx.deny_all_hooks_but('metadata', 'activeintegrity'):
        # execute cubicweb's pre<event> script
        mhandler.cmd_exec_event_script('pre%s' % event)
        # execute cubes pre<event> script if any
        for cube in reversed(cubes):
            mhandler.cmd_exec_event_script('pre%s' % event, cube)
        # execute instance's pre<event> script (useful in tests)
        mhandler.cmd_exec_event_script('pre%s' % event, apphome=True)
        # enter instance'schema into the database
        serialize_schema(cnx, schema)
        cnx.commit()
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
                'datafeed': LazyObject('cubicweb.server.sources.datafeed', 'DataFeedSource'),
                'ldapfeed': LazyObject('cubicweb.server.sources.ldapfeed', 'LDAPFeedSource'),
                }
