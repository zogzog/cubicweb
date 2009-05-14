class Societe(EntityType):
    permissions = {
        'read': ('managers', 'users', 'guests'),
        'update': ('managers', 'owners', ERQLExpression('U login L, X nom L')),
        'delete': ('managers', 'owners', ERQLExpression('U login L, X nom L')),
        'add': ('managers', 'users',)
        }

    nom  = String(maxsize=64, fulltextindexed=True)
    web  = String(maxsize=128)
    type  = String(maxsize=128) # attribute in common with Note
    tel  = Int()
    fax  = Int()
    rncs = String(maxsize=128)
    ad1  = String(maxsize=128)
    ad2  = String(maxsize=128)
    ad3  = String(maxsize=128)
    cp   = String(maxsize=12)
    ville= String(maxsize=32)


class travaille(RelationType):
    permissions = {
        'read':   ('managers', 'users', 'guests'),
        'add':    ('managers', RRQLExpression('U has_update_permission S')),
        'delete': ('managers', RRQLExpression('O owned_by U')),
        }


class Division(Societe):
    __specializes_schema__ = True

class SubDivision(Division):
    __specializes_schema__ = True
    travaille_subdivision = ObjectRelation('Personne')
