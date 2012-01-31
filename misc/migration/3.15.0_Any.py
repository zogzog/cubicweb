sync_schema_props_perms('EmailAddress')

for source in rql('CWSource X WHERE X type "ldapuser"').entities():
    config = source.dictconfig
    host = config.pop('host', 'ldap')
    protocol = config.pop('protocol', 'ldap')
    source.set_attributes(url='%s://%s' % (protocol, host))
    source.update_config(skip_unknown=True, **config)

commit()
