# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from six import string_types

from logilab.common.testlib import mock_object
from logilab.common.decorators import monkeypatch
from yams import BadSchemaDefinition
from yams.buildobjs import RelationDefinition
from rql import parse, nodes, RQLHelper

from cubicweb import Unauthorized, rqlrewrite, devtools
from cubicweb.rqlrewrite import RQLRewriter
from cubicweb.schema import RRQLExpression, ERQLExpression
from cubicweb.devtools import repotest
from cubicweb.devtools.testlib import CubicWebTC, TestCase


def setUpModule(*args):
    global rqlhelper, schema
    config = devtools.TestServerConfiguration('data-rewrite', __file__)
    config.bootstrap_cubes()
    schema = config.load_schema()
    schema.add_relation_def(RelationDefinition(subject='Card', name='in_state',
                                               object='State', cardinality='1*'))
    rqlhelper = RQLHelper(schema, special_relations={'eid': 'uid',
                                                     'has_text': 'fti'})
    repotest.do_monkey_patch()


def tearDownModule(*args):
    repotest.undo_monkey_patch()
    global rqlhelper, schema
    del rqlhelper, schema


def eid_func_map(eid):
    return {1: 'CWUser',
            2: 'Card',
            3: 'Affaire'}[eid]


def _prepare_rewriter(rewriter_cls, kwargs):
    class FakeVReg:
        schema = schema

        @staticmethod
        def solutions(sqlcursor, rqlst, kwargs):
            rqlhelper.compute_solutions(rqlst, {'eid': eid_func_map}, kwargs=kwargs)

        class rqlhelper:
            @staticmethod
            def annotate(rqlst):
                rqlhelper.annotate(rqlst)

    return rewriter_cls(mock_object(vreg=FakeVReg, user=(mock_object(eid=1))))


def rewrite(rqlst, snippets_map, kwargs, existingvars=None):
    rewriter = _prepare_rewriter(rqlrewrite.RQLRewriter, kwargs)
    # turn {(V1, V2): constraints} into [(varmap, constraints)]
    snippets = []
    snippet_varmap = {}
    for v, exprs in sorted(snippets_map.items()):
        rqlexprs = []
        varmap = dict([v])
        for snippet in exprs:
            # when the same snippet is impacting several variables, group them
            # unless there is some conflicts on the snippet's variable name (we
            # only want that for constraint on relations using both S and O)
            if snippet in snippet_varmap and not (
                    set(varmap.values()) & set(snippet_varmap[snippet].values())):
                snippet_varmap[snippet].update(varmap)
                continue
            snippet_varmap[snippet] = varmap
            if isinstance(snippet, string_types):
                snippet = mock_object(snippet_rqlst=parse(u'Any X WHERE ' + snippet).children[0],
                                      expression=u'Any X WHERE ' + snippet)
            rqlexprs.append(snippet)
        if rqlexprs:
            snippets.append((varmap, rqlexprs))

    rqlhelper.compute_solutions(rqlst.children[0], {'eid': eid_func_map}, kwargs=kwargs)
    rewriter.rewrite(rqlst.children[0], snippets, kwargs, existingvars)
    check_vrefs(rqlst.children[0])
    return rewriter.rewritten


def check_vrefs(node):
    vrefmaps = {}
    selects = []
    for vref in node.iget_nodes(nodes.VariableRef):
        stmt = vref.stmt
        try:
            vrefmaps[stmt].setdefault(vref.name, set()).add(vref)
        except KeyError:
            vrefmaps[stmt] = {vref.name: set((vref,))}
            selects.append(stmt)
    assert node in selects, (node, selects)
    for stmt in selects:
        for var in stmt.defined_vars.values():
            assert var.stinfo['references']
            vrefmap = vrefmaps[stmt]
            assert not (var.stinfo['references'] ^ vrefmap[var.name]), (
                node.as_string(), var, var.stinfo['references'], vrefmap[var.name])


