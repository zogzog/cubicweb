

class test(AttributeRelationType):
    permissions = {'read': ('managers', 'users', 'guests'),
                   'delete': ('managers',),
                   'add': ('managers',)}
