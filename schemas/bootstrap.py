"""core CubicWeb schema necessary for bootstrapping the actual instance's schema

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from yams.buildobjs import (EntityType, RelationType, RelationDefinition,
                            SubjectRelation, RichString, String, Boolean, Int)
from cubicweb.schema import (
    RQLConstraint,
    PUB_SYSTEM_ENTITY_PERMS, PUB_SYSTEM_REL_PERMS, PUB_SYSTEM_ATTR_PERMS
    )

# not restricted since as "is" is handled as other relations, guests need
# access to this
class CWEType(EntityType):
    """define an entity type, used to build the instance schema"""
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)
    description = RichString(internationalizable=True,
                             description=_('semantic description of this entity type'))
    # necessary to filter using RQL
    final = Boolean(description=_('automatic'))


class CWRType(EntityType):
    """define a relation type, used to build the instance schema"""
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)
    description = RichString(internationalizable=True,
                             description=_('semantic description of this relation type'))
    symmetric = Boolean(description=_('is this relation equivalent in both direction ?'))
    inlined = Boolean(description=_('is this relation physically inlined? you should know what you\'re doing if you are changing this!'))
    fulltext_container = String(description=_('if full text content of subject/object entity '
                                              'should be added to other side entity (the container).'),
                                vocabulary=('', _('subject'), _('object')),
                                maxsize=8, default=None)
    final = Boolean(description=_('automatic'))


class CWAttribute(EntityType):
    """define a final relation: link a final relation type from a non final
    entity to a final entity type.

    used to build the instance schema
    """
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    relation_type = SubjectRelation('CWRType', cardinality='1*',
                                    constraints=[RQLConstraint('O final TRUE')],
                                    composite='object')
    from_entity = SubjectRelation('CWEType', cardinality='1*',
                                  constraints=[RQLConstraint('O final FALSE')],
                                  composite='object')
    to_entity = SubjectRelation('CWEType', cardinality='1*',
                                constraints=[RQLConstraint('O final TRUE')],
                                composite='object')
    constrained_by = SubjectRelation('CWConstraint', cardinality='*1', composite='subject')

    cardinality = String(maxsize=2, internationalizable=True,
                         vocabulary=[_('?1'), _('11')],
                         description=_('subject/object cardinality'))
    ordernum = Int(description=('control subject entity\'s relations order'), default=0)

    indexed = Boolean(description=_('create an index for quick search on this attribute'))
    fulltextindexed = Boolean(description=_('index this attribute\'s value in the plain text index'))
    internationalizable = Boolean(description=_('is this attribute\'s value translatable'))
    defaultval = String(maxsize=256)

    description = RichString(internationalizable=True,
                             description=_('semantic description of this attribute'))


CARDINALITY_VOCAB = [_('?*'), _('1*'), _('+*'), _('**'),
                     _('?+'), _('1+'), _('++'), _('*+'),
                     _('?1'), _('11'), _('+1'), _('*1'),
                     _('??'), _('1?'), _('+?'), _('*?')]

class CWRelation(EntityType):
    """define a non final relation: link a non final relation type from a non
    final entity to a non final entity type.

    used to build the instance schema
    """
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    relation_type = SubjectRelation('CWRType', cardinality='1*',
                                    constraints=[RQLConstraint('O final FALSE')],
                                    composite='object')
    from_entity = SubjectRelation('CWEType', cardinality='1*',
                                  constraints=[RQLConstraint('O final FALSE')],
                                  composite='object')
    to_entity = SubjectRelation('CWEType', cardinality='1*',
                                constraints=[RQLConstraint('O final FALSE')],
                                composite='object')
    constrained_by = SubjectRelation('CWConstraint', cardinality='*1', composite='subject')

    cardinality = String(maxsize=2, internationalizable=True,
                         vocabulary=CARDINALITY_VOCAB,
                         description=_('subject/object cardinality'))
    ordernum = Int(description=_('control subject entity\'s relations order'),
                   default=0)
    composite = String(description=_('is the subject/object entity of the relation '
                                     'composed of the other ? This implies that when '
                                     'the composite is deleted, composants are also '
                                     'deleted.'),
                       vocabulary=('', _('subject'), _('object')),
                       maxsize=8, default=None)

    description = RichString(internationalizable=True,
                             description=_('semantic description of this relation'))


# not restricted since it has to be read when checking allowed transitions
class RQLExpression(EntityType):
    """define a rql expression used to define permissions"""
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    exprtype = String(required=True, vocabulary=['ERQLExpression', 'RRQLExpression'])
    mainvars = String(maxsize=8,
                      description=_('name of the main variables which should be '
                                    'used in the selection if necessary (comma '
                                    'separated)'))
    expression = String(required=True,
                        description=_('restriction part of a rql query. '
                                      'For entity rql expression, X and U are '
                                      'predefined respectivly to the current object and to '
                                      'the request user. For relation rql expression, '
                                      'S, O and U are predefined respectivly to the current '
                                      'relation\'subject, object and to '
                                      'the request user. '))


class CWConstraint(EntityType):
    """define a schema constraint"""
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    cstrtype = SubjectRelation('CWConstraintType', cardinality='1*')
    value = String(description=_('depends on the constraint type'))


class CWConstraintType(EntityType):
    """define a schema constraint type"""
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)


# not restricted since it has to be read when checking allowed transitions
class CWGroup(EntityType):
    """define a CubicWeb users group"""
    __permissions__ = PUB_SYSTEM_ENTITY_PERMS
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)


class CWProperty(EntityType):
    """used for cubicweb configuration. Once a property has been created you
    can't change the key.
    """
    __permissions__ = {
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

class relation_type(RelationType):
    """link a relation definition to its relation type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True

