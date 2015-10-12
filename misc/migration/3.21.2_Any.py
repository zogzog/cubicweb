sync_schema_props_perms('cwuri')

helper = repo.system_source.dbhelper
cu = session.cnxset.cu
helper.set_null_allowed(cu, 'moved_entities', 'extid', 'VARCHAR(256)', False)

commit()
