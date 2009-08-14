"""Core hooks: workflow related hooks

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from datetime import datetime

from cubicweb import RepositoryError, ValidationError
from cubicweb.interfaces import IWorkflowable
from cubicweb.selectors import entity_implements
from cubicweb.server import hook


def previous_state(session, eid):
    """return the state of the entity with the given eid,
    usually since it's changing in the current transaction. Due to internal
    relation hooks, the relation may has been deleted at this point, so
    we have handle that
    """
    if session.added_in_transaction(eid):
        return
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


def relation_deleted(session, eidfrom, rtype, eidto):
    session.transaction_data.setdefault('pendingrelations', []).append(
        (eidfrom, rtype, eidto))


class _SetInitialStateOp(hook.Operation):
    """make initial state be a default state"""

    def precommit_event(self):
        session = self.session
        entity = self.entity
        # if there is an initial state and the entity's state is not set,
        # use the initial state as a default state
        if not session.deleted_in_transaction(entity.eid) and not entity.in_state:
            rset = session.execute('Any S WHERE ET initial_state S, ET name %(name)s',
                                   {'name': entity.id})
            if rset:
                session.add_relation(entity.eid, 'in_state', rset[0][0])

class WorkflowHook(hook.Hook):
    __abstract__ = True
    category = 'worfklow'


class SetInitialStateHook(WorkflowHook):
    __id__ = 'wfsetinitial'
    __select__ = WorkflowHook.__select__ & entity_implements(IWorkflowable)
    events = ('after_add_entity',)

    def __call__(self):
        _SetInitialStateOp(self._cw, entity=self.entity)


class PrepareStateChangeHook(WorkflowHook):
    """record previous state information"""
    __id__ = 'cwdelstate'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('in_state')
    events = ('before_delete_relation',)

    def __call__(self):
        self._cw.transaction_data.setdefault('pendingrelations', []).append(
            (self.eidfrom, self.rtype, self.eidto))


class FireTransitionHook(PrepareStateChangeHook):
    """check the transition is allowed and record transition information"""
    __id__ = 'wffiretransition'
    events = ('before_add_relation',)

    def __call__(self):
        session = self._cw
        eidfrom = self.eidfrom
        eidto = self.eidto
        state = previous_state(session, eidfrom)
        etype = session.describe(eidfrom)[0]
        if not (session.is_super_session or 'managers' in session.user.groups):
            if not state is None:
                entity = session.entity_from_eid(eidfrom)
                # we should find at least one transition going to this state
                try:
                    iter(state.transitions(entity, eidto)).next()
                except StopIteration:
                    msg = session._('transition is not allowed')
                    raise ValidationError(eidfrom, {'in_state': msg})
            else:
                # not a transition
                # check state is initial state if the workflow defines one
                isrset = session.unsafe_execute('Any S WHERE ET initial_state S, ET name %(etype)s',
                                                {'etype': etype})
                if isrset and not eidto == isrset[0][0]:
                    msg = session._('not the initial state for this entity')
                    raise ValidationError(eidfrom, {'in_state': msg})
        eschema = session.repo.schema[etype]
        if not 'wf_info_for' in eschema.object_relations():
            # workflow history not activated for this entity type
            return
        rql = 'INSERT TrInfo T: T wf_info_for E, T to_state DS, T comment %(comment)s'
        args = {'comment': session.get_shared_data('trcomment', None, pop=True),
                'e': eidfrom, 'ds': eidto}
        cformat = session.get_shared_data('trcommentformat', None, pop=True)
        if cformat is not None:
            args['comment_format'] = cformat
            rql += ', T comment_format %(comment_format)s'
        restriction = ['DS eid %(ds)s, E eid %(e)s']
        if not state is None: # not a transition
            rql += ', T from_state FS'
            restriction.append('FS eid %(fs)s')
            args['fs'] = state.eid
        rql = '%s WHERE %s' % (rql, ', '.join(restriction))
        session.unsafe_execute(rql, args, 'e')


class SetModificationDateOnStateChange(WorkflowHook):
    """update entity's modification date after changing its state"""
    __id__ = 'wfsyncmdate'
    __select__ = WorkflowHook.__select__ & hook.match_rtype('in_state')
    events = ('after_add_relation',)

    def __call__(self):
        if self._cw.added_in_transaction(self.eidfrom):
            # new entity, not needed
            return
        entity = self._cw.entity_from_eid(self.eidfrom)
        try:
            entity.set_attributes(modification_date=datetime.now())
        except RepositoryError, ex:
            # usually occurs if entity is coming from a read-only source
            # (eg ldap user)
            self.warning('cant change modification date for %s: %s', entity, ex)
