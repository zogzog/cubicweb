from cubicweb.predicates import is_instance
from cubicweb.hooks import notification


class FolderUpdateHook(notification.EntityUpdateHook):
    __select__ = (notification.EntityUpdateHook.__select__
                  & is_instance('Folder'))
    order = 100  # late trigger so that metadata hooks come before.
