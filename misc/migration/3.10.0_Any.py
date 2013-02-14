from cubicweb.server.session import hooks_control

for uri, cfg in config.sources().items():
    if uri in ('system', 'admin'):
        continue
    repo.sources_by_uri[uri] = repo.get_source(cfg['adapter'], uri, cfg.copy())

add_entity_type('CWSource')
add_relation_definition('CWSource', 'cw_source', 'CWSource')
add_entity_type('CWSourceHostConfig')

with hooks_control(session, session.HOOKS_ALLOW_ALL, 'cw.sources'):
    create_entity('CWSource', type=u'native', name=u'system')
commit()

sql('INSERT INTO cw_source_relation(eid_from,eid_to) '
    'SELECT e.eid,s.cw_eid FROM entities as e, cw_CWSource as s '
    'WHERE s.cw_name=e.type')
commit()

for uri, cfg in config.sources().items():
    if uri in ('system', 'admin'):
        continue
    repo.sources_by_uri.pop(uri)
    config = u'\n'.join('%s=%s' % (key, value) for key, value in cfg.items()
                        if key != 'adapter' and value is not None)
    create_entity('CWSource', name=unicode(uri), type=unicode(cfg['adapter']),
                  config=config)
commit()

# rename cwprops for boxes/contentnavigation
for x in rql('Any X,XK WHERE X pkey XK, '
             'X pkey ~= "boxes.%" OR '
             'X pkey ~= "contentnavigation.%"').entities():
    x.cw_set(pkey=u'ctxcomponents.' + x.pkey.split('.', 1)[1])

