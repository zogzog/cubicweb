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
"""DB-API 2.0 compliant module

Take a look at http://www.python.org/peps/pep-0249.html

(most parts of this document are reported here in docstrings)

"""
__docformat__ = "restructuredtext en"

from logging import getLogger
from time import time, clock
from itertools import count
from warnings import warn

from logilab.common.logging_ext import set_log_methods
from logilab.common.decorators import monkeypatch
from logilab.common.deprecation import deprecated

from cubicweb import ETYPE_NAME_MAP, ConnectionError, AuthenticationError,\
     cwvreg, cwconfig
from cubicweb.req import RequestSessionBase


_MARKER = object()

def _fake_property_value(self, name):
    try:
        return super(DBAPIRequest, self).property_value(name)
    except KeyError:
        return ''

def multiple_connections_fix():
    """some monkey patching necessary when an application has to deal with
    several connections to different repositories. It tries to hide buggy class
    attributes since classes are not designed to be shared among multiple
    registries.
    """
    defaultcls = cwvreg.VRegistry.REGISTRY_FACTORY[None]

    etypescls = cwvreg.VRegistry.REGISTRY_FACTORY['etypes']
    orig_etype_class = etypescls.orig_etype_class = etypescls.etype_class
    @monkeypatch(defaultcls)
    def etype_class(self, etype):
        """return an entity class for the given entity type.
        Try to find out a specific class for this kind of entity or
        default to a dump of the class registered for 'Any'
        """
        usercls = orig_etype_class(self, etype)
        if etype == 'Any':
            return usercls
        usercls.e_schema = self.schema.eschema(etype)
        return usercls

def multiple_connections_unfix():
    etypescls = cwvreg.VRegistry.REGISTRY_FACTORY['etypes']
    etypescls.etype_class = etypescls.orig_etype_class


class ConnectionProperties(object):
    def __init__(self, cnxtype=None, lang=None, close=True, log=False):
        self.cnxtype = cnxtype or 'pyro'
        self.lang = lang
        self.log_queries = log
        self.close_on_del = close


def get_repository(method, database=None, config=None, vreg=None):
    """get a proxy object to the CubicWeb repository, using a specific RPC method.

    Only 'in-memory' and 'pyro' are supported for now. Either vreg or config
    argument should be given
    """
    assert method in ('pyro', 'inmemory')
    assert vreg or config
    if vreg and not config:
        config = vreg.config
    if method == 'inmemory':
        # get local access to the repository
        from cubicweb.server.repository import Repository
        return Repository(config, vreg=vreg)
    else: # method == 'pyro'
        # resolve the Pyro object
        from logilab.common.pyro_ext import ns_get_proxy
        try:
            return ns_get_proxy(database,
                                defaultnsgroup=config['pyro-ns-group'],
                                nshost=config['pyro-ns-host'])
        except Exception, ex:
            raise ConnectionError(str(ex))

def repo_connect(repo, login, **kwargs):
    """Constructor to create a new connection to the CubicWeb repository.

    Returns a Connection instance.
    """
    if not 'cnxprops' in kwargs:
        kwargs['cnxprops'] = ConnectionProperties('inmemory')
    cnxid = repo.connect(unicode(login), **kwargs)
    cnx = Connection(repo, cnxid, kwargs['cnxprops'])
    if kwargs['cnxprops'].cnxtype == 'inmemory':
        cnx.vreg = repo.vreg
    return cnx

def connect(database=None, login=None, host=None, group=None,
            cnxprops=None, setvreg=True, mulcnx=True, initlog=True, **kwargs):
    """Constructor for creating a connection to the CubicWeb repository.
    Returns a :class:`Connection` object.

    Typical usage::

      cnx = connect('myinstance', login='me', password='toto')

    Arguments:

    :database:
      the instance's pyro identifier.

    :login:
      the user login to use to authenticate.

    :host:
      the pyro nameserver host. Will be detected using broadcast query if
      unspecified.

    :group:
      the instance's pyro nameserver group. You don't have to specify it unless
      tweaked in instance's configuration.

    :cnxprops:
      an optional :class:`ConnectionProperties` instance, allowing to specify
      the connection method (eg in memory or pyro). A Pyro connection will be
      established if you don't specify that argument.

    :setvreg:
      flag telling if a registry should be initialized for the connection.
      Don't change this unless you know what you're doing.

    :mulcnx:
      Will disappear at some point. Try to deal with connections to differents
      instances in the same process unless specified otherwise by setting this
      flag to False. Don't change this unless you know what you're doing.

    :initlog:
      flag telling if logging should be initialized. You usually don't want
      logging initialization when establishing the connection from a process
      where it's already initialized.

    :kwargs:
      there goes authentication tokens. You usually have to specify for
      instance a password for the given user, using a named 'password' argument.
    """
    config = cwconfig.CubicWebNoAppConfiguration()
    if host:
        config.global_set_option('pyro-ns-host', host)
    if group:
        config.global_set_option('pyro-ns-group', group)
    cnxprops = cnxprops or ConnectionProperties()
    method = cnxprops.cnxtype
    repo = get_repository(method, database, config=config)
    if method == 'inmemory':
        vreg = repo.vreg
    elif setvreg:
        if mulcnx:
            multiple_connections_fix()
        vreg = cwvreg.CubicWebVRegistry(config, initlog=initlog)
        schema = repo.get_schema()
        for oldetype, newetype in ETYPE_NAME_MAP.items():
            if oldetype in schema:
                print 'aliasing', newetype, 'to', oldetype
                schema._entities[newetype] = schema._entities[oldetype]
        vreg.set_schema(schema)
    else:
        vreg = None
    cnx = repo_connect(repo, login, cnxprops=cnxprops, **kwargs)
    cnx.vreg = vreg
    return cnx

