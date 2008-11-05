if confirm('remove deprecated database constraints?'):
    execute = session.system_sql
    session.set_pool()
    dbhelper = session.pool.source('system').dbhelper
    cu = session.pool['system']
    for table in dbhelper.list_tables(cu):
        if table.endswith('_relation'):
            try:
                execute('ALTER TABLE %s DROP CONSTRAINT %s_fkey1' % (table, table))
                execute('ALTER TABLE %s DROP CONSTRAINT %s_fkey2' % (table, table))
            except:
                continue
    checkpoint()

if 'inline_view' in schema:
    # inline_view attribute should have been deleted for a while now....
    drop_attribute('ENFRDef', 'inline_view')
    
