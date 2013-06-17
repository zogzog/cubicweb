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
from cubicweb import ConnectionError

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

