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

from yams.buildobjs import EntityType, RelationDefinition, Int, ComputedRelation

class Person(EntityType):
    salary = Int()

class works_for(RelationDefinition):
    subject = 'Person'
    object  = 'Company'
    cardinality = '?*'

class Company(EntityType):
    total_salary = Int(formula='Any SUM(SA) GROUPBY X WHERE '
                       'P works_for X, P salary SA')

class has_employee(ComputedRelation):
    rule = 'O works_for S'
    __permissions__ = {'read': ('managers',)}
