# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
