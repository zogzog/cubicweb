from yams.buildobjs import (EntityType, RelationType, SubjectRelation,
                            RichString)
from cubicweb.schema import RRQLExpression


class Comment(EntityType):
    """a comment is a reply about another entity"""
    __permissions__ = {
        'read':   ('managers', 'users', 'guests',),
        'add':    ('managers', 'users',),
        'delete': ('managers', 'owners',),
        'update': ('managers', 'owners',),
        }
    content = RichString(required=True, fulltextindexed=True)
    comments = SubjectRelation('Comment', cardinality='1*', composite='object')


class comments(RelationType):
    __permissions__ = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', 'users',),
        'delete': ('managers', RRQLExpression('S owned_by U'),),
        }
    inlined = True
    composite = 'object'
    cardinality = '1*'