def in_memory_cnx(config, login, **kwargs):
    """usefull method for testing and scripting to get a dbapi.Connection
    object connected to an in-memory repository instance
    """
    if isinstance(config, cwvreg.CubicWebVRegistry):
        vreg = config
        config = None
    else:
        vreg = None
    # get local access to the repository
    repo = get_repository('inmemory', config=config, vreg=vreg)
    # connection to the CubicWeb repository
    cnxprops = ConnectionProperties('inmemory')
    cnx = repo_connect(repo, login, cnxprops=cnxprops, **kwargs)
    return repo, cnx

class _NeedAuthAccessMock(object):
    def __getattribute__(self, attr):
        raise AuthenticationError()
    def __nonzero__(self):
        return False

class DBAPISession(object):
    def __init__(self, cnx, login=None, authinfo=None):
        self.cnx = cnx
        self.data = {}
        self.login = login
        self.authinfo = authinfo
        # dbapi session identifier is the same as the first connection
        # identifier, but may later differ in case of auto-reconnection as done
        # by the web authentication manager (in cw.web.views.authentication)
        if cnx is not None:
            self.sessionid = cnx.sessionid
        else:
            self.sessionid = None

    @property
    def anonymous_session(self):
        return not self.cnx or self.cnx.anonymous_connection


class DBAPIRequest(RequestSessionBase):

    def __init__(self, vreg, session=None):
        super(DBAPIRequest, self).__init__(vreg)
        try:
            # no vreg or config which doesn't handle translations
            self.translations = vreg.config.translations
        except AttributeError:
            self.translations = {}
        self.set_default_language(vreg)
        # cache entities built during the request
        self._eid_cache = {}
        if session is not None:
            self.set_session(session)
        else:
            # these args are initialized after a connection is
            # established
            self.session = None
            self.cnx = self.user = _NeedAuthAccessMock()

    def base_url(self):
        return self.vreg.config['base-url']

    def from_controller(self):
        return 'view'

    def set_session(self, session, user=None):
        """method called by the session handler when the user is authenticated
        or an anonymous connection is open
        """
        self.session = session
        if session.cnx:
            self.cnx = session.cnx
            self.execute = session.cnx.cursor(self).execute
            if user is None:
                user = self.cnx.user(self, {'lang': self.lang})
        if user is not None:
            self.user = user
            self.set_entity_cache(user)

    def execute(self, *args, **kwargs):
        """overriden when session is set. By default raise authentication error
        so authentication is requested.
        """
        raise AuthenticationError()

    def set_default_language(self, vreg):
        try:
            self.lang = vreg.property_value('ui.language')
        except: # property may not be registered
            self.lang = 'en'
        # use req.__ to translate a message without registering it to the catalog
        try:
            gettext, pgettext = self.translations[self.lang]
            self._ = self.__ = gettext
            self.pgettext = pgettext
        except KeyError:
            # this occurs usually during test execution
            self._ = self.__ = unicode
            self.pgettext = lambda x, y: y
        self.debug('request default language: %s', self.lang)

    # entities cache management ###############################################

    def entity_cache(self, eid):
        return self._eid_cache[eid]

    def set_entity_cache(self, entity):
        self._eid_cache[entity.eid] = entity

    def cached_entities(self):
        return self._eid_cache.values()

    def drop_entity_cache(self, eid=None):
        if eid is None:
            self._eid_cache = {}
        else:
            del self._eid_cache[eid]

    # low level session data management #######################################

    def get_shared_data(self, key, default=None, pop=False):
        """return value associated to `key` in shared data"""
        return self.cnx.get_shared_data(key, default, pop)

    def set_shared_data(self, key, value, querydata=False):
        """set value associated to `key` in shared data

        if `querydata` is true, the value will be added to the repository
        session's query data which are cleared on commit/rollback of the current
        transaction, and won't be available through the connexion, only on the
        repository side.
        """
        return self.cnx.set_shared_data(key, value, querydata)

    # server session compat layer #############################################

    def describe(self, eid):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        return self.cnx.describe(eid)

    def source_defs(self):
        """return the definition of sources used by the repository."""
        return self.cnx.source_defs()

    def hijack_user(self, user):
        """return a fake request/session using specified user"""
        req = DBAPIRequest(self.vreg)
        req.set_session(self.session, user)
        return req

    @deprecated('[3.8] use direct access to req.session.data dictionary')
    def session_data(self):
        """return a dictionnary containing session data"""
        return self.session.data

    @deprecated('[3.8] use direct access to req.session.data dictionary')
    def get_session_data(self, key, default=None, pop=False):
        if pop:
            return self.session.data.pop(key, default)
        return self.session.data.get(key, default)

    @deprecated('[3.8] use direct access to req.session.data dictionary')
    def set_session_data(self, key, value):
        self.session.data[key] = value

    @deprecated('[3.8] use direct access to req.session.data dictionary')
    def del_session_data(self, key):
        self.session.data.pop(key, None)


