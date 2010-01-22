"""hooks to handle attributes mapped to a custom storage
"""
from os import unlink

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
    #__select__ = Hook.__select__ & implements('Repository')

    def __call__(self):
        for attr in ETYPE_ATTR_STORAGE.get(self.entity.__regid__, ()):
            fpath = ETYPE_ATTR_STORAGE[self.entity.__regid__][attr].entity_added(self.entity, attr)
            if fpath is not None:
                AddFileOp(filepath=fpath)

class PreUpdateEntityHook(BFSSHook):
    """"""
    __regid__ = 'bfss_update_entity'
    events = ('before_update_entity', )
    #__select__ = Hook.__select__ & implements('Repository')

    def __call__(self):
        for attr in ETYPE_ATTR_STORAGE.get(self.entity.__regid__, ()):
            ETYPE_ATTR_STORAGE[self.entity.__regid__][attr].entity_updated(self.entity, attr)

class PreDeleteEntityHook(BFSSHook):
    """"""
    __regid__ = 'bfss_delete_entity'
    events = ('before_delete_entity', )
    #__select__ = Hook.__select__ & implements('Repository')

    def __call__(self):
        for attr in ETYPE_ATTR_STORAGE.get(self.entity.__regid__, ()):
            ETYPE_ATTR_STORAGE[self.entity.__regid__][attr].entity_deleted(self.entity, attr)
