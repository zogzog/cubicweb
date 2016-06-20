
from functools import partial

from yams.constraints import UniqueConstraint

from cubicweb.schema import PURE_VIRTUAL_RTYPES
from cubicweb.server.schema2sql import build_index_name, check_constraint

sql = partial(sql, ask_confirm=False)

source = repo.system_source
helper = source.dbhelper

for rschema in schema.relations():
    if rschema.rule or rschema in PURE_VIRTUAL_RTYPES:
        continue
    if rschema.final or rschema.inlined:
        for rdef in rschema.rdefs.values():
            table = 'cw_{0}'.format(rdef.subject)
            column = 'cw_{0}'.format(rdef.rtype)
            if any(isinstance(cstr, UniqueConstraint) for cstr in rdef.constraints):
                old_name = '%s_%s_key' % (table.lower(), column.lower())
                sql('ALTER TABLE %s DROP CONSTRAINT IF EXISTS %s' % (table, old_name))
                source.create_index(cnx, table, column, unique=True)
            if rschema.inlined or rdef.indexed:
                old_name = '%s_%s_idx' % (table.lower(), column.lower())
                sql('DROP INDEX IF EXISTS %s' % old_name)
                source.create_index(cnx, table, column)
    else:
        table = '{0}_relation'.format(rschema)
        sql('ALTER TABLE %s DROP CONSTRAINT IF EXISTS %s_p_key' % (table, table))
        sql('ALTER TABLE %s ADD CONSTRAINT %s PRIMARY KEY(eid_from, eid_to)'
            % (table, build_index_name(table, ['eid_from', 'eid_to'], 'key_')))
        for column in ('from', 'to'):
            sql('DROP INDEX IF EXISTS %s_%s_idx' % (table, column))
            sql('CREATE INDEX %s ON %s(eid_%s);'
                % (build_index_name(table, ['eid_' + column], 'idx_'), table, column))


# we changed constraint serialization, which also changes their name

for table, cstr in sql("""
    SELECT table_name, constraint_name FROM information_schema.constraint_column_usage
    WHERE constraint_name LIKE 'cstr%'"""):
    sql("ALTER TABLE %(table)s DROP CONSTRAINT IF EXISTS %(cstr)s" % locals())

for cwconstraint in rql('Any C WHERE R constrained_by C').entities():
    cwrdef = cwconstraint.reverse_constrained_by[0]
    rdef = cwrdef.yams_schema()
    cstr = rdef.constraint_by_eid(cwconstraint.eid)
    with cnx.deny_all_hooks_but():
        cwconstraint.cw_set(value=unicode(cstr.serialize()))
    if cstr.type() not in ('BoundaryConstraint', 'IntervalBoundConstraint',
                           'StaticVocabularyConstraint'):
        # These cannot be translate into backend CHECK.
        continue
    cstrname, check = check_constraint(rdef.subject, rdef.object, rdef.rtype.type,
                                       cstr, helper, prefix='cw_')
    args = {'e': rdef.subject.type, 'c': cstrname, 'v': check}
    sql('ALTER TABLE cw_%(e)s ADD CONSTRAINT %(c)s CHECK(%(v)s)' % args)

commit()

if 'identity_relation' in helper.list_tables(cnx.cnxset.cu):
    sql('DROP TABLE identity_relation')
