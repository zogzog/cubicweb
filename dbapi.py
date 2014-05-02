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
"""DB-API 2.0 compliant module

Take a look at http://www.python.org/peps/pep-0249.html

(most parts of this document are reported here in docstrings)
"""

__docformat__ = "restructuredtext en"

from threading import currentThread
from logging import getLogger
from time import time, clock
from itertools import count
from warnings import warn
from os.path import join
from uuid import uuid4
from urlparse import  urlparse

from logilab.common.logging_ext import set_log_methods
from logilab.common.decorators import monkeypatch, cachedproperty
from logilab.common.deprecation import deprecated

from cubicweb import (ETYPE_NAME_MAP, AuthenticationError, ProgrammingError,
                      cwvreg, cwconfig)
from cubicweb.repoapi import get_repository
from cubicweb.req import RequestSessionBase


_MARKER = object()

def _fake_property_value(self, name):
    try:
        return super(DBAPIRequest, self).property_value(name)
    except KeyError:
        return ''

def fake(*args, **kwargs):
    return None

def multiple_connections_fix():
    """some monkey patching necessary when an application has to deal with
    several connections to different repositories. It tries to hide buggy class
    attributes since classes are not designed to be shared among multiple
    registries.
    """
    defaultcls = cwvreg.CWRegistryStore.REGISTRY_FACTORY[None]

    etypescls = cwvreg.CWRegistryStore.REGISTRY_FACTORY['etypes']
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
    etypescls = cwvreg.CWRegistryStore.REGISTRY_FACTORY['etypes']
    etypescls.etype_class = etypescls.orig_etype_class


class ConnectionProperties(object):
    def __init__(self, cnxtype=None, close=True, log=False):
        if cnxtype is not None:
            warn('[3.16] cnxtype argument is deprecated', DeprecationWarning,
                 stacklevel=2)
        self.cnxtype = cnxtype
        self.log_queries = log
        self.close_on_del = close


@deprecated('[3.19] the dbapi is deprecated. Have a look at the new repoapi.')
def _repo_connect(repo, login, **kwargs):
    """Constructor to create a new connection to the given CubicWeb repository.

    Returns a Connection instance.

    Raises AuthenticationError if authentication failed
    """
    cnxid = repo.connect(unicode(login), **kwargs)
    cnx = Connection(repo, cnxid, kwargs.get('cnxprops'))
    if cnx.is_repo_in_memory:
        cnx.vreg = repo.vreg
    return cnx

def connect(database, login=None,
            cnxprops=None, setvreg=True, mulcnx=True, initlog=True, **kwargs):
    """Constructor for creating a connection to the CubicWeb repository.
    Returns a :class:`Connection` object.

    Typical usage::

      cnx = connect('myinstance', login='me', password='toto')

    `database` may be:

    * a simple instance id for in-memory connection

    * a uri like scheme://host:port/instanceid where scheme may be one of
      'pyro', 'inmemory' or 'zmqpickle'

      * if scheme is 'pyro', <host:port> determine the name server address. If
        not specified (e.g. 'pyro:///instanceid'), it will be detected through a
        broadcast query. The instance id is the name of the instance in the name
        server and may be prefixed by a group (e.g.
        'pyro:///:cubicweb.instanceid')

      * if scheme is handled by ZMQ (eg 'tcp'), you should not specify an
        instance id

    Other arguments:

    :login:
      the user login to use to authenticate.

    :cnxprops:
      a :class:`ConnectionProperties` instance, allowing to specify
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
      there goes authentication tokens. You usually have to specify a password
      for the given user, using a named 'password' argument.
    """
    if not urlparse(database).scheme:
        warn('[3.16] give an qualified URI as database instead of using '
             'host/cnxprops to specify the connection method',
             DeprecationWarning, stacklevel=2)
        if cnxprops and cnxprops.cnxtype == 'zmq':
            database = kwargs.pop('host')
        elif cnxprops and cnxprops.cnxtype == 'inmemory':
            database = 'inmemory://' + database
        else:
            host = kwargs.pop('host', None)
            if host is None:
                host = ''
            group = kwargs.pop('group', None)
            if group is None:
                group = 'cubicweb'
            database = 'pyro://%s/%s.%s' % (host, group, database)
    puri = urlparse(database)
    method = puri.scheme.lower()
    if method == 'inmemory':
        config = cwconfig.instance_configuration(puri.netloc)
    else:
        config = cwconfig.CubicWebNoAppConfiguration()
    repo = get_repository(database, config=config)
    if method == 'inmemory':
        vreg = repo.vreg
    elif setvreg:
        if mulcnx:
            multiple_connections_fix()
        vreg = cwvreg.CWRegistryStore(config, initlog=initlog)
        schema = repo.get_schema()
        for oldetype, newetype in ETYPE_NAME_MAP.items():
            if oldetype in schema:
                print 'aliasing', newetype, 'to', oldetype
                schema._entities[newetype] = schema._entities[oldetype]
        vreg.set_schema(schema)
    else:
        vreg = None
    cnx = _repo_connect(repo, login, cnxprops=cnxprops, **kwargs)
    cnx.vreg = vreg
    return cnx

