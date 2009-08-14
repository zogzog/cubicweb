from logilab.common.deprecation import class_renamed, class_moved
from cubicweb.server.hook import Hook
SystemHook = class_renamed('SystemHook', Hook)
Hook = class_moved(Hook)
