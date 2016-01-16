from __future__ import print_function

def migrate_varchar_to_nvarchar():
    dbdriver  = config.system_source_config['db-driver']
    if dbdriver != "sqlserver2005":
        return

    introspection_sql = """\
SELECT table_schema, table_name, column_name, is_nullable, character_maximum_length
FROM information_schema.columns
WHERE data_type = 'VARCHAR' and table_name <> 'SYSDIAGRAMS'
"""
    has_index_sql = """\
SELECT i.name AS index_name,
       i.type_desc,
       i.is_unique,
       i.is_unique_constraint
FROM sys.indexes AS i, sys.index_columns as j, sys.columns as k
WHERE is_hypothetical = 0 AND i.index_id <> 0
AND i.object_id = j.object_id
AND i.index_id = j.index_id
AND i.object_id = OBJECT_ID('%(table)s')
AND k.name = '%(col)s'
AND k.object_id=i.object_id
AND j.column_id = k.column_id;"""

    generated_statements = []
    for schema, table, column, is_nullable, length in sql(introspection_sql, ask_confirm=False):
        qualified_table = '[%s].[%s]' % (schema, table)
        rset = sql(has_index_sql % {'table': qualified_table, 'col':column},
                   ask_confirm = False)
        drops = []
        creates = []
        for idx_name, idx_type, idx_unique, is_unique_constraint in rset:
            if is_unique_constraint:
                drops.append('ALTER TABLE %s DROP CONSTRAINT %s' % (qualified_table, idx_name))
                creates.append('ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s)' % (qualified_table, idx_name, column))
            else:
                drops.append('DROP INDEX %s ON %s' % (idx_name, qualified_table))
                if idx_unique:
                    unique = 'UNIQUE'
                else:
                    unique = ''
                creates.append('CREATE %s %s INDEX %s ON %s(%s)' % (unique, idx_type, idx_name, qualified_table, column))

        if length == -1:
            length = 'max'
        if is_nullable == 'YES':
            not_null = 'NULL'
        else:
            not_null = 'NOT NULL'
        alter_sql = 'ALTER TABLE %s ALTER COLUMN %s NVARCHAR(%s) %s' % (qualified_table, column, length, not_null)
        generated_statements+= drops + [alter_sql] + creates


    for statement in generated_statements:
        print(statement)
        sql(statement, ask_confirm=False)
    commit()

migrate_varchar_to_nvarchar()
