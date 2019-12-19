from yams.buildobjs import EntityType, RelationDefinition, String, RichString
from cubicweb.schema import ERQLExpression


class Basket(EntityType):
    """a basket contains a set of other entities"""
    __permissions__ = {
        'read':   ('managers', ERQLExpression('X owned_by U'),),
        'add':    ('managers', 'users',),
        'delete': ('managers', 'owners',),
        'update': ('managers', 'owners',),
    }

    name = String(required=True, indexed=True, internationalizable=True,
                  maxsize=128)
    description = RichString(fulltextindexed=True)


class in_basket(RelationDefinition):
    subject = '*'
    object = 'Basket'
