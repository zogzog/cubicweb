"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
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

