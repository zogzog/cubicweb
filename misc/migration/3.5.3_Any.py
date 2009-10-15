# type attribute might already be there if migrating from
# version < 3.5 to version >= 3.5.3, BaseTransition being added
# in bootstrap_migration
if versions_map['cubicweb'][0] >= (3, 5, 0):
    add_attribute('BaseTransition', 'type')
    sync_schema_props_perms('state_of')
    sync_schema_props_perms('transition_of')
