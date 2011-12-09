sync_schema_props_perms('cw_source', syncprops=False)
if schema['BigInt'].eid is None:
    add_entity_type('BigInt')
