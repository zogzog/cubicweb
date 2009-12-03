sync_schema_props_perms('state_of')
sync_schema_props_perms('transition_of')
for etype in ('State', 'BaseTransition', 'Transition', 'WorkflowTransition'):
    sync_schema_props_perms((etype, 'name', 'String'))

