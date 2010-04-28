# -*- coding: iso-8859-1 -*-
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
"""unit tests for modules cubicweb.server.rqlannotation
"""

from cubicweb.devtools import init_test_database
from cubicweb.devtools.repotest import BaseQuerierTC

repo, cnx = init_test_database()

def teardown_module(*args):
    global repo, cnx
    del repo, cnx


class SQLGenAnnotatorTC(BaseQuerierTC):
    repo = repo

    def get_max_eid(self):
        # no need for cleanup here
        return None
    def cleanup(self):
        # no need for cleanup here
        pass

    def test_0_1(self):
        rqlst = self._prepare('Any SEN,RN,OEN WHERE X from_entity SE, SE eid 44, X relation_type R, R eid 139, X to_entity OE, OE eid 42, R name RN, SE name SEN, OE name OEN')
        self.assertEquals(rqlst.defined_vars['SE']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['OE']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['R']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['SE'].stinfo['attrvar'], None)
        self.assertEquals(rqlst.defined_vars['OE'].stinfo['attrvar'], None)
        self.assertEquals(rqlst.defined_vars['R'].stinfo['attrvar'], None)

    def test_0_2(self):
        rqlst = self._prepare('Any O WHERE NOT S ecrit_par O, S eid 1, S inline1 P, O inline2 P')
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['O'].stinfo['attrvar'], None)

    def test_0_4(self):
        rqlst = self._prepare('Any A,B,C WHERE A eid 12,A comment B, A ?wf_info_for C')
        self.assertEquals(rqlst.defined_vars['A']._q_invariant, False)
        self.assert_(rqlst.defined_vars['B'].stinfo['attrvar'])
        self.assertEquals(rqlst.defined_vars['C']._q_invariant, False)
        self.assertEquals(rqlst.solutions, [{'A': 'TrInfo', 'B': 'String', 'C': 'Affaire'},
                                      {'A': 'TrInfo', 'B': 'String', 'C': 'CWUser'},
                                      {'A': 'TrInfo', 'B': 'String', 'C': 'Note'}])

    def test_0_5(self):
        rqlst = self._prepare('Any P WHERE N ecrit_par P, N eid 0')
        self.assertEquals(rqlst.defined_vars['N']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, True)

    def test_0_6(self):
        rqlst = self._prepare('Any P WHERE NOT N ecrit_par P, N eid 512')
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, False)

    def test_0_7(self):
        rqlst = self._prepare('Personne X,Y where X nom NX, Y nom NX, X eid XE, not Y eid XE')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)
        self.assert_(rqlst.defined_vars['XE'].stinfo['attrvar'])

    def test_0_8(self):
        rqlst = self._prepare('Any P WHERE X eid 0, NOT X connait P')
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, False)
        #self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)
        self.assertEquals(len(rqlst.solutions), 1, rqlst.solutions)

    def test_0_10(self):
        rqlst = self._prepare('Any X WHERE X concerne Y, Y is Note')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_0_11(self):
        rqlst = self._prepare('Any X WHERE X todo_by Y, X is Affaire')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)

    def test_0_12(self):
        rqlst = self._prepare('Personne P WHERE P concerne A, A concerne S, S nom "Logilab"')
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['A']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['S']._q_invariant, False)

    def test_1_0(self):
        rqlst = self._prepare('Any X,Y WHERE X created_by Y, X eid 5, NOT Y eid 6')
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)

    def test_1_1(self):
        rqlst = self._prepare('Any X,Y WHERE X created_by Y, X eid 5, NOT Y eid IN (6,7)')
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)

    def test_2(self):
        rqlst = self._prepare('Any X WHERE X identity Y, Y eid 1')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)

    def test_7(self):
        rqlst = self._prepare('Personne X,Y where X nom NX, Y nom NX, X eid XE, not Y eid XE')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_8(self):
        # DISTINCT Any P WHERE P require_group %(g)s, NOT %(u)s has_group_permission P, P is CWPermission
        rqlst = self._prepare('DISTINCT Any X WHERE A concerne X, NOT N migrated_from X, '
                              'X is Note, N eid 1')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)

    def test_diff_scope_identity_deamb(self):
        rqlst = self._prepare('Any X WHERE X concerne Y, Y is Note, EXISTS(Y identity Z, Z migrated_from N)')
        self.assertEquals(rqlst.defined_vars['Z']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)

    def test_optional_inlined(self):
        rqlst = self._prepare('Any X,S where X from_state S?')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['S']._q_invariant, True)

    def test_optional_inlined_2(self):
        rqlst = self._prepare('Any N,A WHERE N? inline1 A')
        self.assertEquals(rqlst.defined_vars['N']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['A']._q_invariant, False)

    def test_optional_1(self):
        rqlst = self._prepare('Any X,S WHERE X travaille S?')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['S']._q_invariant, True)

    def test_greater_eid(self):
        rqlst = self._prepare('Any X WHERE X eid > 5')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_greater_eid_typed(self):
        rqlst = self._prepare('Any X WHERE X eid > 5, X is Note')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_max_eid(self):
        rqlst = self._prepare('Any MAX(X)')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_max_eid_typed(self):
        rqlst = self._prepare('Any MAX(X) WHERE X is Note')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)

    def test_all_entities(self):
        rqlst = self._prepare('Any X')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_all_typed_entity(self):
        rqlst = self._prepare('Any X WHERE X is Note')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)

    def test_has_text_1(self):
        rqlst = self._prepare('Any X WHERE X has_text "toto tata"')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['X'].stinfo['principal'].r_type, 'has_text')

    def test_has_text_2(self):
        rqlst = self._prepare('Any X WHERE X is Personne, X has_text "coucou"')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['X'].stinfo['principal'].r_type, 'has_text')

    def test_not_relation_1(self):
        # P can't be invariant since deambiguification caused by "NOT X require_permission P"
        # is not considered by generated sql (NOT EXISTS(...))
        rqlst = self._prepare('Any P,G WHERE P require_group G, NOT X require_permission P')
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['G']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_not_relation_2(self):
        rqlst = self._prepare('TrInfo X WHERE X eid 2, NOT X from_state Y, Y is State')
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)

    def test_not_relation_3(self):
        rqlst = self._prepare('Any X, Y WHERE X eid 1, Y eid in (2, 3)')
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_4_1(self):
        rqlst = self._prepare('Note X WHERE NOT Y evaluee X')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)

    def test_not_relation_4_2(self):
        rqlst = self._prepare('Any X WHERE NOT Y evaluee X')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)

    def test_not_relation_4_3(self):
        rqlst = self._prepare('Any Y WHERE NOT Y evaluee X')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_4_4(self):
        rqlst = self._prepare('Any X WHERE NOT Y evaluee X, Y is CWUser')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_4_5(self):
        rqlst = self._prepare('Any X WHERE NOT Y evaluee X, Y eid %s, X is Note' % self.ueid)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.solutions, [{'X': 'Note'}])

    def test_not_relation_5_1(self):
        rqlst = self._prepare('Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT X read_permission Y')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_5_2(self):
        rqlst = self._prepare('DISTINCT Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT X read_permission Y')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_6(self):
        rqlst = self._prepare('Personne P where NOT P concerne A')
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['A']._q_invariant, True)

    def test_not_relation_7(self):
        rqlst = self._prepare('Any K,V WHERE P is CWProperty, P pkey K, P value V, NOT P for_user U')
        self.assertEquals(rqlst.defined_vars['P']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, True)

    def test_exists_1(self):
        rqlst = self._prepare('Any U WHERE U eid IN (1,2), EXISTS(X owned_by U)')
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_exists_2(self):
        rqlst = self._prepare('Any U WHERE EXISTS(U eid IN (1,2), X owned_by U)')
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_exists_3(self):
        rqlst = self._prepare('Any U WHERE EXISTS(X owned_by U, X bookmarked_by U)')
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_exists_4(self):
        rqlst = self._prepare('Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_exists_5(self):
        rqlst = self._prepare('DISTINCT Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), EXISTS(X read_permission Y)')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, True)

    def test_not_exists_1(self):
        rqlst = self._prepare('Any U WHERE NOT EXISTS(X owned_by U, X bookmarked_by U)')
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_not_exists_2(self):
        rqlst = self._prepare('Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT EXISTS(X read_permission Y)')
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_exists_distinct_1(self):
        rqlst = self._prepare('DISTINCT Any X,Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT EXISTS(X read_permission Y)')
        self.assertEquals(rqlst.defined_vars['Y']._q_invariant, False)

    def test_or_1(self):
        rqlst = self._prepare('Any X WHERE X concerne B OR C concerne X, B eid 12, C eid 13')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, False)

    def test_or_2(self):
        rqlst = self._prepare('Any X WHERE X created_by U, X concerne B OR C concerne X, B eid 12, C eid 13')
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['X'].stinfo['principal'].r_type, 'created_by')

    def test_or_3(self):
        rqlst = self._prepare('Any N WHERE A evaluee N or EXISTS(N todo_by U)')
        self.assertEquals(rqlst.defined_vars['N']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['A']._q_invariant, True)
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, True)

    def test_or_exists_1(self):
        # query generated by security rewriting
        rqlst = self._prepare('DISTINCT Any A,S WHERE A is Affaire, S nom "chouette", S is IN(Division, Societe, SubDivision),'
                              '(EXISTS(A owned_by D)) '
                              'OR ((((EXISTS(E concerne C?, C owned_by D, A identity E, C is Note, E is Affaire)) '
                              'OR (EXISTS(I concerne H?, H owned_by D, H is Societe, A identity I, I is Affaire))) '
                              'OR (EXISTS(J concerne G?, G owned_by D, G is SubDivision, A identity J, J is Affaire))) '
                              'OR (EXISTS(K concerne F?, F owned_by D, F is Division, A identity K, K is Affaire)))')
        self.assertEquals(rqlst.defined_vars['A']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['S']._q_invariant, False)

    def test_or_exists_2(self):
        rqlst = self._prepare('Any U WHERE EXISTS(U in_group G, G name "managers") OR EXISTS(X owned_by U, X bookmarked_by U)')
        self.assertEquals(rqlst.defined_vars['U']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['G']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['X']._q_invariant, True)

    def test_or_exists_3(self):
        rqlst = self._prepare('Any COUNT(S),CS GROUPBY CS ORDERBY 1 DESC LIMIT 10 '
                              'WHERE C is Societe, S concerne C, C nom CS, '
                              '(EXISTS(S owned_by D)) OR (EXISTS(S documented_by N, N title "published"))')
        self.assertEquals(rqlst.defined_vars['S']._q_invariant, True)
        rqlst = self._prepare('Any COUNT(S),CS GROUPBY CS ORDERBY 1 DESC LIMIT 10 '
                              'WHERE S is Affaire, C is Societe, S concerne C, C nom CS, '
                              '(EXISTS(S owned_by D)) OR (EXISTS(S documented_by N, N title "published"))')
        self.assertEquals(rqlst.defined_vars['S']._q_invariant, True)

    def test_nonregr_ambiguity(self):
        rqlst = self._prepare('Note N WHERE N attachment F')
        # N may be an image as well, not invariant
        self.assertEquals(rqlst.defined_vars['N']._q_invariant, False)
        self.assertEquals(rqlst.defined_vars['F']._q_invariant, True)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
