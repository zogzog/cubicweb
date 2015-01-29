# copyright 2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.predicates import is_instance
from cubicweb.entities.adapters import ITreeAdapter
from cubicweb.entities import AnyEntity, fetch_config


class TreeNode(AnyEntity):
    __regid__ = 'TreeNode'
    fetch_attrs, cw_fetch_order = fetch_config(['name'])


class ITreeNode(ITreeAdapter):
    __select__ = is_instance('TreeNode')
    tree_relation = 'parent'
