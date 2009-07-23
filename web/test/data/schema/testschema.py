"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from yams.buildobjs import (EntityType, RelationDefinition, RelationType, String,
                            Int, SubjectRelation)
from yams.constraints import IntervalBoundConstraint

class Salesterm(EntityType):
    described_by_test = SubjectRelation('File', cardinality='1*', composite='subject')
    amount = Int(constraints=[IntervalBoundConstraint(0, 100)])
    reason = String(maxsize=20, vocabulary=[u'canceled', u'sold'])

class tags(RelationDefinition):
    subject = 'Tag'
    object = ('BlogEntry', 'CWUser')

class checked_by(RelationType):
    subject = 'BlogEntry'
    object = 'CWUser'
    cardinality = '?*'
    permissions = {
        'add': ('managers',),
        'read': ('managers', 'users'),
        'delete': ('managers',),
        }
