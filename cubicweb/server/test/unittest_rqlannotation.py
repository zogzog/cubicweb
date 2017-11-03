# -*- coding: iso-8859-1 -*-
# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for modules cubicweb.server.rqlannotation"""

from cubicweb import devtools
from cubicweb.devtools.repotest import BaseQuerierTC


class SQLGenAnnotatorTC(BaseQuerierTC):

    def setUp(self):
        handler = devtools.get_test_db_handler(devtools.TestServerConfiguration('data', __file__))
        handler.build_db_cache()
        repo, _cnx = handler.get_repo_and_cnx()
        self.__class__.repo = repo
        super(SQLGenAnnotatorTC, self).setUp()

    def test_0_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any SEN,RN,OEN WHERE X from_entity SE, '
                                  'SE eid 44, X relation_type R, R eid 139, '
                                  'X to_entity OE, OE eid 42, R name RN, SE name SEN, '
                                  'OE name OEN')
            self.assertEqual(rqlst.defined_vars['SE']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['OE']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['R']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['SE'].stinfo['attrvar'], None)
            self.assertEqual(rqlst.defined_vars['OE'].stinfo['attrvar'], None)
            self.assertEqual(rqlst.defined_vars['R'].stinfo['attrvar'], None)

    def test_0_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any O WHERE NOT S ecrit_par O, S eid 1, '
                                  'S inline1 P, O inline2 P')
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['O'].stinfo['attrvar'], None)

    def test_0_4(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any A,B,C WHERE A eid 12,A comment B, '
                                  'A ?wf_info_for C')
            self.assertEqual(rqlst.defined_vars['A']._q_invariant, False)
            self.assertTrue(rqlst.defined_vars['B'].stinfo['attrvar'])
            self.assertEqual(rqlst.defined_vars['C']._q_invariant, False)
            self.assertEqual(rqlst.solutions, [{'A': 'TrInfo', 'B': 'String', 'C': 'Affaire'},
                                               {'A': 'TrInfo', 'B': 'String', 'C': 'CWUser'},
                                               {'A': 'TrInfo', 'B': 'String', 'C': 'Note'}])

    def test_0_5(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any P WHERE N ecrit_par P, N eid 0')
            self.assertEqual(rqlst.defined_vars['N']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, True)

    def test_0_6(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any P WHERE NOT N ecrit_par P, N eid 512')
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, False)

    def test_0_7(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Personne X,Y where X nom NX, '
                                  'Y nom NX, X eid XE, not Y eid XE')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)
            self.assertTrue(rqlst.defined_vars['XE'].stinfo['attrvar'])

    def test_0_8(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any P WHERE X eid 0, NOT X connait P')
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, False)
            self.assertEqual(len(rqlst.solutions), 1, rqlst.solutions)

    def test_0_10(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X concerne Y, Y is Note')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_0_11(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X todo_by Y, X is Affaire')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_0_12(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Personne P WHERE P concerne A, '
                                  'A concerne S, S nom "Logilab"')
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['A']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['S']._q_invariant, False)

    def test_1_0(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X,Y WHERE X created_by Y, '
                                  'X eid 5, NOT Y eid 6')
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_1_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X,Y WHERE X created_by Y, X eid 5, '
                                  'NOT Y eid IN (6,7)')
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X identity Y, Y eid 1')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)

    def test_7(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Personne X,Y where X nom NX, Y nom NX, '
                                  'X eid XE, not Y eid XE')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_8(self):
        with self.admin_access.cnx() as cnx:
            # DISTINCT Any P WHERE P require_group %(g)s,
            # NOT %(u)s has_group_permission P, P is CWPermission
            rqlst = self._prepare(cnx, 'DISTINCT Any X WHERE A concerne X, '
                                  'NOT N migrated_from X, '
                                  'X is Note, N eid 1')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)

    def test_diff_scope_identity_deamb(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X concerne Y, Y is Note, '
                                  'EXISTS(Y identity Z, Z migrated_from N)')
            self.assertEqual(rqlst.defined_vars['Z']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_optional_inlined(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X,S where X from_state S?')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['S']._q_invariant, True)

    def test_optional_inlined_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any N,A WHERE N? inline1 A')
            self.assertEqual(rqlst.defined_vars['N']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['A']._q_invariant, False)

    def test_optional_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X,S WHERE X travaille S?')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['S']._q_invariant, True)

    def test_greater_eid(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X eid > 5')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_greater_eid_typed(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X eid > 5, X is Note')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)

    def test_max_eid(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any MAX(X)')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_max_eid_typed(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any MAX(X) WHERE X is Note')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)

    def test_all_entities(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_all_typed_entity(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X is Note')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)

    def test_has_text_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X has_text "toto tata"')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['X'].stinfo['principal'].r_type,
                             'has_text')

    def test_has_text_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X is Personne, '
                                  'X has_text "coucou"')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['X'].stinfo['principal'].r_type,
                             'has_text')

    def test_not_relation_1(self):
        with self.admin_access.cnx() as cnx:
            # P can't be invariant since deambiguification caused by "NOT X require_permission P"
            # is not considered by generated sql (NOT EXISTS(...))
            rqlst = self._prepare(cnx, 'Any P,G WHERE P require_group G, '
                                  'NOT X require_permission P')
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['G']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_not_relation_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'TrInfo X WHERE X eid 2, '
                                  'NOT X from_state Y, Y is State')
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)

    def test_not_relation_3(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X, Y WHERE X eid 1, Y eid in (2, 3)')
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_4_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Note X WHERE NOT Y evaluee X')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_not_relation_4_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE NOT Y evaluee X')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_not_relation_4_3(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any Y WHERE NOT Y evaluee X')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_4_4(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE NOT Y evaluee X, Y is CWUser')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_4_5(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE NOT Y evaluee X, '
                                  'Y eid %s, X is Note' % self.ueid)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.solutions, [{'X': 'Note'}])

    def test_not_relation_5_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X,Y WHERE X name "CWGroup", '
                                  'Y eid IN(1, 2, 3), NOT X read_permission Y')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_5_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'DISTINCT Any X,Y WHERE X name "CWGroup", '
                                  'Y eid IN(1, 2, 3), NOT X read_permission Y')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_relation_6(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Personne P where NOT P concerne A')
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['A']._q_invariant, True)

    def test_not_relation_7(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any K,V WHERE P is CWProperty, '
                                  'P pkey K, P value V, NOT P for_user U')
            self.assertEqual(rqlst.defined_vars['P']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, True)

    def test_exists_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any U WHERE U eid IN (1,2), EXISTS(X owned_by U)')
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_exists_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any U WHERE EXISTS(U eid IN (1,2), X owned_by U)')
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_exists_3(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any U WHERE EXISTS(X owned_by U, X bookmarked_by U)')
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_exists_4(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X,Y WHERE X name "CWGroup", '
                                  'Y eid IN(1, 2, 3), EXISTS(X read_permission Y)')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_exists_5(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'DISTINCT Any X,Y WHERE X name "CWGroup", '
                                  'Y eid IN(1, 2, 3), EXISTS(X read_permission Y)')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_not_exists_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any U WHERE NOT EXISTS(X owned_by U, '
                                  'X bookmarked_by U)')
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_not_exists_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X,Y WHERE X name "CWGroup", '
                                  'Y eid IN(1, 2, 3), NOT EXISTS(X read_permission Y)')
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_not_exists_distinct_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'DISTINCT Any X,Y WHERE X name "CWGroup", '
                                  'Y eid IN(1, 2, 3), NOT EXISTS(X read_permission Y)')
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, False)

    def test_or_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X concerne B OR '
                                  'C concerne X, B eid 12, C eid 13')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)

    def test_or_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X created_by U, X concerne B OR '
                                  'C concerne X, B eid 12, C eid 13')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['X'].stinfo['principal'].r_type, 'created_by')

    def test_or_3(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any N WHERE A evaluee N or EXISTS(N todo_by U)')
            self.assertEqual(rqlst.defined_vars['N']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['A']._q_invariant, True)
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, True)

    def test_or_exists_1(self):
        with self.admin_access.cnx() as cnx:
            # query generated by security rewriting
            rqlst = self._prepare(cnx, 'DISTINCT Any A,S WHERE A is Affaire, S nom "chouette", '
                                  'S is IN(Division, Societe, SubDivision),'
                                  '(EXISTS(A owned_by D)) '
                                  'OR ((((EXISTS(E concerne C?, C owned_by D, A identity E, '
                                  '              C is Note, E is Affaire)) '
                                  'OR (EXISTS(I concerne H?, H owned_by D, H is Societe, '
                                  '           A identity I, I is Affaire))) '
                                  'OR (EXISTS(J concerne G?, G owned_by D, G is SubDivision, '
                                  '           A identity J, J is Affaire))) '
                                  'OR (EXISTS(K concerne F?, F owned_by D, F is Division, '
                                  '           A identity K, K is Affaire)))')
            self.assertEqual(rqlst.defined_vars['A']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['S']._q_invariant, False)

    def test_or_exists_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any U WHERE EXISTS(U in_group G, G name "managers") OR '
                                  'EXISTS(X owned_by U, X bookmarked_by U)')
            self.assertEqual(rqlst.defined_vars['U']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['G']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, True)

    def test_or_exists_3(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any COUNT(S),CS GROUPBY CS ORDERBY 1 DESC LIMIT 10 '
                                  'WHERE C is Societe, S concerne C, C nom CS, '
                                  '(EXISTS(S owned_by D)) '
                                  'OR (EXISTS(S documented_by N, N title "published"))')
            self.assertEqual(rqlst.defined_vars['S']._q_invariant, True)
            rqlst = self._prepare(cnx, 'Any COUNT(S),CS GROUPBY CS ORDERBY 1 DESC LIMIT 10 '
                                  'WHERE S is Affaire, C is Societe, S concerne C, C nom CS, '
                                  '(EXISTS(S owned_by D)) '
                                  'OR (EXISTS(S documented_by N, N title "published"))')
            self.assertEqual(rqlst.defined_vars['S']._q_invariant, True)

    def test_nonregr_ambiguity(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Note N WHERE N attachment F')
            # N may be an image as well, not invariant
            self.assertEqual(rqlst.defined_vars['N']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['F']._q_invariant, True)

    def test_nonregr_ambiguity_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any S,SN WHERE X has_text "tot", '
                                  'X in_state S, S name SN, X is CWUser')
            # X use has_text but should not be invariant as ambiguous, and has_text
            # may not be its principal
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['S']._q_invariant, False)

    def test_remove_from_deleted_source_1(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Note X WHERE X eid 999998, NOT X cw_source Y')
            self.assertNotIn('X', rqlst.defined_vars)  # simplified
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_remove_from_deleted_source_2(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Note X WHERE X eid IN (999998, 999999), NOT X cw_source Y')
            self.assertEqual(rqlst.defined_vars['X']._q_invariant, False)
            self.assertEqual(rqlst.defined_vars['Y']._q_invariant, True)

    def test_has_text_security_cache_bug(self):
        with self.admin_access.cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any X WHERE X has_text "toto" WITH X BEING '
                                  '(Any C WHERE C is Societe, C nom CS)')
            self.assertTrue(rqlst.parent.has_text_query)


if __name__ == '__main__':
    import unittest
    unittest.main()
