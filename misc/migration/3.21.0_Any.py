from cubicweb.schema import PURE_VIRTUAL_RTYPES
from cubicweb.server.schema2sql import rschema_has_table


def add_foreign_keys():
    source = repo.sources_by_uri['system']
    if not source.dbhelper.alter_column_support:
        return
    for rschema in schema.relations():
        if rschema.inlined:
            add_foreign_keys_inlined(rschema)
        elif rschema_has_table(rschema, skip_relations=PURE_VIRTUAL_RTYPES):
            add_foreign_keys_relation(rschema)
    for eschema in schema.entities():
        if eschema.final:
            continue
        add_foreign_key_etype(eschema)


def add_foreign_keys_relation(rschema):
    args = {'r': rschema.type}
    count = sql('SELECT COUNT(*) FROM ('
                '    SELECT eid_from FROM %(r)s_relation'
                '  UNION'
                '    SELECT eid_to FROM %(r)s_relation'
                '  EXCEPT'
                '    SELECT eid FROM entities) AS eids' % args,
                ask_confirm=False)[0][0]
    if count:
        print '%s references %d unknown entities, deleting' % (rschema, count)
        sql('DELETE FROM %(r)s_relation '
            'WHERE eid_from IN (SELECT eid_from FROM %(r)s_relation EXCEPT SELECT eid FROM entities)' % args)
        sql('DELETE FROM %(r)s_relation '
            'WHERE eid_to IN (SELECT eid_to FROM %(r)s_relation EXCEPT SELECT eid FROM entities)' % args)

    sql('ALTER TABLE %(r)s_relation DROP CONSTRAINT IF EXISTS %(r)s_relation_eid_from_fkey' % args)
    sql('ALTER TABLE %(r)s_relation DROP CONSTRAINT IF EXISTS %(r)s_relation_eid_to_fkey' % args)
    sql('ALTER TABLE %(r)s_relation ADD CONSTRAINT %(r)s_relation_eid_from_fkey '
        'FOREIGN KEY (eid_from) REFERENCES entities (eid)' % args)
    sql('ALTER TABLE %(r)s_relation ADD CONSTRAINT %(r)s_relation_eid_to_fkey '
        'FOREIGN KEY (eid_to) REFERENCES entities (eid)' % args)


def add_foreign_keys_inlined(rschema):
    for eschema in rschema.subjects():
        args = {'e': eschema.type, 'r': rschema.type}
        args['c'] = 'cw_%(e)s_cw_%(r)s_fkey' % args

        if eschema.rdef(rschema).cardinality[0] == '1':
            broken_eids = sql('SELECT cw_eid FROM cw_%(e)s WHERE cw_%(r)s IS NULL' % args, ask_confirm=False)
            if broken_eids:
                print 'Required relation %(e)s.%(r)s missing' % args
                args['eids'] = ', '.join(str(eid) for eid, in broken_eids)
                rql('DELETE %(e)s X WHERE X eid IN (%(eids)s)' % args)
            broken_eids = sql('SELECT cw_eid FROM cw_%(e)s WHERE cw_%(r)s IN (SELECT cw_%(r)s FROM cw_%(e)s '
                              'EXCEPT SELECT eid FROM entities)' % args, ask_confirm=False)
            if broken_eids:
                print 'Required relation %(e)s.%(r)s references unknown objects, deleting subject entities' % args
                args['eids'] = ', '.join(str(eid) for eid, in broken_eids)
                rql('DELETE %(e)s X WHERE X eid IN (%(eids)s)' % args)
        else:
            if sql('SELECT COUNT(*) FROM ('
                   '    SELECT cw_%(r)s FROM cw_%(e)s WHERE cw_%(r)s IS NOT NULL'
                   '  EXCEPT'
                   '    SELECT eid FROM entities) AS eids' % args, ask_confirm=False)[0][0]:
                print '%(e)s.%(r)s references unknown entities, deleting relation' % args
                sql('UPDATE cw_%(e)s SET cw_%(r)s = NULL WHERE cw_%(r)s IS NOT NULL AND cw_%(r)s IN '
                    '(SELECT cw_%(r)s FROM cw_%(e)s EXCEPT SELECT eid FROM entities)' % args)
        sql('ALTER TABLE cw_%(e)s DROP CONSTRAINT IF EXISTS %(c)s' % args)
        sql('ALTER TABLE cw_%(e)s ADD CONSTRAINT %(c)s '
            'FOREIGN KEY (cw_%(r)s) references entities(eid)'
            % args)


def add_foreign_key_etype(eschema):
    args = {'e': eschema.type}
    if sql('SELECT COUNT(*) FROM ('
           '    SELECT cw_eid FROM cw_%(e)s'
           '  EXCEPT'
           '    SELECT eid FROM entities) AS eids' % args,
           ask_confirm=False)[0][0]:
        print '%(e)s has nonexistent entities, deleting' % args
        sql('DELETE FROM cw_%(e)s WHERE cw_eid IN '
            '(SELECT cw_eid FROM cw_%(e)s EXCEPT SELECT eid FROM entities)' % args)
    sql('ALTER TABLE cw_%(e)s DROP CONSTRAINT IF EXISTS cw_%(e)s_cw_eid_fkey' % args)
    sql('ALTER TABLE cw_%(e)s ADD CONSTRAINT cw_%(e)s_cw_eid_fkey '
        'FOREIGN KEY (cw_eid) REFERENCES entities (eid)' % args)


add_foreign_keys()

cu = session.cnxset.cu
helper = repo.system_source.dbhelper

helper.drop_index(cu, 'entities', 'extid', False)
helper.create_index(cu, 'entities', 'extid', True)

if 'moved_entities' not in helper.list_tables(cu):
    sql('''
    CREATE TABLE moved_entities (
      eid INTEGER PRIMARY KEY NOT NULL,
      extid VARCHAR(256) UNIQUE
    )
    ''')

moved_entities = sql('SELECT -eid, extid FROM entities WHERE eid < 0')
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
    sql('ALTER TABLE %s%s DROP CONSTRAINT IF EXISTS %s' % ('cw_', rdef.subject.type, cstrname))
    sql('ALTER TABLE %s%s ADD CONSTRAINT %s CHECK(%s)' % ('cw_', rdef.subject.type, cstrname, check))
commit()
