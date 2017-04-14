from cubicweb.server import SOURCE_TYPES
from cubicweb.server.serverconfig import (SourceConfiguration,
                                          generate_source_config)


sync_schema_props_perms('EmailAddress')


def update_config(source, **config):
    cfg = source.dictconfig
    cfg.update(config)
    options = SOURCE_TYPES[source.type].options
    sconfig = SourceConfiguration(source._cw.vreg.config, options=options)
    for opt, val in cfg.items():
        try:
            sconfig.set_option(opt, val)
        except OptionError:
            continue
    cfgstr = text_type(generate_source_config(sconfig), source._cw.encoding)
    source.cw_set(config=cfgstr)


for source in rql('CWSource X WHERE X type "ldapuser"').entities():
    config = source.dictconfig
    host = config.pop('host', u'ldap')
    protocol = config.pop('protocol', u'ldap')
    source.cw_set(url=u'%s://%s' % (protocol, host))
    update_config(source, **config)

commit()
