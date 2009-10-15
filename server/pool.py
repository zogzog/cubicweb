"""CubicWeb server connections pool :

* the rql repository has a limited number of connections pools, each of them
  dealing with a set of connections on each source used by the repository

* operation may be registered by hooks during a transaction, which will  be
  fired when the pool is commited or rollbacked

This module defined the `ConnectionsPool` class and a set of abstract classes
for operation.


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
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
            self.source_cnxs[source.uri] = (source, source.get_connection())
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
        for uri, (source, cursor) in self.source_cnxs.items():
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


class Operation(object):
    """an operation is triggered on connections pool events related to
    commit / rollback transations. Possible events are:

    precommit:
      the pool is preparing to commit. You shouldn't do anything things which
      has to be reverted if the commit fail at this point, but you can freely
      do any heavy computation or raise an exception if the commit can't go.
      You can add some new operation during this phase but their precommit
      event won't be triggered

    commit:
      the pool is preparing to commit. You should avoid to do to expensive
      stuff or something that may cause an exception in this event

    revertcommit:
      if an operation failed while commited, this event is triggered for
      all operations which had their commit event already to let them
      revert things (including the operation which made fail the commit)

    rollback:
      the transaction has been either rollbacked either
      * intentionaly
      * a precommit event failed, all operations are rollbacked
      * a commit event failed, all operations which are not been triggered for
        commit are rollbacked

    order of operations may be important, and is controlled according to:
    * operation's class
    """

    def __init__(self, session, **kwargs):
        self.session = session
        self.user = session.user
        self.repo = session.repo
        self.schema = session.repo.schema
        self.config = session.repo.config
        self.__dict__.update(kwargs)
        self.register(session)
        # execution information
        self.processed = None # 'precommit', 'commit'
        self.failed = False

    def register(self, session):
        session.add_operation(self, self.insert_index())

    def insert_index(self):
        """return the index of  the lastest instance which is not a
        LateOperation instance
        """
        # faster by inspecting operation in reverse order for heavy transactions
        i = None
        for i, op in enumerate(reversed(self.session.pending_operations)):
            if isinstance(op, (LateOperation, SingleLastOperation)):
                continue
            return -i or None
        if i is None:
            return None
        return -(i + 1)

    def handle_event(self, event):
        """delegate event handling to the opertaion"""
        getattr(self, event)()

    def precommit_event(self):
        """the observed connections pool is preparing a commit"""

    def revertprecommit_event(self):
        """an error went when pre-commiting this operation or a later one

        should revert pre-commit's changes but take care, they may have not
        been all considered if it's this operation which failed
        """

    def commit_event(self):
        """the observed connections pool is commiting"""
        raise NotImplementedError()

    def revertcommit_event(self):
        """an error went when commiting this operation or a later one

        should revert commit's changes but take care, they may have not
        been all considered if it's this operation which failed
        """

    def rollback_event(self):
        """the observed connections pool has been rollbacked

        do nothing by default, the operation will just be removed from the pool
        operation list
        """


class PreCommitOperation(Operation):
    """base class for operation only defining a precommit operation
    """

    def precommit_event(self):
        """the observed connections pool is preparing a commit"""
        raise NotImplementedError()

    def commit_event(self):
        """the observed connections pool is commiting"""


class LateOperation(Operation):
    """special operation which should be called after all possible (ie non late)
    operations
    """
    def insert_index(self):
        """return the index of  the lastest instance which is not a
        SingleLastOperation instance
        """
        # faster by inspecting operation in reverse order for heavy transactions
        i = None
        for i, op in enumerate(reversed(self.session.pending_operations)):
            if isinstance(op, SingleLastOperation):
                continue
            return -i or None
        if i is None:
            return None
        return -(i + 1)


class SingleOperation(Operation):
    """special operation which should be called once"""
    def register(self, session):
        """override register to handle cases where this operation has already
        been added
        """
        operations = session.pending_operations
        index = self.equivalent_index(operations)
        if index is not None:
            equivalent = operations.pop(index)
        else:
            equivalent = None
        session.add_operation(self, self.insert_index())
        return equivalent

    def equivalent_index(self, operations):
        """return the index of the equivalent operation if any"""
        for i, op in enumerate(reversed(operations)):
            if op.__class__ is self.__class__:
                return -(i+1)
        return None


class SingleLastOperation(SingleOperation):
    """special operation which should be called once and after all other
    operations
    """
    def insert_index(self):
        return None

from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Operation, getLogger('cubicweb.session'))
