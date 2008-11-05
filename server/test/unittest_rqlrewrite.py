from logilab.common.testlib import unittest_main, TestCase
from logilab.common.testlib import mock_object

from rql import parse, nodes, RQLHelper

from cubicweb import Unauthorized
from cubicweb.server.rqlrewrite import RQLRewriter
from cubicweb.devtools import repotest, TestServerConfiguration

config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()
schema.add_relation_def(mock_object(subject='Card', name='in_state', object='State', cardinality='1*'))
                        
rqlhelper = RQLHelper(schema, special_relations={'eid': 'uid',
                                                 'has_text': 'fti'})

def setup_module(*args):
    repotest.do_monkey_patch()

def teardown_module(*args):
    repotest.undo_monkey_patch()
    
def eid_func_map(eid):
    return {1: 'EUser',
            2: 'Card'}[eid]

def rewrite(rqlst, snippets_map, kwargs):
    class FakeQuerier:
        schema = schema
        @staticmethod
        def solutions(sqlcursor, mainrqlst, kwargs):
            rqlhelper.compute_solutions(rqlst, {'eid': eid_func_map}, kwargs=kwargs)
        class _rqlhelper:
            @staticmethod
            def annotate(rqlst):
                rqlhelper.annotate(rqlst)
            @staticmethod
            def simplify(mainrqlst, needcopy=False):
                rqlhelper.simplify(rqlst, needcopy)
    rewriter = RQLRewriter(FakeQuerier, mock_object(user=(mock_object(eid=1))))
    for v, snippets in snippets_map.items():
        snippets_map[v] = [mock_object(snippet_rqlst=parse('Any X WHERE '+snippet).children[0],
                                       expression='Any X WHERE '+snippet) 
                           for snippet in snippets]
    rqlhelper.compute_solutions(rqlst.children[0], {'eid': eid_func_map}, kwargs=kwargs)
    solutions = rqlst.children[0].solutions
    rewriter.rewrite(rqlst.children[0], snippets_map.items(), solutions, kwargs)
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
        rewrite(rqlst, {'C': (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any C WHERE C is Card, B eid %(D)s, "
                             "EXISTS(C in_state A, B in_group E, F require_state A, "
                             "F name 'read', F require_group E, A is State, E is EGroup, F is EPermission)")
        
    def test_multiple_var(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        affaire_constraints = ('X ref LIKE "PUBLIC%"', 'U in_group G, G name "public"')
        kwargs = {'u':2}
        rqlst = parse('Any S WHERE S documented_by C, C eid %(u)s')
        rewrite(rqlst, {'C': (card_constraint,), 'S': affaire_constraints},
                kwargs)
        self.assertTextEquals(rqlst.as_string(),
                             "Any S WHERE S documented_by C, C eid %(u)s, B eid %(D)s, "
                             "EXISTS(C in_state A, B in_group E, F require_state A, "
                             "F name 'read', F require_group E, A is State, E is EGroup, F is EPermission), "
                             "(EXISTS(S ref LIKE 'PUBLIC%')) OR (EXISTS(B in_group G, G name 'public', G is EGroup)), "
                             "S is Affaire")
        self.failUnless('D' in kwargs)
        
    def test_or(self):
        constraint = '(X identity U) OR (X in_state ST, CL identity U, CL in_state ST, ST name "subscribed")'
        rqlst = parse('Any S WHERE S owned_by C, C eid %(u)s')
        rewrite(rqlst, {'C': (constraint,)}, {'u':1})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any S WHERE S owned_by C, C eid %(u)s, A eid %(B)s, "
                             "EXISTS((C identity A) OR (C in_state D, E identity A, "
                             "E in_state D, D name 'subscribed'), D is State, E is EUser), "
                             "S is IN(Affaire, Basket, Bookmark, Card, Comment, Division, EConstraint, EConstraintType, EEType, EFRDef, EGroup, ENFRDef, EPermission, EProperty, ERType, EUser, Email, EmailAddress, EmailPart, EmailThread, File, Folder, Image, Note, Personne, RQLExpression, Societe, State, SubDivision, Tag, TrInfo, Transition)")

    def test_simplified_rqlst(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        rqlst = parse('Any 2') # this is the simplified rql st for Any X WHERE X eid 12
        rewrite(rqlst, {'2': (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any 2 WHERE B eid %(C)s, "
                             "EXISTS(2 in_state A, B in_group D, E require_state A, "
                             "E name 'read', E require_group D, A is State, D is EGroup, E is EPermission)")

    def test_optional_var(self):
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        rqlst = parse('Any A,C WHERE A documented_by C?')
        rewrite(rqlst, {'C': (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any A,C WHERE A documented_by C?, A is Affaire "
                             "WITH C BEING "
                             "(Any C WHERE C in_state B, D in_group F, G require_state B, G name 'read', "
                             "G require_group F, D eid %(A)s, C is Card)")
        rqlst = parse('Any A,C,T WHERE A documented_by C?, C title T')
        rewrite(rqlst, {'C': (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             "Any A,C,T WHERE A documented_by C?, A is Affaire "
                             "WITH C,T BEING "
                             "(Any C,T WHERE C in_state B, D in_group F, G require_state B, G name 'read', "
                             "G require_group F, C title T, D eid %(A)s, C is Card)")
        
    def test_relation_optimization(self):
        # since Card in_state State as monovalued cardinality, the in_state
        # relation used in the rql expression can be ignored and S replaced by
        # the variable from the incoming query
        card_constraint = ('X in_state S, U in_group G, P require_state S,'
                           'P name "read", P require_group G')
        rqlst = parse('Card C WHERE C in_state STATE')
        rewrite(rqlst, {'C': (card_constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any C WHERE C in_state STATE, C is Card, A eid %(B)s, "
                             "EXISTS(A in_group D, E require_state STATE, "
                             "E name 'read', E require_group D, D is EGroup, E is EPermission), "
                             "STATE is State")

    def test_unsupported_constraint_1(self):
        # EUser doesn't have require_permission
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse('Any U,T WHERE U is EUser, T wf_info_for U')
        self.assertRaises(Unauthorized, rewrite, rqlst, {'T': (trinfo_constraint,)}, {})
        
    def test_unsupported_constraint_2(self):
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse('Any U,T WHERE U is EUser, T wf_info_for U')
        rewrite(rqlst, {'T': (trinfo_constraint, 'X wf_info_for Y, Y in_group G, G name "managers"')}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any U,T WHERE U is EUser, T wf_info_for U, "
                             "EXISTS(U in_group B, B name 'managers', B is EGroup), T is TrInfo")

    def test_unsupported_constraint_3(self):
        self.skip('raise unauthorized for now')
        trinfo_constraint = ('X wf_info_for Y, Y require_permission P, P name "read"')
        rqlst = parse('Any T WHERE T wf_info_for X')
        rewrite(rqlst, {'T': (trinfo_constraint, 'X in_group G, G name "managers"')}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u'XXX dunno what should be generated')
        
    def test_add_ambiguity_exists(self):
        constraint = ('X concerne Y')
        rqlst = parse('Affaire X')
        rewrite(rqlst, {'X': (constraint,)}, {})
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any X WHERE X is Affaire, (((EXISTS(X concerne A, A is Division)) OR (EXISTS(X concerne D, D is SubDivision))) OR (EXISTS(X concerne C, C is Societe))) OR (EXISTS(X concerne B, B is Note))")
        
    def test_add_ambiguity_outerjoin(self):
        constraint = ('X concerne Y')
        rqlst = parse('Any X,C WHERE X? documented_by C')
        rewrite(rqlst, {'X': (constraint,)}, {})
        # ambiguity are kept in the sub-query, no need to be resolved using OR
        self.failUnlessEqual(rqlst.as_string(),
                             u"Any X,C WHERE X? documented_by C, C is Card WITH X BEING (Any X WHERE X concerne A, X is Affaire)") 
       
        
        
if __name__ == '__main__':
    unittest_main()
