if repo.system_source.dbdriver == 'postgres':
    sql('ALTER TABLE appears ADD COLUMN weight float')
    sql('UPDATE appears SET weight=1.0 ')
