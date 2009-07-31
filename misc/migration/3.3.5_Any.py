# some entities have been added before schema entities, fix the 'is' and
# 'is_instance_of' relations
for rtype in ('is', 'is_instance_of'):
    sql('INSERT INTO %s_relation '
        'SELECT X.eid, ET.cw_eid FROM entities as X, cw_CWEType as ET '
        'WHERE X.type=ET.cw_name AND NOT EXISTS('
        '      SELECT 1 from is_relation '
        '      WHERE eid_from=X.eid AND eid_to=ET.cw_eid)' % rtype)