def in_memory_repo(config):
    """Return and in_memory Repository object from a config (or vreg)"""
    if isinstance(config, cwvreg.CWRegistryStore):
        vreg = config
        config = None
    else:
        vreg = None
    # get local access to the repository
    return get_repository('inmemory://', config=config, vreg=vreg)

def in_memory_repo_cnx(config, login, **kwargs):
    """useful method for testing and scripting to get a dbapi.Connection
    object connected to an in-memory repository instance
    """
    # connection to the CubicWeb repository
    repo = in_memory_repo(config)
    return repo, _repo_connect(repo, login, **kwargs)

# XXX web only method, move to webconfig?
def anonymous_session(vreg):
    """return a new anonymous session

    raises an AuthenticationError if anonymous usage is not allowed
    """
    anoninfo = vreg.config.anonymous_user()
    if anoninfo[0] is None: # no anonymous user
        raise AuthenticationError('anonymous access is not authorized')
    anon_login, anon_password = anoninfo
    # use vreg's repository cache
    repo = vreg.config.repository(vreg)
    anon_cnx = _repo_connect(repo, anon_login, password=anon_password)
    anon_cnx.vreg = vreg
    return DBAPISession(anon_cnx, anon_login)


class _NeedAuthAccessMock(object):
    def __getattribute__(self, attr):
        raise AuthenticationError()
    def __nonzero__(self):
        return False

class DBAPISession(object):
    def __init__(self, cnx, login=None):
        self.cnx = cnx
        self.data = {}
        self.login = login
        # dbapi session identifier is the same as the first connection
        # identifier, but may later differ in case of auto-reconnection as done
        # by the web authentication manager (in cw.web.views.authentication)
        if cnx is not None:
            self.sessionid = cnx.sessionid
        else:
            self.sessionid = uuid4().hex

    @property
    def anonymous_session(self):
        return not self.cnx or self.cnx.anonymous_connection

    def __repr__(self):
        return '<DBAPISession %r>' % self.sessionid


class DBAPIRequest(RequestSessionBase):
    #: Request language identifier eg: 'en'
    lang = None

    def __init__(self, vreg, session=None):
        super(DBAPIRequest, self).__init__(vreg)
        #: 'language' => translation_function() mapping
        try:
            # no vreg or config which doesn't handle translations
            self.translations = vreg.config.translations
        except AttributeError:
            self.translations = {}
        #: cache entities built during the request
        self._eid_cache = {}
        if session is not None:
            self.set_session(session)
        else:
            # these args are initialized after a connection is
            # established
            self.session = DBAPISession(None)
            self.cnx = self.user = _NeedAuthAccessMock()
        self.set_default_language(vreg)

    def get_option_value(self, option, foreid=None):
        if foreid is not None:
            warn('[3.19] foreid argument is deprecated', DeprecationWarning,
                 stacklevel=2)
        return self.cnx.get_option_value(option)

    def set_session(self, session):
        """method called by the session handler when the user is authenticated
        or an anonymous connection is open
        """
        self.session = session
        if session.cnx:
            self.cnx = session.cnx
            self.execute = session.cnx.cursor(self).execute
            self.user = self.cnx.user(self)
            self.set_entity_cache(self.user)

    def execute(self, *args, **kwargs): # pylint: disable=E0202
        """overriden when session is set. By default raise authentication error
        so authentication is requested.
        """
        raise AuthenticationError()

    def set_default_language(self, vreg):
        try:
            lang = vreg.property_value('ui.language')
        except Exception: # property may not be registered
            lang = 'en'
        try:
            self.set_language(lang)
        except KeyError:
            # this occurs usually during test execution
            self._ = self.__ = unicode
            self.pgettext = lambda x, y: unicode(y)

    # server-side service call #################################################

    def call_service(self, regid, **kwargs):
        return self.cnx.call_service(regid, **kwargs)

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

    @deprecated('[3.19] use session or transaction data')
    def get_shared_data(self, key, default=None, pop=False, txdata=False):
        """see :meth:`Connection.get_shared_data`"""
        return self.cnx.get_shared_data(key, default, pop, txdata)

    @deprecated('[3.19] use session or transaction data')
    def set_shared_data(self, key, value, txdata=False, querydata=None):
        """see :meth:`Connection.set_shared_data`"""
        if querydata is not None:
            txdata = querydata
            warn('[3.10] querydata argument has been renamed to txdata',
                 DeprecationWarning, stacklevel=2)
        return self.cnx.set_shared_data(key, value, txdata)

    # server session compat layer #############################################

    def entity_metas(self, eid):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        return self.cnx.entity_metas(eid)

    def source_defs(self):
        """return the definition of sources used by the repository."""
        return self.cnx.source_defs()

    @deprecated('[3.19] use .entity_metas(eid) instead')
    def describe(self, eid, asdict=False):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        return self.cnx.describe(eid, asdict)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