set_log_methods(DBAPIRequest, getLogger('cubicweb.dbapi'))


# exceptions ##################################################################

class ProgrammingError(Exception): #DatabaseError):
    """Exception raised for errors that are related to the database's operation
    and not necessarily under the control of the programmer, e.g. an unexpected
    disconnect occurs, the data source name is not found, a transaction could
    not be processed, a memory allocation error occurred during processing,
    etc.
    """


# cursor / connection objects ##################################################

class Cursor(object):
    """These objects represent a database cursor, which is used to manage the
    context of a fetch operation. Cursors created from the same connection are
    not isolated, i.e., any changes done to the database by a cursor are
    immediately visible by the other cursors. Cursors created from different
    connections are isolated.
    """

    def __init__(self, connection, repo, req=None):
        """This read-only attribute return a reference to the Connection
        object on which the cursor was created.
        """
        self.connection = connection
        """optionnal issuing request instance"""
        self.req = req
        self._repo = repo
        self._sessid = connection.sessionid

    def close(self):
        """no effect"""
        pass

    def execute(self, rql, args=None, eid_key=None, build_descr=True):
        """execute a rql query, return resulting rows and their description in
        a :class:`~cubicweb.rset.ResultSet` object

        * `rql` should be an Unicode string or a plain ASCII string, containing
          the rql query

        * `args` the optional args dictionary associated to the query, with key
          matching named substitution in `rql`

        * `build_descr` is a boolean flag indicating if the description should
          be built on select queries (if false, the description will be en empty
          list)

        on INSERT queries, there will be one row for each inserted entity,
        containing its eid

        on SET queries, XXX describe

        DELETE queries returns no result.

        .. Note::
          to maximize the rql parsing/analyzing cache performance, you should
          always use substitute arguments in queries, i.e. avoid query such as::

            execute('Any X WHERE X eid 123')

          use::

            execute('Any X WHERE X eid %(x)s', {'x': 123})
        """
        if eid_key is not None:
            warn('[3.8] eid_key is deprecated, you can safely remove this argument',
                 DeprecationWarning, stacklevel=2)
        # XXX use named argument for build_descr in case repo is < 3.8
        rset = self._repo.execute(self._sessid, rql, args, build_descr=build_descr)
        rset.req = self.req
        return rset


class LogCursor(Cursor):
    """override the standard cursor to log executed queries"""

    def execute(self, operation, parameters=None, eid_key=None, build_descr=True):
        """override the standard cursor to log executed queries"""
        if eid_key is not None:
            warn('[3.8] eid_key is deprecated, you can safely remove this argument',
                 DeprecationWarning, stacklevel=2)
        tstart, cstart = time(), clock()
        rset = Cursor.execute(self, operation, parameters, build_descr=build_descr)
        self.connection.executed_queries.append((operation, parameters,
                                                 time() - tstart, clock() - cstart))
        return rset


