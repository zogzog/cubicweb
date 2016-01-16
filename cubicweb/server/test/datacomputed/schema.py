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

from yams.buildobjs import EntityType, RelationDefinition, ComputedRelation, Int, Float


class Employee(EntityType):
    pass


class employees(RelationDefinition):
    subject = 'Company'
    object = 'Employee'


class associates(RelationDefinition):
    subject = 'Company'
    object = 'Employee'


class Company(EntityType):
    score100 = Float(formula='Any AVG(NN) WHERE X employees E, N concerns E, N note100 NN')


class Note(EntityType):
    note = Int()
    note20 = Int(formula='Any N*20 WHERE X note N')
    note100 = Int(formula='Any N*20 WHERE X note N')


class concerns(RelationDefinition):
    subject = 'Note'
    object = 'Employee'


class notes(ComputedRelation):
    rule = 'S employees E, O concerns E'


class whatever(ComputedRelation):
    rule = 'S employees E, O concerns E'


class to_be_renamed(ComputedRelation):
    rule = 'S employees E, O concerns E'


class perm_changes(ComputedRelation):
    __permissions__ = {'read': ('managers', 'users')}
    rule = 'S employees E, O concerns E'
