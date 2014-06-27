# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""cubicweb.server.sources.ldapusers unit and functional tests"""

import os
import sys
import shutil
import time
from os.path import join, exists
import subprocess
import tempfile

from logilab.common.testlib import TestCase, unittest_main, mock_object, Tags

from cubicweb import AuthenticationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.repotest import RQLGeneratorTC
from cubicweb.devtools.httptest import get_available_port


CONFIG_LDAPFEED = u'''
user-base-dn=ou=People,dc=cubicweb,dc=test
group-base-dn=ou=Group,dc=cubicweb,dc=test
user-attrs-map=uid=login,mail=email,userPassword=upassword
group-attrs-map=cn=name,memberUid=member
'''
CONFIG_LDAPUSER = u'''
user-base-dn=ou=People,dc=cubicweb,dc=test
user-attrs-map=uid=login,mail=email,userPassword=upassword
'''

URL = None

def create_slapd_configuration(cls):
    global URL
    slapddir = tempfile.mkdtemp('cw-unittest-ldap')
    config = cls.config
    slapdconf = join(config.apphome, "slapd.conf")
    confin = file(join(config.apphome, "slapd.conf.in")).read()
    confstream = file(slapdconf, 'w')
    confstream.write(confin % {'apphome': config.apphome, 'testdir': slapddir})
    confstream.close()
    # fill ldap server with some data
    ldiffile = join(config.apphome, "ldap_test.ldif")
    config.info('Initing ldap database')
    cmdline = ['/usr/sbin/slapadd', '-f', slapdconf, '-l', ldiffile, '-c']
    PIPE = subprocess.PIPE
    slapproc = subprocess.Popen(cmdline, stdout=PIPE, stderr=PIPE)
    stdout, stderr = slapproc.communicate()
    if slapproc.returncode:
        print >> sys.stderr, ('slapadd returned with status: %s'
                              % slapproc.returncode)
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)

    #ldapuri = 'ldapi://' + join(basedir, "ldapi").replace('/', '%2f')
    port = get_available_port(xrange(9000, 9100))
    host = 'localhost:%s' % port
    ldapuri = 'ldap://%s' % host
    cmdline = ["/usr/sbin/slapd", "-f",  slapdconf,  "-h",  ldapuri, "-d", "0"]
    config.info('Starting slapd:', ' '.join(cmdline))
    PIPE = subprocess.PIPE
    cls.slapd_process = subprocess.Popen(cmdline, stdout=PIPE, stderr=PIPE)
    time.sleep(0.2)
    if cls.slapd_process.poll() is None:
        config.info('slapd started with pid %s', cls.slapd_process.pid)
    else:
        raise EnvironmentError('Cannot start slapd with cmdline="%s" (from directory "%s")' %
                               (" ".join(cmdline), os.getcwd()))
    URL = u'ldap://%s' % host
    return slapddir

def terminate_slapd(cls):
    config = cls.config
    if cls.slapd_process and cls.slapd_process.returncode is None:
        config.info('terminating slapd')
        if hasattr(cls.slapd_process, 'terminate'):
            cls.slapd_process.terminate()
        else:
            import os, signal
            os.kill(cls.slapd_process.pid, signal.SIGTERM)
        stdout, stderr = cls.slapd_process.communicate()
        if cls.slapd_process.returncode:
            print >> sys.stderr, ('slapd returned with status: %s'
                                  % cls.slapd_process.returncode)
            sys.stdout.write(stdout)
            sys.stderr.write(stderr)
        config.info('DONE')


