"""hooks to handle attributes mapped to a custom storage
"""
from cubicweb.server.hook import Hook
from cubicweb.server.sources.storages import ETYPE_ATTR_STORAGE


class BFSSHook(Hook):
    """abstract class for bytes file-system storage hooks"""
    __abstract__ = True
    category = 'bfss'


class PreAddEntityHook(BFSSHook):
    """"""
    __regid__ = 'bfss_add_entity'
    events = ('before_add_entity', )

    def __call__(self):
        etype = self.entity.__regid__
        for attr in ETYPE_ATTR_STORAGE.get(etype, ()):
            ETYPE_ATTR_STORAGE[etype][attr].entity_added(self.entity, attr)

class PreUpdateEntityHook(BFSSHook):
    """"""
    __regid__ = 'bfss_update_entity'
    events = ('before_update_entity', )

    def __call__(self):
        etype = self.entity.__regid__
        for attr in ETYPE_ATTR_STORAGE.get(etype, ()):
            ETYPE_ATTR_STORAGE[etype][attr].entity_updated(self.entity, attr)

class PreDeleteEntityHook(BFSSHook):
    """"""
    __regid__ = 'bfss_delete_entity'
    events = ('before_delete_entity', )

    def __call__(self):
        etype = self.entity.__regid__
        for attr in ETYPE_ATTR_STORAGE.get(etype, ()):
            ETYPE_ATTR_STORAGE[etype][attr].entity_deleted(self.entity, attr)
