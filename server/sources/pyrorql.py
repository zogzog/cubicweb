# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Source to query another RQL repository using pyro"""

__docformat__ = "restructuredtext en"
_ = unicode

import threading
from Pyro.errors import PyroError, ConnectionClosedError

from logilab.common.configuration import REQUIRED

from cubicweb import dbapi
from cubicweb import ConnectionError
from cubicweb.server.sources import ConnectionWrapper

from cubicweb.server.sources.remoterql import RemoteSource

class PyroRQLSource(RemoteSource):
    """External repository source, using Pyro connection"""

    CNX_TYPE = 'pyro'

    options = RemoteSource.options + (
        # XXX pyro-ns host/port
        ('pyro-ns-id',
         {'type' : 'string',
          'default': REQUIRED,
          'help': 'identifier of the repository in the pyro name server',
          'group': 'remote-source', 'level': 0,
          }),
        ('pyro-ns-host',
         {'type' : 'string',
          'default': None,
          'help': 'Pyro name server\'s host. If not set, default to the value \
from all_in_one.conf. It may contains port information using <host>:<port> notation.',
          'group': 'remote-source', 'level': 1,
          }),
        ('pyro-ns-group',
         {'type' : 'string',
          'default': None,
          'help': 'Pyro name server\'s group where the repository will be \
registered. If not set, default to the value from all_in_one.conf.',
          'group': 'remote-source', 'level': 2,
          }),
    )

    def _get_connection(self):
        """open and return a connection to the source"""
        nshost = self.config.get('pyro-ns-host') or self.repo.config['pyro-ns-host']
        nsgroup = self.config.get('pyro-ns-group') or self.repo.config['pyro-ns-group']
        self.info('connecting to instance :%s.%s for user %s',
                  nsgroup, self.config['pyro-ns-id'], self.config['cubicweb-user'])
        return dbapi.connect(database=self.config['pyro-ns-id'],
                             login=self.config['cubicweb-user'],
                             password=self.config['cubicweb-password'],
                             host=nshost, group=nsgroup,
                             setvreg=False)

    def get_connection(self):
        try:
            return self._get_connection()
        except (ConnectionError, PyroError), ex:
            self.critical("can't get connection to source %s: %s", self.uri, ex)
            return ConnectionWrapper()

    def check_connection(self, cnx):
        """check connection validity, return None if the connection is still valid
        else a new connection
        """
        # we have to transfer manually thread ownership. This can be done safely
        # since the connections set holding the connection is affected to one
        # session/thread and can't be called simultaneously
        try:
            cnx._repo._transferThread(threading.currentThread())
        except AttributeError:
            # inmemory connection
            pass
        try:
            return super(PyroRQLSource, self).check_connection(cnx)
        except ConnectionClosedError:
            # try to reconnect
            return self.get_connection()

