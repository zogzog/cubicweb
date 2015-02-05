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
"""Core hooks: set generic metadata"""

__docformat__ = "restructuredtext en"

from datetime import datetime

from cubicweb.predicates import is_instance
from cubicweb.server import hook
from cubicweb.server.edition import EditedEntity


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
        edited = self.entity.cw_edited
        if not edited.get('creation_date'):
            edited['creation_date'] = timestamp
        if not edited.get('modification_date'):
            edited['modification_date'] = timestamp
        if not self._cw.transaction_data.get('do-not-insert-cwuri'):
            cwuri = u'%s%s' % (self._cw.base_url(), self.entity.eid)
            edited.setdefault('cwuri', cwuri)


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
            self.entity.cw_edited.setdefault('modification_date', datetime.now())


class SetCreatorOp(hook.DataOperationMixIn, hook.Operation):

    def precommit_event(self):
        cnx = self.cnx
        relations = [(eid, cnx.user.eid) for eid in self.get_data()
                # don't consider entities that have been created and deleted in
                # the same transaction, nor ones where created_by has been
                # explicitly set
                if not cnx.deleted_in_transaction(eid) and \
                   not cnx.entity_from_eid(eid).created_by]
        cnx.add_relations([('created_by', relations)])


class SetOwnershipHook(MetaDataHook):
    """create a new entity -> set owner and creator metadata"""
    __regid__ = 'setowner'
    events = ('after_add_entity',)

    def __call__(self):
        if not self._cw.is_internal_session:
            self._cw.add_relation(self.entity.eid, 'owned_by', self._cw.user.eid)
            SetCreatorOp.get_instance(self._cw).add_data(self.entity.eid)


class SyncOwnersOp(hook.DataOperationMixIn, hook.Operation):
    def precommit_event(self):
        for compositeeid, composedeid in self.get_data():
            if self.cnx.deleted_in_transaction(compositeeid):
                continue
            if self.cnx.deleted_in_transaction(composedeid):
                continue
            self.cnx.execute('SET X owned_by U WHERE C owned_by U, C eid %(c)s,'
                                 'NOT EXISTS(X owned_by U, X eid %(x)s)',
                                 {'c': compositeeid, 'x': composedeid})


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
        composite = self._cw.rtype_eids_rdef(self.rtype, eidfrom, eidto).composite
        if composite == 'subject':
            SyncOwnersOp.get_instance(self._cw).add_data( (eidfrom, eidto) )
        elif composite == 'object':
            SyncOwnersOp.get_instance(self._cw).add_data( (eidto, eidfrom) )


class FixUserOwnershipHook(MetaDataHook):
    """when a user has been created, add owned_by relation on itself"""
    __regid__ = 'fixuserowner'
    __select__ = MetaDataHook.__select__ & is_instance('CWUser')
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
        cnx = self._cw
        ftcontainer = cnx.vreg.schema.rschema(rtype).fulltext_container
        if ftcontainer == 'subject':
            cnx.repo.system_source.index_entity(
                cnx, cnx.entity_from_eid(self.eidfrom))
        elif ftcontainer == 'object':
            cnx.repo.system_source.index_entity(
                cnx, cnx.entity_from_eid(self.eidto))



# entity source handling #######################################################

class ChangeEntitySourceUpdateCaches(hook.Operation):
    oldsource = newsource = entity = None # make pylint happy

    def postcommit_event(self):
        self.oldsource.reset_caches()
        repo = self.cnx.repo
        entity = self.entity
        extid = entity.cw_metainformation()['extid']
        repo._type_source_cache[entity.eid] = (
            entity.cw_etype, None, self.newsource.uri)
        repo._extid_cache[extid] = -entity.eid


class ChangeEntitySourceDeleteHook(MetaDataHook):
    """support for moving an entity from an external source by watching 'Any
    cw_source CWSource' relation
    """

    __regid__ = 'cw.metadata.source-change'
    __select__ = MetaDataHook.__select__ & hook.match_rtype('cw_source')
    events = ('before_delete_relation',)

    def __call__(self):
        if (self._cw.deleted_in_transaction(self.eidfrom)
            or self._cw.deleted_in_transaction(self.eidto)):
            return
        schange = self._cw.transaction_data.setdefault('cw_source_change', {})
        schange[self.eidfrom] = self.eidto


class ChangeEntitySourceAddHook(MetaDataHook):
    __regid__ = 'cw.metadata.source-change'
    __select__ = MetaDataHook.__select__ & hook.match_rtype('cw_source')
    events = ('before_add_relation',)

    def __call__(self):
        schange = self._cw.transaction_data.get('cw_source_change')
        if schange is not None and self.eidfrom in schange:
            newsource = self._cw.entity_from_eid(self.eidto)
            if newsource.name != 'system':
                raise Exception('changing source to something else than the '
                                'system source is unsupported')
            syssource = newsource.repo_source
            oldsource = self._cw.entity_from_eid(schange[self.eidfrom])
            entity = self._cw.entity_from_eid(self.eidfrom)
            # we don't want the moved entity to be reimported later.  To
            # distinguish this state, the trick is to change the associated
            # record in the 'entities' system table with eid=-eid while leaving
            # other fields unchanged, and to add a new record with eid=eid,
            # source='system'. External source will then have consider case
            # where `extid2eid` return a negative eid as 'this entity was known
            # but has been moved, ignore it'.
            self._cw.system_sql('UPDATE entities SET eid=-eid WHERE eid=%(eid)s',
                                {'eid': self.eidfrom})
            attrs = {'type': entity.cw_etype, 'eid': entity.eid, 'extid': None,
                     'asource': 'system'}
            self._cw.system_sql(syssource.sqlgen.insert('entities', attrs), attrs)
            # register an operation to update repository/sources caches
            ChangeEntitySourceUpdateCaches(self._cw, entity=entity,
                                           oldsource=oldsource.repo_source,
                                           newsource=syssource)
