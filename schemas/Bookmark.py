"""the Bookmark entity type for internal links

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from yams.buildobjs import EntityType, RelationType, String

class Bookmark(EntityType):
    """bookmarks are used to have user's specific internal links"""
    permissions = {
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
    permissions = {'read':   ('managers', 'users', 'guests',),
                   # test user in users group to avoid granting permission to anonymous user
                   'add':    ('managers', RRQLExpression('O identity U, U in_group G, G name "users"')),
                   'delete': ('managers', RRQLExpression('O identity U, U in_group G, G name "users"')),
                   }
