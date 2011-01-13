add_relation_definition('CWUniqueTogetherConstraint', 'relations', 'CWRType')
rql('SET C relations RT WHERE C relations RDEF, RDEF relation_type RT')
commit()
drop_relation_definition('CWUniqueTogetherConstraint', 'relations', 'CWAttribute')
drop_relation_definition('CWUniqueTogetherConstraint', 'relations', 'CWRelation')

add_attribute('TrInfo', 'tr_count')
sync_schema_props_perms('TrInfo')
