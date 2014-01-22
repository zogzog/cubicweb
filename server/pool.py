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
"""CubicWeb server connections set : the repository has a limited number of
:class:`ConnectionsSet` (defined in configuration, default to 4). Each of them
hold a connection to the system source.
"""

__docformat__ = "restructuredtext en"

import sys

from logilab.common.deprecation import deprecated


class ConnectionsSet(object):
    """handle connection to the system source, at some point associated to a
    :class:`Session`
    """

    # since 3.19, we only have to manage the system source connection
    def __init__(self, system_source):
        # dictionary of (source, connection), indexed by sources'uri
        self._source = system_source
        self.cnx = system_source.get_connection()
        self.cu = self.cnx.cursor()

    def commit(self):
        """commit the current transaction for this user"""
        # let exception propagates
        self.cnx.commit()

    def rollback(self):
        """rollback the current transaction for this user"""
        # catch exceptions, rollback other sources anyway
        try:
            self.cnx.rollback()
        except Exception:
            self._source.critical('rollback error', exc_info=sys.exc_info())
            # error on rollback, the connection is much probably in a really
            # bad state. Replace it by a new one.
            self.reconnect()

    def close(self, i_know_what_i_do=False):
        """close all connections in the set"""
        if i_know_what_i_do is not True: # unexpected closing safety belt
            raise RuntimeError('connections set shouldn\'t be closed')
        try:
            self.cu.close()
            self.cu = None
        except Exception:
            pass
        try:
            self.cnx.close()
        except Exception:
            pass

    # internals ###############################################################

    def cnxset_set(self):
        """connections set is being set on a session"""
        self.check_connections()

    def cnxset_freed(self):
        """connections set is being freed from a session"""
        self._source.cnxset_freed(self.cnx)

    def reconnect(self):
        """reopen a connection for this source or all sources if none specified
        """
        try:
            # properly close existing connection if any
            self.cnx.close()
        except Exception:
            pass
        self._source.info('trying to reconnect')
        self.cnx = self._source.get_connection()
        self.cu = self.cnx.cursor()

    def check_connections(self):
        newcnx = self._source.check_connection(self.cnx)
        if newcnx is not None:
            self.cnx = newcnx
            self.cu = self.cnx.cursor()

    @deprecated('[3.19] use .cu instead')
    def __getitem__(self, uri):
        assert uri == 'system'
        return self.cu

    @deprecated('[3.19] use repo.system_source instead')
    def source(self, uid):
        assert uid == 'system'
        return self._source

    @deprecated('[3.19] use .cnx instead')
    def connection(self, uid):
        assert uid == 'system'
        return self.cnx

    @property
    @deprecated('[3.19] use .cnx instead')
    def source_cnxs(self):
        return {'system': (self._source, self.cnx)}


from cubicweb.server.hook import Operation, LateOperation, SingleLastOperation
from logilab.common.deprecation import class_moved, class_renamed
Operation = class_moved(Operation)
PreCommitOperation = class_renamed('PreCommitOperation', Operation)
LateOperation = class_moved(LateOperation)
SingleLastOperation = class_moved(SingleLastOperation)
