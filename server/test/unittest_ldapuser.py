# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import socket

from logilab.common.testlib import TestCase, unittest_main, mock_object
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.repotest import RQLGeneratorTC

from cubicweb.server.sources.ldapuser import *

if '17.1' in socket.gethostbyname('ldap1'):
    SYT = 'syt'
    SYT_EMAIL = 'Sylvain Thenault'
    ADIM = 'adim'
    CONFIG = u'''host=ldap1
user-base-dn=ou=People,dc=logilab,dc=fr
user-scope=ONELEVEL
user-classes=top,posixAccount
user-login-attr=uid
user-default-group=users
user-attrs-map=gecos:email,uid:login
'''
else:
    SYT = 'sthenault'
    SYT_EMAIL = 'sylvain.thenault@logilab.fr'
    ADIM = 'adimascio'
    CONFIG = u'''host=ldap1
user-base-dn=ou=People,dc=logilab,dc=net
user-scope=ONELEVEL
user-classes=top,OpenLDAPperson
user-login-attr=uid
user-default-group=users
user-attrs-map=mail:email,uid:login
'''


def nopwd_authenticate(self, session, login, password):
    """used to monkey patch the source to get successful authentication without
    upassword checking
    """
    assert login, 'no login!'
    searchfilter = [filter_format('(%s=%s)', (self.user_login_attr, login))]
    searchfilter.extend([filter_format('(%s=%s)', ('objectClass', o))
                         for o in self.user_classes])
    searchstr = '(&%s)' % ''.join(searchfilter)
    # first search the user
    try:
        user = self._search(session, self.user_base_dn, self.user_base_scope,
                            searchstr)[0]
    except IndexError:
        # no such user
        raise AuthenticationError()
    # don't check upassword !
    return self.extid2eid(user['dn'], 'CWUser', session)

def setUpModule(*args):
    global repo
    LDAPUserSourceTC._init_repo()
    repo = LDAPUserSourceTC.repo
    add_ldap_source(LDAPUserSourceTC.cnx)

def tearDownModule(*args):
    global repo
    repo.shutdown()
    del repo

def add_ldap_source(cnx):
    cnx.request().create_entity('CWSource', name=u'ldapuser', type=u'ldapuser',
                                config=CONFIG)
    cnx.commit()
    # XXX: need this first query else we get 'database is locked' from
    # sqlite since it doesn't support multiple connections on the same
    # database
    # so doing, ldap inserted users don't get removed between each test
    rset = cnx.cursor().execute('CWUser X')
    # check we get some users from ldap
    assert len(rset) > 1


