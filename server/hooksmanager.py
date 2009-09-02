from logilab.common.deprecation import class_renamed, class_moved
from cubicweb.server.hook import Hook
SystemHook = class_renamed('SystemHook', Hook)
PropagateSubjectRelationHook = class_renamed('PropagateSubjectRelationHook', Hook)
PropagateSubjectRelationAddHook = class_renamed('PropagateSubjectRelationAddHook', Hook)
PropagateSubjectRelationDelHook = class_renamed('PropagateSubjectRelationDelHook', Hook)
Hook = class_moved(Hook)