class Connection(object):
    """DB-API 2.0 compatible Connection object for CubicWeb
    """
    # make exceptions available through the connection object
    ProgrammingError = ProgrammingError
    # attributes that may be overriden per connection instance
    anonymous_connection = False
    cursor_class = Cursor
    vreg = None
    _closed = None

    def __init__(self, repo, cnxid, cnxprops=None):
        self._repo = repo
        self.sessionid = cnxid
        self._close_on_del = getattr(cnxprops, 'close_on_del', True)
        self._cnxtype = getattr(cnxprops, 'cnxtype', 'pyro')
        if cnxprops and cnxprops.log_queries:
            self.executed_queries = []
            self.cursor_class = LogCursor

    def __repr__(self):
        if self.anonymous_connection:
            return '<Connection %s (anonymous)>' % self.sessionid
        return '<Connection %s>' % self.sessionid

    def __enter__(self):
        return self.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
            return False #propagate the exception

    def request(self):
        return DBAPIRequest(self.vreg, DBAPISession(self))

    def check(self):
        """raise `BadConnectionId` if the connection is no more valid"""
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        self._repo.check_session(self.sessionid)

    def set_session_props(self, **props):
        """raise `BadConnectionId` if the connection is no more valid"""
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        self._repo.set_session_props(self.sessionid, props)

    def get_shared_data(self, key, default=None, pop=False):
        """return value associated to `key` in shared data"""
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        return self._repo.get_shared_data(self.sessionid, key, default, pop)

    def set_shared_data(self, key, value, querydata=False):
        """set value associated to `key` in shared data

        if `querydata` is true, the value will be added to the repository
        session's query data which are cleared on commit/rollback of the current
        transaction, and won't be available through the connexion, only on the
        repository side.
        """
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        return self._repo.set_shared_data(self.sessionid, key, value, querydata)

    def get_schema(self):
        """Return the schema currently used by the repository.

        This is NOT part of the DB-API.
        """
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        return self._repo.get_schema()

    def load_appobjects(self, cubes=_MARKER, subpath=None, expand=True,
                        force_reload=None):
        config = self.vreg.config
        if cubes is _MARKER:
            cubes = self._repo.get_cubes()
        elif cubes is None:
            cubes = ()
        else:
            if not isinstance(cubes, (list, tuple)):
                cubes = (cubes,)
            if expand:
                cubes = config.expand_cubes(cubes)
        if subpath is None:
            subpath = esubpath = ('entities', 'views')
        else:
            esubpath = subpath
        if 'views' in subpath:
            esubpath = list(subpath)
            esubpath.remove('views')
            esubpath.append('web/views')
        cubes = reversed([config.cube_dir(p) for p in cubes])
        vpath = config.build_vregistry_path(cubes, evobjpath=esubpath,
                                            tvobjpath=subpath)
        self.vreg.register_objects(vpath, force_reload)
        if self._cnxtype == 'inmemory':
            # should reinit hooks manager as well
            hm, config = self._repo.hm, self._repo.config
            hm.set_schema(hm.schema) # reset structure
            hm.register_system_hooks(config)
            # instance specific hooks
            if self._repo.config.instance_hooks:
                hm.register_hooks(config.load_hooks(self.vreg))

    def use_web_compatible_requests(self, baseurl, sitetitle=None):
        """monkey patch DBAPIRequest to fake a cw.web.request, so you should
        able to call html views using rset from a simple dbapi connection.

        You should call `load_appobjects` at some point to register those views.
        """
        from cubicweb.web.request import CubicWebRequestBase as cwrb
        DBAPIRequest.build_ajax_replace_url = cwrb.build_ajax_replace_url.im_func
        DBAPIRequest.list_form_param = cwrb.list_form_param.im_func
        DBAPIRequest.property_value = _fake_property_value
        DBAPIRequest.next_tabindex = count().next
        DBAPIRequest.form = {}
        DBAPIRequest.data = {}
        fake = lambda *args, **kwargs: None
        DBAPIRequest.relative_path = fake
        DBAPIRequest.url = fake
        DBAPIRequest.next_tabindex = fake
        DBAPIRequest.get_page_data = fake
        DBAPIRequest.set_page_data = fake
        DBAPIRequest.add_js = fake #cwrb.add_js.im_func
        DBAPIRequest.add_css = fake #cwrb.add_css.im_func
        # XXX could ask the repo for it's base-url configuration
        self.vreg.config.set_option('base-url', baseurl)
        # XXX why is this needed? if really needed, could be fetched by a query
        if sitetitle is not None:
            self.vreg['propertydefs']['ui.site-title'] = {'default': sitetitle}

    def source_defs(self):
        """Return the definition of sources used by the repository.

        This is NOT part of the DB-API.
        """
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        return self._repo.source_defs()

    def user(self, req=None, props=None):
        """return the User object associated to this connection"""
        # cnx validity is checked by the call to .user_info
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        eid, login, groups, properties = self._repo.user_info(self.sessionid,
                                                              props)
        if req is None:
            req = self.request()
        rset = req.eid_rset(eid, 'CWUser')
        if self.vreg is not None and 'etypes' in self.vreg:
            user = self.vreg['etypes'].etype_class('CWUser')(req, rset, row=0,
                                                             groups=groups,
                                                             properties=properties)
        else:
            from cubicweb.entity import Entity
            user = Entity(req, rset, row=0)
        user['login'] = login # cache login
        return user

    def __del__(self):
        """close the remote connection if necessary"""
        if self._closed is None and self._close_on_del:
            try:
                self.close()
            except:
                pass

    def describe(self, eid):
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        return self._repo.describe(self.sessionid, eid)

    def close(self):
        """Close the connection now (rather than whenever __del__ is called).

        The connection will be unusable from this point forward; an Error (or
        subclass) exception will be raised if any operation is attempted with
        the connection. The same applies to all cursor objects trying to use the
        connection.  Note that closing a connection without committing the
        changes first will cause an implicit rollback to be performed.
        """
        if self._closed:
            raise ProgrammingError('Connection is already closed')
        self._repo.close(self.sessionid)
        del self._repo # necessary for proper garbage collection
        self._closed = 1

    def commit(self):
        """Commit pending transaction for this connection to the repository.

        may raises `Unauthorized` or `ValidationError` if we attempted to do
        something we're not allowed to for security or integrity reason.

        If the transaction is undoable, a transaction id will be returned.
        """
        if not self._closed is None:
            raise ProgrammingError('Connection is already closed')
        return self._repo.commit(self.sessionid)

    def rollback(self):
        """This method is optional since not all databases provide transaction
        support.

        In case a database does provide transactions this method causes the the
        database to roll back to the start of any pending transaction.  Closing
        a connection without committing the changes first will cause an implicit
        rollback to be performed.
        """
        if not self._closed is None:
            raise ProgrammingError('Connection is already closed')
        self._repo.rollback(self.sessionid)

    def cursor(self, req=None):
        """Return a new Cursor Object using the connection.  If the database
        does not provide a direct cursor concept, the module will have to
        emulate cursors using other means to the extent needed by this
        specification.
        """
        if self._closed is not None:
            raise ProgrammingError('Can\'t get cursor on closed connection')
        if req is None:
            req = self.request()
        return self.cursor_class(self, self._repo, req=req)

    # undo support ############################################################

    def undoable_transactions(self, ueid=None, req=None, **actionfilters):
        """Return a list of undoable transaction objects by the connection's
        user, ordered by descendant transaction time.

        Managers may filter according to user (eid) who has done the transaction
        using the `ueid` argument. Others will only see their own transactions.

        Additional filtering capabilities is provided by using the following
        named arguments:

        * `etype` to get only transactions creating/updating/deleting entities
          of the given type

        * `eid` to get only transactions applied to entity of the given eid

        * `action` to get only transactions doing the given action (action in
          'C', 'U', 'D', 'A', 'R'). If `etype`, action can only be 'C', 'U' or
          'D'.

        * `public`: when additional filtering is provided, their are by default
          only searched in 'public' actions, unless a `public` argument is given
          and set to false.
        """
        txinfos = self._repo.undoable_transactions(self.sessionid, ueid,
                                                   **actionfilters)
        if req is None:
            req = self.request()
        for txinfo in txinfos:
            txinfo.req = req
        return txinfos

    def transaction_info(self, txuuid, req=None):
        """Return transaction object for the given uid.

        raise `NoSuchTransaction` if not found or if session's user is not
        allowed (eg not in managers group and the transaction doesn't belong to
        him).
        """
        txinfo = self._repo.transaction_info(self.sessionid, txuuid)
        if req is None:
            req = self.request()
        txinfo.req = req
        return txinfo

    def transaction_actions(self, txuuid, public=True):
        """Return an ordered list of action effectued during that transaction.

        If public is true, return only 'public' actions, eg not ones triggered
        under the cover by hooks, else return all actions.

        raise `NoSuchTransaction` if the transaction is not found or if
        session's user is not allowed (eg not in managers group and the
        transaction doesn't belong to him).
        """
        return self._repo.transaction_actions(self.sessionid, txuuid, public)

    def undo_transaction(self, txuuid):
        """Undo the given transaction. Return potential restoration errors.

        raise `NoSuchTransaction` if not found or if session's user is not
        allowed (eg not in managers group and the transaction doesn't belong to
        him).
        """
        return self._repo.undo_transaction(self.sessionid, txuuid)
