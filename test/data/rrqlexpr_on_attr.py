class ToTo(EntityType):
    permissions = {
        'read': ('managers',),
        'add': ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }
    attr = String()
    
class attr(RelationType):
    permissions = {
        'read': ('managers', ),
        'add': ('managers', RRQLExpression('S bla Y'),),
        'delete': ('managers',),
        }