class RQLRewriteTC(TestCase):
    """a faire:

    * optimisation: detecter les relations utilisees dans les rqlexpressions qui
      sont presentes dans la requete de depart pour les reutiliser si possible

    * "has_<ACTION>_permission" ?
    """

    def test_base_var(self):
        constraint = ('X in_state S, U in_group G, P require_state S,'
                      'P name "read", P require_group G')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {})
        self.assertEqual(
            rqlst.as_string(),
            u'Any C WHERE C is Card, B eid %(D)s, '
            'EXISTS(C in_state A, B in_group E, F require_state A, '
            'F name "read", F require_group E, A is State, E is CWGroup, F is CWPermission)')

    def test_multiple_var(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        affaire_constraints = ('X ref LIKE "PUBLIC%"', 'U in_group G, G name "public"')
        kwargs = {'u': 2}
        rqlst = parse(u'Any S WHERE S documented_by C, C eid %(u)s')
        rewrite(rqlst, {('C', 'X'): (card_constraint,), ('S', 'X'): affaire_constraints},
                kwargs)
        self.assertMultiLineEqual(
            rqlst.as_string(),
            u'Any S WHERE S documented_by C, C eid %(u)s, B eid %(D)s, '
            'EXISTS(C in_state A, B in_group E, F require_state A, '
            'F name "read", F require_group E, A is State, E is CWGroup, F is CWPermission), '
            '(EXISTS(S ref LIKE "PUBLIC%")) '
            'OR (EXISTS(B in_group G, G name "public", G is CWGroup)), '
            'S is Affaire')
        self.assertIn('D', kwargs)

    def test_or(self):
        constraint = (
            '(X identity U) OR '
            '(X in_state ST, CL identity U, CL in_state ST, ST name "subscribed")'
        )
        rqlst = parse(u'Any S WHERE S owned_by C, C eid %(u)s, S is in (CWUser, CWGroup)')
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {'u': 1})
        self.assertEqual(
            rqlst.as_string(),
            'Any S WHERE S owned_by C, C eid %(u)s, S is IN(CWUser, CWGroup), A eid %(B)s, '
            'EXISTS((C identity A) OR (C in_state D, E identity A, '
            'E in_state D, D name "subscribed"), D is State, E is CWUser)')

    def test_simplified_rqlst(self):
        constraint = ('X in_state S, U in_group G, P require_state S,'
                      'P name "read", P require_group G')
        rqlst = parse(u'Any 2')  # this is the simplified rql st for Any X WHERE X eid 12
        rewrite(rqlst, {('2', 'X'): (constraint,)}, {})
        self.assertEqual(
            rqlst.as_string(),
            u'Any 2 WHERE B eid %(C)s, '
            'EXISTS(2 in_state A, B in_group D, E require_state A, '
            'E name "read", E require_group D, A is State, D is CWGroup, E is CWPermission)')

    def test_optional_var_1(self):
        constraint = ('X in_state S, U in_group G, P require_state S,'
                      'P name "read", P require_group G')
        rqlst = parse(u'Any A,C WHERE A documented_by C?')
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {})
        self.assertEqual(
            rqlst.as_string(),
            u'Any A,C WHERE A documented_by C?, A is Affaire '
            'WITH C BEING '
            '(Any C WHERE EXISTS(C in_state B, D in_group F, G require_state B, G name "read", '
            'G require_group F), D eid %(A)s, C is Card)')

    def test_optional_var_2(self):
        constraint = ('X in_state S, U in_group G, P require_state S,'
                      'P name "read", P require_group G')
        rqlst = parse(u'Any A,C,T WHERE A documented_by C?, C title T')
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {})
        self.assertEqual(
            rqlst.as_string(),
            u'Any A,C,T WHERE A documented_by C?, A is Affaire '
            'WITH C,T BEING '
            '(Any C,T WHERE C title T, EXISTS(C in_state B, D in_group F, '
            'G require_state B, G name "read", G require_group F), '
            'D eid %(A)s, C is Card)')

    def test_optional_var_3(self):
        constraint1 = ('X in_state S, U in_group G, P require_state S,'
                       'P name "read", P require_group G')
        constraint2 = 'X in_state S, S name "public"'
        rqlst = parse(u'Any A,C,T WHERE A documented_by C?, C title T')
        rewrite(rqlst, {('C', 'X'): (constraint1, constraint2)}, {})
        self.assertEqual(
            rqlst.as_string(),
            u'Any A,C,T WHERE A documented_by C?, A is Affaire '
            'WITH C,T BEING (Any C,T WHERE C title T, '
            '(EXISTS(C in_state B, D in_group F, G require_state B, '
            'G name "read", G require_group F)) '
            'OR (EXISTS(C in_state E, E name "public")), '
            'D eid %(A)s, C is Card)')

    def test_optional_var_4(self):
        constraint1 = 'A created_by U, X documented_by A'
        constraint2 = 'A created_by U, X concerne A'
        constraint3 = 'X created_by U'
        rqlst = parse(u'Any X,LA,Y WHERE LA? documented_by X, LA concerne Y')
        rewrite(rqlst, {('LA', 'X'): (constraint1, constraint2),
                        ('X', 'X'): (constraint3,),
                        ('Y', 'X'): (constraint3,)}, {})
        self.assertEqual(
            rqlst.as_string(),
            u'Any X,LA,Y WHERE LA? documented_by X, LA concerne Y, B eid %(C)s, '
            'EXISTS(X created_by B), EXISTS(Y created_by B), '
            'X is Card, Y is IN(Division, Note, Societe) '
            'WITH LA BEING (Any LA WHERE (EXISTS(A created_by B, LA documented_by A)) '
            'OR (EXISTS(E created_by B, LA concerne E)), '
            'B eid %(D)s, LA is Affaire)')

    def test_ambiguous_optional_same_exprs(self):
        """See #3013535"""
        # see test of the same name in RewriteFullTC: original problem is
        # unreproducible here because it actually lies in
        # RQLRewriter.insert_local_checks
        rqlst = parse(u'Any A,AR,X,CD WHERE A concerne X?, A ref AR, '
                      'A eid %(a)s, X creation_date CD')
        rewrite(rqlst, {('X', 'X'): ('X created_by U',)}, {'a': 3})
        self.assertEqual(
            rqlst.as_string(),
            u'Any A,AR,X,CD WHERE A concerne X?, A ref AR, A eid %(a)s '
            'WITH X,CD BEING (Any X,CD WHERE X creation_date CD, '
            'EXISTS(X created_by B), B eid %(A)s, X is IN(Division, Note, Societe))')

    def test_ambiguous_optional_same_exprs_constant(self):
        rqlst = parse(u'Any A,AR,X WHERE A concerne X?, A ref AR, '
                      'A eid %(a)s, X creation_date TODAY')
        rewrite(rqlst, {('X', 'X'): ('X created_by U',)}, {'a': 3})
        self.assertEqual(
            rqlst.as_string(),
            u'Any A,AR,X WHERE A concerne X?, A ref AR, A eid %(a)s '
            'WITH X BEING (Any X WHERE X creation_date TODAY, '
            'EXISTS(X created_by B), B eid %(A)s, X is IN(Division, Note, Societe))')

    def test_optional_var_inlined(self):
        c1 = ('X require_permission P')
        c2 = ('X inlined_card O, O require_permission P')
        rqlst = parse(u'Any C,A,R WHERE A? inlined_card C, A ref R')
        rewrite(rqlst, {('C', 'X'): (c1,),
                        ('A', 'X'): (c2,),
                        }, {})
        # XXX suboptimal
        self.assertEqual(
            rqlst.as_string(),
            "Any C,A,R WITH A,C,R BEING "
            "(Any A,C,R WHERE A? inlined_card C, A ref R, "
            "(A is NULL) OR (EXISTS(A inlined_card B, B require_permission D, "
            "B is Card, D is CWPermission)), "
            "A is Affaire, C is Card, EXISTS(C require_permission E, E is CWPermission))")

    # def test_optional_var_inlined_has_perm(self):
    #     c1 = ('X require_permission P')
    #     c2 = ('X inlined_card O, U has_read_permission O')
    #     rqlst = parse(u'Any C,A,R WHERE A? inlined_card C, A ref R')
    #     rewrite(rqlst, {('C', 'X'): (c1,),
    #                     ('A', 'X'): (c2,),
    #                     }, {})
    #     self.assertEqual(rqlst.as_string(),
    #                          "")

    def test_optional_var_inlined_imbricated_error(self):
        c1 = ('X require_permission P')
        c2 = ('X inlined_card O, O require_permission P')
        rqlst = parse(u'Any C,A,R,A2,R2 WHERE A? inlined_card C, A ref R,'
                      'A2? inlined_card C, A2 ref R2')
        self.assertRaises(BadSchemaDefinition,
                          rewrite, rqlst, {('C', 'X'): (c1,),
                                           ('A', 'X'): (c2,),
                                           ('A2', 'X'): (c2,),
                                           }, {})

    def test_optional_var_inlined_linked(self):
        c1 = ('X require_permission P')
        rqlst = parse(u'Any A,W WHERE A inlined_card C?, C inlined_note N, '
                      'N inlined_affaire W')
        rewrite(rqlst, {('C', 'X'): (c1,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any A,W WHERE A inlined_card C?, A is Affaire '
                         'WITH C,N,W BEING (Any C,N,W WHERE C inlined_note N, '
                         'N inlined_affaire W, EXISTS(C require_permission B), '
                         'C is Card, N is Note, W is Affaire)')

    def test_relation_optimization_1_lhs(self):
        # since Card in_state State as monovalued cardinality, the in_state
        # relation used in the rql expression can be ignored and S replaced by
        # the variable from the incoming query
        snippet = ('X in_state S, S name "hop"')
        rqlst = parse(u'Card C WHERE C in_state STATE')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C in_state STATE, C is Card, '
                         'EXISTS(STATE name "hop"), STATE is State')

    def test_relation_optimization_1_rhs(self):
        snippet = ('TW subworkflow_exit X, TW name "hop"')
        rqlst = parse(u'WorkflowTransition C WHERE C subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C subworkflow_exit EXIT, C is WorkflowTransition, '
                         'EXISTS(C name "hop"), EXIT is SubWorkflowExitPoint')

    def test_relation_optimization_2_lhs(self):
        # optional relation can be shared if also optional in the snippet
        snippet = ('X in_state S?, S name "hop"')
        rqlst = parse(u'Card C WHERE C in_state STATE?')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C in_state STATE?, C is Card, '
                         'EXISTS(STATE name "hop"), STATE is State')

    def test_relation_optimization_2_rhs(self):
        snippet = ('TW? subworkflow_exit X, TW name "hop"')
        rqlst = parse(u'SubWorkflowExitPoint EXIT WHERE C? subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any EXIT WHERE C? subworkflow_exit EXIT, EXIT is SubWorkflowExitPoint, '
                         'EXISTS(C name "hop"), C is WorkflowTransition')

    def test_relation_optimization_3_lhs(self):
        # optional relation in the snippet but not in the orig tree can be shared
        snippet = ('X in_state S?, S name "hop"')
        rqlst = parse(u'Card C WHERE C in_state STATE')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C in_state STATE, C is Card, '
                         'EXISTS(STATE name "hop"), STATE is State')

    def test_relation_optimization_3_rhs(self):
        snippet = ('TW? subworkflow_exit X, TW name "hop"')
        rqlst = parse(u'WorkflowTransition C WHERE C subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C subworkflow_exit EXIT, C is WorkflowTransition, '
                         'EXISTS(C name "hop"), EXIT is SubWorkflowExitPoint')

    def test_relation_non_optimization_1_lhs(self):
        # but optional relation in the orig tree but not in the snippet can't be shared
        snippet = ('X in_state S, S name "hop"')
        rqlst = parse(u'Card C WHERE C in_state STATE?')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C in_state STATE?, C is Card, '
                         'EXISTS(C in_state A, A name "hop", A is State), STATE is State')

    def test_relation_non_optimization_1_rhs(self):
        snippet = ('TW subworkflow_exit X, TW name "hop"')
        rqlst = parse(u'SubWorkflowExitPoint EXIT WHERE C? subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any EXIT WHERE C? subworkflow_exit EXIT, EXIT is SubWorkflowExitPoint, '
                         'EXISTS(A subworkflow_exit EXIT, A name "hop", A is WorkflowTransition), '
                         'C is WorkflowTransition')

    def test_relation_non_optimization_2(self):
        """See #3024730"""
        # 'X inlined_note N' must not be shared with 'C inlined_note N'
        # previously inserted, else this may introduce duplicated results, as N
        # will then be shared by multiple EXISTS and so at SQL generation time,
        # the table will be in the FROM clause of the outermost query
        rqlst = parse(u'Any A,C WHERE A inlined_card C')
        rewrite(rqlst, {('A', 'X'): ('X inlined_card C, C inlined_note N, N owned_by U',),
                        ('C', 'X'): ('X inlined_note N, N owned_by U',)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any A,C WHERE A inlined_card C, D eid %(E)s, '
                         'EXISTS(C inlined_note B, B owned_by D, B is Note), '
                         'EXISTS(C inlined_note F, F owned_by D, F is Note), '
                         'A is Affaire, C is Card')

    def test_unsupported_constraint_1(self):
        # CWUser doesn't have require_permission
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse(u'Any U,T WHERE U is CWUser, T wf_info_for U')
        self.assertRaises(Unauthorized, rewrite, rqlst, {('T', 'X'): (trinfo_constraint,)}, {})

    def test_unsupported_constraint_2(self):
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse(u'Any U,T WHERE U is CWUser, T wf_info_for U')
        rewrite(rqlst, {('T', 'X'): (trinfo_constraint,
                                     'X wf_info_for Y, Y in_group G, G name "managers"')}, {})
        self.assertEqual(rqlst.as_string(),
                         u'Any U,T WHERE U is CWUser, T wf_info_for U, '
                         u'EXISTS(U in_group B, B name "managers", B is CWGroup), T is TrInfo')

    def test_unsupported_constraint_3(self):
        self.skipTest('raise unauthorized for now')
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse(u'Any T WHERE T wf_info_for X')
        rewrite(rqlst, {('T', 'X'): (trinfo_constraint, 'X in_group G, G name "managers"')}, {})
        self.assertEqual(rqlst.as_string(),
                         u'XXX dunno what should be generated')

    def test_add_ambiguity_exists(self):
        constraint = ('X concerne Y')
        rqlst = parse(u'Affaire X')
        rewrite(rqlst, {('X', 'X'): (constraint,)}, {})
        self.assertEqual(
            rqlst.as_string(),
            u"Any X WHERE X is Affaire, ((EXISTS(X concerne A, A is Division)) "
            "OR (EXISTS(X concerne C, C is Societe))) OR (EXISTS(X concerne B, B is Note))")

    def test_add_ambiguity_outerjoin(self):
        constraint = ('X concerne Y')
        rqlst = parse(u'Any X,C WHERE X? documented_by C')
        rewrite(rqlst, {('X', 'X'): (constraint,)}, {})
        # ambiguity are kept in the sub-query, no need to be resolved using OR
        self.assertEqual(
            rqlst.as_string(),
            u"Any X,C WHERE X? documented_by C, C is Card "
            "WITH X BEING (Any X WHERE EXISTS(X concerne A), X is Affaire)")

    def test_rrqlexpr_nonexistant_subject_1(self):
        constraint = RRQLExpression('S owned_by U')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.assertEqual(rqlst.as_string(),
                         u"Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A)")
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'OU')
        self.assertEqual(rqlst.as_string(),
                         u"Any C WHERE C is Card")
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SOU')
        self.assertEqual(rqlst.as_string(),
                         u"Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A)")

    def test_rrqlexpr_nonexistant_subject_2(self):
        constraint = RRQLExpression('S owned_by U, O owned_by U, O is Card')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A)')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'OU')
        self.assertEqual(rqlst.as_string(),
                         'Any C WHERE C is Card, B eid %(D)s, EXISTS(A owned_by B, A is Card)')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SOU')
        self.assertEqual(
            rqlst.as_string(),
            'Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A, D owned_by A, D is Card)')

    def test_rrqlexpr_nonexistant_subject_3(self):
        constraint = RRQLExpression('U in_group G, G name "users"')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.assertEqual(
            rqlst.as_string(),
            u'Any C WHERE C is Card, A eid %(B)s, '
            'EXISTS(A in_group D, D name "users", D is CWGroup)')

    def test_rrqlexpr_nonexistant_subject_4(self):
        constraint = RRQLExpression('U in_group G, G name "users", S owned_by U')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.assertEqual(
            rqlst.as_string(),
            u'Any C WHERE C is Card, A eid %(B)s, '
            'EXISTS(A in_group D, D name "users", C owned_by A, D is CWGroup)')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'OU')
        self.assertEqual(
            rqlst.as_string(),
            u'Any C WHERE C is Card, A eid %(B)s, '
            'EXISTS(A in_group D, D name "users", D is CWGroup)')

    def test_rrqlexpr_nonexistant_subject_5(self):
        constraint = RRQLExpression('S owned_by Z, O owned_by Z, O is Card')
        rqlst = parse(u'Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'S')
        self.assertEqual(rqlst.as_string(),
                         u"Any C WHERE C is Card, EXISTS(C owned_by A, A is CWUser)")

    def test_rqlexpr_not_relation_1_1(self):
        constraint = ERQLExpression('X owned_by Z, Z login "hop"', 'X')
        rqlst = parse(u'Affaire A WHERE NOT EXISTS(A documented_by C)')
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {}, 'X')
        self.assertEqual(
            rqlst.as_string(),
            u'Any A WHERE NOT EXISTS(A documented_by C, '
            'EXISTS(C owned_by B, B login "hop", B is CWUser), C is Card), A is Affaire')

    def test_rqlexpr_not_relation_1_2(self):
        constraint = ERQLExpression('X owned_by Z, Z login "hop"', 'X')
        rqlst = parse(u'Affaire A WHERE NOT EXISTS(A documented_by C)')
        rewrite(rqlst, {('A', 'X'): (constraint,)}, {}, 'X')
        self.assertEqual(
            rqlst.as_string(),
            u'Any A WHERE NOT EXISTS(A documented_by C, C is Card), A is Affaire, '
            'EXISTS(A owned_by B, B login "hop", B is CWUser)')

    def test_rqlexpr_not_relation_2(self):
        constraint = ERQLExpression('X owned_by Z, Z login "hop"', 'X')
        rqlst = rqlhelper.parse(u'Affaire A WHERE NOT A documented_by C', annotate=False)
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {}, 'X')
        self.assertEqual(
            rqlst.as_string(),
            u'Any A WHERE NOT EXISTS(A documented_by C, '
            'EXISTS(C owned_by B, B login "hop", B is CWUser), C is Card), A is Affaire')

    def test_rqlexpr_multiexpr_outerjoin(self):
        c1 = ERQLExpression('X owned_by Z, Z login "hop"', 'X')
        c2 = ERQLExpression('X owned_by Z, Z login "hip"', 'X')
        c3 = ERQLExpression('X owned_by Z, Z login "momo"', 'X')
        rqlst = rqlhelper.parse(u'Any A WHERE A documented_by C?', annotate=False)
        rewrite(rqlst, {('C', 'X'): (c1, c2, c3)}, {}, 'X')
        self.assertEqual(
            rqlst.as_string(),
            u'Any A WHERE A documented_by C?, A is Affaire '
            'WITH C BEING (Any C WHERE ((EXISTS(C owned_by B, B login "hop")) '
            'OR (EXISTS(C owned_by D, D login "momo"))) '
            'OR (EXISTS(C owned_by A, A login "hip")), C is Card)')

    def test_multiple_erql_one_bad(self):
        #: reproduce bug #2236985
        #: (rqlrewrite fails to remove rewritten entry for unsupported constraint and then crash)
        #:
        #: This check a very rare code path triggered by the four condition below

        # 1. c_ok introduce an ambiguity
        c_ok = ERQLExpression('X concerne R')
        # 2. c_bad is just plain wrong and won't be kept
        # 3. but it declare a new variable
        # 4. this variable require a rewrite
        c_bad = ERQLExpression('X documented_by R, A in_state R')

        rqlst = parse(u'Any A, R WHERE A ref R, S is Affaire')
        rewrite(rqlst, {('A', 'X'): (c_ok, c_bad)}, {})

    def test_nonregr_is_instance_of(self):
        user_expr = ERQLExpression('NOT X in_group AF, AF name "guests"')
        rqlst = parse(u'Any O WHERE S use_email O, S is CWUser, O is_instance_of EmailAddress')
        rewrite(rqlst, {('S', 'X'): (user_expr,)}, {})
        self.assertEqual(rqlst.as_string(),
                         'Any O WHERE S use_email O, S is CWUser, O is EmailAddress, '
                         'EXISTS(NOT S in_group A, A name "guests", A is CWGroup)')

    def test_ambiguous_constraint_not_exists(self):
        state_constraint = (
            'NOT EXISTS(A require_permission S) '
            'OR EXISTS(B require_permission S, B is Card, O name "state1")'
            'OR EXISTS(C require_permission S, C is Note, O name "state2")'
        )
        rqlst = parse(u'Any P WHERE NOT P require_state S')
        rewrite(rqlst, {('P', 'S'): (state_constraint,), ('S', 'O'): (state_constraint,)}, {})
        self.assertMultiLineEqual(
            rqlst.as_string(),
            u'Any P WHERE NOT P require_state S, '
            '((NOT EXISTS(A require_permission P, A is IN(Card, Note)))'
            ' OR (EXISTS(B require_permission P, B is Card, S name "state1")))'
            ' OR (EXISTS(C require_permission P, C is Note, S name "state2")), '
            'P is CWPermission, S is State')

    def test_ambiguous_using_is_in_function(self):
        state_constraint = (
            'NOT EXISTS(A require_permission S) '
            'OR EXISTS(B require_permission S, B is IN (Card, Note), O name "state1")'
        )
        rqlst = parse(u'Any P WHERE NOT P require_state S')
        rewrite(rqlst, {('P', 'S'): (state_constraint,), ('S', 'O'): (state_constraint,)}, {})
        self.assertMultiLineEqual(
            rqlst.as_string(),
            u'Any P WHERE NOT P require_state S, '
            '(NOT EXISTS(A require_permission P, A is IN(Card, Note))) '
            'OR (EXISTS(B require_permission P, B is IN(Card, Note), S name "state1")), '
            'P is CWPermission, S is State')


