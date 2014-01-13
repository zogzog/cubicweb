for table, column in [
        ('transactions', 'tx_time'),
        ('tx_entity_actions', 'tx_uuid'),
        ('tx_relation_actions', 'tx_uuid')]:
    session.cnxset.source('system').create_index(session, table, column)

commit()
