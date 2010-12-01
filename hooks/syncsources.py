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

class SourceRemovedHook(SourceHook):
    __regid__ = 'cw.sources.removed'
    __select__ = SourceHook.__select__ & hook.match_rtype('cw_support', 'cw_may_cross')
    events = ('after_add_relation',)
    def __call__(self):
        entity = self._cw.entity_from_eid(self.eidto)
        if entity.__regid__ == 'CWRType' and entity.name in  ('is', 'is_instance_of', 'cw_source'):
            msg = self._cw._('the %s relation type can\'t be used here') % entity.name
            raise ValidationError(self.eidto, {role_name(self.rtype, 'subject'): msg})
