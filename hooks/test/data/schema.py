# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from yams.buildobjs import RelationDefinition, EntityType, String

class friend(RelationDefinition):
    subject = ('CWUser', 'CWGroup')
    object = ('CWUser', 'CWGroup')
    symmetric = True

class Folder(EntityType):
    name = String()

class parent(RelationDefinition):
    subject = 'Folder'
    object = 'Folder'
    composite = 'object'
    cardinality = '?*'

class children(RelationDefinition):
    subject = 'Folder'
    object = 'Folder'
    composite = 'subject'
