from cubicweb import ValidationError
from cubicweb.selectors import is_instance
from cubicweb.server import hook

class SourceHook(hook.Hook):
    __abstract__ = True
    category = 'cw.sources'


class SourceAddedOp(hook.Operation):
    def precommit_event(self):
        self.session.repo.add_source(self.entity)

class SourceAddedHook(SourceHook):
    __regid__ = 'cw.sources.added'
    __select__ = SourceHook.__select__ & is_instance('CWSource')
    events = ('after_add_entity',)
    def __call__(self):
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
