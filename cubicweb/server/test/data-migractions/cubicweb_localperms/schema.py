from yams.buildobjs import EntityType, RelationType, RelationDefinition, String
from cubicweb.schema import PUB_SYSTEM_ENTITY_PERMS, PUB_SYSTEM_REL_PERMS


class CWPermission(EntityType):
    """entity type that may be used to construct some advanced security
    configuration
    """
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=100, description=(
                      'name or identifier of the permission'))
    label = String(required=True, internationalizable=True, maxsize=100,
                   description=('distinct label to distinguate between other '
                                'permission entity of the same name'))


class granted_permission(RelationType):
    """explicitly granted permission on an entity"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    # XXX cardinality = '*1'


class require_permission(RelationType):
    __permissions__ = PUB_SYSTEM_REL_PERMS


class require_group(RelationDefinition):
    """groups to which the permission is granted"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    subject = 'CWPermission'
    object = 'CWGroup'


class has_group_permission(RelationDefinition):
    """short cut relation for 'U in_group G, P require_group G' for efficiency
    reason. This relation is set automatically, you should not set this.
    """
    __permissions__ = PUB_SYSTEM_REL_PERMS
    subject = 'CWUser'
    object = 'CWPermission'
