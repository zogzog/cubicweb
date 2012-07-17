sync_schema_props_perms('EmailAddress')

for source in rql('CWSource X WHERE X type "ldapuser"').entities():
    config = source.dictconfig
    host = config.pop('host', u'ldap')
    protocol = config.pop('protocol', u'ldap')
    source.cw_set(url=u'%s://%s' % (protocol, host))
    source.update_config(skip_unknown=True, **config)

commit()
