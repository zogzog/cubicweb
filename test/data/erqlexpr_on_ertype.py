class ToTo(EntityType):
    permissions = {
        'read': ('managers',),
        'add': ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }
    toto = SubjectRelation('TuTu')
    
class TuTu(EntityType):
    permissions = {
        'read': ('managers',),
        'add': ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }

class toto(RelationType):
    permissions = {
        'read': ('managers', ),
        'add': ('managers', ERQLExpression('S bla Y'),),
        'delete': ('managers',),
        }
