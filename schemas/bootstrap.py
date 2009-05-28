"""core CubicWeb schema necessary for bootstrapping the actual application's schema

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from cubicweb.schema import format_constraint


# not restricted since as "is" is handled as other relations, guests need
# access to this
class CWEType(MetaEntityType):
    """define an entity type, used to build the application schema"""
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)
    description = RichString(internationalizable=True,
                             description=_('semantic description of this entity type'))
    meta = Boolean(description=_('is it an application entity type or not ?'))
    # necessary to filter using RQL
    final = Boolean(description=_('automatic'))


class CWRType(MetaEntityType):
    """define a relation type, used to build the application schema"""
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)
    description_format = String(meta=True, internationalizable=True, maxsize=50,
                                default='text/plain', constraints=[format_constraint])
    description = String(internationalizable=True,
                         description=_('semantic description of this relation type'))
    meta = Boolean(description=_('is it an application relation type or not ?'))
    symetric = Boolean(description=_('is this relation equivalent in both direction ?'))
    inlined = Boolean(description=_('is this relation physically inlined? you should know what you\'re doing if you are changing this!'))
    fulltext_container = String(description=_('if full text content of subject/object entity '
                                              'should be added to other side entity (the container).'),
                                vocabulary=('', _('subject'), _('object')),
                                maxsize=8, default=None)
    final = Boolean(description=_('automatic'))


class CWAttribute(MetaEntityType):
    """define a final relation: link a final relation type from a non final
    entity to a final entity type.

    used to build the application schema
    """
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

    description_format = String(meta=True, internationalizable=True, maxsize=50,
                                default='text/plain', constraints=[format_constraint])
    description = String(internationalizable=True,
                         description=_('semantic description of this attribute'))


CARDINALITY_VOCAB = [_('?*'), _('1*'), _('+*'), _('**'),
                     _('?+'), _('1+'), _('++'), _('*+'),
                     _('?1'), _('11'), _('+1'), _('*1'),
                     _('??'), _('1?'), _('+?'), _('*?')]

class CWRelation(MetaEntityType):
    """define a non final relation: link a non final relation type from a non
    final entity to a non final entity type.

    used to build the application schema
    """
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

    description_format = String(meta=True, internationalizable=True, maxsize=50,
                                default='text/plain', constraints=[format_constraint])
    description = String(internationalizable=True,
                         description=_('semantic description of this relation'))


# not restricted since it has to be read when checking allowed transitions
class RQLExpression(MetaEntityType):
    """define a rql expression used to define permissions"""
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

    read_permission = ObjectRelation(('CWEType', 'CWRType'), cardinality='+?', composite='subject',
                                      description=_('rql expression allowing to read entities/relations of this type'))
    add_permission = ObjectRelation(('CWEType', 'CWRType'), cardinality='*?', composite='subject',
                                     description=_('rql expression allowing to add entities/relations of this type'))
    delete_permission = ObjectRelation(('CWEType', 'CWRType'), cardinality='*?', composite='subject',
                                        description=_('rql expression allowing to delete entities/relations of this type'))
    update_permission = ObjectRelation('CWEType', cardinality='*?', composite='subject',
                                        description=_('rql expression allowing to update entities of this type'))


class CWConstraint(MetaEntityType):
    """define a schema constraint"""
    cstrtype = SubjectRelation('CWConstraintType', cardinality='1*')
    value = String(description=_('depends on the constraint type'))


class CWConstraintType(MetaEntityType):
    """define a schema constraint type"""
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)


# not restricted since it has to be read when checking allowed transitions
class CWGroup(MetaEntityType):
    """define a CubicWeb users group"""
    name = String(required=True, indexed=True, internationalizable=True,
                  unique=True, maxsize=64)

    read_permission = ObjectRelation(('CWEType', 'CWRType'), cardinality='+*',
                                      description=_('groups allowed to read entities/relations of this type'))
    add_permission = ObjectRelation(('CWEType', 'CWRType'),
                                     description=_('groups allowed to add entities/relations of this type'))
    delete_permission = ObjectRelation(('CWEType', 'CWRType'),
                                        description=_('groups allowed to delete entities/relations of this type'))
    update_permission = ObjectRelation('CWEType',
                                        description=_('groups allowed to update entities of this type'))



class relation_type(MetaRelationType):
    """link a relation definition to its relation type"""
    inlined = True
class from_entity(MetaRelationType):
    """link a relation definition to its subject entity type"""
    inlined = True
class to_entity(MetaRelationType):
    """link a relation definition to its object entity type"""
    inlined = True
class constrained_by(MetaRelationType):
    """constraints applying on this relation"""

class cstrtype(MetaRelationType):
    """constraint factory"""
    inlined = True

class read_permission(MetaRelationType):
    """core relation giving to a group the permission to read an entity or
    relation type
    """
class add_permission(MetaRelationType):
    """core relation giving to a group the permission to add an entity or
    relation type
    """
class delete_permission(MetaRelationType):
    """core relation giving to a group the permission to delete an entity or
    relation type
    """
class update_permission(MetaRelationType):
    """core relation giving to a group the permission to update an entity type
    """


class is_(MetaRelationType):
    """core relation indicating the type of an entity
    """
    name = 'is'
    # don't explicitly set composite here, this is handled anyway
    #composite = 'object'
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    (),
        'delete': (),
        }
    cardinality = '1*'
    subject = '**'
    object = 'CWEType'

class is_instance_of(MetaRelationType):
    """core relation indicating the types (including specialized types)
    of an entity
    """
    # don't explicitly set composite here, this is handled anyway
    #composite = 'object'
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    (),
        'delete': (),
        }
    cardinality = '+*'
    subject = '**'
    object = 'CWEType'

class specializes(MetaRelationType):
    name = 'specializes'
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers',),
        'delete': ('managers',),
        }
    cardinality = '?*'
    subject = 'CWEType'
    object = 'CWEType'
