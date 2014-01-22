from yams import schema2sql as y2sql

dbhelper = repo.system_source.dbhelper
rdefdef = schema['CWSource'].rdef('name')
attrtype = y2sql.type_from_constraints(dbhelper, rdefdef.object, rdefdef.constraints).split()[0]

cursor = session.cnxset.cu
sql('UPDATE entities SET asource = source WHERE asource is NULL')
dbhelper.change_col_type(cursor, 'entities', 'asource', attrtype, False)
dbhelper.change_col_type(cursor, 'entities', 'source', attrtype, False)