class LDAPUserSourceTC(CubicWebTC):

    def patch_authenticate(self):
        self._orig_authenticate = LDAPUserSource.authenticate
        LDAPUserSource.authenticate = nopwd_authenticate

    def tearDown(self):
        if hasattr(self, '_orig_authenticate'):
            LDAPUserSource.authenticate = self._orig_authenticate
        CubicWebTC.tearDown(self)

    def test_authenticate(self):
        source = self.repo.sources_by_uri['ldapuser']
        self.session.set_pool()
        self.assertRaises(AuthenticationError,
                          source.authenticate, self.session, 'toto', 'toto')

    def test_synchronize(self):
        source = self.repo.sources_by_uri['ldapuser']
        source.synchronize()

    def test_base(self):
        # check a known one
        e = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT}).get_entity(0, 0)
        self.assertEqual(e.login, SYT)
        e.complete()
        self.assertEqual(e.creation_date, None)
        self.assertEqual(e.modification_date, None)
        self.assertEqual(e.firstname, None)
        self.assertEqual(e.surname, None)
        self.assertEqual(e.in_group[0].name, 'users')
        self.assertEqual(e.owned_by[0].login, SYT)
        self.assertEqual(e.created_by, ())
        self.assertEqual(e.primary_email[0].address, SYT_EMAIL)
        # email content should be indexed on the user
        rset = self.sexecute('CWUser X WHERE X has_text "thenault"')
        self.assertEqual(rset.rows, [[e.eid]])

    def test_not(self):
        eid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT})[0][0]
        rset = self.sexecute('CWUser X WHERE NOT X eid %s' % eid)
        self.assert_(rset)
        self.assert_(not eid in (r[0] for r in rset))

    def test_multiple(self):
        seid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT})[0][0]
        aeid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': ADIM})[0][0]
        rset = self.sexecute('CWUser X, Y WHERE X login %(syt)s, Y login %(adim)s',
                            {'syt': SYT, 'adim': ADIM})
        self.assertEqual(rset.rows, [[seid, aeid]])
        rset = self.sexecute('Any X,Y,L WHERE X login L, X login %(syt)s, Y login %(adim)s',
                            {'syt': SYT, 'adim': ADIM})
        self.assertEqual(rset.rows, [[seid, aeid, SYT]])

    def test_in(self):
        seid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT})[0][0]
        aeid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': ADIM})[0][0]
        rset = self.sexecute('Any X,L ORDERBY L WHERE X login IN("%s", "%s"), X login L' % (SYT, ADIM))
        self.assertEqual(rset.rows, [[aeid, ADIM], [seid, SYT]])

    def test_relations(self):
        eid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT})[0][0]
        rset = self.sexecute('Any X,E WHERE X is CWUser, X login L, X primary_email E')
        self.assert_(eid in (r[0] for r in rset))
        rset = self.sexecute('Any X,L,E WHERE X is CWUser, X login L, X primary_email E')
        self.assert_(SYT in (r[1] for r in rset))

    def test_count(self):
        nbusers = self.sexecute('Any COUNT(X) WHERE X is CWUser')[0][0]
        # just check this is a possible number
        self.assert_(nbusers > 1, nbusers)
        self.assert_(nbusers < 30, nbusers)

    def test_upper(self):
        eid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT})[0][0]
        rset = self.sexecute('Any UPPER(L) WHERE X eid %s, X login L' % eid)
        self.assertEqual(rset[0][0], SYT.upper())

    def test_unknown_attr(self):
        eid = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT})[0][0]
        rset = self.sexecute('Any L,C,M WHERE X eid %s, X login L, '
                            'X creation_date C, X modification_date M' % eid)
        self.assertEqual(rset[0][0], SYT)
        self.assertEqual(rset[0][1], None)
        self.assertEqual(rset[0][2], None)

    def test_sort(self):
        logins = [l for l, in self.sexecute('Any L ORDERBY L WHERE X login L')]
        self.assertEqual(logins, sorted(logins))

    def test_lower_sort(self):
        logins = [l for l, in self.sexecute('Any L ORDERBY lower(L) WHERE X login L')]
        self.assertEqual(logins, sorted(logins))

    def test_or(self):
        rset = self.sexecute('DISTINCT Any X WHERE X login %(login)s OR (X in_group G, G name "managers")',
                            {'login': SYT})
        self.assertEqual(len(rset), 2, rset.rows) # syt + admin

    def test_nonregr_set_owned_by(self):
        # test that when a user coming from ldap is triggering a transition
        # the related TrInfo has correct owner information
        self.sexecute('SET X in_group G WHERE X login %(syt)s, G name "managers"', {'syt': SYT})
        self.commit()
        syt = self.sexecute('CWUser X WHERE X login %(login)s', {'login': SYT}).get_entity(0, 0)
        self.assertEqual([g.name for g in syt.in_group], ['managers', 'users'])
        self.patch_authenticate()
        cnx = self.login(SYT, password='dummypassword')
        cu = cnx.cursor()
        adim = cu.execute('CWUser X WHERE X login %(login)s', {'login': ADIM}).get_entity(0, 0)
        iworkflowable = adim.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate')
        try:
            cnx.commit()
            adim.clear_all_caches()
            self.assertEqual(adim.in_state[0].name, 'deactivated')
            trinfo = iworkflowable.latest_trinfo()
            self.assertEqual(trinfo.owned_by[0].login, SYT)
            # select from_state to skip the user's creation TrInfo
            rset = self.sexecute('Any U ORDERBY D DESC WHERE WF wf_info_for X,'
                                'WF creation_date D, WF from_state FS,'
                                'WF owned_by U?, X eid %(x)s',
                                {'x': adim.eid})
            self.assertEqual(rset.rows, [[syt.eid]])
        finally:
            # restore db state
            self.restore_connection()
            adim = self.sexecute('CWUser X WHERE X login %(login)s', {'login': ADIM}).get_entity(0, 0)
            adim.cw_adapt_to('IWorkflowable').fire_transition('activate')
            self.sexecute('DELETE X in_group G WHERE X login %(syt)s, G name "managers"', {'syt': SYT})

    def test_same_column_names(self):
        self.sexecute('Any X, Y WHERE X copain Y, X login "comme", Y login "cochon"')

    def test_multiple_entities_from_different_sources(self):
        self.create_user('cochon')
        self.failUnless(self.sexecute('Any X,Y WHERE X login %(syt)s, Y login "cochon"', {'syt': SYT}))

    def test_exists1(self):
        self.session.set_pool()
        self.session.create_entity('CWGroup', name=u'bougloup1')
        self.session.create_entity('CWGroup', name=u'bougloup2')
        self.sexecute('SET U in_group G WHERE G name ~= "bougloup%", U login "admin"')
        self.sexecute('SET U in_group G WHERE G name = "bougloup1", U login %(syt)s', {'syt': SYT})
        rset = self.sexecute('Any L,SN ORDERBY L WHERE X in_state S, S name SN, X login L, EXISTS(X in_group G, G name ~= "bougloup%")')
        self.assertEqual(rset.rows, [['admin', 'activated'], [SYT, 'activated']])

    def test_exists2(self):
        self.create_user('comme')
        self.create_user('cochon')
        self.sexecute('SET X copain Y WHERE X login "comme", Y login "cochon"')
        rset = self.sexecute('Any GN ORDERBY GN WHERE X in_group G, G name GN, (G name "managers" OR EXISTS(X copain T, T login in ("comme", "cochon")))')
        self.assertEqual(rset.rows, [['managers'], ['users']])

    def test_exists3(self):
        self.create_user('comme')
        self.create_user('cochon')
        self.sexecute('SET X copain Y WHERE X login "comme", Y login "cochon"')
        self.failUnless(self.sexecute('Any X, Y WHERE X copain Y, X login "comme", Y login "cochon"'))
        self.sexecute('SET X copain Y WHERE X login %(syt)s, Y login "cochon"', {'syt': SYT})
        self.failUnless(self.sexecute('Any X, Y WHERE X copain Y, X login %(syt)s, Y login "cochon"', {'syt': SYT}))
        rset = self.sexecute('Any GN,L WHERE X in_group G, X login L, G name GN, G name "managers" OR EXISTS(X copain T, T login in ("comme", "cochon"))')
        self.assertEqual(sorted(rset.rows), [['managers', 'admin'], ['users', 'comme'], ['users', SYT]])

    def test_exists4(self):
        self.create_user('comme')
        self.create_user('cochon', groups=('users', 'guests'))
        self.create_user('billy')
        self.sexecute('SET X copain Y WHERE X login "comme", Y login "cochon"')
        self.sexecute('SET X copain Y WHERE X login "cochon", Y login "cochon"')
        self.sexecute('SET X copain Y WHERE X login "comme", Y login "billy"')
        self.sexecute('SET X copain Y WHERE X login %(syt)s, Y login "billy"', {'syt': SYT})
        # search for group name, login where
        #   CWUser copain with "comme" or "cochon" AND same login as the copain
        # OR
        #   CWUser in_state activated AND not copain with billy
        #
        # SO we expect everybody but "comme" and "syt"
        rset= self.sexecute('Any GN,L WHERE X in_group G, X login L, G name GN, '
                           'EXISTS(X copain T, T login L, T login in ("comme", "cochon")) OR '
                           'EXISTS(X in_state S, S name "activated", NOT X copain T2, T2 login "billy")')
        all = self.sexecute('Any GN, L WHERE X in_group G, X login L, G name GN')
        all.rows.remove(['users', 'comme'])
        all.rows.remove(['users', SYT])
        self.assertEqual(sorted(rset.rows), sorted(all.rows))

    def test_exists5(self):
        self.create_user('comme')
        self.create_user('cochon', groups=('users', 'guests'))
        self.create_user('billy')
        self.sexecute('SET X copain Y WHERE X login "comme", Y login "cochon"')
        self.sexecute('SET X copain Y WHERE X login "cochon", Y login "cochon"')
        self.sexecute('SET X copain Y WHERE X login "comme", Y login "billy"')
        self.sexecute('SET X copain Y WHERE X login %(syt)s, Y login "cochon"', {'syt': SYT})
        rset= self.sexecute('Any L WHERE X login L, '
                           'EXISTS(X copain T, T login in ("comme", "cochon")) AND '
                           'NOT EXISTS(X copain T2, T2 login "billy")')
        self.assertEqual(sorted(rset.rows), [['cochon'], [SYT]])
        rset= self.sexecute('Any GN,L WHERE X in_group G, X login L, G name GN, '
                           'EXISTS(X copain T, T login in ("comme", "cochon")) AND '
                           'NOT EXISTS(X copain T2, T2 login "billy")')
        self.assertEqual(sorted(rset.rows), [['guests', 'cochon'],
                                              ['users', 'cochon'],
                                              ['users', SYT]])

    def test_cd_restriction(self):
        rset = self.sexecute('CWUser X WHERE X creation_date > "2009-02-01"')
        # admin/anon but no ldap user since it doesn't support creation_date
        self.assertEqual(sorted(e.login for e in rset.entities()),
                          ['admin', 'anon'])

    def test_union(self):
        afeids = self.sexecute('State X')
        ueids = self.sexecute('CWUser X')
        rset = self.sexecute('(Any X WHERE X is State) UNION (Any X WHERE X is CWUser)')
        self.assertEqual(sorted(r[0] for r in rset.rows),
                          sorted(r[0] for r in afeids + ueids))

    def _init_security_test(self):
        self.create_user('iaminguestsgrouponly', groups=('guests',))
        cnx = self.login('iaminguestsgrouponly')
        return cnx.cursor()

    def test_security1(self):
        cu = self._init_security_test()
        rset = cu.execute('CWUser X WHERE X login %(login)s', {'login': SYT})
        self.assertEqual(rset.rows, [])
        rset = cu.execute('Any X WHERE X login "iaminguestsgrouponly"')
        self.assertEqual(len(rset.rows), 1)

    def test_security2(self):
        cu = self._init_security_test()
        rset = cu.execute('Any X WHERE X has_text %(syt)s', {'syt': SYT})
        self.assertEqual(rset.rows, [])
        rset = cu.execute('Any X WHERE X has_text "iaminguestsgrouponly"')
        self.assertEqual(len(rset.rows), 1)

    def test_security3(self):
        cu = self._init_security_test()
        rset = cu.execute('Any F WHERE X has_text %(syt)s, X firstname F', {'syt': SYT})
        self.assertEqual(rset.rows, [])
        rset = cu.execute('Any F WHERE X has_text "iaminguestsgrouponly", X firstname F')
        self.assertEqual(rset.rows, [[None]])

    def test_nonregr1(self):
        self.sexecute('Any X,AA ORDERBY AA DESC WHERE E eid %(x)s, E owned_by X, '
                     'X modification_date AA',
                     {'x': self.session.user.eid})

    def test_nonregr2(self):
        self.sexecute('Any X,L,AA WHERE E eid %(x)s, E owned_by X, '
                     'X login L, X modification_date AA',
                     {'x': self.session.user.eid})

    def test_nonregr3(self):
        self.sexecute('Any X,AA ORDERBY AA DESC WHERE E eid %(x)s, '
                     'X modification_date AA',
                     {'x': self.session.user.eid})

    def test_nonregr4(self):
        emaileid = self.sexecute('INSERT EmailAddress X: X address "toto@logilab.org"')[0][0]
        self.sexecute('Any X,AA WHERE X use_email Y, Y eid %(x)s, X modification_date AA',
                     {'x': emaileid})

    def test_nonregr5(self):
        # original jpl query:
        # Any X, NOW - CD, P WHERE P is Project, U interested_in P, U is CWUser, U login "sthenault", X concerns P, X creation_date CD ORDERBY CD DESC LIMIT 5
        rql = 'Any X, NOW - CD, P ORDERBY CD DESC LIMIT 5 WHERE P bookmarked_by U, U login "%s", P is X, X creation_date CD' % self.session.user.login
        self.sexecute(rql, )#{'x': })

    def test_nonregr6(self):
        self.sexecute('Any B,U,UL GROUPBY B,U,UL WHERE B created_by U?, B is File '
                     'WITH U,UL BEING (Any U,UL WHERE ME eid %(x)s, (EXISTS(U identity ME) '
                     'OR (EXISTS(U in_group G, G name IN("managers", "staff")))) '
                     'OR (EXISTS(U in_group H, ME in_group H, NOT H name "users")), U login UL, U is CWUser)',
                     {'x': self.session.user.eid})