class RewriteFullTC(CubicWebTC):
    appid = 'data-rewrite'

    def process(self, rql, args=None):
        if args is None:
            args = {}
        querier = self.repo.querier
        union = parse(rql)  # self.vreg.parse(rql, annotate=True)
        with self.admin_access.repo_cnx() as cnx:
            self.vreg.solutions(cnx, union, args)
            querier._annotate(union)
            plan = querier.plan_factory(union, args, cnx)
            plan.preprocess(union)
            return union

    def test_ambiguous_optional_same_exprs(self):
        """See #3013535"""
        edef1 = self.schema['Societe']
        edef2 = self.schema['Division']
        edef3 = self.schema['Note']
        with self.temporary_permissions((edef1, {'read': (ERQLExpression('X owned_by U'),)}),
                                        (edef2, {'read': (ERQLExpression('X owned_by U'),)}),
                                        (edef3, {'read': (ERQLExpression('X owned_by U'),)})):
            union = self.process('Any A,AR,X,CD WHERE A concerne X?, A ref AR, X creation_date CD')
            self.assertEqual('Any A,AR,X,CD WHERE A concerne X?, A ref AR, A is Affaire '
                             'WITH X,CD BEING (Any X,CD WHERE X creation_date CD, '
                             'EXISTS(X owned_by %(A)s), X is IN(Division, Note, Societe))',
                             union.as_string())

    def test_ambiguous_optional_diff_exprs(self):
        """See #3013554"""
        self.skipTest('bad request generated (may generate duplicated results)')
        edef1 = self.schema['Societe']
        edef2 = self.schema['Division']
        edef3 = self.schema['Note']
        with self.temporary_permissions((edef1, {'read': (ERQLExpression('X created_by U'),)}),
                                        (edef2, {'read': ('users',)}),
                                        (edef3, {'read': (ERQLExpression('X owned_by U'),)})):
            union = self.process('Any A,AR,X,CD WHERE A concerne X?, A ref AR, X creation_date CD')
            self.assertEqual(union.as_string(), 'not generated today')

    def test_xxxx(self):
        edef1 = self.schema['Societe']
        edef2 = self.schema['Division']
        read_expr = ERQLExpression('X responsable E, U has_read_permission E')
        with self.temporary_permissions((edef1, {'read': (read_expr,)}),
                                        (edef2, {'read': (read_expr,)})):
            union = self.process('Any X,AA,AC,AD ORDERBY AD DESC '
                                 'WHERE X responsable E, X nom AA, '
                                 'X responsable AC?, AC modification_date AD')
            self.assertEqual('Any X,AA,AC,AD ORDERBY AD DESC '
                             'WHERE X responsable E, X nom AA, '
                             'X responsable AC?, AC modification_date AD, '
                             'AC is CWUser, E is CWUser, X is IN(Division, Societe)',
                             union.as_string())

    def test_question_mark_attribute_snippet(self):
        # see #3661918
        repotest.undo_monkey_patch()
        orig_insert_snippets = RQLRewriter.insert_snippets
        # patch insert_snippets and not rewrite, insert_snippets is already
        # monkey patches (see above setupModule/repotest)

        @monkeypatch(RQLRewriter)
        def insert_snippets(self, snippets, varexistsmap=None):
            # crash occurs if snippets are processed in a specific order, force
            # destiny
            if snippets[0][0] != {u'N': 'X'}:
                snippets = list(reversed(snippets))
            return orig_insert_snippets(self, snippets, varexistsmap)
        try:
            with self.temporary_permissions(
                    (self.schema['Affaire'],
                     {'read': (ERQLExpression('X ref "blah"'), )}),
                    (self.schema['Note'],
                     {'read': (ERQLExpression(
                         'EXISTS(X inlined_affaire Z), EXISTS(Z owned_by U)'), )}),
            ):
                union = self.process(
                    'Any A,COUNT(N) GROUPBY A '
                    'WHERE A is Affaire, N? inlined_affaire A')
                self.assertEqual('Any A,COUNT(N) GROUPBY A WHERE A is Affaire '
                                 'WITH N,A BEING (Any N,A WHERE N? inlined_affaire A, '
                                 '(N is NULL) OR (EXISTS(EXISTS(N inlined_affaire B), '
                                 'EXISTS(B owned_by %(E)s), B is Affaire)), '
                                 'A is Affaire, N is Note, EXISTS(A ref "blah"))',
                                 union.as_string())
        finally:
            RQLRewriter.insert_snippets = orig_insert_snippets


