# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from logilab.common.testlib import unittest_main, TestCase
from logilab.common.testlib import mock_object
from yams import BadSchemaDefinition
from rql import parse, nodes, RQLHelper

from cubicweb import Unauthorized
from cubicweb.schema import RRQLExpression, ERQLExpression
from cubicweb.rqlrewrite import RQLRewriter
from cubicweb.devtools import repotest, TestServerConfiguration


def setUpModule(*args):
    global rqlhelper, schema
    config = TestServerConfiguration(RQLRewriteTC.datapath('rewrite'))
    config.bootstrap_cubes()
    schema = config.load_schema()
    from yams.buildobjs import RelationDefinition
    schema.add_relation_def(RelationDefinition(subject='Card', name='in_state', object='State', cardinality='1*'))

    rqlhelper = RQLHelper(schema, special_relations={'eid': 'uid',
                                                     'has_text': 'fti'})
    repotest.do_monkey_patch()

def tearDownModule(*args):
    repotest.undo_monkey_patch()
    global rqlhelper, schema
    del rqlhelper, schema

def eid_func_map(eid):
    return {1: 'CWUser',
            2: 'Card'}[eid]

def rewrite(rqlst, snippets_map, kwargs, existingvars=None):
    class FakeVReg:
        schema = schema
        @staticmethod
        def solutions(sqlcursor, mainrqlst, kwargs):
            rqlhelper.compute_solutions(rqlst, {'eid': eid_func_map}, kwargs=kwargs)
        class rqlhelper:
            @staticmethod
            def annotate(rqlst):
                rqlhelper.annotate(rqlst)
            @staticmethod
            def simplify(mainrqlst, needcopy=False):
                rqlhelper.simplify(rqlst, needcopy)
    rewriter = RQLRewriter(mock_object(vreg=FakeVReg, user=(mock_object(eid=1))))
    snippets = []
    for v, exprs in snippets_map.items():
        rqlexprs = [isinstance(snippet, basestring)
                    and mock_object(snippet_rqlst=parse('Any X WHERE '+snippet).children[0],
                                    expression='Any X WHERE '+snippet)
                    or snippet
                    for snippet in exprs]
        snippets.append((dict([v]), rqlexprs))
    rqlhelper.compute_solutions(rqlst.children[0], {'eid': eid_func_map}, kwargs=kwargs)
    solutions = rqlst.children[0].solutions
    rewriter.rewrite(rqlst.children[0], snippets, solutions, kwargs,
                     existingvars)
    test_vrefs(rqlst.children[0])
    return rewriter.rewritten

def test_vrefs(node):
    vrefmap = {}
    for vref in node.iget_nodes(nodes.VariableRef):
        vrefmap.setdefault(vref.name, set()).add(vref)
    for var in node.defined_vars.itervalues():
        assert not (var.stinfo['references'] ^ vrefmap[var.name])
        assert (var.stinfo['references'])

