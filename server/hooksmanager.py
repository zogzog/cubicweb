from logilab.common.deprecation import class_renamed, class_moved
from cubicweb.server import hook
SystemHook = class_renamed('SystemHook', hook.Hook)
PropagateSubjectRelationHook = class_renamed('PropagateSubjectRelationHook',
                                             hook.PropagateSubjectRelationHook)
PropagateSubjectRelationAddHook = class_renamed('PropagateSubjectRelationAddHook',
                                                hook.PropagateSubjectRelationAddHook)
PropagateSubjectRelationDelHook = class_renamed('PropagateSubjectRelationDelHook',
                                                hook.PropagateSubjectRelationDelHook)
Hook = class_moved(hook.Hook)
