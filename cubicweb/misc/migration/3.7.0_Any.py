typemap = repo.system_source.dbhelper.TYPE_MAPPING
sqls = """
CREATE TABLE transactions (
  tx_uuid CHAR(32) PRIMARY KEY NOT NULL,
  tx_user INTEGER NOT NULL,
  tx_time %s NOT NULL
);;
CREATE INDEX transactions_tx_user_idx ON transactions(tx_user);;

CREATE TABLE tx_entity_actions (
  tx_uuid CHAR(32) REFERENCES transactions(tx_uuid) ON DELETE CASCADE,
  txa_action CHAR(1) NOT NULL,
  txa_public %s NOT NULL,
  txa_order INTEGER,
  eid INTEGER NOT NULL,
  etype VARCHAR(64) NOT NULL,
  changes %s
);;
CREATE INDEX tx_entity_actions_txa_action_idx ON tx_entity_actions(txa_action);;
CREATE INDEX tx_entity_actions_txa_public_idx ON tx_entity_actions(txa_public);;
CREATE INDEX tx_entity_actions_eid_idx ON tx_entity_actions(eid);;
CREATE INDEX tx_entity_actions_etype_idx ON tx_entity_actions(etype);;

CREATE TABLE tx_relation_actions (
  tx_uuid CHAR(32) REFERENCES transactions(tx_uuid) ON DELETE CASCADE,
  txa_action CHAR(1) NOT NULL,
  txa_public %s NOT NULL,
  txa_order INTEGER,
  eid_from INTEGER NOT NULL,
  eid_to INTEGER NOT NULL,
  rtype VARCHAR(256) NOT NULL
);;
CREATE INDEX tx_relation_actions_txa_action_idx ON tx_relation_actions(txa_action);;
CREATE INDEX tx_relation_actions_txa_public_idx ON tx_relation_actions(txa_public);;
CREATE INDEX tx_relation_actions_eid_from_idx ON tx_relation_actions(eid_from);;
CREATE INDEX tx_relation_actions_eid_to_idx ON tx_relation_actions(eid_to)
""" % (typemap['Datetime'],
       typemap['Boolean'], typemap['Bytes'], typemap['Boolean'])
for statement in sqls.split(';;'):
    sql(statement)
