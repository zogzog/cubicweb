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
from yams.buildobjs import EntityType, String, Int, SubjectRelation, RelationDefinition

from cubicweb import _

THISYEAR = 2014

class Person(EntityType):
    name = String()
    salaire = Int()
    birth_year = Int(required=True)
    travaille = SubjectRelation('Societe')
    age = Int(formula='Any %d - D WHERE X birth_year D' % THISYEAR)

class Societe(EntityType):
    nom = String()
    salaire_total = Int(formula='Any SUM(SA) GROUPBY X WHERE P travaille X, P salaire SA')


class Agent(EntityType):
    asalae_id = String(formula='Any E WHERE M mirror_of X, M extid E')

class MirrorEntity(EntityType):
    extid = String(required=True, unique=True,
                   description=_('external identifier of the object'))


class mirror_of(RelationDefinition):
    subject  = 'MirrorEntity'
    object = ('Agent', 'Societe')
    cardinality = '?*'
    inlined = True
