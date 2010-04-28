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
"""

"""
from yams.buildobjs import EntityType, SubjectRelation, String, Int, Date

from cubes.person.schema import Person

Person.add_relation(Date(), 'birthday')

class Bug(EntityType):
    title = String(maxsize=64, required=True, fulltextindexed=True)
    severity = String(vocabulary=('important', 'normal', 'minor'), default='normal')
    cost = Int()
    description	= String(maxsize=4096, fulltextindexed=True)
    identical_to = SubjectRelation('Bug', symmetric=True)

