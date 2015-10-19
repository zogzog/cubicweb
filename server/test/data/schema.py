# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from yams.buildobjs import (EntityType, RelationType, RelationDefinition, ComputedRelation,
                            SubjectRelation, RichString, String, Int, Float,
                            Boolean, Datetime, TZDatetime, Bytes)
from yams.constraints import SizeConstraint
from cubicweb.schema import (WorkflowableEntityType,
                             RQLConstraint, RQLUniqueConstraint,
                             RQLVocabularyConstraint,
                             ERQLExpression, RRQLExpression)
from cubicweb import _

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
    invoiced = Float()
    opt_attr = Bytes()

    depends_on = SubjectRelation('Affaire')
    require_permission = SubjectRelation('CWPermission')
    concerne = SubjectRelation(('Societe', 'Note'))
    todo_by = SubjectRelation('Personne', cardinality='?*')
    documented_by = SubjectRelation('Card')


class Societe(EntityType):
    __unique_together__ = [('nom', 'type', 'cp')]
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
next(CWUser.get_relations('login')).fulltextindexed = True

class Note(WorkflowableEntityType):
    date = String(maxsize=10)
    type = String(vocabulary=[u'todo', u'a', u'b', u'T', u'lalala'])
    para = String(maxsize=512,
                  __permissions__ = {
                      'add': ('managers', ERQLExpression('X in_state S, S name "todo"')),
                      'read':   ('managers', 'users', 'guests'),
                      'update': ('managers', ERQLExpression('X in_state S, S name "todo"')),
                      })
    something = String(maxsize=1,
                      __permissions__ = {
                          'read': ('managers', 'users', 'guests'),
                          'add': (ERQLExpression('NOT X para NULL'),),
                          'update': ('managers', 'owners')
                      })
    migrated_from = SubjectRelation('Note')
    attachment = SubjectRelation('File')
    inline1 = SubjectRelation('Affaire', inlined=True, cardinality='?*',
                              constraints=[RQLUniqueConstraint('S type T, S inline1 A1, A1 todo_by C, '
                                                              'Y type T, Y inline1 A2, A2 todo_by C',
                                                               'S,Y')])
    todo_by = SubjectRelation('CWUser')


class Frozable(EntityType):
    __permissions__ = {
        'read':   ('managers', 'users'),
        'add':    ('managers', 'users'),
        'update': ('managers', ERQLExpression('X frozen False'),),
        'delete': ('managers', ERQLExpression('X frozen False'),)
    }
    name = String()
    frozen = Boolean(default=False,
                     __permissions__ = {
                         'read':   ('managers', 'users'),
                         'add':    ('managers', 'users'),
                         'update': ('managers', 'owners')
                         })


class Personne(EntityType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'), # 'guests' will be removed
        'add':    ('managers', 'users'),
        'update': ('managers', 'owners'),
        'delete': ('managers', 'owners')
    }
    __unique_together__ = [('nom', 'prenom', 'inline2')]
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
    tzdatenaiss = TZDatetime()
    test   = Boolean(__permissions__={
        'read': ('managers', 'users', 'guests'),
        'add': ('managers',),
        'update': ('managers',),
        })
    description = String()
    firstname = String(fulltextindexed=True, maxsize=64)

    concerne = SubjectRelation('Affaire')
    connait = SubjectRelation('Personne')
    inline2 = SubjectRelation('Affaire', inlined=True, cardinality='?*')


class Old(EntityType):
    name = String(__permissions__ = {
        'read'   : ('managers', 'users', 'guests'),
        'add'    : ('managers', 'users', 'guests'),
        'update' : ()
    })


class Email(EntityType):
    subject = String(fulltextindexed=True)
    messageid = String(required=True, indexed=True, unique=True)
    sender = SubjectRelation('EmailAddress', cardinality='?*')
    recipients = SubjectRelation('EmailAddress')
    attachment = SubjectRelation('File')


class EmailPart(EntityType):
    pass


class EmailThread(EntityType):
    see_also = SubjectRelation('EmailThread')


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
    constraints = [RQLVocabularyConstraint('S owned_by U'),
                   RQLVocabularyConstraint('S created_by U')]

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
    constraints = [
        RQLVocabularyConstraint('S created_by U'),
        RQLVocabularyConstraint('S owned_by U'),
    ]

class ecrit_par(RelationType):
    inlined = True

class ecrit_par_1(RelationDefinition):
    name = 'ecrit_par'
    subject = 'Note'
    object ='Personne'
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

class Folder(EntityType):
    """folders are used to classify entities. They may be defined as a tree.
    """
    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=64)
    description = RichString(fulltextindexed=True)
    filed_under = SubjectRelation('Folder', description=_('parent folder'))

class filed_under(RelationDefinition):
    subject = ('Note', 'Affaire')
    object = 'Folder'

class require_permission(RelationDefinition):
    subject = ('Card', 'Note', 'Personne')
    object = 'CWPermission'

class require_state(RelationDefinition):
    subject = 'CWPermission'
    object = 'State'

class personne_composite(RelationDefinition):
    subject='Personne'
    object='Personne'
    composite='subject'

class personne_inlined(RelationDefinition):
    subject='Personne'
    object='Personne'
    cardinality='?*'
    inlined=True


class login_user(RelationDefinition):
    subject = 'Personne'
    object = 'CWUser'
    cardinality = '??'

class ambiguous_inlined(RelationDefinition):
    subject = ('Affaire', 'Note')
    object = 'CWUser'
    inlined = True
    cardinality = '?*'


class user_login(ComputedRelation):
    rule = 'O login_user S'
