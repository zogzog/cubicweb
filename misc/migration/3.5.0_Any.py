add_relation_type('prefered_form')

rql('SET X prefered_form Y WHERE Y canonical TRUE, X identical_to Y')
checkpoint()

drop_attribute('EmailAddress', 'canonical')
drop_relation_definition('EmailAddress', 'identical_to', 'EmailAddress')

if 'see_also' in schema:
    sync_schema_props_perms('see_also', syncprops=False, syncrdefs=False)
