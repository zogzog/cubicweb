# copyright 2004-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from yams.buildobjs import EntityType, RelationType, RelationDefinition, \
     SubjectRelation, String

class Company(EntityType):
    name = String()

class Subcompany(Company):
    __specializes_schema__ = True
    subcompany_of = SubjectRelation('Company')

class Division(Company):
    __specializes_schema__ = True
    division_of = SubjectRelation('Company')

class Subdivision(Division):
    __specializes_schema__ = True
    subdivision_of = SubjectRelation('Company')

class Employee(EntityType):
    works_for = SubjectRelation('Company')

class require_permission(RelationType):
    """link a permission to the entity. This permission should be used in the
    security definition of the entity's type to be useful.
    """
    fulltext_container = 'subject'
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }


class missing_require_permission(RelationDefinition):
    name = 'require_permission'
    subject = 'Company'
    object = 'EPermission'

class EPermission(EntityType):
    """entity type that may be used to construct some advanced security configuration
    """
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers',),
        'delete': ('managers',),
        'update': ('managers', 'owners',),
        }
    name = String(required=True, indexed=True, internationalizable=True,
                  fulltextindexed=True, maxsize=100,
                  description=_('name or identifier of the permission'))
