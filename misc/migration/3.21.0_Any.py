
helper = repo.system_source.dbhelper
sql('DROP INDEX entities_extid_idx')
sql(helper.sql_create_index('entities', 'extid', True))
commit()