class RQLRelationRewriterTC(TestCase):
    # XXX valid rules: S and O specified, not in a SET, INSERT, DELETE scope
    #     valid uses: no outer join

    # Basic tests
    def test_base_rule(self):
        rules = {'participated_in': 'S contributor O'}
        rqlst = rqlhelper.parse(u'Any X WHERE X participated_in S')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any X WHERE X contributor S',
                         rqlst.as_string())

    def test_complex_rule_1(self):
        rules = {'illustrator_of': ('C is Contribution, C contributor S, '
                                    'C manifestation O, C role R, '
                                    'R name "illustrator"')}
        rqlst = rqlhelper.parse(u'Any A,B WHERE A illustrator_of B')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE C is Contribution, '
                         'C contributor A, C manifestation B, '
                         'C role D, D name "illustrator"',
                         rqlst.as_string())

    def test_complex_rule_2(self):
        rules = {'illustrator_of': ('C is Contribution, C contributor S, '
                                    'C manifestation O, C role R, '
                                    'R name "illustrator"')}
        rqlst = rqlhelper.parse(u'Any A WHERE EXISTS(A illustrator_of B)')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A WHERE EXISTS(C is Contribution, '
                         'C contributor A, C manifestation B, '
                         'C role D, D name "illustrator")',
                         rqlst.as_string())

    def test_rewrite2(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'Any A,B WHERE A illustrator_of B, C require_permission R, S'
                                'require_state O')
        rule_rewrite(rqlst, rules)
        self.assertEqual(
            'Any A,B WHERE C require_permission R, S require_state O, '
            'D is Contribution, D contributor A, D manifestation B, D role E, '
            'E name "illustrator"',
            rqlst.as_string())

    def test_rewrite3(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'Any A,B WHERE E require_permission T, A illustrator_of B')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE E require_permission T, '
                         'C is Contribution, C contributor A, C manifestation B, '
                         'C role D, D name "illustrator"',
                         rqlst.as_string())

    def test_rewrite4(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'Any A,B WHERE C require_permission R, A illustrator_of B')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE C require_permission R, '
                         'D is Contribution, D contributor A, D manifestation B, '
                         'D role E, E name "illustrator"',
                         rqlst.as_string())

    def test_rewrite5(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'Any A,B WHERE C require_permission R, A illustrator_of B, '
                                'S require_state O')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE C require_permission R, S require_state O, '
                         'D is Contribution, D contributor A, D manifestation B, D role E, '
                         'E name "illustrator"',
                         rqlst.as_string())

    # Tests for the with clause
    def test_rewrite_with(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'Any A,B WITH A, B BEING(Any X, Y WHERE X illustrator_of Y)')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WITH A,B BEING '
                         '(Any X,Y WHERE A is Contribution, A contributor X, '
                         'A manifestation Y, A role B, B name "illustrator")',
                         rqlst.as_string())

    def test_rewrite_with2(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'Any A,B WHERE T require_permission C '
                                'WITH A, B BEING(Any X, Y WHERE X illustrator_of Y)')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE T require_permission C '
                         'WITH A,B BEING (Any X,Y WHERE A is Contribution, '
                         'A contributor X, A manifestation Y, A role B, B name "illustrator")',
                         rqlst.as_string())

    def test_rewrite_with3(self):
        rules = {'participated_in': 'S contributor O'}
        rqlst = rqlhelper.parse(u'Any A,B WHERE A participated_in B '
                                'WITH A, B BEING(Any X,Y WHERE X contributor Y)')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE A contributor B WITH A,B BEING '
                         '(Any X,Y WHERE X contributor Y)',
                         rqlst.as_string())

    def test_rewrite_with4(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'Any A,B WHERE A illustrator_of B '
                                'WITH A, B BEING(Any X, Y WHERE X illustrator_of Y)')
        rule_rewrite(rqlst, rules)
        self.assertEqual(
            'Any A,B WHERE C is Contribution, '
            'C contributor A, C manifestation B, C role D, '
            'D name "illustrator" WITH A,B BEING '
            '(Any X,Y WHERE A is Contribution, A contributor X, '
            'A manifestation Y, A role B, B name "illustrator")',
            rqlst.as_string())

    # Tests for the union
    def test_rewrite_union(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'(Any A,B WHERE A illustrator_of B) UNION'
                                '(Any X,Y WHERE X is CWUser, Z manifestation Y)')
        rule_rewrite(rqlst, rules)
        self.assertEqual(
            '(Any A,B WHERE C is Contribution, '
            'C contributor A, C manifestation B, C role D, '
            'D name "illustrator") UNION (Any X,Y WHERE X is CWUser, Z manifestation Y)',
            rqlst.as_string())

    def test_rewrite_union2(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'(Any Y WHERE Y match W) UNION '
                                '(Any A WHERE A illustrator_of B) UNION '
                                '(Any Y WHERE Y is ArtWork)')
        rule_rewrite(rqlst, rules)
        self.assertEqual('(Any Y WHERE Y match W) '
                         'UNION (Any A WHERE C is Contribution, C contributor A, '
                         'C manifestation B, C role D, D name "illustrator") '
                         'UNION (Any Y WHERE Y is ArtWork)',
                         rqlst.as_string())

    # Tests for the exists clause
    def test_rewrite_exists(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'(Any A,B WHERE A illustrator_of B, '
                                'EXISTS(B is ArtWork))')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE EXISTS(B is ArtWork), '
                         'C is Contribution, C contributor A, C manifestation B, C role D, '
                         'D name "illustrator"',
                         rqlst.as_string())

    def test_rewrite_exists2(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'(Any A,B WHERE B contributor A, EXISTS(A illustrator_of W))')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE B contributor A, '
                         'EXISTS(C is Contribution, C contributor A, C manifestation W, '
                         'C role D, D name "illustrator")',
                         rqlst.as_string())

    def test_rewrite_exists3(self):
        rules = {'illustrator_of': 'C is Contribution, C contributor S, '
                 'C manifestation O, C role R, R name "illustrator"'}
        rqlst = rqlhelper.parse(u'(Any A,B WHERE A illustrator_of B, EXISTS(A illustrator_of W))')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any A,B WHERE EXISTS(C is Contribution, C contributor A, '
                         'C manifestation W, C role D, D name "illustrator"), '
                         'E is Contribution, E contributor A, E manifestation B, E role F, '
                         'F name "illustrator"',
                         rqlst.as_string())

    # Test for GROUPBY
    def test_rewrite_groupby(self):
        rules = {'participated_in': 'S contributor O'}
        rqlst = rqlhelper.parse(u'Any SUM(SA) GROUPBY S '
                                'WHERE P participated_in S, P manifestation SA')
        rule_rewrite(rqlst, rules)
        self.assertEqual('Any SUM(SA) GROUPBY S WHERE P manifestation SA, P contributor S',
                         rqlst.as_string())


