"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from os.path import dirname, join, abspath
from datetime import datetime, timedelta

from logilab.common.decorators import cached

from cubicweb.devtools import TestServerConfiguration, init_test_database
from cubicweb.devtools.testlib import CubicWebTC, refresh_repo
from cubicweb.devtools.repotest import do_monkey_patch, undo_monkey_patch

TestServerConfiguration.no_sqlite_wrap = True

class TwoSourcesConfiguration(TestServerConfiguration):
    sourcefile = 'sources_multi'


class ExternalSource1Configuration(TestServerConfiguration):
    sourcefile = 'sources_extern'

class ExternalSource2Configuration(TestServerConfiguration):
    sourcefile = 'sources_multi2'

MTIME = datetime.now() - timedelta(0, 10)
repo2, cnx2 = init_test_database(config=ExternalSource1Configuration('data'))
repo3, cnx3 = init_test_database(config=ExternalSource2Configuration('data'))

# hi-jacking
from cubicweb.server.sources.pyrorql import PyroRQLSource
from cubicweb.dbapi import Connection

PyroRQLSource_get_connection = PyroRQLSource.get_connection
Connection_close = Connection.close

def setup_module(*args):
    # hi-jack PyroRQLSource.get_connection to access existing connection (no
    # pyro connection)
    PyroRQLSource.get_connection = lambda x: x.uri == 'extern-multi' and cnx3 or cnx2
    # also necessary since the repository is closing its initial connections
    # pool though we want to keep cnx2 valid
    Connection.close = lambda x: None

def teardown_module(*args):
    PyroRQLSource.get_connection = PyroRQLSource_get_connection
    Connection.close = Connection_close


