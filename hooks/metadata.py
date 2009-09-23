"""Core hooks: set generic metadata

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"


from datetime import datetime

from cubicweb.selectors import entity_implements
from cubicweb.server import hook
from cubicweb.server.repository import FTIndexEntityOp


def eschema_type_eid(session, etype):
    """get eid of the CWEType entity for the given yams type"""
    eschema = session.repo.schema.eschema(etype)
    # eschema.eid is None if schema has been readen from the filesystem, not
    # from the database (eg during tests)
    if eschema.eid is None:
        eschema.eid = session.unsafe_execute(
            'Any X WHERE X is CWEType, X name %(name)s',
            {'name': str(etype)})[0][0]
    return eschema.eid


class MetaDataHook(hook.Hook):
    __abstract__ = True
    category = 'metadata'


class InitMetaAttrsHook(MetaDataHook):
    """before create a new entity -> set creation and modification date

    this is a conveniency hook, you shouldn't have to disable it
    """
    __regid__ = 'metaattrsinit'
    events = ('before_add_entity',)

    def __call__(self):
        timestamp = datetime.now()
        self.entity.setdefault('creation_date', timestamp)
        self.entity.setdefault('modification_date', timestamp)
        if not self._cw.get_shared_data('do-not-insert-cwuri'):
            cwuri = u'%seid/%s' % (self._cw.base_url(), self.entity.eid)
            self.entity.setdefault('cwuri', cwuri)


class UpdateMetaAttrsHook(MetaDataHook):
    """update an entity -> set modification date"""
    __regid__ = 'metaattrsupdate'
    events = ('before_update_entity',)

    def __call__(self):
        self.entity.setdefault('modification_date', datetime.now())


class _SetCreatorOp(hook.Operation):

    def precommit_event(self):
        session = self.session
        if session.deleted_in_transaction(self.entity.eid):
            # entity have been created and deleted in the same transaction
            return
        if not self.entity.created_by:
            session.add_relation(self.entity.eid, 'created_by', session.user.eid)


class SetIsHook(MetaDataHook):
    """create a new entity -> set is relation"""
    __regid__ = 'setis'
    events = ('after_add_entity',)

    def __call__(self):
        if hasattr(self.entity, '_cw_recreating'):
            return
        session = self._cw
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


class SetOwnershipHook(MetaDataHook):
    """create a new entity -> set owner and creator metadata"""
    __regid__ = 'setowner'
    events = ('after_add_entity',)

    def __call__(self):
        asession = self._cw.actual_session()
        if not asession.is_internal_session:
            self._cw.add_relation(self.entity.eid, 'owned_by', asession.user.eid)
            _SetCreatorOp(asession, entity=self.entity)


class _SyncOwnersOp(hook.Operation):
    def precommit_event(self):
        self.session.unsafe_execute('SET X owned_by U WHERE C owned_by U, C eid %(c)s,'
                                    'NOT EXISTS(X owned_by U, X eid %(x)s)',
                                    {'c': self.compositeeid, 'x': self.composedeid},
                                    ('c', 'x'))


class SyncCompositeOwner(MetaDataHook):
    """when adding composite relation, the composed should have the same owners
    has the composite
    """
    __regid__ = 'synccompositeowner'
    events = ('after_add_relation',)

    def __call__(self):
        if self.rtype == 'wf_info_for':
            # skip this special composite relation # XXX (syt) why?
            return
        eidfrom, eidto = self.eidfrom, self.eidto
        composite = self._cw.schema_rproperty(self.rtype, eidfrom, eidto, 'composite')
        if composite == 'subject':
            _SyncOwnersOp(self._cw, compositeeid=eidfrom, composedeid=eidto)
        elif composite == 'object':
            _SyncOwnersOp(self._cw, compositeeid=eidto, composedeid=eidfrom)


class FixUserOwnershipHook(MetaDataHook):
    """when a user has been created, add owned_by relation on itself"""
    __regid__ = 'fixuserowner'
    __select__ = MetaDataHook.__select__ & entity_implements('CWUser')
    events = ('after_add_entity',)

    def __call__(self):
        self._cw.add_relation(self.entity.eid, 'owned_by', self.entity.eid)


class UpdateFTIHook(MetaDataHook):
    """sync fulltext index when relevant relation is added / removed
    """
    __regid__ = 'updateftirel'
    events = ('after_add_relation', 'after_delete_relation')

    def __call__(self):
        rtype = self.rtype
        session = self._cw
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

