class ToTo(EntityType):
    permissions = {
        'read': ('managers', RRQLExpression('S bla Y'),),
        'add': ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }
    attr = String()
