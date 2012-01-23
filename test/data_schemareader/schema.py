from cubicweb.schemas.base import in_group, CWSourceSchemaConfig
# copy __permissions__ to avoid modifying a shared dictionary
in_group.__permissions__ = in_group.__permissions__.copy()
in_group.__permissions__['read'] = ('managers',)

cw_for_source = CWSourceSchemaConfig.get_relation('cw_for_source')
cw_for_source.__permissions__ = {'read': ('managers', 'users'),
                                 'add': ('managers',),
                                 'delete': ('managers',)}


