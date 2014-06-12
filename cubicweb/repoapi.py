# copyright 2013-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from warnings import warn

from six import add_metaclass

from logilab.common.deprecation import class_deprecated

from cubicweb.utils import parse_repo_uri
from cubicweb import AuthenticationError
from cubicweb.server.session import Connection


### public API ######################################################

def get_repository(uri=None, config=None, vreg=None):
    """get a repository for the given URI or config/vregistry (in case we're
    loading the repository for a client, eg web server, configuration).

    The returned repository may be an in-memory repository or a proxy object
    using a specific RPC method, depending on the given URI.
    """
    if uri is not None:
        warn('[3.22] get_repository only wants a config')

    assert config is not None, 'get_repository(config=config)'
    return config.repository(vreg)

def connect(repo, login, **kwargs):
    """Take credential and return associated Connection.

    raise AuthenticationError if the credential are invalid."""
    return repo.new_session(login, **kwargs).new_cnx()

def anonymous_cnx(repo):
    """return a Connection for Anonymous user.

    raises an AuthenticationError if anonymous usage is not allowed
    """
    anoninfo = getattr(repo.config, 'anonymous_user', lambda: None)()
    if anoninfo is None: # no anonymous user
        raise AuthenticationError('anonymous access is not authorized')
    anon_login, anon_password = anoninfo
    # use vreg's repository cache
    return connect(repo, anon_login, password=anon_password)


@add_metaclass(class_deprecated)
class ClientConnection(Connection):
    __deprecation_warning__ = '[3.20] %(cls)s is deprecated, use Connection instead'
