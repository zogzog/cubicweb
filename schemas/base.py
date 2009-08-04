"""core CubicWeb schema, but not necessary at bootstrap time

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from yams.buildobjs import (EntityType, RelationType, SubjectRelation,
                            String, Boolean, Datetime, Password)
from cubicweb.schema import (RQLConstraint, WorkflowableEntityType,
                             ERQLExpression, RRQLExpression)
from cubicweb.schemas import META_ETYPE_PERMS, META_RTYPE_PERMS

class CWUser(WorkflowableEntityType):
    """define a CubicWeb user"""
    permissions = {
        'read':   ('managers', 'users', ERQLExpression('X identity U')),
        'add':    ('managers',),
        'delete': ('managers',),
        'update': ('managers', ERQLExpression('X identity U, NOT U in_group G, G name "guests"'),),
        }

    login     = String(required=True, unique=True, maxsize=64,
                       description=_('unique identifier used to connect to the application'))
    upassword = Password(required=True) # password is a reserved word for mysql
    firstname = String(maxsize=64)
    surname   = String(maxsize=64)
    last_login_time  = Datetime(description=_('last connection date'))
    # allowing an email to be the primary email of multiple entities is necessary for
    # test at least :-/
    primary_email = SubjectRelation('EmailAddress', cardinality='??',
                                    description=_('email address to use for notification'))
    use_email     = SubjectRelation('EmailAddress', cardinality='*?', composite='subject')

    in_group = SubjectRelation('CWGroup', cardinality='+*',
                               constraints=[RQLConstraint('NOT O name "owners"')],
                               description=_('groups grant permissions to the user'))


class EmailAddress(EntityType):
    """an electronic mail address associated to a short alias"""
    permissions = {
        'read':   ('managers', 'users', 'guests',), # XXX if P use_email X, U has_read_permission P
        'add':    ('managers', 'users',),
        'delete': ('managers', 'owners', ERQLExpression('P use_email X, U has_update_permission P')),
        'update': ('managers', 'owners', ERQLExpression('P use_email X, U has_update_permission P')),
        }

    alias   = String(fulltextindexed=True, maxsize=56)
    address = String(required=True, fulltextindexed=True,
                     indexed=True, unique=True, maxsize=128)
    canonical = Boolean(default=False,
                        description=_('when multiple addresses are equivalent \
(such as python-projects@logilab.org and python-projects@lists.logilab.org), set this \
to true on one of them which is the preferred form.'))
    identical_to = SubjectRelation('EmailAddress')

class use_email(RelationType):
    """ """
    permissions = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', RRQLExpression('U has_update_permission S'),),
        'delete': ('managers', RRQLExpression('U has_update_permission S'),),
        }
    fulltext_container = 'subject'

class primary_email(RelationType):
    """the prefered email"""
    permissions = use_email.permissions

class identical_to(RelationType):
    """identical_to"""
    symetric = True
    permissions = {
        'read':   ('managers', 'users', 'guests',),
        # XXX should have update permissions on both subject and object,
        #     though by doing this we will probably have no way to add
        #     this relation in the web ui. The easiest way to acheive this
        #     is probably to be able to have "U has_update_permission O" as
        #     RQLConstraint of the relation definition, though this is not yet
        #     possible
        'add':    ('managers', RRQLExpression('U has_update_permission S'),),
        'delete': ('managers', RRQLExpression('U has_update_permission S'),),
        }

class in_group(RelationType):
    """core relation indicating a user's groups"""
    permissions = META_RTYPE_PERMS

class owned_by(RelationType):
    """core relation indicating owners of an entity. This relation
    implicitly put the owner into the owners group for the entity
    """
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('S owned_by U'),),
        'delete': ('managers', RRQLExpression('S owned_by U'),),
        }
    # 0..n cardinality for entities created by internal session (no attached user)
    # and to support later deletion of a user which has created some entities
    cardinality = '**'
    subject = '*'
    object = 'CWUser'

class created_by(RelationType):
    """core relation indicating the original creator of an entity"""
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    # 0..1 cardinality for entities created by internal session (no attached user)
    # and to support later deletion of a user which has created some entities
    cardinality = '?*'
    subject = '*'
    object = 'CWUser'


class creation_date(RelationType):
    """creation time of an entity"""
    cardinality = '11'
    subject = '*'
    object = 'Datetime'

class modification_date(RelationType):
    """latest modification time of an entity"""
    cardinality = '11'
    subject = '*'
    object = 'Datetime'

class cwuri(RelationType):
    """internal entity uri"""
    cardinality = '11'
    subject = '*'
    object = 'String'


class CWProperty(EntityType):
    """used for cubicweb configuration. Once a property has been created you
    can't change the key.
    """
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', 'users',),
        'update': ('managers', 'owners',),
        'delete': ('managers', 'owners',),
        }
    # key is a reserved word for mysql
    pkey = String(required=True, internationalizable=True, maxsize=256,
                  description=_('defines what\'s the property is applied for. '
                                'You must select this first to be able to set '
                                'value'))
    value = String(internationalizable=True, maxsize=256)

    for_user = SubjectRelation('CWUser', cardinality='?*', composite='object',
                               description=_('user for which this property is '
                                             'applying. If this relation is not '
                                             'set, the property is considered as'
                                             ' a global property'))


class for_user(RelationType):
    """link a property to the user which want this property customization. Unless
    you're a site manager, this relation will be handled automatically.
    """
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    inlined = True


class CWPermission(EntityType):
    """entity type that may be used to construct some advanced security configuration
    """
    permissions = META_ETYPE_PERMS

    name = String(required=True, indexed=True, internationalizable=True, maxsize=100,
                  description=_('name or identifier of the permission'))
    label = String(required=True, internationalizable=True, maxsize=100,
                   description=_('distinct label to distinguate between other permission entity of the same name'))
    require_group = SubjectRelation('CWGroup',
                                    description=_('groups to which the permission is granted'))

# explicitly add X require_permission CWPermission for each entity that should have
# configurable security
class require_permission(RelationType):
    """link a permission to the entity. This permission should be used in the
    security definition of the entity's type to be useful.
    """
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }

class require_group(RelationType):
    """used to grant a permission to a group"""
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }


class see_also(RelationType):
    """generic relation to link one entity to another"""
    symetric = True

class ExternalUri(EntityType):
    """a URI representing an object in external data store"""
    uri = String(required=True, unique=True, maxsize=256,
                 description=_('the URI of the object'))

class same_as(RelationType):
    """generic relation to specify that an external entity represent the same
    object as a local one:
       http://www.w3.org/TR/owl-ref/#sameAs-def

    NOTE: You'll have to explicitly declare which entity types can have a
    same_as relation
    """
    permissions = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users'),
        'delete': ('managers', 'owners'),
        }
    cardinality = '*1'
    symetric = True
    # NOTE: the 'object = ExternalUri' declaration will still be mandatory
    #       in the cube's schema.
    object = 'ExternalUri'

class CWCache(EntityType):
    """a simple cache entity characterized by a name and
    a validity date.

    The target application is responsible for updating timestamp
    when necessary to invalidate the cache (typically in hooks).

    Also, checkout the AppObject.get_cache() method.
    """
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'update': ('managers', 'users',), # XXX
        'delete': ('managers',),
        }

    name = String(required=True, unique=True, indexed=True,  maxsize=128,
                  description=_('name of the cache'))
    timestamp = Datetime(default='NOW')
