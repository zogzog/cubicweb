
helper = repo.system_source.dbhelper
sql('DROP INDEX entities_extid_idx')
sql(helper.sql_create_index('entities', 'extid', True))

sql('''
CREATE TABLE moved_entities (
  eid INTEGER PRIMARY KEY NOT NULL,
  extid VARCHAR(256) UNIQUE
)
''')

moved_entities = sql('SELECT -eid, extid FROM entities WHERE eid < 0')
cu = session.cnxset.cu
cu.executemany('INSERT INTO moved_entities (eid, extid) VALUES (%s, %s)',
               moved_entities)
sql('DELETE FROM entities WHERE eid < 0')

commit()

sync_schema_props_perms('CWEType')

sync_schema_props_perms('cwuri')

from cubicweb.server.schema2sql import check_constraint

for cwconstraint in rql('Any C WHERE R constrained_by C').entities():
    cwrdef = cwconstraint.reverse_constrained_by[0]
    rdef = cwrdef.yams_schema()
    cstr = rdef.constraint_by_eid(cwconstraint.eid)
    if cstr.type() not in ('BoundaryConstraint', 'IntervalBoundConstraint', 'StaticVocabularyConstraint'):
        continue
    cstrname, check = check_constraint(rdef.subject, rdef.object, rdef.rtype.type,
            cstr, helper, prefix='cw_')
    sql('ALTER TABLE %s%s ADD CONSTRAINT %s CHECK(%s)' % ('cw_', rdef.subject.type, cstrname, check))
commit()
