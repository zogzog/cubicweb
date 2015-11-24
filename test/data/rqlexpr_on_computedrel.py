from yams.buildobjs import ComputedRelation, EntityType, RelationDefinition
from cubicweb.schema import RRQLExpression

class Subject(EntityType):
    pass

class Object(EntityType):
    pass

class relation(RelationDefinition):
    subject = 'Subject'
    object = 'Object'

class computed(ComputedRelation):
    rule = 'S relation O'
    __permissions__ = {'read': (RRQLExpression('S is ET'),)}