class LDAPFeedTestBase(CubicWebTC):
    test_db_id = 'ldap-feed'
    loglevel = 'ERROR'

    @classmethod
    def setUpClass(cls):
        from cubicweb.cwctl import init_cmdline_log_threshold
        init_cmdline_log_threshold(cls.config, cls.loglevel)
        cls._tmpdir = create_slapd_configuration(cls)

    @classmethod
    def tearDownClass(cls):
        terminate_slapd(cls)
        try:
            shutil.rmtree(cls._tmpdir)
        except:
            pass

    @classmethod
    def pre_setup_database(cls, cnx, config):
        cnx.create_entity('CWSource', name=u'ldap', type=u'ldapfeed', parser=u'ldapfeed',
                          url=URL, config=CONFIG_LDAPFEED)

        cnx.commit()
        return cls.pull(cnx)

    @classmethod
    def pull(self, cnx):
        lfsource = cnx.repo.sources_by_uri['ldap']
        stats = lfsource.pull_data(cnx, force=True, raise_on_error=True)
        cnx.commit()
        return stats

    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('DELETE Any E WHERE E cw_source S, S name "ldap"')
            cnx.execute('SET S config %(conf)s, S url %(url)s '
                        'WHERE S is CWSource, S name "ldap"',
                        {"conf": CONFIG_LDAPFEED, 'url': URL} )
            cnx.commit()
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx)

    def add_ldap_entry(self, dn, mods):
        """
        add an LDAP entity
        """
        modcmd = ['dn: %s'%dn, 'changetype: add']
        for key, values in mods.iteritems():
            if isinstance(values, basestring):
                values = [values]
            for value in values:
                modcmd.append('%s: %s'%(key, value))
        self._ldapmodify(modcmd)

    def delete_ldap_entry(self, dn):
        """
        delete an LDAP entity
        """
        modcmd = ['dn: %s'%dn, 'changetype: delete']
        self._ldapmodify(modcmd)

    def update_ldap_entry(self, dn, mods):
        """
        modify one or more attributes of an LDAP entity
        """
        modcmd = ['dn: %s'%dn, 'changetype: modify']
        for (kind, key), values in mods.iteritems():
            modcmd.append('%s: %s' % (kind, key))
            if isinstance(values, basestring):
                values = [values]
            for value in values:
                modcmd.append('%s: %s'%(key, value))
            modcmd.append('-')
        self._ldapmodify(modcmd)

    def _ldapmodify(self, modcmd):
        uri = self.repo.sources_by_uri['ldap'].urls[0]
        updatecmd = ['ldapmodify', '-H', uri, '-v', '-x', '-D',
                     'cn=admin,dc=cubicweb,dc=test', '-w', 'cw']
        PIPE = subprocess.PIPE
        p = subprocess.Popen(updatecmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        p.stdin.write('\n'.join(modcmd))
        p.stdin.close()
        if p.wait():
            raise RuntimeError("ldap update failed: %s"%('\n'.join(p.stderr.readlines())))

class CheckWrongGroup(LDAPFeedTestBase):
    """
    A testcase for situations where the default group for CWUser
    created from LDAP is wrongly configured.
    """

    def test_wrong_group(self):
        with self.admin_access.repo_cnx() as cnx:
            source = cnx.execute('CWSource S WHERE S type="ldapfeed"').get_entity(0,0)
            config = source.repo_source.check_config(source)
            # inject a bogus group here, along with at least a valid one
            config['user-default-group'] = ('thisgroupdoesnotexists','users')
            source.repo_source.update_config(source, config)
            cnx.commit()
            # here we emitted an error log entry
            stats = source.repo_source.pull_data(cnx, force=True, raise_on_error=True)
            cnx.commit()



class LDAPFeedUserTC(LDAPFeedTestBase):
    """
    A testcase for CWUser support in ldapfeed (basic tests and authentication).
    """

    def assertMetadata(self, entity):
        self.assertTrue(entity.creation_date)
        self.assertTrue(entity.modification_date)

    def test_authenticate(self):
        source = self.repo.sources_by_uri['ldap']
        with self.admin_access.repo_cnx() as cnx:
            # ensure we won't be logged against
            self.assertRaises(AuthenticationError,
                              source.authenticate, cnx, 'toto', 'toto')
            self.assertTrue(source.authenticate(cnx, 'syt', 'syt'))
        sessionid = self.repo.connect('syt', password='syt')
        self.assertTrue(sessionid)
        self.repo.close(sessionid)

    def test_base(self):
        with self.admin_access.repo_cnx() as cnx:
            # check a known one
            rset = cnx.execute('CWUser X WHERE X login %(login)s', {'login': 'syt'})
            e = rset.get_entity(0, 0)
            self.assertEqual(e.login, 'syt')
            e.complete()
            self.assertMetadata(e)
            self.assertEqual(e.firstname, None)
            self.assertEqual(e.surname, None)
            self.assertIn('users', set(g.name for g in e.in_group))
            self.assertEqual(e.owned_by[0].login, 'syt')
            self.assertEqual(e.created_by, ())
            addresses = [pe.address for pe in e.use_email]
            addresses.sort()
            self.assertEqual(['sylvain.thenault@logilab.fr', 'syt@logilab.fr'],
                             addresses)
            self.assertIn(e.primary_email[0].address, ['sylvain.thenault@logilab.fr',
                                                       'syt@logilab.fr'])
            # email content should be indexed on the user
            rset = cnx.execute('CWUser X WHERE X has_text "thenault"')
            self.assertEqual(rset.rows, [[e.eid]])

    def test_copy_to_system_source(self):
        "make sure we can 'convert' an LDAP user into a system one"
        with self.admin_access.repo_cnx() as cnx:
            source = self.repo.sources_by_uri['ldap']
            eid = cnx.execute('CWUser X WHERE X login %(login)s', {'login': 'syt'})[0][0]
            cnx.execute('SET X cw_source S WHERE X eid %(x)s, S name "system"', {'x': eid})
            cnx.commit()
            source.reset_caches()
            rset = cnx.execute('CWUser X WHERE X login %(login)s', {'login': 'syt'})
            self.assertEqual(len(rset), 1)
            e = rset.get_entity(0, 0)
            self.assertEqual(e.eid, eid)
            self.assertEqual(e.cw_metainformation(), {'source': {'type': u'native',
                                                                 'uri': u'system',
                                                                 'use-cwuri-as-url': False},
                                                      'type': 'CWUser',
                                                      'extid': None})
            self.assertEqual(e.cw_source[0].name, 'system')
            self.assertTrue(e.creation_date)
            self.assertTrue(e.modification_date)
            source.pull_data(cnx)
            rset = cnx.execute('CWUser X WHERE X login %(login)s', {'login': 'syt'})
            self.assertEqual(len(rset), 1)
            self.assertTrue(self.repo.system_source.authenticate(cnx, 'syt', password='syt'))
            # make sure the pull from ldap have not "reverted" user as a ldap-feed user
            self.assertEqual(e.cw_metainformation(), {'source': {'type': u'native',
                                                                 'uri': u'system',
                                                                 'use-cwuri-as-url': False},
                                                      'type': 'CWUser',
                                                      'extid': None})
            # and that the password stored in the system source is not empty or so
            user = cnx.execute('CWUser U WHERE U login "syt"').get_entity(0, 0)
            user.cw_clear_all_caches()
            pwd = cnx.system_sql("SELECT cw_upassword FROM cw_cwuser WHERE cw_login='syt';").fetchall()[0][0]
            self.assertIsNotNone(pwd)
            self.assertTrue(str(pwd))



class LDAPFeedUserDeletionTC(LDAPFeedTestBase):
    """
    A testcase for situations where users are deleted from or
    unavailable in the LDAP database.
    """

    def test_a_filter_inactivate(self):
        """ filtered out people should be deactivated, unable to authenticate """
        with self.admin_access.repo_cnx() as cnx:
            source = cnx.execute('CWSource S WHERE S type="ldapfeed"').get_entity(0,0)
            config = source.repo_source.check_config(source)
            # filter with adim's phone number
            config['user-filter'] = u'(%s=%s)' % ('telephoneNumber', '109')
            source.repo_source.update_config(source, config)
            cnx.commit()
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx)
        self.assertRaises(AuthenticationError, self.repo.connect, 'syt', password='syt')
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.execute('Any N WHERE U login "syt", '
                                         'U in_state S, S name N').rows[0][0],
                             'deactivated')
            self.assertEqual(cnx.execute('Any N WHERE U login "adim", '
                                         'U in_state S, S name N').rows[0][0],
                             'activated')
            # unfilter, syt should be activated again
            config['user-filter'] = u''
            source.repo_source.update_config(source, config)
            cnx.commit()
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx)
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.execute('Any N WHERE U login "syt", '
                                         'U in_state S, S name N').rows[0][0],
                             'activated')
            self.assertEqual(cnx.execute('Any N WHERE U login "adim", '
                                         'U in_state S, S name N').rows[0][0],
                             'activated')

    def test_delete(self):
        """ delete syt, pull, check deactivation, repull,
        read syt, pull, check activation
        """
        self.delete_ldap_entry('uid=syt,ou=People,dc=cubicweb,dc=test')
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx)
        self.assertRaises(AuthenticationError, self.repo.connect, 'syt', password='syt')
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.execute('Any N WHERE U login "syt", '
                                         'U in_state S, S name N').rows[0][0],
                             'deactivated')
        with self.repo.internal_cnx() as cnx:
            # check that it doesn't choke
            self.pull(cnx)
        # reinsert syt
        self.add_ldap_entry('uid=syt,ou=People,dc=cubicweb,dc=test',
                            { 'objectClass': ['OpenLDAPperson','posixAccount','top','shadowAccount'],
                              'cn': 'Sylvain Thenault',
                              'sn': 'Thenault',
                              'gidNumber': '1004',
                              'uid': 'syt',
                              'homeDirectory': '/home/syt',
                              'shadowFlag': '134538764',
                              'uidNumber': '1004',
                              'givenName': 'Sylvain',
                              'telephoneNumber': '106',
                              'displayName': 'sthenault',
                              'gecos': 'Sylvain Thenault',
                              'mail': ['sylvain.thenault@logilab.fr','syt@logilab.fr'],
                              'userPassword': 'syt',
                          })
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx)
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(cnx.execute('Any N WHERE U login "syt", '
                                         'U in_state S, S name N').rows[0][0],
                             'activated')

    def test_reactivate_deleted(self):
        # test reactivating BY HAND the user isn't enough to
        # authenticate, as the native source refuse to authenticate
        # user from other sources
        self.delete_ldap_entry('uid=syt,ou=People,dc=cubicweb,dc=test')
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx)
        with self.admin_access.repo_cnx() as cnx:
            # reactivate user (which source is still ldap-feed)
            user = cnx.execute('CWUser U WHERE U login "syt"').get_entity(0, 0)
            user.cw_adapt_to('IWorkflowable').fire_transition('activate')
            cnx.commit()
            with self.assertRaises(AuthenticationError):
                self.repo.connect('syt', password='syt')

            # ok now let's try to make it a system user
            cnx.execute('SET X cw_source S WHERE X eid %(x)s, S name "system"', {'x': user.eid})
            cnx.commit()
        # and that we can now authenticate again
        self.assertRaises(AuthenticationError, self.repo.connect, 'syt', password='toto')
        sessionid = self.repo.connect('syt', password='syt')
        self.assertTrue(sessionid)
        self.repo.close(sessionid)


