"""DB-API 2.0 compliant module

Take a look at http://www.python.org/peps/pep-0249.html

(most parts of this document are reported here in docstrings)

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logging import getLogger
from time import time, clock

from logilab.common.logging_ext import set_log_methods
from cubicweb import ETYPE_NAME_MAP, ConnectionError, RequestSessionMixIn
from cubicweb.cwvreg import CubicWebRegistry, MulCnxCubicWebRegistry
from cubicweb.cwconfig import CubicWebNoAppConfiguration

_MARKER = object()

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
        from Pyro import core, naming
        from Pyro.errors import NamingError, ProtocolError
        core.initClient(banner=0)
        nsid = ':%s.%s' % (config['pyro-ns-group'], database)
        locator = naming.NameServerLocator()
        # resolve the Pyro object
        try:
            nshost, nsport = config['pyro-ns-host'], config['pyro-ns-port']
            uri = locator.getNS(nshost, nsport).resolve(nsid)
        except ProtocolError:
            raise ConnectionError('Could not connect to the Pyro name server '
                                  '(host: %s:%i)' % (nshost, nsport))
        except NamingError:
            raise ConnectionError('Could not get repository for %s '
                                  '(not registered in Pyro), '
                                  'you may have to restart your server-side '
                                  'application' % nsid)
        return core.getProxyForURI(uri)

def repo_connect(repo, user, password, cnxprops=None):
    """Constructor to create a new connection to the CubicWeb repository.

    Returns a Connection instance.
    """
    cnxprops = cnxprops or ConnectionProperties('inmemory')
    cnxid = repo.connect(unicode(user), password, cnxprops=cnxprops)
    cnx = Connection(repo, cnxid, cnxprops)
    if cnxprops.cnxtype == 'inmemory':
        cnx.vreg = repo.vreg
    return cnx

def connect(database=None, user=None, password=None, host=None,
            group=None, cnxprops=None, port=None, setvreg=True, mulcnx=True,
            initlog=True):
    """Constructor for creating a connection to the CubicWeb repository.
    Returns a Connection object.

    When method is 'pyro' and setvreg is True, use a special registry class
    (MulCnxCubicWebRegistry) made to deal with connections to differents instances
    in the same process unless specified otherwise by setting the mulcnx to
    False.
    """
    config = CubicWebNoAppConfiguration()
    if host:
        config.global_set_option('pyro-ns-host', host)
    if port:
        config.global_set_option('pyro-ns-port', port)
    if group:
        config.global_set_option('pyro-ns-group', group)
    cnxprops = cnxprops or ConnectionProperties()
    method = cnxprops.cnxtype
    repo = get_repository(method, database, config=config)
    if method == 'inmemory':
        vreg = repo.vreg
    elif setvreg:
        if mulcnx:
            vreg = MulCnxCubicWebRegistry(config, initlog=initlog)
        else:
            vreg = CubicWebRegistry(config, initlog=initlog)
        schema = repo.get_schema()
        for oldetype, newetype in ETYPE_NAME_MAP.items():
            if oldetype in schema:
                print 'aliasing', newetype, 'to', oldetype
                schema._entities[newetype] = schema._entities[oldetype]
        vreg.set_schema(schema)
    else:
        vreg = None
    cnx = repo_connect(repo, user, password, cnxprops)
    cnx.vreg = vreg
    return cnx

def in_memory_cnx(config, user, password):
    """usefull method for testing and scripting to get a dbapi.Connection
    object connected to an in-memory repository instance
    """
    if isinstance(config, CubicWebRegistry):
        vreg = config
        config = None
    else:
        vreg = None
    # get local access to the repository
    repo = get_repository('inmemory', config=config, vreg=vreg)
    # connection to the CubicWeb repository
    cnxprops = ConnectionProperties('inmemory')
    cnx = repo_connect(repo, user, password, cnxprops=cnxprops)
    return repo, cnx


class DBAPIRequest(RequestSessionMixIn):

    def __init__(self, vreg, cnx=None):
        super(DBAPIRequest, self).__init__(vreg)
        try:
            # no vreg or config which doesn't handle translations
            self.translations = vreg.config.translations
        except AttributeError:
            self.translations = {}
        self.set_default_language(vreg)
        # cache entities built during the request
        self._eid_cache = {}
        # these args are initialized after a connection is
        # established
        self.cnx = None   # connection associated to the request
        self._user = None # request's user, set at authentication
        if cnx is not None:
            self.set_connection(cnx)

    def base_url(self):
        return self.vreg.config['base-url']

    def from_controller(self):
        return 'view'

    def set_connection(self, cnx, user=None):
        """method called by the session handler when the user is authenticated
        or an anonymous connection is open
        """
        self.cnx = cnx
        self.cursor = cnx.cursor(self)
        self.set_user(user)

    def set_default_language(self, vreg):
        try:
            self.lang = vreg.property_value('ui.language')
        except: # property may not be registered
            self.lang = 'en'
        # use req.__ to translate a message without registering it to the catalog
        try:
            self._ = self.__ = self.translations[self.lang]
        except KeyError:
            # this occurs usually during test execution
            self._ = self.__ = unicode
        self.debug('request default language: %s', self.lang)

    def decorate_rset(self, rset):
        rset.vreg = self.vreg
        rset.req = self
        return rset

    def describe(self, eid):
        """return a tuple (type, sourceuri, extid) for the entity with id <eid>"""
        return self.cnx.describe(eid)

    def source_defs(self):
        """return the definition of sources used by the repository."""
        return self.cnx.source_defs()

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

    def session_data(self):
        """return a dictionnary containing session data"""
        return self.cnx.session_data()

    def get_session_data(self, key, default=None, pop=False):
        """return value associated to `key` in session data"""
        return self.cnx.get_session_data(key, default, pop)

    def set_session_data(self, key, value):
        """set value associated to `key` in session data"""
        return self.cnx.set_session_data(key, value)

    def del_session_data(self, key):
        """remove value associated to `key` in session data"""
        return self.cnx.del_session_data(key)

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

    @property
    def user(self):
        if self._user is None and self.cnx:
            self.set_user(self.cnx.user(self, {'lang': self.lang}))
        return self._user

    def set_user(self, user):
        self._user = user
        if user:
            self.set_entity_cache(user)

    def execute(self, *args, **kwargs):
        """Session interface compatibility"""
        return self.cursor.execute(*args, **kwargs)

set_log_methods(DBAPIRequest, getLogger('cubicweb.dbapi'))


# exceptions ##################################################################

class ProgrammingError(Exception): #DatabaseError):
    """Exception raised for errors that are related to the database's operation
    and not necessarily under the control of the programmer, e.g. an unexpected
    disconnect occurs, the data source name is not found, a transaction could
    not be processed, a memory allocation error occurred during processing,
    etc.
    """

# module level objects ########################################################


apilevel = '2.0'

"""Integer constant stating the level of thread safety the interface supports.
Possible values are:

                0     Threads may not share the module.
                1     Threads may share the module, but not connections.
                2     Threads may share the module and connections.
                3     Threads may share the module, connections and
                      cursors.

