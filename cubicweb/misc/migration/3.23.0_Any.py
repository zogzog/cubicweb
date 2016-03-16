# we changed constraint serialization, which also changes their name
from cubicweb.server.schema2sql import check_constraint

helper = repo.system_source.dbhelper

for table, cstr in sql("""
    SELECT table_name, constraint_name FROM information_schema.constraint_column_usage
    WHERE constraint_name LIKE 'cstr%'"""):
    sql("ALTER TABLE %(table)s DROP CONSTRAINT %(cstr)s" % locals())

for cwconstraint in rql('Any C WHERE R constrained_by C').entities():
    cwrdef = cwconstraint.reverse_constrained_by[0]
    rdef = cwrdef.yams_schema()
    cstr = rdef.constraint_by_eid(cwconstraint.eid)
    if cstr.type() not in ('BoundaryConstraint', 'IntervalBoundConstraint',
                           'StaticVocabularyConstraint'):
        # These cannot be translate into backend CHECK.
        continue
    cstrname, check = check_constraint(rdef.subject, rdef.object, rdef.rtype.type,
                                       cstr, helper, prefix='cw_')
    args = {'e': rdef.subject.type, 'c': cstrname, 'v': check}
    sql('ALTER TABLE cw_%(e)s ADD CONSTRAINT %(c)s CHECK(%(v)s)' % args)

commit()
