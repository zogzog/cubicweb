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
from cubicweb.utils import parse_repo_uri
from cubicweb import ConnectionError, ProgrammingError
from uuid import uuid4
from contextlib import contextmanager
from cubicweb.req import RequestSessionBase

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

def _srv_cnx_func(name):
    """Decorate ClientConnection method blindly forward to Connection
    THIS TRANSITIONAL PURPOSE

    will be dropped when we have standalone connection"""
    def proxy(clt_cnx, *args, **kwargs):
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        with clt_cnx._srv_cnx as cnx:
            return getattr(cnx, name)(*args, **kwargs)
    return proxy

class ClientConnection(RequestSessionBase):
    """A Connection object to be used Client side.

    This object is aimed to be used client side (so potential communication
    with the repo through RTC) and aims to offer some compatibility with the
    cubicweb.dbapi.Connection interface.

    The autoclose_session paramenter informs the connection that this session
    have been open explictly and only for this client connection. The
    connection will close the session of exit.
    """
    # make exceptions available through the connection object
    ProgrammingError = ProgrammingError
    # attributes that may be overriden per connection instance
    anonymous_connection = False # XXX really needed ?
    is_repo_in_memory = True # BC, always true

    def __init__(self, session, autoclose_session=False):
        self._session = session
        self._cnxid = None
        self._open = None
        self._web_request = False
        self.vreg = session.vreg
        self._set_user(session.user)
        self._autoclose_session = autoclose_session

    def __enter__(self):
        assert self._open is None
        self._open = True
        self._cnxid = '%s-%s' % (self._session.id, uuid4().hex)
        self._session.set_cnx(self._cnxid)
        self._session._cnx.ctx_count += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._open = False
        cnxid = self._cnxid
        self._cnxid = None
        self._session._cnx.ctx_count -= 1
        self._session.close_cnx(cnxid)
        if self._autoclose_session:
            # we have to call repo.close to unsure the repo properly forget the
            # session calling session.close() is not enought :-(
            self._session.repo.close(self._session.id)


    # begin silly BC
    @property
    def _closed(self):
        return not self._open

    def close(self):
        if self._open:
            self.__exit__(None, None, None)

    def __repr__(self):
        if self.anonymous_connection:
            return '<Connection %s (anonymous)>' % self._cnxid
        return '<Connection %s>' % self._cnxid
    # end silly BC

    @property
    @contextmanager
    def _srv_cnx(self):
        """ensure that the session is locked to the right transaction

        TRANSITIONAL PURPOSE, This will be dropped once we use standalone
        session object"""
        if not self._open:
            raise ProgrammingError('Closed connection %s' % self._cnxid)
        session = self._session
        old_cnx = session._current_cnx_id
        try:
            session.set_cnx(self._cnxid)
            session.set_cnxset()
            try:
                yield session
            finally:
                session.free_cnxset()
        finally:
            if old_cnx is not None:
                session.set_cnx(old_cnx)

    # Main Connection purpose in life #########################################

    call_service = _srv_cnx_func('call_service')

    def execute(self, *args, **kwargs):
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        with self._srv_cnx as cnx:
            rset = cnx.execute(*args, **kwargs)
        rset.req = self
        # XXX keep the same behavior as the old dbapi
        # otherwise multiple tests break.
        # The little internet kitten is very sad about this situation.
        rset._rqlst = None
        return rset

    commit = _srv_cnx_func('commit')
    rollback = _srv_cnx_func('rollback')

    # session data methods #####################################################

    get_shared_data = _srv_cnx_func('get_shared_data')
    set_shared_data = _srv_cnx_func('set_shared_data')

    # meta-data accessors ######################################################

    def source_defs(self):
        """Return the definition of sources used by the repository."""
        return self._session.repo.source_defs()

    def get_schema(self):
        """Return the schema currently used by the repository."""
        return self._session.repo.source_defs()

    def get_option_value(self, option, foreid=None):
        """Return the value for `option` in the configuration. If `foreid` is
        specified, the actual repository to which this entity belongs is
        dereferenced and the option value retrieved from it.
        """
        return self._session.repo.get_option_value(option, foreid)

    describe = _srv_cnx_func('describe')

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
        # the ``with`` dance is transitional. We do not have Standalone
        # Connection yet so we use this trick to unsure the session have the
        # proper cnx loaded. This can be simplified one we have Standalone
        # Connection object
        with self._srv_cnx as cnx:
            source = cnx.repo.system_source
            txinfos = source.undoable_transactions(cnx, ueid, **actionfilters)
        for txinfo in txinfos:
            txinfo.req = req or self  # XXX mostly wrong
        return txinfos

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
        with self._srv_cnx as cnx:
            txinfo = cnx.repo.system_source.tx_info(cnx, txuuid)
        if req:
            txinfo.req = req
        else:
            txinfo.cnx = self
        return txinfo

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
        with self._srv_cnx as cnx:
            return cnx.repo.system_source.tx_actions(cnx, txuuid, public)

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
        with self._srv_cnx as cnx:
            return cnx.repo.system_source.undo_transaction(cnx, txuuid)

    def request(self):
        # XXX This is DBAPI compatibility method. Deprecate it ASAP.
        return self

    def cursor(self):
        # XXX This is DBAPI compatibility method. Deprecate it ASAP.
        return self

    @ property
    def sessionid(self):
        # XXX This is DBAPI compatibility property. Deprecate it ASAP.
        return self._session.id

    @property
    def connection(self):
        # XXX This is DBAPI compatibility property. Deprecate it ASAP.
        return self

    @property
    def _repo(self):
        # XXX This is DBAPI compatibility property. Deprecate it ASAP.
        return self._session.repo
