sync_schema_props_perms('defaultval')

def convert_defaultval(cwattr, default):
    from decimal import Decimal
    import yams
    from cubicweb import Binary
    if default is None:
        return
    atype = cwattr.to_entity[0].name
    if atype == 'Boolean':
        # boolean attributes with default=False were stored as ''
        assert default in ('True', 'False', ''), repr(default)
        default = default == 'True'
    elif atype in ('Int', 'BigInt'):
        default = int(default)
    elif atype == 'Float':
        default = float(default)
    elif atype == 'Decimal':
        default = Decimal(default)
    elif atype in ('Date', 'Datetime', 'TZDatetime', 'Time'):
        try:
            # handle NOW and TODAY, keep them stored as strings
            yams.KEYWORD_MAP[atype][default.upper()]
            default = default.upper()
        except KeyError:
            # otherwise get an actual date or datetime
            default = yams.DATE_FACTORY_MAP[atype](default)
    else:
        assert atype == 'String', atype
        default = unicode(default)
    return Binary.zpickle(default)

dbh = repo.system_source.dbhelper
driver = config.sources()['system']['db-driver']

if driver == 'postgres' or driver.startswith('sqlserver'):

    sql('ALTER TABLE cw_cwattribute ADD new_defaultval %s' % dbh.TYPE_MAPPING['Bytes'])

    for cwattr in rql('CWAttribute X').entities():
        olddefault = cwattr.defaultval
        if olddefault is not None:
            req = "UPDATE cw_cwattribute SET new_defaultval = %(val)s WHERE cw_eid = %(eid)s"
            args = {'val': dbh.binary_value(convert_defaultval(cwattr, olddefault).getvalue()), 'eid': cwattr.eid}
            sql(req, args, ask_confirm=False)

    sql('ALTER TABLE cw_cwattribute DROP COLUMN cw_defaultval')
    if config.sources()['system']['db-driver'] == 'postgres':
        sql('ALTER TABLE cw_cwattribute RENAME COLUMN new_defaultval TO cw_defaultval')
    else:
        sql("sp_rename 'cw_cwattribute.new_defaultval', 'cw_defaultval', 'COLUMN'")

elif driver == 'sqlite':

    import re
    create = sql("SELECT sql FROM sqlite_master WHERE name = 'cw_CWAttribute'")[0][0]
    create = re.sub('cw_defaultval varchar[^,]*,', 'cw_defaultval bytea,', create, re.I)
    create = re.sub('cw_CWAttribute', 'tmp_cw_CWAttribute', create, re.I)
    sql(create)
    sql("INSERT INTO tmp_cw_CWAttribute SELECT * FROM cw_CWAttribute")
    for cwattr in rql('CWAttribute X').entities():
        olddefault = cwattr.defaultval
        if olddefault is None:
            continue
        req = "UPDATE tmp_cw_CWAttribute SET cw_defaultval = %(val)s WHERE cw_eid = %(eid)s"
        args = {'val': dbh.binary_value(convert_defaultval(cwattr, olddefault).getvalue()),
                'eid': cwattr.eid}
        sql(req, args, ask_confirm=False)

    sql('DROP TABLE cw_CWAttribute')
    sql('ALTER TABLE tmp_cw_CWAttribute RENAME TO cw_CWAttribute')

else:
    assert False, 'upgrade not supported on this database backend'

# Set object type to "Bytes" for CWAttribute's "defaultval" attribute
rql('SET X to_entity B WHERE X is CWAttribute, X from_entity Y, Y name "CWAttribute", '
    'X relation_type Z, Z name "defaultval", B name "Bytes"')

from yams import buildobjs as ybo
schema.add_relation_def(ybo.RelationDefinition('CWAttribute', 'defaultval', 'Bytes'))
schema.del_relation_def('CWAttribute', 'defaultval', 'String')

commit()


for rschema in schema.relations():
    if rschema.symmetric:
        with session.allow_all_hooks_but('activeintegrity'):
            rql('SET X %(r)s Y WHERE Y %(r)s X, NOT X %(r)s Y' % {'r': rschema.type})
    commit()
