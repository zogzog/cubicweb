# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""schema for cubicweb.devtools tests"""
from yams.buildobjs import EntityType, SubjectRelation, String, RichString, Int, Date


class Person(EntityType):
    """a physical person"""
    surname = String(required=True, fulltextindexed=True, indexed=True,
                     maxsize=64)
    firstname = String(fulltextindexed=True, maxsize=64)
    civility = String(required=True, internationalizable=True,
                      vocabulary=('Mr', 'Ms', 'Mrs'),
                      default='Mr')
    description = RichString(fulltextindexed=True)
    birthday = Date()


class Bug(EntityType):
    title = String(maxsize=64, required=True, fulltextindexed=True)
    severity = String(vocabulary=('important', 'normal', 'minor'),
                      default='normal')
    cost = Int()
    description = String(maxsize=4096, fulltextindexed=True)
    identical_to = SubjectRelation('Bug', symmetric=True)