class RQLRewriteTC(TestCase):
    """a faire:

    * optimisation: detecter les relations utilisees dans les rqlexpressions qui
      sont presentes dans la requete de depart pour les reutiliser si possible

    * "has_<ACTION>_permission" ?
    """

    def test_base_var(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'X'): (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any C WHERE C is Card, B eid %(D)s, "
                             "EXISTS(C in_state A, B in_group E, F require_state A, "
                             "F name 'read', F require_group E, A is State, E is CWGroup, F is CWPermission)")

    def test_multiple_var(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        affaire_constraints = ('X ref LIKE "PUBLIC%"', 'U in_group G, G name "public"')
        kwargs = {'u':2}
        rqlst = parse('Any S WHERE S documented_by C, C eid %(u)s')
        rewrite(rqlst, {('C', 'X'): (card_constraint,), ('S', 'X'): affaire_constraints},
                kwargs)
        self.assertMultiLineEqual(rqlst.as_string(),
                             "Any S WHERE S documented_by C, C eid %(u)s, B eid %(D)s, "
                             "EXISTS(C in_state A, B in_group E, F require_state A, "
                             "F name 'read', F require_group E, A is State, E is CWGroup, F is CWPermission), "
                             "(EXISTS(S ref LIKE 'PUBLIC%')) OR (EXISTS(B in_group G, G name 'public', G is CWGroup)), "
                             "S is Affaire")
        self.failUnless('D' in kwargs)

    def test_or(self):
        constraint = '(X identity U) OR (X in_state ST, CL identity U, CL in_state ST, ST name "subscribed")'
        rqlst = parse('Any S WHERE S owned_by C, C eid %(u)s, S is in (CWUser, CWGroup)')
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {'u':1})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any S WHERE S owned_by C, C eid %(u)s, S is IN(CWUser, CWGroup), A eid %(B)s, "
                             "EXISTS((C identity A) OR (C in_state D, E identity A, "
                             "E in_state D, D name 'subscribed'), D is State, E is CWUser)")

    def test_simplified_rqlst(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        rqlst = parse('Any 2') # this is the simplified rql st for Any X WHERE X eid 12
        rewrite(rqlst, {('2', 'X'): (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any 2 WHERE B eid %(C)s, "
                             "EXISTS(2 in_state A, B in_group D, E require_state A, "
                             "E name 'read', E require_group D, A is State, D is CWGroup, E is CWPermission)")

    def test_optional_var_base(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        rqlst = parse('Any A,C WHERE A documented_by C?')
        rewrite(rqlst, {('C', 'X'): (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any A,C WHERE A documented_by C?, A is Affaire "
                             "WITH C BEING "
                             "(Any C WHERE EXISTS(C in_state B, D in_group F, G require_state B, G name 'read', "
                             "G require_group F), D eid %(A)s, C is Card)")
        rqlst = parse('Any A,C,T WHERE A documented_by C?, C title T')
        rewrite(rqlst, {('C', 'X'): (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any A,C,T WHERE A documented_by C?, A is Affaire "
                             "WITH C,T BEING "
                             "(Any C,T WHERE C title T, EXISTS(C in_state B, D in_group F, "
                             "G require_state B, G name 'read', G require_group F), "
                             "D eid %(A)s, C is Card)")

    def test_optional_var_inlined(self):
        c1 = ('X require_permission P')
        c2 = ('X inlined_card O, O require_permission P')
        rqlst = parse('Any C,A,R WHERE A? inlined_card C, A ref R')
        rewrite(rqlst, {('C', 'X'): (c1,),
                        ('A', 'X'): (c2,),
                        }, {})
        # XXX suboptimal
        self.failUnlessEqual(rqlst.as_string(),
                             "Any C,A,R WITH A,R,C BEING "
                             "(Any A,R,C WHERE A ref R, A? inlined_card C, "
                             "(A is NULL) OR (EXISTS(A inlined_card B, B require_permission D, "
                             "B is Card, D is CWPermission)), "
                             "A is Affaire, C is Card, EXISTS(C require_permission E, E is CWPermission))")

    # def test_optional_var_inlined_has_perm(self):
    #     c1 = ('X require_permission P')
    #     c2 = ('X inlined_card O, U has_read_permission O')
    #     rqlst = parse('Any C,A,R WHERE A? inlined_card C, A ref R')
    #     rewrite(rqlst, {('C', 'X'): (c1,),
    #                     ('A', 'X'): (c2,),
    #                     }, {})
    #     self.failUnlessEqual(rqlst.as_string(),
    #                          "")

    def test_optional_var_inlined_imbricated_error(self):
        c1 = ('X require_permission P')
        c2 = ('X inlined_card O, O require_permission P')
        rqlst = parse('Any C,A,R,A2,R2 WHERE A? inlined_card C, A ref R,A2? inlined_card C, A2 ref R2')
        self.assertRaises(BadSchemaDefinition,
                          rewrite, rqlst, {('C', 'X'): (c1,),
                                           ('A', 'X'): (c2,),
                                           ('A2', 'X'): (c2,),
                                           }, {})

    def test_relation_optimization_1_lhs(self):
        # since Card in_state State as monovalued cardinality, the in_state
        # relation used in the rql expression can be ignored and S replaced by
        # the variable from the incoming query
        snippet = ('X in_state S, S name "hop"')
        rqlst = parse('Card C WHERE C in_state STATE')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any C WHERE C in_state STATE, C is Card, "
                             "EXISTS(STATE name 'hop'), STATE is State")
    def test_relation_optimization_1_rhs(self):
        snippet = ('TW subworkflow_exit X, TW name "hop"')
        rqlst = parse('WorkflowTransition C WHERE C subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any C WHERE C subworkflow_exit EXIT, C is WorkflowTransition, "
                             "EXISTS(C name 'hop'), EXIT is SubWorkflowExitPoint")

    def test_relation_optimization_2_lhs(self):
        # optional relation can be shared if also optional in the snippet
        snippet = ('X in_state S?, S name "hop"')
        rqlst = parse('Card C WHERE C in_state STATE?')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any C WHERE C in_state STATE?, C is Card, "
                             "EXISTS(STATE name 'hop'), STATE is State")
    def test_relation_optimization_2_rhs(self):
        snippet = ('TW? subworkflow_exit X, TW name "hop"')
        rqlst = parse('SubWorkflowExitPoint EXIT WHERE C? subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any EXIT WHERE C? subworkflow_exit EXIT, EXIT is SubWorkflowExitPoint, "
                             "EXISTS(C name 'hop'), C is WorkflowTransition")

    def test_relation_optimization_3_lhs(self):
        # optional relation in the snippet but not in the orig tree can be shared
        snippet = ('X in_state S?, S name "hop"')
        rqlst = parse('Card C WHERE C in_state STATE')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any C WHERE C in_state STATE, C is Card, "
                             "EXISTS(STATE name 'hop'), STATE is State")
    def test_relation_optimization_3_rhs(self):
        snippet = ('TW? subworkflow_exit X, TW name "hop"')
        rqlst = parse('WorkflowTransition C WHERE C subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any C WHERE C subworkflow_exit EXIT, C is WorkflowTransition, "
                             "EXISTS(C name 'hop'), EXIT is SubWorkflowExitPoint")

    def test_relation_non_optimization_1_lhs(self):
        # but optional relation in the orig tree but not in the snippet can't be shared
        snippet = ('X in_state S, S name "hop"')
        rqlst = parse('Card C WHERE C in_state STATE?')
        rewrite(rqlst, {('C', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any C WHERE C in_state STATE?, C is Card, "
                             "EXISTS(C in_state A, A name 'hop', A is State), STATE is State")
    def test_relation_non_optimization_1_rhs(self):
        snippet = ('TW subworkflow_exit X, TW name "hop"')
        rqlst = parse('SubWorkflowExitPoint EXIT WHERE C? subworkflow_exit EXIT')
        rewrite(rqlst, {('EXIT', 'X'): (snippet,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any EXIT WHERE C? subworkflow_exit EXIT, EXIT is SubWorkflowExitPoint, "
                             "EXISTS(A subworkflow_exit EXIT, A name 'hop', A is WorkflowTransition), "
                             "C is WorkflowTransition")

    def test_unsupported_constraint_1(self):
        # CWUser doesn't have require_permission
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse('Any U,T WHERE U is CWUser, T wf_info_for U')
        self.assertRaises(Unauthorized, rewrite, rqlst, {('T', 'X'): (trinfo_constraint,)}, {})

    def test_unsupported_constraint_2(self):
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse('Any U,T WHERE U is CWUser, T wf_info_for U')
        rewrite(rqlst, {('T', 'X'): (trinfo_constraint, 'X wf_info_for Y, Y in_group G, G name "managers"')}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any U,T WHERE U is CWUser, T wf_info_for U, "
                             "EXISTS(U in_group B, B name 'managers', B is CWGroup), T is TrInfo")

    def test_unsupported_constraint_3(self):
        self.skipTest('raise unauthorized for now')
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse('Any T WHERE T wf_info_for X')
        rewrite(rqlst, {('T', 'X'): (trinfo_constraint, 'X in_group G, G name "managers"')}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u'XXX dunno what should be generated')

    def test_add_ambiguity_exists(self):
        constraint = ('X concerne Y')
        rqlst = parse('Affaire X')
        rewrite(rqlst, {('X', 'X'): (constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any X WHERE X is Affaire, ((EXISTS(X concerne A, A is Division)) OR (EXISTS(X concerne C, C is Societe))) OR (EXISTS(X concerne B, B is Note))")

    def test_add_ambiguity_outerjoin(self):
        constraint = ('X concerne Y')
        rqlst = parse('Any X,C WHERE X? documented_by C')
        rewrite(rqlst, {('X', 'X'): (constraint,)}, {})
        # ambiguity are kept in the sub-query, no need to be resolved using OR
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any X,C WHERE X? documented_by C, C is Card WITH X BEING (Any X WHERE EXISTS(X concerne A), X is Affaire)")


    def test_rrqlexpr_nonexistant_subject_1(self):
        constraint = RRQLExpression('S owned_by U')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A)")
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'OU')
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any C WHERE C is Card")
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SOU')
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A)")

    def test_rrqlexpr_nonexistant_subject_2(self):
        constraint = RRQLExpression('S owned_by U, O owned_by U, O is Card')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.failUnlessEqual(rqlst.as_string(),
                             'Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A)')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'OU')
        self.failUnlessEqual(rqlst.as_string(),
                             'Any C WHERE C is Card, B eid %(D)s, EXISTS(A owned_by B, A is Card)')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SOU')
        self.failUnlessEqual(rqlst.as_string(),
                             'Any C WHERE C is Card, A eid %(B)s, EXISTS(C owned_by A, D owned_by A, D is Card)')

    def test_rrqlexpr_nonexistant_subject_3(self):
        constraint = RRQLExpression('U in_group G, G name "users"')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.failUnlessEqual(rqlst.as_string(),
                             u'Any C WHERE C is Card, A eid %(B)s, EXISTS(A in_group D, D name "users", D is CWGroup)')

    def test_rrqlexpr_nonexistant_subject_4(self):
        constraint = RRQLExpression('U in_group G, G name "users", S owned_by U')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'SU')
        self.failUnlessEqual(rqlst.as_string(),
                             u'Any C WHERE C is Card, A eid %(B)s, EXISTS(A in_group D, D name "users", C owned_by A, D is CWGroup)')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'OU')
        self.failUnlessEqual(rqlst.as_string(),
                             u'Any C WHERE C is Card, A eid %(B)s, EXISTS(A in_group D, D name "users", D is CWGroup)')

    def test_rrqlexpr_nonexistant_subject_5(self):
        constraint = RRQLExpression('S owned_by Z, O owned_by Z, O is Card')
        rqlst = parse('Card C')
        rewrite(rqlst, {('C', 'S'): (constraint,)}, {}, 'S')
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any C WHERE C is Card, EXISTS(C owned_by A, A is CWUser)")

    def test_rqlexpr_not_relation_1_1(self):
        constraint = RRQLExpression('X owned_by Z, Z login "hop"', 'X')
        rqlst = parse('Affaire A WHERE NOT EXISTS(A documented_by C)')
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {}, 'X')
        self.failUnlessEqual(rqlst.as_string(),
                             u'Any A WHERE NOT EXISTS(A documented_by C, EXISTS(C owned_by B, B login "hop", B is CWUser), C is Card), A is Affaire')

    def test_rqlexpr_not_relation_1_2(self):
        constraint = RRQLExpression('X owned_by Z, Z login "hop"', 'X')
        rqlst = parse('Affaire A WHERE NOT EXISTS(A documented_by C)')
        rewrite(rqlst, {('A', 'X'): (constraint,)}, {}, 'X')
        self.failUnlessEqual(rqlst.as_string(),
                             u'Any A WHERE NOT EXISTS(A documented_by C, C is Card), A is Affaire, EXISTS(A owned_by B, B login "hop", B is CWUser)')

    def test_rqlexpr_not_relation_2(self):
        constraint = RRQLExpression('X owned_by Z, Z login "hop"', 'X')
        rqlst = rqlhelper.parse('Affaire A WHERE NOT A documented_by C', annotate=False)
        rewrite(rqlst, {('C', 'X'): (constraint,)}, {}, 'X')
        self.failUnlessEqual(rqlst.as_string(),
                             u'Any A WHERE NOT EXISTS(A documented_by C, EXISTS(C owned_by B, B login "hop", B is CWUser), C is Card), A is Affaire')


if __name__ == '__main__':
    unittest_main()
