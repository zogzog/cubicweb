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
"""the Bookmark entity type for internal links

"""
__docformat__ = "restructuredtext en"
_ = unicode

from yams.buildobjs import EntityType, RelationType, SubjectRelation, String
from cubicweb.schema import RRQLExpression

class Bookmark(EntityType):
    """bookmarks are used to have user's specific internal links"""
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users',),
        'delete': ('managers', 'owners',),
        'update': ('managers', 'owners',),
        }

    title = String(required=True, maxsize=128, internationalizable=True)
    path  = String(maxsize=512, required=True,
                   description=_("relative url of the bookmarked page"))

    bookmarked_by = SubjectRelation('CWUser',
                                    description=_("users using this bookmark"))


class bookmarked_by(RelationType):
    __permissions__ = {'read':   ('managers', 'users', 'guests',),
                   # test user in users group to avoid granting permission to anonymous user
                   'add':    ('managers', RRQLExpression('O identity U, U in_group G, G name "users"')),
                   'delete': ('managers', RRQLExpression('O identity U, U in_group G, G name "users"')),
                   }
