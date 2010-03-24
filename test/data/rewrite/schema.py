from yams.buildobjs import EntityType, RelationDefinition, String, SubjectRelation
from cubicweb.schema import ERQLExpression

class Affaire(EntityType):
    __permissions__ = {
        'read':   ('managers',
                   ERQLExpression('X owned_by U'), ERQLExpression('X concerne S?, S owned_by U')),
        'add':    ('managers', ERQLExpression('X concerne S, S owned_by U')),
        'update': ('managers', 'owners', ERQLExpression('X in_state S, S name in ("pitetre", "en cours")')),
        'delete': ('managers', 'owners', ERQLExpression('X concerne S, S owned_by U')),
        }
    ref = String(fulltextindexed=True, indexed=True, maxsize=16)
    documented_by = SubjectRelation('Card')
    concerne = SubjectRelation(('Societe', 'Note'))


class Societe(EntityType):
    __permissions__ = {
        'read': ('managers', 'users', 'guests'),
        'update': ('managers', 'owners', ERQLExpression('U login L, X nom L')),
        'delete': ('managers', 'owners', ERQLExpression('U login L, X nom L')),
        'add': ('managers', 'users',)
        }


class Division(Societe):
    __specializes_schema__ = True


class Note(EntityType):
    pass


class require_permission(RelationDefinition):
    subject = ('Card', 'Note', 'Person')
    object = 'CWPermission'


class require_state(RelationDefinition):
    subject = 'CWPermission'
    object = 'State'


class inlined_card(RelationDefinition):
    subject = 'Affaire'
    object = 'Card'
    inlined = True
    cardinality = '?*'
