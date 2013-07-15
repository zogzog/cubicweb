# -*- coding: utf-8 -*-
# copyright 2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

"""cubicweb-forum views/forms/actions/components for web ui"""

from cubicweb.predicates import is_instance
from cubicweb.web.views import uicfg
from cubicweb.web.views.uicfg import autoform_section as afs

class MyAFS(uicfg.AutoformSectionRelationTags):
    __select__ = is_instance('ForumThread')

_myafs = MyAFS()
_myafs.__module__ = "cubes.i18ntestcube.views.uicfg"

_myafs.tag_object_of(('*', 'in_forum', 'Forum'), 'main', 'inlined')
