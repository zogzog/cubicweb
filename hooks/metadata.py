"""Core hooks: set generic metadata

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"


from datetime import datetime

from cubicweb.selectors import entity_implements
from cubicweb.server.hook import Hook
from cubicweb.server.pool import Operation, LateOperation, PreCommitOperation
from cubicweb.server.hookhelper import rproperty
from cubicweb.server.repository import FTIndexEntityOp


def eschema_type_eid(session, etype):
    """get eid of the CWEType entity for the given yams type"""
    eschema = session.repo.schema.eschema(etype)
    # eschema.eid is None if schema has been readen from the filesystem, not
    # from the database (eg during tests)
    if eschema.eid is None:
        eschema.eid = session.unsafe_execute(
            'Any X WHERE X is CWEType, X name %(name)s', {'name': etype})[0][0]
    return eschema.eid


class InitMetaAttrsHook(Hook):
    """before create a new entity -> set creation and modification date

    this is a conveniency hook, you shouldn't have to disable it
    """
    id = 'metaattrsinit'
    events = ('before_add_entity',)
    category = 'metadata'

    def __call__(self):
        timestamp = datetime.now()
        self.entity.setdefault('creation_date', timestamp)
        self.entity.setdefault('modification_date', timestamp)
        if not self.cw_req.get_shared_data('do-not-insert-cwuri'):
            cwuri = u'%seid/%s' % (self.cw_req.base_url(), self.entity.eid)
            self.entity.setdefault('cwuri', cwuri)


class UpdateMetaAttrsHook(Hook):
    """update an entity -> set modification date"""
    id = 'metaattrsupdate'
    events = ('before_update_entity',)
    category = 'metadata'
    def __call__(self):
        self.entity.setdefault('modification_date', datetime.now())


class _SetCreatorOp(PreCommitOperation):

    def precommit_event(self):
        session = self.session
        if self.entity.eid in session.transaction_data.get('pendingeids', ()):
            # entity have been created and deleted in the same transaction
            return
        if not self.entity.created_by:
            session.add_relation(self.entity.eid, 'created_by', session.user.eid)


class SetIsHook(Hook):
    """create a new entity -> set is relation"""
    id = 'setis'
    events = ('after_add_entity',)
    category = 'metadata'
    def __call__(self):
        if hasattr(self.entity, '_cw_recreating'):
            return
        session = self.cw_req
        entity = self.entity
        try:
            session.add_relation(entity.eid, 'is',
                                 eschema_type_eid(session, entity.id))
        except IndexError:
            # during schema serialization, skip
            return
        for etype in entity.e_schema.ancestors() + [entity.e_schema]:
            session.add_relation(entity.eid, 'is_instance_of',
                                 eschema_type_eid(session, etype))


class SetOwnershipHook(Hook):
    """create a new entity -> set owner and creator metadata"""
    id = 'setowner'
    events = ('after_add_entity',)
    category = 'metadata'
    def __call__(self):
        asession = self.cw_req.actual_session()
        if not asession.is_internal_session:
            self.cw_req.add_relation(self.entity.eid, 'owned_by', asession.user.eid)
            _SetCreatorOp(asession, entity=self.entity)


class _SyncOwnersOp(PreCommitOperation):
    def precommit_event(self):
        self.session.unsafe_execute('SET X owned_by U WHERE C owned_by U, C eid %(c)s,'
                                    'NOT EXISTS(X owned_by U, X eid %(x)s)',
                                    {'c': self.compositeeid, 'x': self.composedeid},
                                    ('c', 'x'))

class SyncCompositeOwner(Hook):
    """when adding composite relation, the composed should have the same owners
    has the composite
    """
    id = 'synccompositeowner'
    events = ('after_add_relation',)
    category = 'metadata'
    def __call__(self):
        if self.rtype == 'wf_info_for':
            # skip this special composite relation # XXX (syt) why?
            return
        eidfrom, eidto = self.eidfrom, self.eidto
        composite = rproperty(self.cw_req, self.rtype, eidfrom, eidto, 'composite')
        if composite == 'subject':
            _SyncOwnersOp(self.cw_req, compositeeid=eidfrom, composedeid=eidto)
        elif composite == 'object':
            _SyncOwnersOp(self.cw_req, compositeeid=eidto, composedeid=eidfrom)


class FixUserOwnershipHook(Hook):
    """when a user has been created, add owned_by relation on itself"""
    id = 'fixuserowner'
    __select__ = Hook.__select__ & entity_implements('CWUser')
    events = ('after_add_entity',)
    category = 'metadata'
    def __call__(self):
        self.cw_req.add_relation(self.entity.eid, 'owned_by', self.entity.eid)


class UpdateFTIHook(Hook):
    """sync fulltext index when relevant relation is added / removed
    """
    id = 'updateftirel'
    events = ('after_add_relation', 'after_delete_relation')
    category = 'metadata'

    def __call__(self):
        rtype = self.rtype
        session = self.cw_req
        if self.event == 'after_add_relation':
            # Reindexing the contained entity is enough since it will implicitly
            # reindex the container entity.
            ftcontainer = session.vreg.schema.rschema(rtype).fulltext_container
            if ftcontainer == 'subject':
                FTIndexEntityOp(session, entity=session.entity_from_eid(self.eidto))
            elif ftcontainer == 'object':
                FTIndexEntityOp(session, entity=session.entity_from_eid(self.eidfrom))
        elif session.repo.schema.rschema(rtype).fulltext_container:
            FTIndexEntityOp(session, entity=session.entity_from_eid(self.eidto))
            FTIndexEntityOp(session, entity=session.entity_from_eid(self.eidfrom))

