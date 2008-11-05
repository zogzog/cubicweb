"""core CubicWeb schema, but not necessary at bootstrap time

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.schema import format_constraint


class EUser(RestrictedEntityType):
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

    in_group = SubjectRelation('EGroup', cardinality='+*',
                               constraints=[RQLConstraint('NOT O name "owners"')],
                               description=_('groups grant permissions to the user'))
    in_state = SubjectRelation('State', cardinality='1*',
                               # XXX automatize this
                               constraints=[RQLConstraint('S is ET, O state_of ET')],
                               description=_('account state'))
    wf_info_for = ObjectRelation('TrInfo', cardinality='1*', composite='object')


class EmailAddress(MetaEntityType):
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
    """"""
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

class in_group(MetaRelationType):
    """core relation indicating a user's groups"""
    meta = False
    
class owned_by(MetaRelationType):
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
    subject = '**'
    object = 'EUser'
    
class created_by(MetaRelationType):
    """core relation indicating the original creator of an entity"""
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    # 0..1 cardinality for entities created by internal session (no attached user)
    # and to support later deletion of a user which has created some entities
    cardinality = '?*' 
    subject = '**'
    object = 'EUser'

    
class creation_date(MetaAttributeRelationType):
    """creation time of an entity"""
    cardinality = '11'
    subject = '**'
    object = 'Datetime'

class modification_date(MetaAttributeRelationType):
    """latest modification time of an entity"""
    cardinality = '11'
    subject = '**'
    object = 'Datetime'


class State(MetaEntityType):
    """used to associate simple states to an entity type and/or to define
    workflows
    """
    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description_format = String(meta=True, internationalizable=True, maxsize=50,
                                default='text/rest', constraints=[format_constraint])
    description = String(fulltextindexed=True,
                         description=_('semantic description of this state'))
    
    state_of = SubjectRelation('EEType', cardinality='+*',
                    description=_('entity types which may use this state'),
                    constraints=[RQLConstraint('O final FALSE')])
    allowed_transition = SubjectRelation('Transition', cardinality='**',
                                         constraints=[RQLConstraint('S state_of ET, O transition_of ET')],
                                         description=_('allowed transitions from this state'))
    
    initial_state = ObjectRelation('EEType', cardinality='?*',
                                   # S initial_state O, O state_of S
                                   constraints=[RQLConstraint('O state_of S')],
                                   description=_('initial state for entities of this type'))


class Transition(MetaEntityType):
    """use to define a transition from one or multiple states to a destination
    states in workflow's definitions.
    """
    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=256)
    description_format = String(meta=True, internationalizable=True, maxsize=50,
                                default='text/rest', constraints=[format_constraint])
    description = String(fulltextindexed=True,
                         description=_('semantic description of this transition'))
    condition = SubjectRelation('RQLExpression', cardinality='*?', composite='subject',
                                description=_('a RQL expression which should return some results, '
                                              'else the transition won\'t be available. '
                                              'This query may use X and U variables '
                                              'that will respectivly represents '
                                              'the current entity and the current user'))
    
    require_group = SubjectRelation('EGroup', cardinality='**',
                                    description=_('group in which a user should be to be '
                                                  'allowed to pass this transition'))
    transition_of = SubjectRelation('EEType', cardinality='+*',
                                    description=_('entity types which may use this transition'),
                                    constraints=[RQLConstraint('O final FALSE')])
    destination_state = SubjectRelation('State', cardinality='?*',
                                        constraints=[RQLConstraint('S transition_of ET, O state_of ET')],
                                        description=_('destination state for this transition'))


class TrInfo(MetaEntityType):
    from_state = SubjectRelation('State', cardinality='?*')
    to_state = SubjectRelation('State', cardinality='1*')
    comment_format = String(meta=True, internationalizable=True, maxsize=50,
                            default='text/rest', constraints=[format_constraint])
    comment = String(fulltextindexed=True)
    # get actor and date time using owned_by and creation_date


class from_state(MetaRelationType):
    inlined = True
class to_state(MetaRelationType):
    inlined = True
class wf_info_for(MetaRelationType):
    """link a transition information to its object"""
    permissions = {
        'read':   ('managers', 'users', 'guests',),# RRQLExpression('U has_read_permission O')),
        'add':    (), # handled automatically, no one should add one explicitly
        'delete': ('managers',), # RRQLExpression('U has_delete_permission O')
        }
    inlined = True
    composite = 'object'
    fulltext_container = composite
    
class state_of(MetaRelationType):
    """link a state to one or more entity type"""
class transition_of(MetaRelationType):
    """link a transition to one or more entity type"""
    
class initial_state(MetaRelationType):
    """indicate which state should be used by default when an entity using
    states is created
    """
    inlined = True

class destination_state(MetaRelationType):
    """destination state of a transition"""
    inlined = True
    
class allowed_transition(MetaRelationType):
    """allowed transition from this state"""

class in_state(UserRelationType):
    """indicate the current state of an entity"""
    meta = True
    # not inlined intentionnaly since when using ldap sources, user'state
    # has to be stored outside the EUser table
    
    # add/delete perms given to managers/users, after what most of the job
    # is done by workflow enforcment
    

class EProperty(EntityType):
    """used for cubicweb configuration. Once a property has been created you
    can't change the key.
    """
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', 'users',),
        'update': ('managers', 'owners',),
        'delete': ('managers', 'owners',),
        }
    meta = True
    # key is a reserved word for mysql
    pkey = String(required=True, internationalizable=True, maxsize=256,
                  description=_('defines what\'s the property is applied for. '
                                'You must select this first to be able to set '
                                'value'))
    value = String(internationalizable=True, maxsize=256)
    
    for_user = SubjectRelation('EUser', cardinality='?*', composite='object',
                               description=_('user for which this property is '
                                             'applying. If this relation is not '
                                             'set, the property is considered as'
                                             ' a global property'))


class for_user(MetaRelationType):
    """link a property to the user which want this property customization. Unless
    you're a site manager, this relation will be handled automatically.
    """
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    inlined = True


class EPermission(MetaEntityType):
    """entity type that may be used to construct some advanced security configuration
    """
    name = String(required=True, indexed=True, internationalizable=True, maxsize=100,
                  description=_('name or identifier of the permission'))
    label = String(required=True, internationalizable=True, maxsize=100,
                   description=_('distinct label to distinguate between other permission entity of the same name'))
    require_group = SubjectRelation('EGroup', 
                                    description=_('groups to which the permission is granted'))

# explicitly add X require_permission EPermission for each entity that should have
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
    
class require_group(MetaRelationType):
    """used to grant a permission to a group"""
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }

    
class see_also(RelationType):
    """generic relation to link one entity to another"""
    symetric = True

class ECache(EntityType):
    name = String(required=True, unique=True, indexed=True, 
                  description=_('name of the cache'))
    timestamp = Datetime(default='NOW')