class GlobTrFuncTC(TestCase):

    def test_count(self):
        trfunc = GlobTrFunc('count', 0)
        res = trfunc.apply([[1], [2], [3], [4]])
        self.assertEqual(res, [[4]])
        trfunc = GlobTrFunc('count', 1)
        res = trfunc.apply([[1, 2], [2, 4], [3, 6], [1, 5]])
        self.assertEqual(res, [[1, 2], [2, 1], [3, 1]])

    def test_sum(self):
        trfunc = GlobTrFunc('sum', 0)
        res = trfunc.apply([[1], [2], [3], [4]])
        self.assertEqual(res, [[10]])
        trfunc = GlobTrFunc('sum', 1)
        res = trfunc.apply([[1, 2], [2, 4], [3, 6], [1, 5]])
        self.assertEqual(res, [[1, 7], [2, 4], [3, 6]])

    def test_min(self):
        trfunc = GlobTrFunc('min', 0)
        res = trfunc.apply([[1], [2], [3], [4]])
        self.assertEqual(res, [[1]])
        trfunc = GlobTrFunc('min', 1)
        res = trfunc.apply([[1, 2], [2, 4], [3, 6], [1, 5]])
        self.assertEqual(res, [[1, 2], [2, 4], [3, 6]])

    def test_max(self):
        trfunc = GlobTrFunc('max', 0)
        res = trfunc.apply([[1], [2], [3], [4]])
        self.assertEqual(res, [[4]])
        trfunc = GlobTrFunc('max', 1)
        res = trfunc.apply([[1, 2], [2, 4], [3, 6], [1, 5]])
        self.assertEqual(res, [[1, 5], [2, 4], [3, 6]])