Sharing in the above context means that two threads may use a resource without
wrapping it using a mutex semaphore to implement resource locking. Note that
you cannot always make external resources thread safe by managing access using
a mutex: the resource may rely on global variables or other external sources
that are beyond your control.
"""
threadsafety = 1

"""String constant stating the type of parameter marker formatting expected by
the interface. Possible values are :

                'qmark'         Question mark style,
                                e.g. '...WHERE name=?'
                'numeric'       Numeric, positional style,
                                e.g. '...WHERE name=:1'
                'named'         Named style,
                                e.g. '...WHERE name=:name'
                'format'        ANSI C printf format codes,
                                e.g. '...WHERE name=%s'
                'pyformat'      Python extended format codes,
                                e.g. '...WHERE name=%(name)s'
"""
paramstyle = 'pyformat'


# connection object ###########################################################

class Connection(object):
    """DB-API 2.0 compatible Connection object for CubicWebt
    """
    # make exceptions available through the connection object
    ProgrammingError = ProgrammingError

    def __init__(self, repo, cnxid, cnxprops=None):
        self._repo = repo
        self.sessionid = cnxid
        self._close_on_del = getattr(cnxprops, 'close_on_del', True)
        self._cnxtype = getattr(cnxprops, 'cnxtype', 'pyro')
        self._closed = None
        if cnxprops and cnxprops.log_queries:
            self.executed_queries = []
            self.cursor_class = LogCursor
        else:
            self.cursor_class = Cursor
        self.anonymous_connection = False
        self.vreg = None
        # session's data
        self.data = {}

    def __repr__(self):
        if self.anonymous_connection:
            return '<Connection %s (anonymous)>' % self.sessionid
        return '<Connection %s>' % self.sessionid

    def request(self):
        return DBAPIRequest(self.vreg, self)

    def session_data(self):
        """return a dictionnary containing session data"""
        return self.data

    def get_session_data(self, key, default=None, pop=False):
        """return value associated to `key` in session data"""
        if pop:
            return self.data.pop(key, default)
        else:
            return self.data.get(key, default)

    def set_session_data(self, key, value):
        """set value associated to `key` in session data"""
        self.data[key] = value

    def del_session_data(self, key):
        """remove value associated to `key` in session data"""
        try:
            del self.data[key]
        except KeyError:
            pass

    def check(self):
        """raise `BadSessionId` if the connection is no more valid"""
        self._repo.check_session(self.sessionid)

    def set_session_props(self, **props):
        """raise `BadSessionId` if the connection is no more valid"""
        self._repo.set_session_props(self.sessionid, props)

    def get_shared_data(self, key, default=None, pop=False):
        """return value associated to `key` in shared data"""
        return self._repo.get_shared_data(self.sessionid, key, default, pop)

    def set_shared_data(self, key, value, querydata=False):
        """set value associated to `key` in shared data

        if `querydata` is true, the value will be added to the repository
        session's query data which are cleared on commit/rollback of the current
        transaction, and won't be available through the connexion, only on the
        repository side.
        """
        return self._repo.set_shared_data(self.sessionid, key, value, querydata)

    def get_schema(self):
        """Return the schema currently used by the repository.

        This is NOT part of the DB-API.
        """
        if self._closed is not None:
            raise ProgrammingError('Closed connection')
        return self._repo.get_schema()

    def load_vobjects(self, cubes=_MARKER, subpath=None, expand=True, force_reload=None):
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
            # application specific hooks
            if self._repo.config.application_hooks:
                hm.register_hooks(config.load_hooks(self.vreg))

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
        eid, login, groups, properties = self._repo.user_info(self.sessionid,
                                                              props)
        if req is None:
            req = self.request()
        rset = req.eid_rset(eid, 'CWUser')
        user = self.vreg.etype_class('CWUser')(req, rset, row=0, groups=groups,
                                               properties=properties)
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
        self._closed = 1

    def commit(self):
        """Commit any pending transaction to the database. Note that if the
        database supports an auto-commit feature, this must be initially off. An
        interface method may be provided to turn it back on.

        Database modules that do not support transactions should implement this
        method with void functionality.
        """
        if not self._closed is None:
            raise ProgrammingError('Connection is already closed')
        self._repo.commit(self.sessionid)

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


# cursor object ###############################################################

class Cursor(object):
    """These objects represent a database cursor, which is used to manage the
    context of a fetch operation. Cursors created from the same connection are
    not isolated, i.e., any changes done to the database by a cursor are
    immediately visible by the other cursors. Cursors created from different
    connections can or can not be isolated, depending on how the transaction
    support is implemented (see also the connection's rollback() and commit()
    methods.)
    """

    def __init__(self, connection, repo, req=None):
        """This read-only attribute return a reference to the Connection
        object on which the cursor was created.
        """
        self.connection = connection
        """optionnal issuing request instance"""
        self.req = req

        """This read/write attribute specifies the number of rows to fetch at a
        time with fetchmany(). It defaults to 1 meaning to fetch a single row
        at a time.

        Implementations must observe this value with respect to the fetchmany()
        method, but are free to interact with the database a single row at a
        time. It may also be used in the implementation of executemany().
        """
        self.arraysize = 1

        self._repo = repo
        self._sessid = connection.sessionid
        self._res = None
        self._closed = None
        self._index = 0


    def close(self):
        """Close the cursor now (rather than whenever __del__ is called).  The
        cursor will be unusable from this point forward; an Error (or subclass)
        exception will be raised if any operation is attempted with the cursor.
        """
        self._closed = True


    def execute(self, operation, parameters=None, eid_key=None, build_descr=True):
        """Prepare and execute a database operation (query or command).
        Parameters may be provided as sequence or mapping and will be bound to
        variables in the operation.  Variables are specified in a
        database-specific notation (see the module's paramstyle attribute for
        details).

        A reference to the operation will be retained by the cursor.  If the
        same operation object is passed in again, then the cursor can optimize
        its behavior.  This is most effective for algorithms where the same
        operation is used, but different parameters are bound to it (many
        times).

        For maximum efficiency when reusing an operation, it is best to use the
        setinputsizes() method to specify the parameter types and sizes ahead
        of time.  It is legal for a parameter to not match the predefined
        information; the implementation should compensate, possibly with a loss
        of efficiency.

        The parameters may also be specified as list of tuples to e.g. insert
        multiple rows in a single operation, but this kind of usage is
        depreciated: executemany() should be used instead.

        Return values are not defined by the DB-API, but this here it returns a
        ResultSet object.
        """
        self._res = res = self._repo.execute(self._sessid, operation,
                                             parameters, eid_key, build_descr)
        self.req.decorate_rset(res)
        self._index = 0
        return res


    def executemany(self, operation, seq_of_parameters):
        """Prepare a database operation (query or command) and then execute it
        against all parameter sequences or mappings found in the sequence
        seq_of_parameters.

        Modules are free to implement this method using multiple calls to the
        execute() method or by using array operations to have the database
        process the sequence as a whole in one call.

        Use of this method for an operation which produces one or more result
        sets constitutes undefined behavior, and the implementation is
        permitted (but not required) to raise an exception when it detects that
        a result set has been created by an invocation of the operation.

        The same comments as for execute() also apply accordingly to this
        method.

        Return values are not defined.
        """
        for parameters in seq_of_parameters:
            self.execute(operation, parameters)
            if self._res.rows is not None:
                self._res = None
                raise ProgrammingError('Operation returned a result set')


    def fetchone(self):
        """Fetch the next row of a query result set, returning a single
        sequence, or None when no more data is available.

        An Error (or subclass) exception is raised if the previous call to
        execute*() did not produce any result set or no call was issued yet.
        """
        if self._res is None:
            raise ProgrammingError('No result set')
        row = self._res.rows[self._index]
        self._index += 1
        return row


    def fetchmany(self, size=None):
        """Fetch the next set of rows of a query result, returning a sequence
        of sequences (e.g. a list of tuples). An empty sequence is returned
        when no more rows are available.

        The number of rows to fetch per call is specified by the parameter.  If
        it is not given, the cursor's arraysize determines the number of rows
        to be fetched. The method should try to fetch as many rows as indicated
        by the size parameter. If this is not possible due to the specified
        number of rows not being available, fewer rows may be returned.

        An Error (or subclass) exception is raised if the previous call to
        execute*() did not produce any result set or no call was issued yet.

        Note there are performance considerations involved with the size
        parameter.  For optimal performance, it is usually best to use the
        arraysize attribute.  If the size parameter is used, then it is best
        for it to retain the same value from one fetchmany() call to the next.
        """
        if self._res is None:
            raise ProgrammingError('No result set')
        if size is None:
            size = self.arraysize
        rows = self._res.rows[self._index:self._index + size]
        self._index += size
        return rows


    def fetchall(self):
        """Fetch all (remaining) rows of a query result, returning them as a
        sequence of sequences (e.g. a list of tuples).  Note that the cursor's
        arraysize attribute can affect the performance of this operation.

        An Error (or subclass) exception is raised if the previous call to
        execute*() did not produce any result set or no call was issued yet.
        """
        if self._res is None:
            raise ProgrammingError('No result set')
        if not self._res.rows:
            return []
        rows = self._res.rows[self._index:]
        self._index = len(self._res)
        return rows


    def setinputsizes(self, sizes):
        """This can be used before a call to execute*() to predefine memory
        areas for the operation's parameters.

        sizes is specified as a sequence -- one item for each input parameter.
        The item should be a Type Object that corresponds to the input that
        will be used, or it should be an integer specifying the maximum length
        of a string parameter.  If the item is None, then no predefined memory
        area will be reserved for that column (this is useful to avoid
        predefined areas for large inputs).

        This method would be used before the execute*() method is invoked.

        Implementations are free to have this method do nothing and users are
        free to not use it.
        """
        pass


    def setoutputsize(self, size, column=None):
        """Set a column buffer size for fetches of large columns (e.g. LONGs,
        BLOBs, etc.).  The column is specified as an index into the result
        sequence.  Not specifying the column will set the default size for all
        large columns in the cursor.

        This method would be used before the execute*() method is invoked.

        Implementations are free to have this method do nothing and users are
        free to not use it.
        """
        pass


class LogCursor(Cursor):
    """override the standard cursor to log executed queries"""

    def execute(self, operation, parameters=None, eid_key=None, build_descr=True):
        """override the standard cursor to log executed queries"""
        tstart, cstart = time(), clock()
        rset = Cursor.execute(self, operation, parameters, eid_key, build_descr)
        self.connection.executed_queries.append((operation, parameters,
                                                 time() - tstart, clock() - cstart))
        return rset

