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
"""CubicWeb server connections pool : the repository has a limited number of
connections pools, each of them dealing with a set of connections on each source
used by the repository. A connections pools (`ConnectionsPool`) is an
abstraction for a group of connection to each source.
"""

__docformat__ = "restructuredtext en"

import sys

class ConnectionsPool(object):
    """handle connections on a set of sources, at some point associated to a
    user session
    """

    def __init__(self, sources):
        # dictionnary of (source, connection), indexed by sources'uri
        self.source_cnxs = {}
        for source in sources:
            self.add_source(source)
        if not 'system' in self.source_cnxs:
            self.source_cnxs['system'] = self.source_cnxs[sources[0].uri]
        self._cursors = {}

    def __getitem__(self, uri):
        """subscription notation provide access to sources'cursors"""
        try:
            cursor = self._cursors[uri]
        except KeyError:
            cursor = self.source_cnxs[uri][1].cursor()
            if cursor is not None:
                # None possible on sources without cursor support such as ldap
                self._cursors[uri] = cursor
        return cursor

    def add_source(self, source):
        assert not source.uri in self.source_cnxs
        self.source_cnxs[source.uri] = (source, source.get_connection())

    def remove_source(self, source):
        source, cnx = self.source_cnxs.pop(source.uri)
        cnx.close()
        self._cursors.pop(source.uri, None)

    def commit(self):
        """commit the current transaction for this user"""
        # FIXME: what happends if a commit fail
        # would need a two phases commit or like, but I don't know how to do
        # this using the db-api...
        for source, cnx in self.source_cnxs.values():
            # let exception propagates
            cnx.commit()

    def rollback(self):
        """rollback the current transaction for this user"""
        for source, cnx in self.source_cnxs.values():
            # catch exceptions, rollback other sources anyway
            try:
                cnx.rollback()
            except:
                source.critical('rollback error', exc_info=sys.exc_info())
                # error on rollback, the connection is much probably in a really
                # bad state. Replace it by a new one.
                self.reconnect(source)

    def close(self, i_know_what_i_do=False):
        """close all connections in the pool"""
        if i_know_what_i_do is not True: # unexpected closing safety belt
            raise RuntimeError('pool shouldn\'t be closed')
        for cu in self._cursors.values():
            try:
                cu.close()
            except:
                continue
        for _, cnx in self.source_cnxs.values():
            try:
                cnx.close()
            except:
                continue

    # internals ###############################################################

    def pool_set(self):
        """pool is being set"""
        self.check_connections()

    def pool_reset(self):
        """pool is being reseted"""
        for source, cnx in self.source_cnxs.values():
            source.pool_reset(cnx)

    def sources(self):
        """return the source objects handled by this pool"""
        # implementation details of flying insert requires the system source
        # first
        yield self.source_cnxs['system'][0]
        for uri, (source, cnx) in self.source_cnxs.items():
            if uri == 'system':
                continue
            yield source
        #return [source_cnx[0] for source_cnx in self.source_cnxs.values()]

    def source(self, uid):
        """return the source object with the given uri"""
        return self.source_cnxs[uid][0]

    def connection(self, uid):
        """return the connection on the source object with the given uri"""
        return self.source_cnxs[uid][1]

    def reconnect(self, source=None):
        """reopen a connection for this source or all sources if none specified
        """
        if source is None:
            sources = self.sources()
        else:
            sources = (source,)
        for source in sources:
            try:
                # properly close existing connection if any
                self.source_cnxs[source.uri][1].close()
            except:
                pass
            source.info('trying to reconnect')
            self.source_cnxs[source.uri] = (source, source.get_connection())
            self._cursors.pop(source.uri, None)

    def check_connections(self):
        for source, cnx in self.source_cnxs.itervalues():
            newcnx = source.check_connection(cnx)
            if newcnx is not None:
                self.reset_connection(source, newcnx)

    def reset_connection(self, source, cnx):
        self.source_cnxs[source.uri] = (source, cnx)
        self._cursors.pop(source.uri, None)


from cubicweb.server.hook import Operation, LateOperation, SingleLastOperation
from logilab.common.deprecation import class_moved, class_renamed
Operation = class_moved(Operation)
PreCommitOperation = class_renamed('PreCommitOperation', Operation)
LateOperation = class_moved(LateOperation)
SingleLastOperation = class_moved(SingleLastOperation)
