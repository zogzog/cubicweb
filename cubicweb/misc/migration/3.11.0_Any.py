for rtype in ('cw_support', 'cw_dont_cross', 'cw_may_cross'):
    drop_relation_type(rtype)

if not 'url' in schema['CWSource'].subjrels:
    add_attribute('CWSource', 'url')
    add_attribute('CWSource', 'parser')
    add_attribute('CWSource', 'latest_retrieval')
