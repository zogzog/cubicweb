# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from datetime import datetime, timedelta
from itertools import repeat

from cubicweb.devtools import TestServerConfiguration, init_test_database
from cubicweb.devtools.testlib import CubicWebTC, Tags
from cubicweb.devtools.repotest import do_monkey_patch, undo_monkey_patch
from cubicweb.devtools import get_test_db_handler

class ExternalSource1Configuration(TestServerConfiguration):
    sourcefile = 'sources_extern'

class ExternalSource2Configuration(TestServerConfiguration):
    sourcefile = 'sources_multi'

MTIME = datetime.utcnow() - timedelta(0, 10)

EXTERN_SOURCE_CFG = u'''
cubicweb-user = admin
cubicweb-password = gingkow
base-url=http://extern.org/
'''

# hi-jacking
from cubicweb.server.sources.pyrorql import PyroRQLSource
from cubicweb.dbapi import Connection

PyroRQLSource_get_connection = PyroRQLSource.get_connection
Connection_close = Connection.close

def add_extern_mapping(source):
    source.init_mapping(zip(('Card', 'Affaire', 'State',
                             'in_state', 'documented_by', 'multisource_inlined_rel'),
                            repeat(u'write')))


def pre_setup_database_extern(session, config):
    session.execute('INSERT Card X: X title "C3: An external card", X wikiid "aaa"')
    session.execute('INSERT Card X: X title "C4: Ze external card", X wikiid "zzz"')
    session.execute('INSERT Affaire X: X ref "AFFREF"')
    session.commit()

def pre_setup_database_multi(session, config):
    session.create_entity('CWSource', name=u'extern', type=u'pyrorql',
                          url=u'pyro:///extern', config=EXTERN_SOURCE_CFG)
    session.commit()


