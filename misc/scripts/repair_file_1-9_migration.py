"""execute this script if you've migration to file >= 1.9.0 with cubicweb <= 3.9.2

FYI, this migration occurred :
* on our intranet on July 07 2010
* on our extranet on July 16 2010
"""

try:
    backupinstance, = __args__
except ValueError:
    print 'USAGE: cubicweb-ctl shell <instance> repair_file_1-9_migration.py -- <backup instance id>'
    print
    print 'you should restored the backup on a new instance, accessible through pyro'

from cubicweb import cwconfig, dbapi
from cubicweb.server.session import hooks_control

defaultadmin = repo.config.default_admin_config
backupcfg = cwconfig.instance_configuration(backupinstance)
backupcfg.repairing = True
backuprepo, backupcnx = dbapi.in_memory_repo_cnx(backupcfg, defaultadmin['login'],
                                                 password=defaultadmin['password'],
                                                 host='localhost')
backupcu = backupcnx.cursor()

with hooks_control(session, session.HOOKS_DENY_ALL):
    rql('SET X is Y WHERE X is File, Y name "File", NOT X is Y')
    rql('SET X is_instance_of Y WHERE X is File, Y name "File", NOT X is_instance_of Y')
    for rtype, in backupcu.execute('DISTINCT Any RTN WHERE X relation_type RT, RT name RTN,'
                                   'X from_entity Y, Y name "Image", X is CWRelation, '
                                   'EXISTS(XX is CWRelation, XX relation_type RT, '
                                   'XX from_entity YY, YY name "File")'):
        if rtype in ('is', 'is_instance_of'):
            continue
        print rtype
        for feid, xeid in backupcu.execute('Any F,X WHERE F %s X, F is IN (File,Image)' % rtype):
            print 'restoring relation %s between file %s and %s' % (rtype, feid, xeid),
            print rql('SET F %s X WHERE F eid %%(f)s, X eid %%(x)s, NOT F %s X' % (rtype, rtype),
                      {'f': feid, 'x': xeid})

    for rtype, in backupcu.execute('DISTINCT Any RTN WHERE X relation_type RT, RT name RTN,'
                                   'X to_entity Y, Y name "Image", X is CWRelation, '
                                   'EXISTS(XX is CWRelation, XX relation_type RT, '
                                   'XX to_entity YY, YY name "File")'):
        print rtype
        for feid, xeid in backupcu.execute('Any F,X WHERE X %s F, F is IN (File,Image)' % rtype):
            print 'restoring relation %s between %s and file %s' % (rtype, xeid, feid),
            print rql('SET X %s F WHERE F eid %%(f)s, X eid %%(x)s, NOT X %s F' % (rtype, rtype),
                      {'f': feid, 'x': xeid})

commit()