class TwoSourcesTC(CubicWebTC):
    config = TwoSourcesConfiguration('data')

    @classmethod
    def _refresh_repo(cls):
        super(TwoSourcesTC, cls)._refresh_repo()
        cnx2.rollback()
        refresh_repo(repo2)
        cnx3.rollback()
        refresh_repo(repo3)

    def setUp(self):
        CubicWebTC.setUp(self)
        do_monkey_patch()

    def tearDown(self):
        CubicWebTC.tearDown(self)
        undo_monkey_patch()

    def setup_database(self):
        cu = cnx2.cursor()
        self.ec1 = cu.execute('INSERT Card X: X title "C3: An external card", X wikiid "aaa"')[0][0]
        cu.execute('INSERT Card X: X title "C4: Ze external card", X wikiid "zzz"')
        self.aff1 = cu.execute('INSERT Affaire X: X ref "AFFREF"')[0][0]
        cnx2.commit()
        # trigger discovery
        self.sexecute('Card X')
        self.sexecute('Affaire X')
        self.sexecute('State X')
        # add some entities
        self.ic1 = self.sexecute('INSERT Card X: X title "C1: An internal card", X wikiid "aaai"')[0][0]
        self.ic2 = self.sexecute('INSERT Card X: X title "C2: Ze internal card", X wikiid "zzzi"')[0][0]

    def test_eid_comp(self):
        rset = self.sexecute('Card X WHERE X eid > 1')
        self.assertEquals(len(rset), 4)
        rset = self.sexecute('Any X,T WHERE X title T, X eid > 1')
        self.assertEquals(len(rset), 4)

    def test_metainformation(self):
        rset = self.sexecute('Card X ORDERBY T WHERE X title T')
        # 2 added to the system source, 2 added to the external source
        self.assertEquals(len(rset), 4)
        # since they are orderd by eid, we know the 3 first one is coming from the system source
        # and the others from external source
        self.assertEquals(rset.get_entity(0, 0).metainformation(),
                          {'source': {'adapter': 'native', 'uri': 'system'},
                           'type': u'Card', 'extid': None})
        externent = rset.get_entity(3, 0)
        metainf = externent.metainformation()
        self.assertEquals(metainf['source'], {'adapter': 'pyrorql', 'base-url': 'http://extern.org/', 'uri': 'extern'})
        self.assertEquals(metainf['type'], 'Card')
        self.assert_(metainf['extid'])
        etype = self.sexecute('Any ETN WHERE X is ET, ET name ETN, X eid %(x)s',
                             {'x': externent.eid}, 'x')[0][0]
        self.assertEquals(etype, 'Card')

    def test_order_limit_offset(self):
        rsetbase = self.sexecute('Any W,X ORDERBY W,X WHERE X wikiid W')
        self.assertEquals(len(rsetbase), 4)
        self.assertEquals(sorted(rsetbase.rows), rsetbase.rows)
        rset = self.sexecute('Any W,X ORDERBY W,X LIMIT 2 OFFSET 2 WHERE X wikiid W')
        self.assertEquals(rset.rows, rsetbase.rows[2:4])

    def test_has_text(self):
        self.repo.sources_by_uri['extern'].synchronize(MTIME) # in case fti_update has been run before
        self.failUnless(self.sexecute('Any X WHERE X has_text "affref"'))
        self.failUnless(self.sexecute('Affaire X WHERE X has_text "affref"'))

    def test_anon_has_text(self):
        self.repo.sources_by_uri['extern'].synchronize(MTIME) # in case fti_update has been run before
        self.sexecute('INSERT Affaire X: X ref "no readable card"')[0][0]
        aff1 = self.sexecute('INSERT Affaire X: X ref "card"')[0][0]
        # grant read access
        self.sexecute('SET X owned_by U WHERE X eid %(x)s, U login "anon"', {'x': aff1}, 'x')
        self.commit()
        cnx = self.login('anon')
        cu = cnx.cursor()
        rset = cu.execute('Any X WHERE X has_text "card"')
        self.assertEquals(len(rset), 5, zip(rset.rows, rset.description))
        cnx.close()

    def test_synchronization(self):
        cu = cnx2.cursor()
        assert cu.execute('Any X WHERE X eid %(x)s', {'x': self.aff1}, 'x')
        cu.execute('SET X ref "BLAH" WHERE X eid %(x)s', {'x': self.aff1}, 'x')
        aff2 = cu.execute('INSERT Affaire X: X ref "AFFREUX"')[0][0]
        cnx2.commit()
        try:
            # force sync
            self.repo.sources_by_uri['extern'].synchronize(MTIME)
            self.failUnless(self.sexecute('Any X WHERE X has_text "blah"'))
            self.failUnless(self.sexecute('Any X WHERE X has_text "affreux"'))
            cu.execute('DELETE Affaire X WHERE X eid %(x)s', {'x': aff2})
            cnx2.commit()
            self.repo.sources_by_uri['extern'].synchronize(MTIME)
            rset = self.sexecute('Any X WHERE X has_text "affreux"')
            self.failIf(rset)
        finally:
            # restore state
            cu.execute('SET X ref "AFFREF" WHERE X eid %(x)s', {'x': self.aff1}, 'x')
            cnx2.commit()

    def test_simplifiable_var(self):
        affeid = self.sexecute('Affaire X WHERE X ref "AFFREF"')[0][0]
        rset = self.sexecute('Any X,AA,AB WHERE E eid %(x)s, E in_state X, X name AA, X modification_date AB',
                            {'x': affeid}, 'x')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset[0][1], "pitetre")

    def test_simplifiable_var_2(self):
        affeid = self.sexecute('Affaire X WHERE X ref "AFFREF"')[0][0]
        rset = self.sexecute('Any E WHERE E eid %(x)s, E in_state S, NOT S name "moved"',
                            {'x': affeid, 'u': self.session.user.eid}, 'x')
        self.assertEquals(len(rset), 1)

    def test_sort_func(self):
        self.sexecute('Affaire X ORDERBY DUMB_SORT(RF) WHERE X ref RF')

    def test_sort_func_ambigous(self):
        self.sexecute('Any X ORDERBY DUMB_SORT(RF) WHERE X title RF')

    def test_in_eid(self):
        iec1 = self.repo.extid2eid(self.repo.sources_by_uri['extern'], str(self.ec1),
                                   'Card', self.session)
        rset = self.sexecute('Any X WHERE X eid IN (%s, %s)' % (iec1, self.ic1))
        self.assertEquals(sorted(r[0] for r in rset.rows), sorted([iec1, self.ic1]))

    def test_greater_eid(self):
        rset = self.sexecute('Any X WHERE X eid > %s' % (self.ic1 - 1))
        self.assertEquals(len(rset.rows), 2) # self.ic1 and self.ic2
        cu = cnx2.cursor()
        ec2 = cu.execute('INSERT Card X: X title "glup"')[0][0]
        cnx2.commit()
        # 'X eid > something' should not trigger discovery
        rset = self.sexecute('Any X WHERE X eid > %s' % (self.ic1 - 1))
        self.assertEquals(len(rset.rows), 2)
        # trigger discovery using another query
        crset = self.sexecute('Card X WHERE X title "glup"')
        self.assertEquals(len(crset.rows), 1)
        rset = self.sexecute('Any X WHERE X eid > %s' % (self.ic1 - 1))
        self.assertEquals(len(rset.rows), 3)
        rset = self.sexecute('Any MAX(X)')
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(rset.rows[0][0], crset[0][0])

    def test_attr_unification_1(self):
        n1 = self.sexecute('INSERT Note X: X type "AFFREF"')[0][0]
        n2 = self.sexecute('INSERT Note X: X type "AFFREU"')[0][0]
        rset = self.sexecute('Any X,Y WHERE X is Note, Y is Affaire, X type T, Y ref T')
        self.assertEquals(len(rset), 1, rset.rows)

    def test_attr_unification_2(self):
        cu = cnx2.cursor()
        ec2 = cu.execute('INSERT Card X: X title "AFFREF"')[0][0]
        cnx2.commit()
        try:
            c1 = self.sexecute('INSERT Card C: C title "AFFREF"')[0][0]
            rset = self.sexecute('Any X,Y WHERE X is Card, Y is Affaire, X title T, Y ref T')
            self.assertEquals(len(rset), 2, rset.rows)
        finally:
            cu.execute('DELETE Card X WHERE X eid %(x)s', {'x': ec2}, 'x')
            cnx2.commit()

    def test_attr_unification_neq_1(self):
        # XXX complete
        self.sexecute('Any X,Y WHERE X is Note, Y is Affaire, X creation_date D, Y creation_date > D')

    def test_attr_unification_neq_2(self):
        # XXX complete
        self.sexecute('Any X,Y WHERE X is Card, Y is Affaire, X creation_date D, Y creation_date > D')

    def test_union(self):
        afeids = self.sexecute('Affaire X')
        ueids = self.sexecute('CWUser X')
        rset = self.sexecute('(Any X WHERE X is Affaire) UNION (Any X WHERE X is CWUser)')
        self.assertEquals(sorted(r[0] for r in rset.rows),
                          sorted(r[0] for r in afeids + ueids))

    def test_subquery1(self):
        rsetbase = self.sexecute('Any W,X WITH W,X BEING (Any W,X ORDERBY W,X WHERE X wikiid W)')
        self.assertEquals(len(rsetbase), 4)
        self.assertEquals(sorted(rsetbase.rows), rsetbase.rows)
        rset = self.sexecute('Any W,X LIMIT 2 OFFSET 2 WITH W,X BEING (Any W,X ORDERBY W,X WHERE X wikiid W)')
        self.assertEquals(rset.rows, rsetbase.rows[2:4])
        rset = self.sexecute('Any W,X ORDERBY W,X LIMIT 2 OFFSET 2 WITH W,X BEING (Any W,X WHERE X wikiid W)')
        self.assertEquals(rset.rows, rsetbase.rows[2:4])
        rset = self.sexecute('Any W,X WITH W,X BEING (Any W,X ORDERBY W,X LIMIT 2 OFFSET 2 WHERE X wikiid W)')
        self.assertEquals(rset.rows, rsetbase.rows[2:4])

    def test_subquery2(self):
        affeid = self.sexecute('Affaire X WHERE X ref "AFFREF"')[0][0]
        rset = self.sexecute('Any X,AA,AB WITH X,AA,AB BEING (Any X,AA,AB WHERE E eid %(x)s, E in_state X, X name AA, X modification_date AB)',
                            {'x': affeid})
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset[0][1], "pitetre")

    def test_not_relation(self):
        states = set(tuple(x) for x in self.sexecute('Any S,SN WHERE S is State, S name SN'))
        self.session.user.clear_all_caches()
        userstate = self.session.user.in_state[0]
        states.remove((userstate.eid, userstate.name))
        notstates = set(tuple(x) for x in self.sexecute('Any S,SN WHERE S is State, S name SN, NOT X in_state S, X eid %(x)s',
                                                       {'x': self.session.user.eid}, 'x'))
        self.assertSetEquals(notstates, states)
        aff1 = self.sexecute('Any X WHERE X is Affaire, X ref "AFFREF"')[0][0]
        aff1stateeid, aff1statename = self.sexecute('Any S,SN WHERE X eid %(x)s, X in_state S, S name SN', {'x': aff1}, 'x')[0]
        self.assertEquals(aff1statename, 'pitetre')
        states.add((userstate.eid, userstate.name))
        states.remove((aff1stateeid, aff1statename))
        notstates = set(tuple(x) for x in self.sexecute('Any S,SN WHERE S is State, S name SN, NOT X in_state S, X eid %(x)s',
                                                       {'x': aff1}, 'x'))
        self.assertSetEquals(notstates, states)

    def test_absolute_url_base_url(self):
        cu = cnx2.cursor()
        ceid = cu.execute('INSERT Card X: X title "without wikiid to get eid based url"')[0][0]
        cnx2.commit()
        lc = self.sexecute('Card X WHERE X title "without wikiid to get eid based url"').get_entity(0, 0)
        self.assertEquals(lc.absolute_url(), 'http://extern.org/card/eid/%s' % ceid)
        cu.execute('DELETE Card X WHERE X eid %(x)s', {'x':ceid})
        cnx2.commit()

    def test_absolute_url_no_base_url(self):
        cu = cnx3.cursor()
        ceid = cu.execute('INSERT Card X: X title "without wikiid to get eid based url"')[0][0]
        cnx3.commit()
        lc = self.sexecute('Card X WHERE X title "without wikiid to get eid based url"').get_entity(0, 0)
        self.assertEquals(lc.absolute_url(), 'http://testing.fr/cubicweb/card/eid/%s' % lc.eid)
        cu.execute('DELETE Card X WHERE X eid %(x)s', {'x':ceid})
        cnx3.commit()

    def test_nonregr1(self):
        ueid = self.session.user.eid
        affaire = self.sexecute('Affaire X WHERE X ref "AFFREF"').get_entity(0, 0)
        self.sexecute('Any U WHERE U in_group G, (G name IN ("managers", "logilab") OR (X require_permission P?, P name "bla", P require_group G)), X eid %(x)s, U eid %(u)s',
                     {'x': affaire.eid, 'u': ueid})

    def test_nonregr2(self):
        self.session.user.fire_transition('deactivate')
        treid = self.session.user.latest_trinfo().eid
        rset = self.sexecute('Any X ORDERBY D DESC WHERE E eid %(x)s, E wf_info_for X, X modification_date D',
                            {'x': treid})
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.rows[0], [self.session.user.eid])

    def test_nonregr3(self):
        self.sexecute('DELETE Card X WHERE X eid %(x)s, NOT X multisource_inlined_rel Y', {'x': self.ic1})

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
