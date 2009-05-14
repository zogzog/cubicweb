
class Affaire(EntityType):
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', ERQLExpression('X concerne S, S owned_by U')),
        'update': ('managers', 'owners', ERQLExpression('X concerne S, S owned_by U')),
        'delete': ('managers', 'owners', ERQLExpression('X concerne S, S owned_by U')),
        }

    ref = String(fulltextindexed=True, indexed=True,
                 constraints=[SizeConstraint(16)])
    sujet = String(fulltextindexed=True,
                 constraints=[SizeConstraint(256)])

class concerne(RelationType):
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('U has_update_permission S')),
        'delete': ('managers', RRQLExpression('O owned_by U')),
        }

