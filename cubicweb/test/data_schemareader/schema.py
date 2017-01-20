from yams.buildobjs import EntityType, SubjectRelation
from cubicweb.schemas.base import in_group, RELATION_MANAGERS_PERMISSIONS

# copy __permissions__ to avoid modifying a shared dictionary
in_group.__permissions__ = in_group.__permissions__.copy()
in_group.__permissions__['read'] = ('managers',)


class CWSourceSchemaConfig(EntityType):
    cw_for_source = SubjectRelation(
        'CWSource', inlined=True, cardinality='1*', composite='object',
        __permissions__=RELATION_MANAGERS_PERMISSIONS)


cw_for_source = CWSourceSchemaConfig.get_relation('cw_for_source')
cw_for_source.__permissions__ = {'read': ('managers', 'users'),
                                 'add': ('managers',),
                                 'delete': ('managers',)}
