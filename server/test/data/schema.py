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
                            SubjectRelation, RichString, String, Int, Boolean, Datetime)
from yams.constraints import SizeConstraint
from cubicweb.schema import (WorkflowableEntityType, RQLConstraint,
                             ERQLExpression, RRQLExpression)

class Affaire(WorkflowableEntityType):
    __permissions__ = {
        'read':   ('managers',
                   ERQLExpression('X owned_by U'), ERQLExpression('X concerne S?, S owned_by U')),
        'add':    ('managers', ERQLExpression('X concerne S, S owned_by U')),
        'update': ('managers', 'owners', ERQLExpression('X in_state S, S name in ("pitetre", "en cours")')),
        'delete': ('managers', 'owners', ERQLExpression('X concerne S, S owned_by U')),
        }

    ref = String(fulltextindexed=True, indexed=True,
                 constraints=[SizeConstraint(16)])
    sujet = String(fulltextindexed=True,
                   constraints=[SizeConstraint(256)])
    descr = RichString(fulltextindexed=True,
                       description=_('more detailed description'))

    duration = Int()
    invoiced = Int()

    depends_on = SubjectRelation('Affaire')
    require_permission = SubjectRelation('CWPermission')
    concerne = SubjectRelation(('Societe', 'Note'))
    todo_by = SubjectRelation('Personne', cardinality='?*')
    documented_by = SubjectRelation('Card')


class Societe(EntityType):
    __permissions__ = {
        'read': ('managers', 'users', 'guests'),
        'update': ('managers', 'owners', ERQLExpression('U login L, X nom L')),
        'delete': ('managers', 'owners', ERQLExpression('U login L, X nom L')),
        'add': ('managers', 'users',)
        }

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


class Division(Societe):
    __specializes_schema__ = True

class SubDivision(Division):
    __specializes_schema__ = True

class travaille_subdivision(RelationDefinition):
    subject = 'Personne'
    object = 'SubDivision'

from cubicweb.schemas.base import CWUser
CWUser.get_relations('login').next().fulltextindexed = True

class Note(WorkflowableEntityType):
    date = String(maxsize=10)
    type = String(maxsize=6)
    para = String(maxsize=512,
                  __permissions__ = {
                      'read':   ('managers', 'users', 'guests'),
                      'update': ('managers', ERQLExpression('X in_state S, S name "todo"')),
                      })

    migrated_from = SubjectRelation('Note')
    attachment = SubjectRelation(('File', 'Image'))
    inline1 = SubjectRelation('Affaire', inlined=True, cardinality='?*')
    todo_by = SubjectRelation('CWUser')

class Personne(EntityType):
    nom    = String(fulltextindexed=True, required=True, maxsize=64)
    prenom = String(fulltextindexed=True, maxsize=64)
    sexe   = String(maxsize=1, default='M', fulltextindexed=True)
    promo  = String(vocabulary=('bon','pasbon'))
    titre  = String(fulltextindexed=True, maxsize=128)
    adel   = String(maxsize=128)
    ass    = String(maxsize=128)
    web    = String(maxsize=128)
    tel    = Int()
    fax    = Int()
    datenaiss = Datetime()
    test   = Boolean(__permissions__={
        'read': ('managers', 'users', 'guests'),
        'update': ('managers',),
        })
    description = String()
    firstname = String(fulltextindexed=True, maxsize=64)

    concerne = SubjectRelation('Affaire')
    connait = SubjectRelation('Personne')
    inline2 = SubjectRelation('Affaire', inlined=True, cardinality='?*')



class connait(RelationType):
    symmetric = True

class concerne(RelationType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('U has_update_permission S')),
        'delete': ('managers', RRQLExpression('O owned_by U')),
        }

class travaille(RelationDefinition):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('U has_update_permission S')),
        'delete': ('managers', RRQLExpression('O owned_by U')),
        }
    subject = 'Personne'
    object = 'Societe'

class comments(RelationDefinition):
    subject = 'Comment'
    object = 'Personne'

class fiche(RelationDefinition):
    inlined = True
    subject = 'Personne'
    object = 'Card'
    cardinality = '??'

class multisource_inlined_rel(RelationDefinition):
    inlined = True
    cardinality = '?*'
    subject = ('Card', 'Note')
    object = ('Affaire', 'Note')

class multisource_rel(RelationDefinition):
    subject = ('Card', 'Note')
    object = 'Note'

class multisource_crossed_rel(RelationDefinition):
    subject = ('Card', 'Note')
    object = 'Note'


class see_also_1(RelationDefinition):
    name = 'see_also'
    subject = object = 'Folder'

class see_also_2(RelationDefinition):
    name = 'see_also'
    subject = ('Bookmark', 'Note')
    object = ('Bookmark', 'Note')

class evaluee(RelationDefinition):
    subject = ('Personne', 'CWUser', 'Societe')
    object = ('Note')

class ecrit_par(RelationType):
    inlined = True

class ecrit_par_1(RelationDefinition):
    name = 'ecrit_par'
    subject = 'Note'
    object ='Personne'
    constraints = [RQLConstraint('E concerns P, S version_of P')]
    cardinality = '?*'

class ecrit_par_2(RelationDefinition):
    name = 'ecrit_par'
    subject = 'Note'
    object ='CWUser'
    cardinality='?*'


class copain(RelationDefinition):
    subject = object = 'CWUser'

class tags(RelationDefinition):
    subject = 'Tag'
    object = ('CWUser', 'CWGroup', 'State', 'Note', 'Card', 'Affaire')

class filed_under(RelationDefinition):
    subject = ('Note', 'Affaire')
    object = 'Folder'

class require_permission(RelationDefinition):
    subject = ('Card', 'Note', 'Personne')
    object = 'CWPermission'

class require_state(RelationDefinition):
    subject = 'CWPermission'
    object = 'State'
