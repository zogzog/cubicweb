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
from yams.buildobjs import (EntityType, RelationType, RelationDefinition,
                            SubjectRelation,
                            RichString, String, Int, Boolean, Datetime, Date)
from yams.constraints import SizeConstraint, UniqueConstraint
from cubicweb.schema import (WorkflowableEntityType, RQLConstraint,
                             ERQLExpression, RRQLExpression)

class Affaire(EntityType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', ERQLExpression('X concerne S, S owned_by U')),
        'update': ('managers', 'owners', ERQLExpression('X concerne S, S owned_by U')),
        'delete': ('managers', 'owners', ERQLExpression('X concerne S, S owned_by U')),
        }

    ref = String(fulltextindexed=True, indexed=True,
                 constraints=[SizeConstraint(16)])
    sujet = String(fulltextindexed=True,
                 constraints=[SizeConstraint(256)])
    concerne = SubjectRelation('Societe')

class concerne(RelationType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('U has_update_permission S')),
        'delete': ('managers', RRQLExpression('O owned_by U')),
        }

class Para(EntityType):
    para = String(maxsize=512)
    newattr = String()
    newinlined = SubjectRelation('Affaire', cardinality='?*', inlined=True)
    newnotinlined = SubjectRelation('Affaire', cardinality='?*')

class Note(Para):
    __specializes_schema__ = True

    __permissions__ = {'read':   ('managers', 'users', 'guests',),
                   'update': ('managers', 'owners',),
                   'delete': ('managers', ),
                   'add':    ('managers',
                              ERQLExpression('X ecrit_part PE, U in_group G, '
                                             'PE require_permission P, P name "add_note", '
                                             'P require_group G'),)}

    whatever = Int(default=2)  # keep it before `date` for unittest_migraction.test_add_attribute_int
    date = Datetime()
    type = String(maxsize=1)
    mydate = Date(default='TODAY')
    shortpara = String(maxsize=64)
    ecrit_par = SubjectRelation('Personne', constraints=[RQLConstraint('S concerne A, O concerne A')])
    attachment = SubjectRelation(('File', 'Image'))

class Text(Para):
    __specializes_schema__ = True
    summary = String(maxsize=512)

class ecrit_par(RelationType):
    __permissions__ = {'read':   ('managers', 'users', 'guests',),
                   'delete': ('managers', ),
                   'add':    ('managers',
                              RRQLExpression('O require_permission P, P name "add_note", '
                                             'U in_group G, P require_group G'),)
                   }
    inlined = True
    cardinality = '?*'


class Folder2(EntityType):
    """folders are used to classify entities. They may be defined as a tree.
    When you include the Folder entity, all application specific entities
    may then be classified using the "filed_under" relation.
    """
    name = String(required=True, indexed=True, internationalizable=True,
                  constraints=[UniqueConstraint(), SizeConstraint(64)])
    description = RichString(fulltextindexed=True)

class filed_under2(RelationDefinition):
    subject ='*'
    object = 'Folder2'


class Personne(EntityType):
    nom    = String(fulltextindexed=True, required=True, maxsize=64)
    prenom = String(fulltextindexed=True, maxsize=64)
    civility   = String(maxsize=1, default='M', fulltextindexed=True)
    promo  = String(vocabulary=('bon','pasbon'))
    titre  = String(fulltextindexed=True, maxsize=128)
    adel   = String(maxsize=128)
    ass    = String(maxsize=128)
    web    = String(maxsize=128)
    tel    = Int()
    fax    = Int()
    datenaiss = Datetime()
    test   = Boolean()

    travaille = SubjectRelation('Societe')
    concerne = SubjectRelation('Affaire')
    concerne2 = SubjectRelation(('Affaire', 'Note'), cardinality='1*')
    connait = SubjectRelation('Personne', symmetric=True)

class Societe(WorkflowableEntityType):
    __permissions__ = {
        'read': ('managers', 'users', 'guests'),
        'update': ('managers', 'owners'),
        'delete': ('managers', 'owners'),
        'add': ('managers', 'users',)
        }

    nom  = String(maxsize=64, fulltextindexed=True)
    web  = String(maxsize=128)
    tel  = Int()
    fax  = Int()
    rncs = String(maxsize=128)
    ad1  = String(maxsize=128)
    ad2  = String(maxsize=128)
    ad3  = String(maxsize=128)
    cp   = String(maxsize=12)
    ville= String(maxsize=32)


class evaluee(RelationDefinition):
    subject = ('Personne', 'CWUser', 'Societe')
    object = ('Note')
