from yams.schema import role_name
from cubicweb import ValidationError
from cubicweb.selectors import is_instance
from cubicweb.server import SOURCE_TYPES, hook

class SourceHook(hook.Hook):
    __abstract__ = True
    category = 'cw.sources'


class SourceAddedOp(hook.Operation):
    def postcommit_event(self):
        self.session.repo.add_source(self.entity)

class SourceAddedHook(SourceHook):
    __regid__ = 'cw.sources.added'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('after_add_entity',)
    def __call__(self):
        if not self.entity.type in SOURCE_TYPES:
            msg = self._cw._('unknown source type')
            raise ValidationError(self.entity.eid,
                                  {role_name('type', 'subject'): msg})
        SourceAddedOp(self._cw, entity=self.entity)


class SourceRemovedOp(hook.Operation):
    def precommit_event(self):
        self.session.repo.remove_source(self.uri)

class SourceRemovedHook(SourceHook):
    __regid__ = 'cw.sources.removed'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('before_delete_entity',)
    def __call__(self):
        if self.entity.name == 'system':
            raise ValidationError(self.entity.eid, {None: 'cant remove system source'})
        SourceRemovedOp(self._cw, uri=self.entity.name)

# source mapping synchronization. Expect cw_for_source/cw_schema are immutable
# relations (i.e. can't change from a source or schema to another).

class SourceMappingDeleteHook(SourceHook):
    """check cw_for_source and cw_schema are immutable relations

    XXX empty delete perms would be enough?
    """
    __regid__ = 'cw.sources.delschemaconfig'
    __select__ = SourceHook.__select__ & hook.match_rtype('cw_for_source', 'cw_schema')
    events = ('before_add_relation',)
    def __call__(self):
        if not self._cw.added_in_transaction(self.eidfrom):
            msg = self._cw._("can't change this relation")
            raise ValidationError(self.eidfrom, {self.rtype: msg})


class SourceMappingChangedOp(hook.DataOperationMixIn, hook.Operation):
    def check_or_update(self, checkonly):
        session = self.session
        # take care, can't call get_data() twice
        try:
            data = self.__data
        except AttributeError:
            data = self.__data = self.get_data()
        for schemacfg, source in data:
            if source is None:
                source = schemacfg.source
            if session.added_in_transaction(schemacfg.eid):
                if not session.deleted_in_transaction(schemacfg.eid):
                    source.add_schema_config(schemacfg, checkonly=checkonly)
            elif session.deleted_in_transaction(schemacfg.eid):
                source.delete_schema_config(schemacfg, checkonly=checkonly)
            else:
                source.update_schema_config(schemacfg, checkonly=checkonly)

    def precommit_event(self):
        self.check_or_update(True)

    def postcommit_event(self):
        self.check_or_update(False)


class SourceMappingChangedHook(SourceHook):
    __regid__ = 'cw.sources.schemaconfig'
    __select__ = SourceHook.__select__ & is_instance('CWSourceSchemaConfig')
    events = ('after_add_entity', 'after_update_entity')
    def __call__(self):
        if self.event == 'after_add_entity' or (
            self.event == 'after_update_entity' and 'options' in self.entity.cw_edited):
            SourceMappingChangedOp.get_instance(self._cw).add_data(
                (self.entity, None) )

class SourceMappingDeleteHook(SourceHook):
    __regid__ = 'cw.sources.delschemaconfig'
    __select__ = SourceHook.__select__ & hook.match_rtype('cw_for_source')
    events = ('before_delete_relation',)
    def __call__(self):
        SourceMappingChangedOp.get_instance(self._cw).add_data(
            (self._cw.entity_from_eid(self.eidfrom),
             self._cw.entity_from_eid(self.eidto)) )