class from_entity(RelationType):
    """link a relation definition to its subject entity type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True

class to_entity(RelationType):
    """link a relation definition to its object entity type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True

class constrained_by(RelationType):
    """constraints applying on this relation"""
    __permissions__ = PUB_SYSTEM_REL_PERMS

class cstrtype(RelationType):
    """constraint factory"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    inlined = True


class read_permission_cwgroup(RelationDefinition):
    """groups allowed to read entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'read_permission'
    subject = ('CWEType', 'CWAttribute', 'CWRelation')
    object = 'CWGroup'
    cardinality = '**'

class add_permission_cwgroup(RelationDefinition):
    """groups allowed to add entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'add_permission'
    subject = ('CWEType', 'CWRelation')
    object = 'CWGroup'
    cardinality = '**'

class delete_permission_cwgroup(RelationDefinition):
    """groups allowed to delete entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'delete_permission'
    subject = ('CWEType', 'CWRelation')
    object = 'CWGroup'
    cardinality = '**'

class update_permission_cwgroup(RelationDefinition):
    """groups allowed to update entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'update_permission'
    subject = ('CWEType', 'CWAttribute')
    object = 'CWGroup'
    cardinality = '**'

class read_permission_rqlexpr(RelationDefinition):
    """rql expression allowing to read entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'read_permission'
    subject = ('CWEType', 'CWAttribute', 'CWRelation')
    object = 'RQLExpression'
    cardinality = '*?'
    composite = 'subject'

class add_permission_rqlexpr(RelationDefinition):
    """rql expression allowing to add entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'add_permission'
    subject = ('CWEType', 'CWRelation')
    object = 'RQLExpression'
    cardinality = '*?'
    composite = 'subject'

class delete_permission_rqlexpr(RelationDefinition):
    """rql expression allowing to delete entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'delete_permission'
    subject = ('CWEType', 'CWRelation')
    object = 'RQLExpression'
    cardinality = '*?'
    composite = 'subject'

class update_permission_rqlexpr(RelationDefinition):
    """rql expression allowing to update entities/relations of this type"""
    __permissions__ = PUB_SYSTEM_REL_PERMS
    name = 'update_permission'
    subject = ('CWEType', 'CWAttribute')
    object = 'RQLExpression'
    cardinality = '*?'
    composite = 'subject'


class is_(RelationType):
    """core relation indicating the type of an entity
    """
    name = 'is'
    # don't explicitly set composite here, this is handled anyway
    #composite = 'object'
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    (),
        'delete': (),
        }
    cardinality = '1*'
    subject = '*'
    object = 'CWEType'

class is_instance_of(RelationType):
    """core relation indicating the types (including specialized types)
    of an entity
    """
    # don't explicitly set composite here, this is handled anyway
    #composite = 'object'
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    (),
        'delete': (),
        }
    cardinality = '+*'
    subject = '*'
    object = 'CWEType'

class specializes(RelationType):
    name = 'specializes'
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    cardinality = '?*'
    subject = 'CWEType'
    object = 'CWEType'

def post_build_callback(schema):
    """set attributes permissions for schema/workflow entities"""
    from cubicweb.schema import SCHEMA_TYPES, WORKFLOW_TYPES, META_RTYPES
    for eschema in schema.entities():
        if eschema in SCHEMA_TYPES or eschema in WORKFLOW_TYPES:
            for rschema in eschema.subject_relations():
                if rschema.final and not rschema in META_RTYPES:
                    rdef = eschema.rdef(rschema)
                    rdef.permissions = PUB_SYSTEM_ATTR_PERMS