set_log_methods(DBAPIRequest, getLogger('cubicweb.dbapi'))



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

    def _txid(self):
        return self.connection._txid(self)

    def execute(self, rql, args=None, build_descr=True):
        """execute a rql query, return resulting rows and their description in
        a :class:`~cubicweb.rset.ResultSet` object

        * `rql` should be a Unicode string or a plain ASCII string, containing
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
        rset = self._repo.execute(self._sessid, rql, args,
                                  build_descr=build_descr, **self._txid())
        rset.req = self.req
        return rset


class LogCursor(Cursor):
    """override the standard cursor to log executed queries"""

    def execute(self, operation, parameters=None, build_descr=True):
        """override the standard cursor to log executed queries"""
        tstart, cstart = time(), clock()
        rset = Cursor.execute(self, operation, parameters, build_descr=build_descr)
        self.connection.executed_queries.append((operation, parameters,
                                                 time() - tstart, clock() - cstart))
        return rset

def check_not_closed(func):
    def decorator(self, *args, **kwargs):
        if self._closed is not None:
            raise ProgrammingError('Closed connection %s' % self.sessionid)
        return func(self, *args, **kwargs)
    return decorator

class Connection(object):
    """DB-API 2.0 compatible Connection object for CubicWeb
    """
    # make exceptions available through the connection object
    ProgrammingError = ProgrammingError
    # attributes that may be overriden per connection instance
    cursor_class = Cursor
    vreg = None
    _closed = None

    def __init__(self, repo, cnxid, cnxprops=None):
        self._repo = repo
        self.sessionid = cnxid
        self._close_on_del = getattr(cnxprops, 'close_on_del', True)
        self._web_request = False
        if cnxprops and cnxprops.log_queries:
            self.executed_queries = []
            self.cursor_class = LogCursor

    @property
    def is_repo_in_memory(self):
        """return True if this is a local, aka in-memory, connection to the
        repository
        """
        try:
            from cubicweb.server.repository import Repository
        except ImportError:
            # code not available, no way
            return False
        return isinstance(self._repo, Repository)

    @property # could be a cached property but we want to prevent assigment to
              # catch potential programming error.
    def anonymous_connection(self):
        login = self._repo.user_info(self.sessionid)[1]
        anon_login = self.vreg.config.get('anonymous-user')
        return login == anon_login

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

    def __del__(self):
        """close the remote connection if necessary"""
        if self._closed is None and self._close_on_del:
            try:
                self.close()
            except Exception:
                pass

    # server-side service call #################################################

    @check_not_closed
    def call_service(self, regid, **kwargs):
        return self._repo.call_service(self.sessionid, regid, **kwargs)

    # connection initialization methods ########################################

    def load_appobjects(self, cubes=_MARKER, subpath=None, expand=True):
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
            esubpath.append(join('web', 'views'))
        # first load available configs, necessary for proper persistent
        # properties initialization
        config.load_available_configs()
        # then init cubes
        config.init_cubes(cubes)
        # then load appobjects into the registry
        vpath = config.build_appobjects_path(reversed(config.cubes_path()),
                                             evobjpath=esubpath,
                                             tvobjpath=subpath)
        self.vreg.register_objects(vpath)

    def use_web_compatible_requests(self, baseurl, sitetitle=None):
        """monkey patch DBAPIRequest to fake a cw.web.request, so you should
        able to call html views using rset from a simple dbapi connection.

        You should call `load_appobjects` at some point to register those views.
        """
        DBAPIRequest.property_value = _fake_property_value
        DBAPIRequest.next_tabindex = count().next
        DBAPIRequest.relative_path = fake
        DBAPIRequest.url = fake
        DBAPIRequest.get_page_data = fake
        DBAPIRequest.set_page_data = fake
        # XXX could ask the repo for it's base-url configuration
        self.vreg.config.set_option('base-url', baseurl)
        self.vreg.config.uiprops = {}
        self.vreg.config.datadir_url = baseurl + '/data'
        # XXX why is this needed? if really needed, could be fetched by a query
        if sitetitle is not None:
            self.vreg['propertydefs']['ui.site-title'] = {'default': sitetitle}
        self._web_request = True

    def request(self):
        if self._web_request:
            from cubicweb.web.request import DBAPICubicWebRequestBase
            req = DBAPICubicWebRequestBase(self.vreg, False)
            req.get_header = lambda x, default=None: default
            req.set_session = lambda session: DBAPIRequest.set_session(
                req, session)
            req.relative_path = lambda includeparams=True: ''
        else:
            req = DBAPIRequest(self.vreg)
        req.set_session(DBAPISession(self))
        return req

    @check_not_closed
    def user(self, req=None, props=None):
        """return the User object associated to this connection"""
        # cnx validity is checked by the call to .user_info
        eid, login, groups, properties = self._repo.user_info(self.sessionid,
                                                              props)
        if req is None:
            req = self.request()
        rset = req.eid_rset(eid, 'CWUser')
        if self.vreg is not None and 'etypes' in self.vreg:
            user = self.vreg['etypes'].etype_class('CWUser')(
                req, rset, row=0, groups=groups, properties=properties)
        else:
            from cubicweb.entity import Entity
            user = Entity(req, rset, row=0)
        user.cw_attr_cache['login'] = login # cache login
        return user

    @check_not_closed
    def check(self):
        """raise `BadConnectionId` if the connection is no more valid, else
        return its latest activity timestamp.
        """
        return self._repo.check_session(self.sessionid)

    def _txid(self, cursor=None): # pylint: disable=E0202
        # XXX could now handle various isolation level!
        # return a dict as bw compat trick
        return {'txid': currentThread().getName()}

    # session data methods #####################################################

    @check_not_closed
    def get_shared_data(self, key, default=None, pop=False, txdata=False):
        """return value associated to key in the session's data dictionary or
        session's transaction's data if `txdata` is true.

        If pop is True, value will be removed from the dictionary.

        If key isn't defined in the dictionary, value specified by the
        `default` argument will be returned.
        """
        return self._repo.get_shared_data(self.sessionid, key, default, pop, txdata)

    @check_not_closed
    def set_shared_data(self, key, value, txdata=False):
        """set value associated to `key` in shared data

        if `txdata` is true, the value will be added to the repository
        session's query data which are cleared on commit/rollback of the current
        transaction.
        """
        return self._repo.set_shared_data(self.sessionid, key, value, txdata)

    # meta-data accessors ######################################################

    @check_not_closed
    def source_defs(self):
        """Return the definition of sources used by the repository."""
        return self._repo.source_defs()

    @check_not_closed
    def get_schema(self):
        """Return the schema currently used by the repository."""
        return self._repo.get_schema()

    @check_not_closed
    def get_option_value(self, option, foreid=None):
        """Return the value for `option` in the configuration.

        `foreid` argument is deprecated and now useless (as of 3.19).
        """
        if foreid is not None:
            warn('[3.19] foreid argument is deprecated', DeprecationWarning,
                 stacklevel=2)
        return self._repo.get_option_value(option)


    @check_not_closed
    def entity_metas(self, eid):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        try:
            return self._repo.entity_metas(self.sessionid, eid, **self._txid())
        except AttributeError:
            # talking to pre 3.19 repository
            metas = self._repo.describe(self.sessionid, eid, **self._txid())
            if len(metas) == 3: # even older backward compat
                metas = list(metas)
                metas.append(metas[1])
            return dict(zip(('type', 'source', 'extid', 'asource'), metas))


    @deprecated('[3.19] use .entity_metas(eid) instead')
    @check_not_closed
    def describe(self, eid, asdict=False):
        try:
            metas = self._repo.entity_metas(self.sessionid, eid, **self._txid())
        except AttributeError:
            metas = self._repo.describe(self.sessionid, eid, **self._txid())
            # talking to pre 3.19 repository
            if len(metas) == 3: # even older backward compat
                metas = list(metas)
                metas.append(metas[1])
            if asdict:
                return dict(zip(('type', 'source', 'extid', 'asource'), metas))
            return metas[:-1]
        if asdict:
            metas['asource'] = meta['source'] # XXX pre 3.19 client compat
            return metas
        return metas['type'], metas['source'], metas['extid']


    # db-api like interface ####################################################

    @check_not_closed
    def commit(self):
        """Commit pending transaction for this connection to the repository.

        may raises `Unauthorized` or `ValidationError` if we attempted to do
        something we're not allowed to for security or integrity reason.

        If the transaction is undoable, a transaction id will be returned.
        """
        return self._repo.commit(self.sessionid, **self._txid())

    @check_not_closed
    def rollback(self):
        """This method is optional since not all databases provide transaction
        support.

        In case a database does provide transactions this method causes the the
        database to roll back to the start of any pending transaction.  Closing
        a connection without committing the changes first will cause an implicit
        rollback to be performed.
        """
        self._repo.rollback(self.sessionid, **self._txid())

    @check_not_closed
    def cursor(self, req=None):
        """Return a new Cursor Object using the connection.

        On pyro connection, you should get cursor after calling if
        load_appobjects method if desired (which you should call if you intend
        to use ORM abilities).
        """
        if req is None:
            req = self.request()
        return self.cursor_class(self, self._repo, req=req)

    @check_not_closed
    def close(self):
        """Close the connection now (rather than whenever __del__ is called).

        The connection will be unusable from this point forward; an Error (or
        subclass) exception will be raised if any operation is attempted with
        the connection. The same applies to all cursor objects trying to use the
        connection.  Note that closing a connection without committing the
        changes first will cause an implicit rollback to be performed.
        """
        self._repo.close(self.sessionid, **self._txid())
        del self._repo # necessary for proper garbage collection
        self._closed = 1

    # undo support ############################################################

    @check_not_closed
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
        actionfilters.update(self._txid())
        txinfos = self._repo.undoable_transactions(self.sessionid, ueid,
                                                   **actionfilters)
        if req is None:
            req = self.request()
        for txinfo in txinfos:
            txinfo.req = req
        return txinfos

    @check_not_closed
    def transaction_info(self, txuuid, req=None):
        """Return transaction object for the given uid.

        raise `NoSuchTransaction` if not found or if session's user is not
        allowed (eg not in managers group and the transaction doesn't belong to
        him).
        """
        txinfo = self._repo.transaction_info(self.sessionid, txuuid,
                                             **self._txid())
        if req is None:
            req = self.request()
        txinfo.req = req
        return txinfo

    @check_not_closed
    def transaction_actions(self, txuuid, public=True):
        """Return an ordered list of action effectued during that transaction.

        If public is true, return only 'public' actions, eg not ones triggered
        under the cover by hooks, else return all actions.

        raise `NoSuchTransaction` if the transaction is not found or if
        session's user is not allowed (eg not in managers group and the
        transaction doesn't belong to him).
        """
        return self._repo.transaction_actions(self.sessionid, txuuid, public,
                                              **self._txid())

    @check_not_closed
    def undo_transaction(self, txuuid):
        """Undo the given transaction. Return potential restoration errors.

        raise `NoSuchTransaction` if not found or if session's user is not
        allowed (eg not in managers group and the transaction doesn't belong to
        him).
        """
        return self._repo.undo_transaction(self.sessionid, txuuid,
                                           **self._txid())

in_memory_cnx = deprecated('[3.16] use _repo_connect instead)')(_repo_connect)
