from datetime import datetime

for rtype in ('cw_support', 'cw_dont_cross', 'cw_may_cross'):
    drop_relation_type(rtype)

add_entity_type('CWSourceSchemaConfig')

if not 'url' in schema['CWSource'].subjrels:
    add_attribute('CWSource', 'url')
    add_attribute('CWSource', 'parser')
    add_attribute('CWSource', 'latest_retrieval')

try:
    from cubicweb.server.sources.pyrorql import PyroRQLSource
except ImportError:
    pass
else:

    from os.path import join
    # function to read old python mapping file
    def load_mapping_file(source):
        mappingfile = source.config['mapping-file']
        mappingfile = join(source.repo.config.apphome, mappingfile)
        mapping = {}
        execfile(mappingfile, mapping)
        for junk in ('__builtins__', '__doc__'):
            mapping.pop(junk, None)
        mapping.setdefault('support_relations', {})
        mapping.setdefault('dont_cross_relations', set())
        mapping.setdefault('cross_relations', set())
        # do some basic checks of the mapping content
        assert 'support_entities' in mapping, \
               'mapping file should at least define support_entities'
        assert isinstance(mapping['support_entities'], dict)
        assert isinstance(mapping['support_relations'], dict)
        assert isinstance(mapping['dont_cross_relations'], set)
        assert isinstance(mapping['cross_relations'], set)
        unknown = set(mapping) - set( ('support_entities', 'support_relations',
                                       'dont_cross_relations', 'cross_relations') )
        assert not unknown, 'unknown mapping attribute(s): %s' % unknown
        # relations that are necessarily not crossed
        for rtype in ('is', 'is_instance_of', 'cw_source'):
            assert rtype not in mapping['dont_cross_relations'], \
                   '%s relation should not be in dont_cross_relations' % rtype
            assert rtype not in mapping['support_relations'], \
                   '%s relation should not be in support_relations' % rtype
        return mapping
    # for now, only pyrorql sources have a mapping
    for source in repo.sources_by_uri.itervalues():
        if not isinstance(source, PyroRQLSource):
            continue
        sourceentity = session.entity_from_eid(source.eid)
        mapping = load_mapping_file(source)
        # write mapping as entities
        print 'migrating map for', source
        for etype, write in mapping['support_entities'].items():
            create_entity('CWSourceSchemaConfig',
                          cw_for_source=sourceentity,
                          cw_schema=session.entity_from_eid(schema[etype].eid),
                          options=write and u'write' or None,
                          ask_confirm=False)
        for rtype, write in mapping['support_relations'].items():
            options = []
            if write:
                options.append(u'write')
            if rtype in mapping['cross_relations']:
                options.append(u'maycross')
            create_entity('CWSourceSchemaConfig',
                          cw_for_source=sourceentity,
                          cw_schema=session.entity_from_eid(schema[rtype].eid),
                          options=u':'.join(options) or None,
                          ask_confirm=False)
        for rtype in mapping['dont_cross_relations']:
            create_entity('CWSourceSchemaConfig',
                          cw_for_source=source,
                          cw_schema=session.entity_from_eid(schema[rtype].eid),
                          options=u'dontcross',
                          ask_confirm=False)
        # latest update time cwproperty is now a source attribute (latest_retrieval)
        pkey = u'sources.%s.latest-update-time' % source.uri
        rset = session.execute('Any V WHERE X is CWProperty, X value V, X pkey %(k)s',
                               {'k': pkey})
        timestamp = int(rset[0][0])
        sourceentity.cw_set(latest_retrieval=datetime.fromtimestamp(timestamp))
        session.execute('DELETE CWProperty X WHERE X pkey %(k)s', {'k': pkey})
