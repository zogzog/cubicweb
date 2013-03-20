sync_schema_props_perms('EmailAddress')

for source in rql('CWSource X WHERE X type "pyrorql"').entities():
    sconfig = source.dictconfig
    nsid = sconfig.pop('pyro-ns-id', config.appid)
    nshost = sconfig.pop('pyro-ns-host', '')
    nsgroup = sconfig.pop('pyro-ns-group', ':cubicweb')
    if nsgroup:
        nsgroup += '.'
    source.cw_set(url=u'pyro://%s/%s%s' % (nshost, nsgroup, nsid))
    source.update_config(skip_unknown=True, **sconfig)

commit()
