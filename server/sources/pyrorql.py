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

# module is lazily imported
import warnings
warnings.warn('Imminent drop of pyrorql source. Switch to datafeed now!',
              DeprecationWarning)

import threading
from Pyro.errors import PyroError, ConnectionClosedError

from cubicweb import ConnectionError
from cubicweb.server.sources import ConnectionWrapper

from cubicweb.server.sources.remoterql import RemoteSource

class PyroRQLSource(RemoteSource):
    """External repository source, using Pyro connection"""

    def get_connection(self):
        try:
            return self._get_connection()
        except (ConnectionError, PyroError) as ex:
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

