# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from yams.buildobjs import EntityType, RelationDefinition, ComputedRelation


class Employee(EntityType):
    pass


class employees(RelationDefinition):
    subject = 'Company'
    object = 'Employee'


class associates(RelationDefinition):
    subject = 'Company'
    object = 'Employee'


class works_for(ComputedRelation):
    rule = 'O employees S, NOT EXISTS (O associates S)'


class Company(EntityType):
    pass


class Note(EntityType):
    pass


class concerns(RelationDefinition):
    subject = 'Note'
    object = 'Employee'