class RQL2LDAPFilterTC(RQLGeneratorTC):

    def setUp(self):
        self.schema = repo.schema
        RQLGeneratorTC.setUp(self)
        ldapsource = repo.sources[-1]
        self.pool = repo._get_pool()
        session = mock_object(pool=self.pool)
        self.o = RQL2LDAPFilter(ldapsource, session)
        self.ldapclasses = ''.join('(objectClass=%s)' % ldapcls
                                   for ldapcls in ldapsource.user_classes)

    def tearDown(self):
        repo._free_pool(self.pool)
        RQLGeneratorTC.tearDown(self)

    def test_base(self):
        rqlst = self._prepare('CWUser X WHERE X login "toto"').children[0]
        self.assertEqual(self.o.generate(rqlst, 'X')[1],
                          '(&%s(uid=toto))' % self.ldapclasses)

    def test_kwargs(self):
        rqlst = self._prepare('CWUser X WHERE X login %(x)s').children[0]
        self.o._args = {'x': "toto"}
        self.assertEqual(self.o.generate(rqlst, 'X')[1],
                          '(&%s(uid=toto))' % self.ldapclasses)

    def test_get_attr(self):
        rqlst = self._prepare('Any X WHERE E firstname X, E eid 12').children[0]
        self.assertRaises(UnknownEid, self.o.generate, rqlst, 'E')


if __name__ == '__main__':
    unittest_main()
