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
"""Core hooks: set generic metadata

"""
__docformat__ = "restructuredtext en"


from datetime import datetime

from cubicweb.selectors import implements
from cubicweb.server import hook
from cubicweb.server.utils import eschema_eid


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
        # repairing is true during c-c upgrade/shell and similar commands. We
        # usually don't want to update modification date in such cases.
        #
        # XXX to be really clean, we should turn off modification_date update
        # explicitly on each command where we do not want that behaviour.
        if not self._cw.vreg.config.repairing:
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
    """create a new entity -> set is and is_instance_of relations

    those relations are inserted using sql so they are not hookable.
    """
    __regid__ = 'setis'
    events = ('after_add_entity',)

    def __call__(self):
        if hasattr(self.entity, '_cw_recreating'):
            return
        session = self._cw
        entity = self.entity
        try:
            session.system_sql('INSERT INTO is_relation(eid_from,eid_to) VALUES (%s,%s)'
                           % (entity.eid, eschema_eid(session, entity.e_schema)))
        except IndexError:
            # during schema serialization, skip
            return
        for eschema in entity.e_schema.ancestors() + [entity.e_schema]:
            session.system_sql('INSERT INTO is_instance_of_relation(eid_from,eid_to) VALUES (%s,%s)'
                               % (entity.eid, eschema_eid(session, eschema)))


class SetOwnershipHook(MetaDataHook):
    """create a new entity -> set owner and creator metadata"""
    __regid__ = 'setowner'
    events = ('after_add_entity',)

    def __call__(self):
        if not self._cw.is_internal_session:
            self._cw.add_relation(self.entity.eid, 'owned_by', self._cw.user.eid)
            _SetCreatorOp(self._cw, entity=self.entity)


class _SyncOwnersOp(hook.Operation):
    def precommit_event(self):
        self.session.execute('SET X owned_by U WHERE C owned_by U, C eid %(c)s,'
                             'NOT EXISTS(X owned_by U, X eid %(x)s)',
                             {'c': self.compositeeid, 'x': self.composedeid})


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
    __select__ = MetaDataHook.__select__ & implements('CWUser')
    events = ('after_add_entity',)

    def __call__(self):
        self._cw.add_relation(self.entity.eid, 'owned_by', self.entity.eid)


class UpdateFTIHook(MetaDataHook):
    """sync fulltext index text index container when a relation with
    fulltext_container set is added / removed
    """
    __regid__ = 'updateftirel'
    events = ('after_add_relation', 'after_delete_relation')

    def __call__(self):
        rtype = self.rtype
        session = self._cw
        ftcontainer = session.vreg.schema.rschema(rtype).fulltext_container
        if self.event == 'after_add_relation':
            if ftcontainer == 'subject':
                session.repo.system_source.index_entity(
                    session, session.entity_from_eid(self.eidfrom))
            elif ftcontainer == 'object':
                session.repo.system_source.index_entity(
                    session, session.entity_from_eid(self.eidto))
        # after delete relation
        elif ftcontainer == 'subject':
            session.repo.system_source.index_entity(
                session, entity=session.entity_from_eid(self.eidfrom))
        elif ftcontainer == 'object':
            session.repo.system_source.index_entity(
                session, entity=session.entity_from_eid(self.eidto))

