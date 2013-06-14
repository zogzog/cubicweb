from cubicweb import UnknownEid
source, = __args__

sql("DELETE FROM entities WHERE type='Int'")

ecnx = session.cnxset.connection(source)
for e in rql('Any X WHERE X cw_source S, S name %(name)s', {'name': source}).entities():
    meta = e.cw_metainformation()
    assert meta['source']['uri'] == source
    try:
        suri = ecnx.describe(meta['extid'])[1]
    except UnknownEid:
        print 'cant describe', e.cw_etype, e.eid, meta
        continue
    if suri != 'system':
        try:
            print 'deleting', e.cw_etype, e.eid, suri, e.dc_title().encode('utf8')
            repo.delete_info(session, e, suri, scleanup=e.eid)
        except UnknownEid:
            print '  cant delete', e.cw_etype, e.eid, meta


commit()
