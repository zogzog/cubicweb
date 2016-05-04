# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from yams.buildobjs import (EntityType, RelationDefinition, SubjectRelation,
                            String, Int, Datetime, Boolean, Float, TZDatetime)
from yams.constraints import IntervalBoundConstraint

from cubicweb import _


class Salesterm(EntityType):
    described_by_test = SubjectRelation('File', cardinality='1*',
                                        composite='subject', inlined=True)
    amount = Int(constraints=[IntervalBoundConstraint(0, 100)])
    reason = String(maxsize=20, vocabulary=[u'canceled', u'sold'])

class tags(RelationDefinition):
    subject = 'Tag'
    object = ('BlogEntry', 'CWUser')

class checked_by(RelationDefinition):
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
    sexe   = String(maxsize=1, default='M',
                    __permissions__={
                        'read': ('managers', 'users', 'guests',),
                        'add': ('managers', 'users'),
                        'update': ('managers', )})
    promo  = String(vocabulary=('bon','pasbon'))
    titre  = String(fulltextindexed=True, maxsize=128)
    ass    = String(maxsize=128)
    web    = String(maxsize=128)
    tel    = Int()
    fax    = Int()
    datenaiss = Datetime()
    tzdatenaiss = TZDatetime()
    test   = Boolean()
    description = String()
    salary = Float()
    travaille = SubjectRelation('Societe')

class connait(RelationDefinition):
    subject = 'CWUser'
    object = 'Personne'

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

# enough relations to cover most reledit use cases
class Project(EntityType):
    title = String(maxsize=32, required=True, fulltextindexed=True)
    long_desc = SubjectRelation('Blog', composite='subject', cardinality='?*')
    manager = SubjectRelation('Personne', cardinality='?*')

class composite_card11_2ttypes(RelationDefinition):
    subject = 'Project'
    object = ('File', 'Blog')
    composite = 'subject'
    cardinality = '?*'

class Ticket(EntityType):
    title = String(maxsize=32, required=True, fulltextindexed=True)
    concerns = SubjectRelation('Project', composite='object')
    in_version = SubjectRelation('Version', composite='object',
                                 cardinality='?*', inlined=True)

class Version(EntityType):
    name = String(required=True)

class Filesystem(EntityType):
    name = String()

class DirectoryPermission(EntityType):
    value = String()

class parent_fs(RelationDefinition):
    name = 'parent'
    subject = 'Directory'
    object = 'Filesystem'

class Directory(EntityType):
    name = String(required=True)
    has_permission = SubjectRelation('DirectoryPermission', cardinality='*1',
                                     composite='subject')

class parent_directory(RelationDefinition):
    name = 'parent'
    subject = 'Directory'
    object = 'Directory'
    composite = 'object'

class Folder(EntityType):
    name = String(required=True)
    filed_under = SubjectRelation('Folder', description=_('parent folder'))

class TreeNode(EntityType):
    name = String(required=True)
    parent = SubjectRelation('TreeNode', cardinality='?*')
