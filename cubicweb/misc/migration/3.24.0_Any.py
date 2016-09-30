# Check the CW versions and add the entity only if needed ?
add_entity_type('CWSession')
rql('DELETE CWProperty X WHERE X pkey "system.version.pyramid"',
    ask_confirm=False)

sql('DROP TABLE moved_entities')
sql('ALTER TABLE entities DROP COLUMN asource')
