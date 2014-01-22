for table, column in [
        ('transactions', 'tx_time'),
        ('tx_entity_actions', 'tx_uuid'),
        ('tx_relation_actions', 'tx_uuid')]:
    repo.system_source.create_index(session, table, column)

commit()
