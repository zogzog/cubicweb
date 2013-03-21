"""
CAUTION: READ THIS CAREFULLY

Sometimes it happens that ldap (specifically ldapuser type) source
yield "ghost" users. The reasons may vary (server upgrade while some
instances are still running & syncing with the ldap source, unmanaged
updates to the upstream ldap, etc.).

This script was written and refined enough times that we are confident
in that it does something reasonnable (at least it did for the
target application).

However you should really REALLY understand what it does before
deciding to apply it for you. And then ADAPT it tou your needs.

"""

import base64
from collections import defaultdict

from cubicweb.server.session import hooks_control

try:
    source_name, = __args__
    source = repo.sources_by_uri[source_name]
except ValueError:
    print('you should specify the source name as script argument (i.e. after --'
          ' on the command line)')
    sys.exit(1)
except KeyError:
    print '%s is not an active source' % source_name
    sys.exit(1)

# check source is reachable before doing anything
if not source.get_connection().cnx:
    print '%s is not reachable. Fix this before running this script' % source_name
    sys.exit(1)

def find_dupes():
    # XXX this retrieves entities from a source name "ldap"
    #     you will want to adjust
    rset = sql("SELECT eid, extid FROM entities WHERE source='%s'" % source_name)
    extid2eids = defaultdict(list)
    for eid, extid in rset:
        extid2eids[extid].append(eid)
    return dict((base64.b64decode(extid).lower(), eids)
                for extid, eids in extid2eids.items()
                if len(eids) > 1)

def merge_dupes(dupes, docommit=False):
    gone_eids = []
    CWUser = schema['CWUser']
    for extid, eids in dupes.items():
        newest = eids.pop() # we merge everything on the newest
        print 'merging ghosts of', extid, 'into', newest
        # now we merge pairwise into the newest
        for old in eids:
            subst = {'old': old, 'new': newest}
            print '  merging', old
            gone_eids.append(old)
            for rschema in CWUser.subject_relations():
                if rschema.final or rschema == 'identity':
                    continue
                if CWUser.rdef(rschema, 'subject').composite == 'subject':
                    # old 'composite' property is wiped ...
                    # think about email addresses, excel preferences
                    for eschema in rschema.objects():
                        rql('DELETE %s X WHERE U %s X, U eid %%(old)s' % (eschema, rschema), subst)
                else:
                    # relink the new user to its old relations
                    rql('SET NU %s X WHERE NU eid %%(new)s, NOT NU %s X, OU %s X, OU eid %%(old)s' %
                        (rschema, rschema, rschema), subst)
                    # delete the old relations
                    rql('DELETE U %s X WHERE U eid %%(old)s' % rschema, subst)
            # same thing ...
            for rschema in CWUser.object_relations():
                if rschema.final or rschema == 'identity':
                    continue
                rql('SET X %s NU WHERE NU eid %%(new)s, NOT X %s NU, X %s OU, OU eid %%(old)s' %
                    (rschema, rschema, rschema), subst)
                rql('DELETE X %s U WHERE U eid %%(old)s' % rschema, subst)
    if not docommit:
        rollback()
        return
    commit() # XXX flushing operations is wanted rather than really committing
    print 'clean up entities table'
    sql('DELETE FROM entities WHERE eid IN (%s)' % (', '.join(str(x) for x in gone_eids)))
    commit()

def main():
    dupes = find_dupes()
    if not dupes:
        print 'No duplicate user'
        return

    print 'Found %s duplicate user instances' % len(dupes)

    while True:
        print 'Fix or dry-run? (f/d)  ... or Ctrl-C to break out'
        answer = raw_input('> ')
        if answer.lower() not in 'fd':
            continue
        print 'Please STOP THE APPLICATION INSTANCES (service or interactive), and press Return when done.'
        raw_input('<I swear all running instances and workers of the application are stopped>')
        with hooks_control(session, session.HOOKS_DENY_ALL):
            merge_dupes(dupes, docommit=answer=='f')

main()
