
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
