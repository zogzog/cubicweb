sync_schema_props_perms('state_of')
sync_schema_props_perms('transition_of')

# type attribute might already be there if migrating from
# version < 3.5 to version >= 3.5.3, BaseTransition being added
# in bootstrap_migration
if not schema.eschema('BaseTransition').has_subject_relation('type'):
    add_attribute('BaseTransition', 'type')