class RQLRelationRewriterCWTC(CubicWebTC):

    appid = 'data-rewrite'

    def test_base_rule(self):
        with self.admin_access.client_cnx() as cnx:
            art = cnx.create_entity('ArtWork', name=u'Les travailleurs de la Mer')
            role = cnx.create_entity('Role', name=u'illustrator')
            vic = cnx.create_entity('Person', name=u'Victor Hugo')
            cnx.create_entity('Contribution', code=96, contributor=vic,
                              manifestation=art, role=role)
            rset = cnx.execute('Any X WHERE X illustrator_of S')
            self.assertEqual([u'Victor Hugo'],
                             [result.name for result in rset.entities()])
            rset = cnx.execute('Any S WHERE X illustrator_of S, X eid %(x)s',
                               {'x': vic.eid})
            self.assertEqual([u'Les travailleurs de la Mer'],
                             [result.name for result in rset.entities()])


def rule_rewrite(rqlst, kwargs=None):
    rewriter = _prepare_rewriter(rqlrewrite.RQLRelationRewriter, kwargs)
    rqlhelper.compute_solutions(rqlst.children[0], {'eid': eid_func_map},
                                kwargs=kwargs)
    rewriter.rewrite(rqlst)
    for select in rqlst.children:
        check_vrefs(select)
    return rewriter.rewritten


if __name__ == '__main__':
    import unittest
    unittest.main()
