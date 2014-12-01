driver = config.system_source_config['db-driver']
if not (driver == 'postgres' or driver.startswith('sqlserver')):
    import sys
    print >>sys.stderr, 'This migration is not supported for backends other than sqlserver or postgres (yet).'
    sys.exit(1)

add_relation_definition('CWAttribute', 'add_permission', 'CWGroup')
add_relation_definition('CWAttribute', 'add_permission', 'RQLExpression')

# a bad defaultval in 3.13.8 schema was fixed in 3.13.9, but the migration was missed
rql('SET ATTR defaultval NULL WHERE ATTR from_entity E, E name "CWSource", ATTR relation_type T, T name "in_synchronization"')

# the migration gets confused when we change rdefs out from under it.  So
# explicitly remove this size constraint so it doesn't stick around and break
# things later.
rdefeid = schema['defaultval'].rdefs.values()[0].eid
rql('DELETE CWConstraint C WHERE C cstrtype T, T name "SizeConstraint", R constrained_by C, R eid %(eid)s', {'eid': rdefeid})

sync_schema_props_perms('defaultval')

def convert_defaultval(cwattr, default):
    from decimal import Decimal
    import yams
    from cubicweb import Binary
    if default is None:
        return
    if isinstance(default, Binary):
        # partially migrated instance, try to be idempotent
        return default
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


sql('ALTER TABLE cw_cwattribute ADD new_defaultval %s' % dbh.TYPE_MAPPING['Bytes'])

for cwattr in rql('CWAttribute X').entities():
    olddefault = cwattr.defaultval
    if olddefault is not None:
        req = "UPDATE cw_cwattribute SET new_defaultval = %(val)s WHERE cw_eid = %(eid)s"
        args = {'val': dbh.binary_value(convert_defaultval(cwattr, olddefault).getvalue()), 'eid': cwattr.eid}
        sql(req, args, ask_confirm=False)

sql('ALTER TABLE cw_cwattribute DROP COLUMN cw_defaultval')
if driver == 'postgres':
    sql('ALTER TABLE cw_cwattribute RENAME COLUMN new_defaultval TO cw_defaultval')
else: # sqlserver
    sql("sp_rename 'cw_cwattribute.new_defaultval', 'cw_defaultval', 'COLUMN'")


# Set object type to "Bytes" for CWAttribute's "defaultval" attribute
rql('SET X to_entity B WHERE X is CWAttribute, X from_entity Y, Y name "CWAttribute", '
    'X relation_type Z, Z name "defaultval", B name "Bytes", NOT X to_entity B')

oldrdef = schema['CWAttribute'].rdef('defaultval')
import yams.buildobjs as ybo
newrdef = ybo.RelationDefinition('CWAttribute', 'defaultval', 'Bytes')
newrdef.eid = oldrdef.eid
schema.add_relation_def(newrdef)
schema.del_relation_def('CWAttribute', 'defaultval', 'String')

commit()

sync_schema_props_perms('defaultval')

for rschema in schema.relations():
    if rschema.symmetric:
        subjects = set(repr(e.type) for e in rschema.subjects())
        objects = set(repr(e.type) for e in rschema.objects())
        assert subjects == objects
        martians = set(str(eid) for eid, in sql('SELECT eid_to FROM %s_relation, entities WHERE eid_to = eid AND type NOT IN (%s)' %
                                           (rschema.type, ','.join(subjects))))
        martians |= set(str(eid) for eid, in sql('SELECT eid_from FROM %s_relation, entities WHERE eid_from = eid AND type NOT IN (%s)' %
                                            (rschema.type, ','.join(subjects))))
        if martians:
            martians = ','.join(martians)
            print 'deleting broken relations %s for eids %s' % (rschema.type, martians)
            sql('DELETE FROM %s_relation WHERE eid_from IN (%s) OR eid_to IN (%s)' % (rschema.type, martians, martians))
        with session.deny_all_hooks_but():
            rql('SET X %(r)s Y WHERE Y %(r)s X, NOT X %(r)s Y' % {'r': rschema.type})
        commit()


# multi columns unique constraints regeneration
from cubicweb.server import schemaserial

# syncschema hooks would try to remove indices but
# 1) we already do that below
# 2) the hook expects the CWUniqueTogetherConstraint.name attribute that hasn't
#    yet been added
with session.allow_all_hooks_but('syncschema'):
    rql('DELETE CWUniqueTogetherConstraint C')
commit()

add_attribute('CWUniqueTogetherConstraint', 'name')

# low-level wipe code for postgres & sqlserver, plain sql ...
if driver == 'postgres':
    for indexname, in sql('select indexname from pg_indexes'):
        if indexname.startswith('unique_'):
            print 'dropping index', indexname
            sql('DROP INDEX %s' % indexname)
    commit()
elif driver.startswith('sqlserver'):
    for viewname, in sql('select name from sys.views'):
        if viewname.startswith('utv_'):
            print 'dropping view (index should be cascade-deleted)', viewname
            sql('DROP VIEW %s' % viewname)
    commit()

# recreate the constraints, hook will lead to low-level recreation
for eschema in sorted(schema.entities()):
    if eschema._unique_together:
        print 'recreate unique indexes for', eschema
        rql_args = schemaserial.uniquetogether2rqls(eschema)
        for rql, args in rql_args:
            args['x'] = eschema.eid
            session.execute(rql, args)
commit()

# all attributes perms have to be refreshed ...
for rschema in sorted(schema.relations()):
    if rschema.final:
        if rschema.type in fsschema:
            print 'sync perms for', rschema.type
            sync_schema_props_perms(rschema.type, syncprops=False, ask_confirm=False, commit=False)
        else:
            print 'WARNING: attribute %s missing from fs schema' % rschema.type
commit()
