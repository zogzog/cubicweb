from yams import schema2sql as y2sql

dbhelper = repo.system_source.dbhelper
rdefdef = schema['CWSource'].rdef('name')
attrtype = y2sql.type_from_constraints(dbhelper, rdefdef.object, rdefdef.constraints).split()[0]

sql(dbhelper.sql_change_col_type('entities', 'asource', attrtype, False))
sql(dbhelper.sql_change_col_type('entities', 'source', attrtype, False))
sql(dbhelper.sql_change_col_type('deleted_entities', 'source', attrtype, False))