class LDAPFeedGroupTC(LDAPFeedTestBase):
    """
    A testcase for group support in ldapfeed.
    """

    def test_groups_exist(self):
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('CWGroup X WHERE X name "dir"')
            self.assertEqual(len(rset), 1)

            rset = cnx.execute('CWGroup X WHERE X cw_source S, S name "ldap"')
            self.assertEqual(len(rset), 2)

    def test_group_deleted(self):
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('CWGroup X WHERE X name "dir"')
            self.assertEqual(len(rset), 1)

    def test_in_group(self):
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('CWGroup X WHERE X name %(name)s', {'name': 'dir'})
            dirgroup = rset.get_entity(0, 0)
            self.assertEqual(set(['syt', 'adim']),
                             set([u.login for u in dirgroup.reverse_in_group]))
            rset = cnx.execute('CWGroup X WHERE X name %(name)s', {'name': 'logilab'})
            logilabgroup = rset.get_entity(0, 0)
            self.assertEqual(set(['adim']),
                             set([u.login for u in logilabgroup.reverse_in_group]))

    def test_group_member_added(self):
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx)
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('Any L WHERE U in_group G, G name %(name)s, U login L',
                               {'name': 'logilab'})
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset[0][0], 'adim')

        try:
            self.update_ldap_entry('cn=logilab,ou=Group,dc=cubicweb,dc=test',
                                       {('add', 'memberUid'): ['syt']})
            time.sleep(1.1) # timestamps precision is 1s
            with self.repo.internal_cnx() as cnx:
                self.pull(cnx)

            with self.admin_access.repo_cnx() as cnx:
                rset = cnx.execute('Any L WHERE U in_group G, G name %(name)s, U login L',
                                   {'name': 'logilab'})
                self.assertEqual(len(rset), 2)
                members = set([u[0] for u in rset])
                self.assertEqual(set(['adim', 'syt']), members)

        finally:
            # back to normal ldap setup
            self.tearDownClass()
            self.setUpClass()

    def test_group_member_deleted(self):
        with self.repo.internal_cnx() as cnx:
            self.pull(cnx) # ensure we are sync'ed
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('Any L WHERE U in_group G, G name %(name)s, U login L',
                               {'name': 'logilab'})
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset[0][0], 'adim')

        try:
            self.update_ldap_entry('cn=logilab,ou=Group,dc=cubicweb,dc=test',
                                   {('delete', 'memberUid'): ['adim']})
            time.sleep(1.1) # timestamps precision is 1s
            with self.repo.internal_cnx() as cnx:
                self.pull(cnx)

            with self.admin_access.repo_cnx() as cnx:
                rset = cnx.execute('Any L WHERE U in_group G, G name %(name)s, U login L',
                                   {'name': 'logilab'})
                self.assertEqual(len(rset), 0)
        finally:
            # back to normal ldap setup
            self.tearDownClass()
            self.setUpClass()



if __name__ == '__main__':
    unittest_main()
