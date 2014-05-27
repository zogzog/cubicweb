# copyright 2013-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Official API to access the content of a repository
"""
from logilab.common.deprecation import deprecated

from cubicweb.utils import parse_repo_uri
from cubicweb import ConnectionError, ProgrammingError, AuthenticationError
from uuid import uuid4
from contextlib import contextmanager
from cubicweb.req import RequestSessionBase
from functools import wraps

### private function for specific method ############################

def _get_inmemory_repo(config, vreg=None):
    from cubicweb.server.repository import Repository
    from cubicweb.server.utils import TasksManager
    return Repository(config, TasksManager(), vreg=vreg)


### public API ######################################################

def get_repository(uri=None, config=None, vreg=None):
    """get a repository for the given URI or config/vregistry (in case we're
    loading the repository for a client, eg web server, configuration).

    The returned repository may be an in-memory repository or a proxy object
    using a specific RPC method, depending on the given URI (pyro or zmq).
    """
    if uri is None:
        return _get_inmemory_repo(config, vreg)

    protocol, hostport, appid = parse_repo_uri(uri)

    if protocol == 'inmemory':
        # me may have been called with a dummy 'inmemory://' uri ...
        return _get_inmemory_repo(config, vreg)

    if protocol == 'pyroloc':  # direct connection to the instance
        from logilab.common.pyro_ext import get_proxy
        uri = uri.replace('pyroloc', 'PYRO')
        return get_proxy(uri)

    if protocol == 'pyro':  # connection mediated through the pyro ns
        from logilab.common.pyro_ext import ns_get_proxy
        path = appid.strip('/')
        if not path:
            raise ConnectionError(
                "can't find instance name in %s (expected to be the path component)"
                % uri)
        if '.' in path:
            nsgroup, nsid = path.rsplit('.', 1)
        else:
            nsgroup = 'cubicweb'
            nsid = path
        return ns_get_proxy(nsid, defaultnsgroup=nsgroup, nshost=hostport)

    if protocol.startswith('zmqpickle-'):
        from cubicweb.zmqclient import ZMQRepositoryClient
        return ZMQRepositoryClient(uri)
    else:
        raise ConnectionError('unknown protocol: `%s`' % protocol)

def connect(repo, login, **kwargs):
    """Take credential and return associated ClientConnection.

    The ClientConnection is associated to a new Session object that will be
    closed when the ClientConnection is closed.

    raise AuthenticationError if the credential are invalid."""
    sessionid = repo.connect(login, **kwargs)
    session = repo._get_session(sessionid)
    # XXX the autoclose_session should probably be handle on the session directly
    # this is something to consider once we have proper server side Connection.
    return ClientConnection(session, autoclose_session=True)

def anonymous_cnx(repo):
    """return a ClientConnection for Anonymous user.

    The ClientConnection is associated to a new Session object that will be
    closed when the ClientConnection is closed.

    raises an AuthenticationError if anonymous usage is not allowed
    """
    anoninfo = getattr(repo.config, 'anonymous_user', lambda: None)()
    if anoninfo is None: # no anonymous user
        raise AuthenticationError('anonymous access is not authorized')
    anon_login, anon_password = anoninfo
    # use vreg's repository cache
    return connect(repo, anon_login, password=anon_password)

def _srv_cnx_func(name):
    """Decorate ClientConnection method blindly forward to Connection
    THIS TRANSITIONAL PURPOSE

    will be dropped when we have standalone connection"""
    def proxy(clt_cnx, *args, **kwargs):
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        if not clt_cnx._open:
            raise ProgrammingError('Closed client connection')
        return getattr(clt_cnx._cnx, name)(*args, **kwargs)
    return proxy

def _open_only(func):
    """decorator for ClientConnection method that check it is open"""
    @wraps(func)
    def check_open(clt_cnx, *args, **kwargs):
        if not clt_cnx._open:
            raise ProgrammingError('Closed client connection')
        return func(clt_cnx, *args, **kwargs)
    return check_open


class ClientConnection(RequestSessionBase):
    """A Connection object to be used Client side.

    This object is aimed to be used client side (so potential communication
    with the repo through RPC) and aims to offer some compatibility with the
    cubicweb.dbapi.Connection interface.

    The autoclose_session parameter informs the connection that this session
    has been opened explicitly and only for this client connection. The
    connection will close the session on exit.
    """
    # make exceptions available through the connection object
    ProgrammingError = ProgrammingError
    # attributes that may be overriden per connection instance
    anonymous_connection = False # XXX really needed ?
    is_repo_in_memory = True # BC, always true

    def __init__(self, session, autoclose_session=False):
        super(ClientConnection, self).__init__(session.vreg)
        self._session = session # XXX there is no real reason to keep the
                                # session around function still using it should
                                # be rewritten and migrated.
        self._cnx = None
        self._open = None
        self._web_request = False
        #: cache entities built during the connection
        self._eid_cache = {}
        self._set_user(session.user)
        self._autoclose_session = autoclose_session

    def __enter__(self):
        assert self._open is None
        self._open = True
        self._cnx = self._session.new_cnx()
        self._cnx.__enter__()
        self._cnx.ctx_count += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._open = False
        self._cnx.ctx_count -= 1
        self._cnx.__exit__(exc_type, exc_val, exc_tb)
        self._cnx = None
        if self._autoclose_session:
            # we have to call repo.close to ensure the repo properly forgets the
            # session; calling session.close() is not enough :-(
            self._session.repo.close(self._session.sessionid)


    # begin silly BC
    @property
    def _closed(self):
        return not self._open

    def close(self):
        if self._open:
            self.__exit__(None, None, None)

    def __repr__(self):
        # XXX we probably want to reference the user of the session here
        if self._open is None:
            return '<ClientConnection (not open yet)>'
        elif not self._open:
            return '<ClientConnection (closed)>'
        elif self.anonymous_connection:
            return '<ClientConnection %s (anonymous)>' % self._cnx.connectionid
        else:
            return '<ClientConnection %s>' % self._cnx.connectionid
    # end silly BC

    # Main Connection purpose in life #########################################

    call_service = _srv_cnx_func('call_service')

    @_open_only
    def execute(self, *args, **kwargs):
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        rset = self._cnx.execute(*args, **kwargs)
        rset.req = self
        return rset

    @_open_only
    def commit(self, *args, **kwargs):
        try:
            return self._cnx.commit(*args, **kwargs)
        finally:
            self.drop_entity_cache()

    @_open_only
    def rollback(self, *args, **kwargs):
        try:
            return self._cnx.rollback(*args, **kwargs)
        finally:
            self.drop_entity_cache()

    # security #################################################################

    allow_all_hooks_but = _srv_cnx_func('allow_all_hooks_but')
    deny_all_hooks_but = _srv_cnx_func('deny_all_hooks_but')
    security_enabled = _srv_cnx_func('security_enabled')

    # direct sql ###############################################################

    system_sql = _srv_cnx_func('system_sql')

    # session data methods #####################################################

    get_shared_data = _srv_cnx_func('get_shared_data')
    set_shared_data = _srv_cnx_func('set_shared_data')

    @property
    def transaction_data(self):
        return self._cnx.transaction_data

    # meta-data accessors ######################################################

    @_open_only
    def source_defs(self):
        """Return the definition of sources used by the repository."""
        return self._session.repo.source_defs()

    @_open_only
    def get_schema(self):
        """Return the schema currently used by the repository."""
        return self._session.repo.source_defs()

    @_open_only
    def get_option_value(self, option):
        """Return the value for `option` in the configuration."""
        return self._session.repo.get_option_value(option)

    entity_metas = _srv_cnx_func('entity_metas')
    describe = _srv_cnx_func('describe') # XXX deprecated in 3.19

    # undo support ############################################################

    @_open_only
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
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        source = self._cnx.repo.system_source
        txinfos = source.undoable_transactions(self._cnx, ueid, **actionfilters)
        for txinfo in txinfos:
            txinfo.req = req or self  # XXX mostly wrong
        return txinfos

    @_open_only
    def transaction_info(self, txuuid, req=None):
        """Return transaction object for the given uid.

        raise `NoSuchTransaction` if not found or if session's user is not
        allowed (eg not in managers group and the transaction doesn't belong to
        him).
        """
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        txinfo = self._cnx.repo.system_source.tx_info(self._cnx, txuuid)
        if req:
            txinfo.req = req
        else:
            txinfo.cnx = self
        return txinfo

    @_open_only
    def transaction_actions(self, txuuid, public=True):
        """Return an ordered list of action effectued during that transaction.

        If public is true, return only 'public' actions, eg not ones triggered
        under the cover by hooks, else return all actions.

        raise `NoSuchTransaction` if the transaction is not found or if
        session's user is not allowed (eg not in managers group and the
        transaction doesn't belong to him).
        """
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        return self._cnx.repo.system_source.tx_actions(self._cnx, txuuid, public)

    @_open_only
    def undo_transaction(self, txuuid):
        """Undo the given transaction. Return potential restoration errors.

        raise `NoSuchTransaction` if not found or if session's user is not
        allowed (eg not in managers group and the transaction doesn't belong to
        him).
        """
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        return self._cnx.repo.system_source.undo_transaction(self._cnx, txuuid)

    # cache management

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

    # deprecated stuff

    @deprecated('[3.19] This is a repoapi.ClientConnection object not a dbapi one')
    def request(self):
        return self

    @deprecated('[3.19] This is a repoapi.ClientConnection object not a dbapi one')
    def cursor(self):
        return self

    @property
    @deprecated('[3.19] This is a repoapi.ClientConnection object not a dbapi one')
    def sessionid(self):
        return self._session.sessionid

    @property
    @deprecated('[3.19] This is a repoapi.ClientConnection object not a dbapi one')
    def connection(self):
        return self

    @property
    @deprecated('[3.19] This is a repoapi.ClientConnection object not a dbapi one')
    def _repo(self):
        return self._session.repo
