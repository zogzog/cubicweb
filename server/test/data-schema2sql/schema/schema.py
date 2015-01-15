# copyright 2004-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of yams.
#
# yams is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# yams is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with yams. If not, see <http://www.gnu.org/licenses/>.
from yams.buildobjs import (EntityType, RelationDefinition, RelationType,
                            SubjectRelation, String, Int, Float, Date, Boolean)

class Affaire(EntityType):
    sujet = String(maxsize=128)
    ref = String(maxsize=12)

    concerne = SubjectRelation('Societe')
    obj_wildcard = SubjectRelation('*')
    sym_rel = SubjectRelation('Person', symmetric=True)
    inline_rel = SubjectRelation('Person', inlined=True, cardinality='?*')

class subj_wildcard(RelationDefinition):
    subject = '*'
    object = 'Affaire'


class Person(EntityType):
    __unique_together__ = [('nom', 'prenom')]
    nom    = String(maxsize=64, fulltextindexed=True, required=True)
    prenom = String(maxsize=64, fulltextindexed=True)
    sexe   = String(maxsize=1, default='M')
    promo  = String(vocabulary=('bon','pasbon'))
    titre  = String(maxsize=128, fulltextindexed=True)
    adel   = String(maxsize=128)
    ass    = String(maxsize=128)
    web    = String(maxsize=128)
    tel    = Int(__permissions__={'read': (),
                                  'add': ('managers',),
                                  'update': ('managers',)})
    fax    = Int()
    datenaiss = Date()
    test   = Boolean()
    salary = Float()
    travaille = SubjectRelation('Societe',
                                __permissions__={'read': (),
                                                 'add': (),
                                                 'delete': ('managers',),
                                                 })

    evaluee = SubjectRelation('Note')

class Salaried(Person):
    __specializes_schema__ = True

class Societe(EntityType):
    nom  = String(maxsize=64, fulltextindexed=True)
    web = String(maxsize=128)
    tel  = Int()
    fax  = Int()
    rncs = String(maxsize=32)
    ad1  = String(maxsize=128)
    ad2  = String(maxsize=128)
    ad3  = String(maxsize=128)
    cp   = String(maxsize=12)
    ville = String(maxsize=32)

    evaluee = SubjectRelation('Note')


class Note(EntityType):
    date = String(maxsize=10)
    type = String(maxsize=1)
    para = String(maxsize=512)


class pkginfo(EntityType):
    modname = String(maxsize=30, required=True)
    version = String(maxsize=10, required=True, default='0.1')
    copyright = String(required=True)
    license = String(vocabulary=('GPL', 'ZPL'))
    short_desc = String(maxsize=80, required=True)
    long_desc = String(required=True, fulltextindexed=True)
    author = String(maxsize=100, required=True)
    author_email = String(maxsize=100, required=True)
    mailinglist = String(maxsize=100)
    debian_handler = String(vocabulary=('machin', 'bidule'))


class evaluee(RelationType):
    __permissions__ = {
        'read': ('managers',),
        'add': ('managers',),
        'delete': ('managers',),
        }

class concerne(RelationDefinition):
    subject = 'Person'
    object = 'Affaire'
    __permissions__ = {
        'read': ('managers',),
        'add': ('managers',),
        'delete': ('managers',),
        }

