"""helper functions for application hooks

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb import RepositoryError
from cubicweb.server.pool import SingleLastOperation


def entity_name(session, eid):
    """return the "name" attribute of the entity with the given eid"""
    return entity_attr(session, eid, 'name')

def entity_attr(session, eid, attr):
    """return an arbitrary attribute of the entity with the given eid"""
    return getattr(session.entity_from_eid(eid), attr)

def rproperty(session, rtype, eidfrom, eidto, rprop):
    rschema = session.repo.schema[rtype]
    subjtype = session.describe(eidfrom)[0]
    objtype = session.describe(eidto)[0]
    return rschema.rproperty(subjtype, objtype, rprop)

def check_internal_entity(session, eid, internal_names):
    """check that the entity's name is not in the internal_names list.
    raise a RepositoryError if so, else return the entity's name
    """
    name = entity_name(session, eid)
    if name in internal_names:
        raise RepositoryError('%s entity can\'t be deleted' % name)
    return name

def get_user_sessions(repo, ueid):
    for session in repo._sessions.values():
        if ueid == session.user.eid:
            yield session


# mail related ################################################################

class SendMailOp(SingleLastOperation):
    def __init__(self, session, msg=None, recipients=None, **kwargs):
        # may not specify msg yet, as
        # `cubicweb.sobjects.supervision.SupervisionMailOp`
        if msg is not None:
            assert recipients
            self.to_send = [(msg, recipients)]
        else:
            assert recipients is None
            self.to_send = []
        super(SendMailOp, self).__init__(session, **kwargs)

    def register(self, session):
        previous = super(SendMailOp, self).register(session)
        if previous:
            self.to_send = previous.to_send + self.to_send

    def commit_event(self):
        self.repo.threaded_task(self.sendmails)

    def sendmails(self):
        self.config.sendmails(self.to_send)


# state related ###############################################################

def previous_state(session, eid):
    """return the state of the entity with the given eid,
    usually since it's changing in the current transaction. Due to internal
    relation hooks, the relation may has been deleted at this point, so
    we have handle that
    """
    # don't check eid in session.transaction_data.get('neweids', ()), we don't
    # want to miss previous state of entity whose state change in the same
    # transaction as it's being created
    pending = session.transaction_data.get('pendingrelations', ())
    for eidfrom, rtype, eidto in reversed(pending):
        if rtype == 'in_state' and eidfrom == eid:
            rset = session.execute('Any S,N WHERE S eid %(x)s, S name N',
                                   {'x': eidto}, 'x')
            return rset.get_entity(0, 0)
    rset = session.execute('Any S,N WHERE X eid %(x)s, X in_state S, S name N',
                           {'x': eid}, 'x')
    if rset:
        return rset.get_entity(0, 0)
