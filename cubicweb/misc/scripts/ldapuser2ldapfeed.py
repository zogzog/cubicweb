"""turn a pyro source into a datafeed source

Once this script is run, execute c-c db-check to cleanup relation tables.
"""
from __future__ import print_function

import sys
from collections import defaultdict
from logilab.common.shellutils import generate_password

try:
    source_name, = __args__
    source = repo.sources_by_uri[source_name]
except ValueError:
    print('you should specify the source name as script argument (i.e. after --'
          ' on the command line)')
    sys.exit(1)
except KeyError:
    print('%s is not an active source' % source_name)
    sys.exit(1)

# check source is reachable before doing anything
if not source.get_connection().cnx:
    print('%s is not reachable. Fix this before running this script' % source_name)
    sys.exit(1)

raw_input('Ensure you have shutdown all instances of this application before continuing.'
          ' Type enter when ready.')

system_source = repo.system_source

from datetime import datetime
from cubicweb.server.edition import EditedEntity


print('******************** backport entity content ***************************')

todelete = defaultdict(list)
extids = set()
duplicates = []
for entity in rql('Any X WHERE X cw_source S, S eid %(s)s', {'s': source.eid}).entities():
    etype = entity.cw_etype
    if not source.support_entity(etype):
        print("source doesn't support %s, delete %s" % (etype, entity.eid))
        todelete[etype].append(entity)
        continue
    try:
        entity.complete()
    except Exception:
        print('%s %s much probably deleted, delete it (extid %s)' % (
            etype, entity.eid, entity.cw_metainformation()['extid']))
        todelete[etype].append(entity)
        continue
    print('get back', etype, entity.eid)
    entity.cw_edited = EditedEntity(entity, **entity.cw_attr_cache)
    if not entity.creation_date:
        entity.cw_edited['creation_date'] = datetime.utcnow()
    if not entity.modification_date:
        entity.cw_edited['modification_date'] = datetime.utcnow()
    if not entity.upassword:
        entity.cw_edited['upassword'] = generate_password()
    extid = entity.cw_metainformation()['extid']
    if not entity.cwuri:
        entity.cw_edited['cwuri'] = '%s/?dn=%s' % (
            source.urls[0], extid.decode('utf-8', 'ignore'))
    print(entity.cw_edited)
    if extid in extids:
        duplicates.append(extid)
        continue
    extids.add(extid)
    system_source.add_entity(session, entity)
    sql("UPDATE entities SET source='system' "
        "WHERE eid=%(eid)s", {'eid': entity.eid})

# only cleanup entities table, remaining stuff should be cleaned by a c-c
# db-check to be run after this script
if duplicates:
    print('found %s duplicate entries' % len(duplicates))
    from pprint import pprint
    pprint(duplicates)

print(len(todelete), 'entities will be deleted')
for etype, entities in todelete.items():
    print('deleting', etype, [e.login for e in entities])
    system_source.delete_info_multi(session, entities, source_name)



source_ent = rql('CWSource S WHERE S eid %(s)s', {'s': source.eid}).get_entity(0, 0)
source_ent.cw_set(type=u"ldapfeed", parser=u"ldapfeed")


if raw_input('Commit?') in 'yY':
    print('committing')
    commit()
else:
    rollback()
    print('rolled back')
