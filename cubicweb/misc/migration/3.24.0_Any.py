from base64 import b64decode


# Check the CW versions and add the entity only if needed ?
add_entity_type('CWSession')
rql('DELETE CWProperty X WHERE X pkey "system.version.pyramid"',
    ask_confirm=False)

sql('DROP TABLE moved_entities')
sql('ALTER TABLE entities DROP COLUMN asource')
# before removing extid, ensure it's coherent with cwuri
for eid, etype, encoded_extid in sql(
        "SELECT eid, type, extid FROM entities, cw_CWSource "
        "WHERE cw_CWSource.cw_name=entities.asource AND cw_CWSource.cw_type='ldapfeed'"):
    sql('UPDATE cw_{} SET cw_cwuri=%(cwuri)s WHERE cw_eid=%(eid)s'.format(etype),
        {'eid': eid, 'cwuri': b64decode(encoded_extid)})
sql('ALTER TABLE entities DROP COLUMN extid')
sql('DROP INDEX entities_type_idx')

# force cw_schema deletion before CWSourceSchemaConfig to avoid nasty bug
drop_relation_type('cw_schema')
drop_entity_type('CWSourceSchemaConfig')
