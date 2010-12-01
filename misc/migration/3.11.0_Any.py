sync_schema_props_perms('cw_support', syncperms=False)
sync_schema_props_perms('cw_dont_cross', syncperms=False)
sync_schema_props_perms('cw_may_cross', syncperms=False)

try:
    from cubicweb.server.sources.pyrorql import PyroRQLSource
except ImportError:
    pass
else:

    from os.path import join

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

    for source in repo.sources_by_uri.values():
        if not isinstance(source, PyroRQLSource):
            continue
        mapping = load_mapping_file(source)
        print 'migrating map for', source
        for etype in mapping['support_entities']: # XXX write support
            rql('SET S cw_support ET WHERE ET name %(etype)s, ET is CWEType, S eid %(s)s',
                {'etype': etype, 's': source.eid})
        for rtype in mapping['support_relations']: # XXX write support
            rql('SET S cw_support RT WHERE RT name %(rtype)s, RT is CWRType, S eid %(s)s',
                {'rtype': rtype, 's': source.eid})
        for rtype in mapping['dont_cross_relations']: # XXX write support
            rql('SET S cw_dont_cross RT WHERE RT name %(rtype)s, S eid %(s)s',
                {'rtype': rtype, 's': source.eid})
        for rtype in mapping['cross_relations']: # XXX write support
            rql('SET S cw_may_cross RT WHERE RT name %(rtype)s, S eid %(s)s',
                {'rtype': rtype, 's': source.eid})
