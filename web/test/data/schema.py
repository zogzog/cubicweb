"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from yams.buildobjs import (EntityType, RelationType, RelationDefinition,
                            SubjectRelation, ObjectRelation,
                            String, Int, Datetime, Boolean, Float)
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
    __permissions__ = {
        'add': ('managers',),
        'read': ('managers', 'users'),
        'delete': ('managers',),
        }

class Personne(EntityType):
    nom    = String(fulltextindexed=True, required=True, maxsize=64)
    prenom = String(fulltextindexed=True, maxsize=64)
    sexe   = String(maxsize=1, default='M')
    promo  = String(vocabulary=('bon','pasbon'))
    titre  = String(fulltextindexed=True, maxsize=128)
    ass    = String(maxsize=128)
    web    = String(maxsize=128)
    tel    = Int()
    fax    = Int()
    datenaiss = Datetime()
    test   = Boolean()
    description = String()
    salary = Float()
    travaille = SubjectRelation('Societe')
    connait = ObjectRelation('CWUser')

class Societe(EntityType):
    nom  = String(maxsize=64, fulltextindexed=True)
    web  = String(maxsize=128)
    type  = String(maxsize=128) # attribute in common with Note
    tel  = Int()
    fax  = Int()
    rncs = String(maxsize=128)
    ad1  = String(maxsize=128)
    ad2  = String(maxsize=128)
    ad3  = String(maxsize=128)
    cp   = String(maxsize=12)
    ville= String(maxsize=32)