class TwoSourcesTC(CubicWebTC):
    """Main repo -> extern-multi -> extern
                  \-------------/
    """
    test_db_id= 'cw-server-multisources'
    tags = CubicWebTC.tags | Tags(('multisources'))

    @classmethod
    def setUpClass(cls):
        cls._cfg2 = ExternalSource1Configuration('data', apphome=TwoSourcesTC.datadir)
        cls._cfg3 = ExternalSource2Configuration('data', apphome=TwoSourcesTC.datadir)
        TestServerConfiguration.no_sqlite_wrap = True
        # hi-jack PyroRQLSource.get_connection to access existing connection (no
        # pyro connection)
        PyroRQLSource.get_connection = lambda x: x.uri == 'extern-multi' and cls.cnx3 or cls.cnx2
        # also necessary since the repository is closing its initial connections
        # pool though we want to keep cnx2 valid
        Connection.close = lambda x: None

    @classmethod
    def tearDowncls(cls):
        PyroRQLSource.get_connection = PyroRQLSource_get_connection
        Connection.close = Connection_close
        cls.cnx2.close()
        cls.cnx3.close()
        TestServerConfiguration.no_sqlite_wrap = False

    @classmethod
    def _init_repo(cls):
        repo2_handler = get_test_db_handler(cls._cfg2)
        repo2_handler.build_db_cache('4cards-1affaire',pre_setup_func=pre_setup_database_extern)
        cls.repo2, cls.cnx2 = repo2_handler.get_repo_and_cnx('4cards-1affaire')

        repo3_handler = get_test_db_handler(cls._cfg3)
        repo3_handler.build_db_cache('multisource',pre_setup_func=pre_setup_database_multi)
        cls.repo3, cls.cnx3 = repo3_handler.get_repo_and_cnx('multisource')


        super(TwoSourcesTC, cls)._init_repo()

    def setUp(self):
        CubicWebTC.setUp(self)
        self.addCleanup(self.cnx2.close)
        self.addCleanup(self.cnx3.close)
        do_monkey_patch()

    def tearDown(self):
        for source in self.repo.sources[1:]:
            self.repo.remove_source(source.uri)
        CubicWebTC.tearDown(self)
        self.cnx2.close()
        self.cnx3.close()
        undo_monkey_patch()

    @staticmethod
    def pre_setup_database(session, config):
        for uri, src_config in [('extern', EXTERN_SOURCE_CFG),
                            ('extern-multi', '''
cubicweb-user = admin
cubicweb-password = gingkow
''')]:
            source = session.create_entity('CWSource', name=unicode(uri),
                                           type=u'pyrorql', url=u'pyro:///extern-multi',
                                           config=unicode(src_config))
            session.commit()
            add_extern_mapping(source)

        session.commit()
        # trigger discovery
        session.execute('Card X')
        session.execute('Affaire X')
        session.execute('State X')

    def setup_database(self):
        cu2 = self.cnx2.cursor()
        self.ec1 = cu2.execute('Any X WHERE X is Card, X title "C3: An external card", X wikiid "aaa"')[0][0]
        self.aff1 = cu2.execute('Any X WHERE X is Affaire, X ref "AFFREF"')[0][0]
        cu2.close()
        # add some entities
        self.ic1 = self.sexecute('INSERT Card X: X title "C1: An internal card", X wikiid "aaai"')[0][0]
        self.ic2 = self.sexecute('INSERT Card X: X title "C2: Ze internal card", X wikiid "zzzi"')[0][0]

    def test_eid_comp(self):
        rset = self.sexecute('Card X WHERE X eid > 1')
        self.assertEqual(len(rset), 4)
        rset = self.sexecute('Any X,T WHERE X title T, X eid > 1')
        self.assertEqual(len(rset), 4)

    def test_metainformation(self):
        rset = self.sexecute('Card X ORDERBY T WHERE X title T')
        # 2 added to the system source, 2 added to the external source
        self.assertEqual(len(rset), 4)
        # since they are orderd by eid, we know the 3 first one is coming from the system source
        # and the others from external source
        self.assertEqual(rset.get_entity(0, 0).cw_metainformation(),
                          {'source': {'type': 'native', 'uri': 'system', 'use-cwuri-as-url': False},
                           'type': u'Card', 'extid': None})
        externent = rset.get_entity(3, 0)
        metainf = externent.cw_metainformation()
        self.assertEqual(metainf['source'], {'type': 'pyrorql', 'base-url': 'http://extern.org/', 'uri': 'extern', 'use-cwuri-as-url': False})
        self.assertEqual(metainf['type'], 'Card')
        self.assert_(metainf['extid'])
        etype = self.sexecute('Any ETN WHERE X is ET, ET name ETN, X eid %(x)s',
                             {'x': externent.eid})[0][0]
        self.assertEqual(etype, 'Card')

    def test_order_limit_offset(self):
        rsetbase = self.sexecute('Any W,X ORDERBY W,X WHERE X wikiid W')
        self.assertEqual(len(rsetbase), 4)
        self.assertEqual(sorted(rsetbase.rows), rsetbase.rows)
        rset = self.sexecute('Any W,X ORDERBY W,X LIMIT 2 OFFSET 2 WHERE X wikiid W')
        self.assertEqual(rset.rows, rsetbase.rows[2:4])

    def test_has_text(self):
        self.repo.sources_by_uri['extern'].synchronize(MTIME) # in case fti_update has been run before
        self.assertTrue(self.sexecute('Any X WHERE X has_text "affref"'))
        self.assertTrue(self.sexecute('Affaire X WHERE X has_text "affref"'))
        self.assertTrue(self.sexecute('Any X ORDERBY FTIRANK(X) WHERE X has_text "affref"'))
        self.assertTrue(self.sexecute('Affaire X ORDERBY FTIRANK(X) WHERE X has_text "affref"'))

    def test_anon_has_text(self):
        self.repo.sources_by_uri['extern'].synchronize(MTIME) # in case fti_update has been run before
        self.sexecute('INSERT Affaire X: X ref "no readable card"')[0][0]
        aff1 = self.sexecute('INSERT Affaire X: X ref "card"')[0][0]
        # grant read access
        self.sexecute('SET X owned_by U WHERE X eid %(x)s, U login "anon"', {'x': aff1})
        self.commit()
        cnx = self.login('anon')
        cu = cnx.cursor()
        rset = cu.execute('Any X WHERE X has_text "card"')
        # 5: 4 card + 1 readable affaire
        self.assertEqual(len(rset), 5, zip(rset.rows, rset.description))
        rset = cu.execute('Any X ORDERBY FTIRANK(X) WHERE X has_text "card"')
        self.assertEqual(len(rset), 5, zip(rset.rows, rset.description))
        Connection_close(cnx.cnx) # cnx is a TestCaseConnectionProxy

    def test_synchronization(self):
        cu = self.cnx2.cursor()
        assert cu.execute('Any X WHERE X eid %(x)s', {'x': self.aff1})
        cu.execute('SET X ref "BLAH" WHERE X eid %(x)s', {'x': self.aff1})
        aff2 = cu.execute('INSERT Affaire X: X ref "AFFREUX"')[0][0]
        self.cnx2.commit()
        try:
            # force sync
            self.repo.sources_by_uri['extern'].synchronize(MTIME)
            self.assertTrue(self.sexecute('Any X WHERE X has_text "blah"'))
            self.assertTrue(self.sexecute('Any X WHERE X has_text "affreux"'))
            cu.execute('DELETE Affaire X WHERE X eid %(x)s', {'x': aff2})
            self.cnx2.commit()
            self.repo.sources_by_uri['extern'].synchronize(MTIME)
            rset = self.sexecute('Any X WHERE X has_text "affreux"')
            self.assertFalse(rset)
        finally:
            # restore state
            cu.execute('SET X ref "AFFREF" WHERE X eid %(x)s', {'x': self.aff1})
            self.cnx2.commit()

    def test_simplifiable_var(self):
        affeid = self.sexecute('Affaire X WHERE X ref "AFFREF"')[0][0]
        rset = self.sexecute('Any X,AA,AB WHERE E eid %(x)s, E in_state X, X name AA, X modification_date AB',
                            {'x': affeid})
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset[0][1], "pitetre")

    def test_simplifiable_var_2(self):
        affeid = self.sexecute('Affaire X WHERE X ref "AFFREF"')[0][0]
        rset = self.sexecute('Any E WHERE E eid %(x)s, E in_state S, NOT S name "moved"',
                             {'x': affeid, 'u': self.session.user.eid})
        self.assertEqual(len(rset), 1)

    def test_sort_func(self):
        self.sexecute('Affaire X ORDERBY DUMB_SORT(RF) WHERE X ref RF')

    def test_sort_func_ambigous(self):
        self.sexecute('Any X ORDERBY DUMB_SORT(RF) WHERE X title RF')

    def test_in_eid(self):
        iec1 = self.repo.extid2eid(self.repo.sources_by_uri['extern'], str(self.ec1),
                                   'Card', self.session)
        rset = self.sexecute('Any X WHERE X eid IN (%s, %s)' % (iec1, self.ic1))
        self.assertEqual(sorted(r[0] for r in rset.rows), sorted([iec1, self.ic1]))

    def test_greater_eid(self):
        rset = self.sexecute('Any X WHERE X eid > %s' % (self.ic1 - 1))
        self.assertEqual(len(rset.rows), 2) # self.ic1 and self.ic2
        cu = self.cnx2.cursor()
        ec2 = cu.execute('INSERT Card X: X title "glup"')[0][0]
        self.cnx2.commit()
        # 'X eid > something' should not trigger discovery
        rset = self.sexecute('Any X WHERE X eid > %s' % (self.ic1 - 1))
        self.assertEqual(len(rset.rows), 2)
        # trigger discovery using another query
        crset = self.sexecute('Card X WHERE X title "glup"')
        self.assertEqual(len(crset.rows), 1)
        rset = self.sexecute('Any X WHERE X eid > %s' % (self.ic1 - 1))
        self.assertEqual(len(rset.rows), 3)
        rset = self.sexecute('Any MAX(X)')
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(rset.rows[0][0], crset[0][0])

    def test_attr_unification_1(self):
        n1 = self.sexecute('INSERT Note X: X type "AFFREF"')[0][0]
        n2 = self.sexecute('INSERT Note X: X type "AFFREU"')[0][0]
        rset = self.sexecute('Any X,Y WHERE X is Note, Y is Affaire, X type T, Y ref T')
        self.assertEqual(len(rset), 1, rset.rows)

    def test_attr_unification_2(self):
        cu = self.cnx2.cursor()
        ec2 = cu.execute('INSERT Card X: X title "AFFREF"')[0][0]
        self.cnx2.commit()
        try:
            c1 = self.sexecute('INSERT Card C: C title "AFFREF"')[0][0]
            rset = self.sexecute('Any X,Y WHERE X is Card, Y is Affaire, X title T, Y ref T')
            self.assertEqual(len(rset), 2, rset.rows)
        finally:
            cu.execute('DELETE Card X WHERE X eid %(x)s', {'x': ec2})
            self.cnx2.commit()

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
        self.assertEqual(sorted(r[0] for r in rset.rows),
                          sorted(r[0] for r in afeids + ueids))

    def test_subquery1(self):
        rsetbase = self.sexecute('Any W,X WITH W,X BEING (Any W,X ORDERBY W,X WHERE X wikiid W)')
        self.assertEqual(len(rsetbase), 4)
        self.assertEqual(sorted(rsetbase.rows), rsetbase.rows)
        rset = self.sexecute('Any W,X LIMIT 2 OFFSET 2 WITH W,X BEING (Any W,X ORDERBY W,X WHERE X wikiid W)')
        self.assertEqual(rset.rows, rsetbase.rows[2:4])
        rset = self.sexecute('Any W,X ORDERBY W,X LIMIT 2 OFFSET 2 WITH W,X BEING (Any W,X WHERE X wikiid W)')
        self.assertEqual(rset.rows, rsetbase.rows[2:4])
        rset = self.sexecute('Any W,X WITH W,X BEING (Any W,X ORDERBY W,X LIMIT 2 OFFSET 2 WHERE X wikiid W)')
        self.assertEqual(rset.rows, rsetbase.rows[2:4])

    def test_subquery2(self):
        affeid = self.sexecute('Affaire X WHERE X ref "AFFREF"')[0][0]
        rset = self.sexecute('Any X,AA,AB WITH X,AA,AB BEING (Any X,AA,AB WHERE E eid %(x)s, E in_state X, X name AA, X modification_date AB)',
                            {'x': affeid})
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset[0][1], "pitetre")

    def test_not_relation(self):
        states = set(tuple(x) for x in self.sexecute('Any S,SN WHERE S is State, S name SN'))
        userstate = self.session.user.in_state[0]
        states.remove((userstate.eid, userstate.name))
        notstates = set(tuple(x) for x in self.sexecute('Any S,SN WHERE S is State, S name SN, NOT X in_state S, X eid %(x)s',
                                                       {'x': self.session.user.eid}))
        self.assertSetEqual(notstates, states)
        aff1 = self.sexecute('Any X WHERE X is Affaire, X ref "AFFREF"')[0][0]
        aff1stateeid, aff1statename = self.sexecute('Any S,SN WHERE X eid %(x)s, X in_state S, S name SN', {'x': aff1})[0]
        self.assertEqual(aff1statename, 'pitetre')
        states.add((userstate.eid, userstate.name))
        states.remove((aff1stateeid, aff1statename))
        notstates = set(tuple(x) for x in self.sexecute('Any S,SN WHERE S is State, S name SN, NOT X in_state S, X eid %(x)s',
                                                       {'x': aff1}))
        self.assertSetEqual(notstates, states)

    def test_absolute_url_base_url(self):
        cu = self.cnx2.cursor()
        ceid = cu.execute('INSERT Card X: X title "without wikiid to get eid based url"')[0][0]
        self.cnx2.commit()
        lc = self.sexecute('Card X WHERE X title "without wikiid to get eid based url"').get_entity(0, 0)
        self.assertEqual(lc.absolute_url(), 'http://extern.org/%s' % ceid)
        cu.execute('DELETE Card X WHERE X eid %(x)s', {'x':ceid})
        self.cnx2.commit()

    def test_absolute_url_no_base_url(self):
        cu = self.cnx3.cursor()
        ceid = cu.execute('INSERT Card X: X title "without wikiid to get eid based url"')[0][0]
        self.cnx3.commit()
        lc = self.sexecute('Card X WHERE X title "without wikiid to get eid based url"').get_entity(0, 0)
        self.assertEqual(lc.absolute_url(), 'http://testing.fr/cubicweb/%s' % lc.eid)
        cu.execute('DELETE Card X WHERE X eid %(x)s', {'x':ceid})
        self.cnx3.commit()

    def test_crossed_relation_noeid_needattr(self):
        """http://www.cubicweb.org/ticket/1382452"""
        aff1 = self.sexecute('INSERT Affaire X: X ref "AFFREF"')[0][0]
        # link within extern source
        ec1 = self.sexecute('Card X WHERE X wikiid "zzz"')[0][0]
        self.sexecute('SET A documented_by C WHERE E eid %(a)s, C eid %(c)s',
                      {'a': aff1, 'c': ec1})
        # link from system to extern source
        self.sexecute('SET A documented_by C WHERE E eid %(a)s, C eid %(c)s',
                      {'a': aff1, 'c': self.ic2})
        rset = self.sexecute('DISTINCT Any DEP WHERE P ref "AFFREF", P documented_by DEP, DEP wikiid LIKE "z%"')
        self.assertEqual(sorted(rset.rows), [[ec1], [self.ic2]])

    def test_nonregr1(self):
        ueid = self.session.user.eid
        affaire = self.sexecute('Affaire X WHERE X ref "AFFREF"').get_entity(0, 0)
        self.sexecute('Any U WHERE U in_group G, (G name IN ("managers", "logilab") OR (X require_permission P?, P name "bla", P require_group G)), X eid %(x)s, U eid %(u)s',
                     {'x': affaire.eid, 'u': ueid})

    def test_nonregr2(self):
        iworkflowable = self.session.user.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate')
        treid = iworkflowable.latest_trinfo().eid
        rset = self.sexecute('Any X ORDERBY D DESC WHERE E eid %(x)s, E wf_info_for X, X modification_date D',
                            {'x': treid})
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset.rows[0], [self.session.user.eid])

    def test_nonregr3(self):
        self.sexecute('DELETE Card X WHERE X eid %(x)s, NOT X multisource_inlined_rel Y', {'x': self.ic1})

    def test_nonregr4(self):
        self.sexecute('Any X,S,U WHERE X in_state S, X todo_by U')

    def test_delete_source(self):
        req = self.request()
        req.execute('DELETE CWSource S WHERE S name "extern"')
        self.commit()
        cu = self.session.system_sql("SELECT * FROM entities WHERE source='extern'")
        self.assertFalse(cu.fetchall())

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
