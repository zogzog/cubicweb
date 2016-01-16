sync_schema_props_perms('CWSourceHostConfig', syncperms=False)

sql('INSERT INTO cw_source_relation(eid_from, eid_to) '
    'SELECT e.eid,s.cw_eid FROM entities as e, cw_CWSource as s '
    'WHERE s.cw_name=e.source AND NOT EXISTS(SELECT 1 FROM cw_source_relation WHERE eid_from=e.eid AND eid_to=s.cw_eid)')
commit()
