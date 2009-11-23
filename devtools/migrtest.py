"""Migration test script

* migration will be played into a chroot of the local machine
* the database server used can be configured
* test tested instance may be on another host


We are using postgres'.pgpass file. Here is a copy of postgres documentation
about that:

The file .pgpass in a user's home directory or the file referenced by
PGPASSFILE can contain passwords to be used if the connection requires
a password (and no password has been specified otherwise).


This file should contain lines of the following format:

hostname:port:database:username:password

Each of the first four fields may be a literal value, or *, which
matches anything. The password field from the first line that matches
the current connection parameters will be used. (Therefore, put
more-specific entries first when you are using wildcards.) If an entry
needs to contain : or \, escape this character with \. A hostname of
localhost matches both host (TCP) and local (Unix domain socket)
connections coming from the local machine.

The permissions on .pgpass must disallow any access to world or group;
achieve this by the command chmod 0600 ~/.pgpass. If the permissions
are less strict than this, the file will be ignored.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from os import system
from os.path import join, basename

from logilab.common.shellutils import cp, rm

from cubicweb.toolsutils import read_config
from cubicweb.server.utils import generate_sources_file

# XXXX use db-copy instead

# test environment configuration
chrootpath = '/sandbox/cubicwebtest'
tmpdbhost = 'crater'
tmpdbuser = 'syt'
tmpdbpasswd = 'syt'

def play_migration(applhome, applhost='', sudo=False):
    applid = dbname = basename(applhome)
    testapplhome = join(chrootpath, applhome)
    # copy instance into the chroot
    if applhost:
        system('scp -r %s:%s %s' % (applhost, applhome, testapplhome))
    else:
        cp(applhome, testapplhome)
##     # extract db parameters
##     sources = read_config(join(testapplhome, 'sources'))
##     dbname = sources['system']['db-name']
##     dbhost = sources['system'].get('db-host') or ''
##     dbuser = sources['system'].get('db-user') or ''
##     dbpasswd = sources['system'].get('db-password') or ''
    # generate sources file
    # XXX multisources
    sources = {'system': {}}
    sources['system']['db-encoding'] = 'UTF8' # XXX
    sources['system']['db-name'] = dbname
    sources['system']['db-host'] = None
    sources['system']['db-user'] = tmpdbuser
    sources['system']['db-password'] = None
    generate_sources_file(applid, join(testapplhome, 'sources'), sources)
##     # create postgres password file so we won't need anymore passwords
##     # XXX may exist!
##     pgpassfile = expanduser('~/.pgpass')
##     pgpass = open(pgpassfile, 'w')
##     if dbpasswd:
##         pgpass.write('%s:*:%s:%s:%s\n' % (dbhost or applhost or 'localhost',
##                                           dbname, dbuser, dbpasswd))
##     if tmpdbpasswd:
##         pgpass.write('%s:*:%s:%s:%s\n' % (tmpdbhost or 'localhost', dbname,
##                                           tmpdbuser, tmpdbpasswd))
##     pgpass.close()
##     chmod(pgpassfile, 0600)
    # dump db
##     dumpcmd = 'pg_dump -Fc -U %s -f /tmp/%s.dump %s' % (
##         dbuser, dbname, dbname)
##     if dbhost:
##         dumpcmd += ' -h %s' % dbhost
    dumpfile = '/tmp/%s.dump' % applid
    dumpcmd = 'cubicweb-ctl db-dump --output=%s %s' % (dumpfile, applid)
    if sudo:
        dumpcmd = 'sudo %s' % dumpcmd
    if applhost:
        dumpcmd = 'ssh %s "%s"' % (applhost, dumpcmd)
    if system(dumpcmd):
        raise Exception('error while dumping the database')
##     if not dbhost and applhost:
    if applhost:
        # retrieve the dump
        if system('scp %s:%s %s' % (applhost, dumpfile, dumpfile)):
            raise Exception('error while retreiving the dump')
    # move the dump into the chroot
    system('mv %s %s%s' % (dumpfile, chrootpath, dumpfile))
    # locate installed versions
    vcconf = read_config(join(testapplhome, 'vc.conf'))
    template = vcconf['TEMPLATE']
    cubicwebversion = vcconf['CW']
    templversion = vcconf['TEMPLATE_VERSION']
    # install the same versions cubicweb and template versions into the chroot
    system('sudo chroot %s apt-get update' % chrootpath)
    system('sudo chroot %s apt-get install cubicweb-server=%s cubicweb-client=%s'
           % (chrootpath, cubicwebversion, cubicwebversion))
    system('sudo chroot %s apt-get install cubicweb-%s-appl-server=%s cubicweb-%s-appl-client=%s'
           % (chrootpath, template, templversion, template, templversion))
    # update and upgrade to the latest version
    system('sudo chroot %s apt-get install cubicweb-server cubicweb-client' % chrootpath)
    system('sudo chroot %s apt-get install cubicweb-%s-appl-server cubicweb-%s-appl-client'
           % (chrootpath, template, template))
    # create and fill the database
    system('sudo chroot cubicweb-ctl db-restore %s %s' % (applid, dumpfile))
##     if not tmpdbhost:
##         system('createdb -U %s -T template0 -E UTF8 %s' % (tmpdbuser, dbname))
##         system('pg_restore -U %s -O -Fc -d %s /tmp/%s.dump'
##                % (tmpdbuser, dbname, dbname))
##     else:
##         system('createdb -h %s -U %s -T template0 -E UTF8 %s'
##                % (tmpdbhost, tmpdbuser, dbname))
##         system('pg_restore -h %s -U %s -O -Fc -d %s /tmp/%s.dump'
##                % (tmpdbhost, tmpdbuser, dbname, dbname))
    # launch upgrade
    system('sudo chroot %s cubicweb-ctl upgrade %s' % (chrootpath, applid))

    # cleanup
    rm(testapplhome)
##     rm(pgpassfile)
##     if tmpdbhost:
##         system('dropdb -h %s -U %s %s' % (tmpdbuser, tmpdbhost, dbname))
##     else:
##         system('dropdb -U %s %s' % (tmpdbuser, dbname))
##     if not dbhost and applhost:
    if applhost:
        system('ssh %s rm %s' % (applhost, dumpfile))
    rm('%s%s' % (chrootpath, dumpfile))


if __name__ == '__main__':
    play_migration('/etc/cubicweb.d/jpl', 'lepus')
