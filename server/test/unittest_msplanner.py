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
"""unit tests for module cubicweb.server.msplanner"""

from logilab.common.decorators import clear_cache
from yams.buildobjs import RelationDefinition
from rql import BadRQLQuery

from cubicweb.devtools import get_test_db_handler, TestServerConfiguration
from cubicweb.devtools.repotest import BasePlannerTC, test_plan

class _SetGenerator(object):
    """singleton to easily create set using "s[0]" or "s[0,1,2]" for instance
    """
    def __getitem__(self, key):
        try:
            it = iter(key)
        except TypeError:
            it = (key,)
        return set(it)
s = _SetGenerator()

from cubicweb.schema import ERQLExpression
from cubicweb.server.sources import AbstractSource
from cubicweb.server.msplanner import MSPlanner, PartPlanInformation

class FakeUserROSource(AbstractSource):
    support_entities = {'CWUser': False}
    support_relations = {}
    def syntax_tree_search(self, *args, **kwargs):
        return []


class FakeCardSource(AbstractSource):
    support_entities = {'Card': True, 'Note': True, 'State': True}
    support_relations = {'in_state': True, 'multisource_rel': True, 'multisource_inlined_rel': True,
                         'multisource_crossed_rel': True,}
    dont_cross_relations = set(('fiche', 'state_of'))
    cross_relations = set(('multisource_crossed_rel',))

    def syntax_tree_search(self, *args, **kwargs):
        return []


class FakeDataFeedSource(FakeCardSource):
    copy_based_source = True

X_ALL_SOLS = sorted([{'X': 'Affaire'}, {'X': 'BaseTransition'}, {'X': 'Basket'},
                     {'X': 'Bookmark'}, {'X': 'CWAttribute'}, {'X': 'CWCache'},
                     {'X': 'CWConstraint'}, {'X': 'CWConstraintType'}, {'X': 'CWDataImport'}, {'X': 'CWEType'},
                     {'X': 'CWGroup'}, {'X': 'CWPermission'}, {'X': 'CWProperty'},
                     {'X': 'CWRType'}, {'X': 'CWRelation'},
                     {'X': 'CWSource'}, {'X': 'CWSourceHostConfig'}, {'X': 'CWSourceSchemaConfig'},
                     {'X': 'CWUser'}, {'X': 'CWUniqueTogetherConstraint'},
                     {'X': 'Card'}, {'X': 'Comment'}, {'X': 'Division'},
                     {'X': 'Email'}, {'X': 'EmailAddress'}, {'X': 'EmailPart'},
                     {'X': 'EmailThread'}, {'X': 'ExternalUri'}, {'X': 'File'},
                     {'X': 'Folder'}, {'X': 'Note'}, {'X': 'Old'},
                     {'X': 'Personne'}, {'X': 'RQLExpression'}, {'X': 'Societe'},
                     {'X': 'State'}, {'X': 'SubDivision'}, {'X': 'SubWorkflowExitPoint'},
                     {'X': 'Tag'}, {'X': 'TrInfo'}, {'X': 'Transition'},
                     {'X': 'Workflow'}, {'X': 'WorkflowTransition'}])


# keep cnx so it's not garbage collected and the associated session is closed
def setUpModule(*args):
    global repo, cnx
    handler = get_test_db_handler(TestServerConfiguration(apphome=BaseMSPlannerTC.datadir))
    handler.build_db_cache()
    repo, cnx = handler.get_repo_and_cnx()

def tearDownModule(*args):
    global repo, cnx
    del repo, cnx


class BaseMSPlannerTC(BasePlannerTC):
    """test planner related feature on a 3-sources repository:

    * system source supporting everything
    * ldap source supporting CWUser
    * rql source supporting Card
    """

    def setUp(self):
        self.__class__.repo = repo
        #_QuerierTC.setUp(self)
        self.setup()
        # hijack Affaire security
        affreadperms = list(self.schema['Affaire'].permissions['read'])
        self.prevrqlexpr_affaire = affreadperms[-1]
        # add access to type attribute so S can't be invariant
        affreadperms[-1] = ERQLExpression('X concerne S?, S owned_by U, S type "X"')
        self.schema['Affaire'].set_action_permissions('read', affreadperms)
        # hijack CWUser security
        userreadperms = list(self.schema['CWUser'].permissions['read'])
        self.prevrqlexpr_user = userreadperms[-1]
        userreadperms[-1] = ERQLExpression('X owned_by U')
        self.schema['CWUser'].set_action_permissions('read', userreadperms)
        self.add_source(FakeUserROSource, 'ldap')
        self.add_source(FakeCardSource, 'cards')
        self.add_source(FakeDataFeedSource, 'datafeed')

    def tearDown(self):
        # restore hijacked security
        self.restore_orig_affaire_security()
        self.restore_orig_cwuser_security()
        super(BaseMSPlannerTC, self).tearDown()

    def restore_orig_affaire_security(self):
        affreadperms = list(self.schema['Affaire'].permissions['read'])
        affreadperms[-1] = self.prevrqlexpr_affaire
        self.schema['Affaire'].set_action_permissions('read', affreadperms)

    def restore_orig_cwuser_security(self):
        if hasattr(self, '_orig_cwuser_security_restored'):
            return
        self._orig_cwuser_security_restored = True
        userreadperms = list(self.schema['CWUser'].permissions['read'])
        userreadperms[-1] = self.prevrqlexpr_user
        self.schema['CWUser'].set_action_permissions('read', userreadperms)


class PartPlanInformationTC(BaseMSPlannerTC):

    def _test(self, rql, *args):
        if len(args) == 3:
            kwargs, sourcesterms, needsplit = args
        else:
            sourcesterms, needsplit = args
            kwargs = None
        plan = self._prepare_plan(rql, kwargs)
        union = plan.rqlst
        plan.preprocess(union)
        ppi = PartPlanInformation(plan, union.children[0])
        for sourcevars in ppi._sourcesterms.itervalues():
            for var in list(sourcevars):
                solindices = sourcevars.pop(var)
                sourcevars[var._ms_table_key()] = solindices
        self.assertEqual(ppi._sourcesterms, sourcesterms)
        self.assertEqual(ppi.needsplit, needsplit)


    def test_simple_system_only(self):
        """retrieve entities only supported by the system source"""
        self._test('CWGroup X',
                   {self.system: {'X': s[0]}}, False)

    def test_simple_system_ldap(self):
        """retrieve CWUser X from both sources and return concatenation of results
        """
        self._test('CWUser X',
                   {self.system: {'X': s[0]}, self.ldap: {'X': s[0]}}, False)

    def test_simple_system_rql(self):
        """retrieve Card X from both sources and return concatenation of results
        """
        self._test('Any X, XT WHERE X is Card, X title XT',
                   {self.system: {'X': s[0]}, self.cards: {'X': s[0]}}, False)

    def test_simple_eid_specified(self):
        """retrieve CWUser X from system source (eid is specified, can locate the entity)
        """
        ueid = self.session.user.eid
        self._test('Any X,L WHERE X eid %(x)s, X login L', {'x': ueid},
                   {self.system: {'X': s[0]}}, False)

    def test_simple_eid_invariant(self):
        """retrieve CWUser X from system source (eid is specified, can locate the entity)
        """
        ueid = self.session.user.eid
        self._test('Any X WHERE X eid %(x)s', {'x': ueid},
                   {self.system: {'x': s[0]}}, False)

    def test_simple_invariant(self):
        """retrieve CWUser X from system source only (X is invariant and in_group not supported by ldap source)
        """
        self._test('Any X WHERE X is CWUser, X in_group G, G name "users"',
                   {self.system: {'X': s[0], 'G': s[0], 'in_group': s[0]}}, False)

    def test_security_has_text(self):
        """retrieve CWUser X from system source only (has_text not supported by ldap source)
        """
        # specify CWUser instead of any since the way this test is written we aren't well dealing
        # with ambigous query (eg only considering the first solution)
        self._test('CWUser X WHERE X has_text "bla"',
                   {self.system: {'X': s[0]}}, False)

    def test_complex_base(self):
        """
        1. retrieve Any X, L WHERE X is CWUser, X login L from system and ldap sources, store
           concatenation of results into a temporary table
        2. return the result of Any X, L WHERE X is TMP, X login L, X in_group G,
           G name 'users' on the system source
        """
        self._test('Any X,L WHERE X is CWUser, X in_group G, X login L, G name "users"',
                   {self.system: {'X': s[0], 'G': s[0], 'in_group': s[0]},
                    self.ldap : {'X': s[0]}}, True)

    def test_complex_invariant_ordered(self):
        """
        1. retrieve Any X,AA WHERE X modification_date AA from system and ldap sources, store
           concatenation of results into a temporary table
        2. return the result of Any X,AA ORDERBY AA WHERE %s owned_by X, X modification_date AA
           on the system source
        """
        ueid = self.session.user.eid
        self._test('Any X,AA ORDERBY AA WHERE E eid %(x)s, E owned_by X, X modification_date AA', {'x': ueid},
                   {self.system: {'x': s[0], 'X': s[0], 'owned_by': s[0]},
                    self.ldap : {'X': s[0]}}, True)

    def test_complex_invariant(self):
        """
        1. retrieve Any X,L,AA WHERE X login L, X modification_date AA from system and ldap sources, store
           concatenation of results into a temporary table
        2. return the result of Any X,L,AA WHERE %s owned_by X, X login L, X modification_date AA
           on the system source
        """
        ueid = self.session.user.eid
        self._test('Any X,L,AA WHERE E eid %(x)s, E owned_by X, X login L, X modification_date AA', {'x': ueid},
                   {self.system: {'x': s[0], 'X': s[0], 'owned_by': s[0]},
                    self.ldap : {'X': s[0]}}, True)

    def test_complex_ambigous(self):
        """retrieve CWUser X from system and ldap sources, Person X from system source only
        """
        self._test('Any X,F WHERE X firstname F',
                   {self.system: {'X': s[0, 1]},
                    self.ldap: {'X': s[0]}}, True)

    def test_complex_multiple(self):
        """
        1. retrieve Any X,A,Y,B WHERE X login A, Y login B from system and ldap sources, store
           cartesian product of results into a temporary table
        2. return the result of Any X,Y WHERE X login 'syt', Y login 'adim'
           on the system source
        """
        ueid = self.session.user.eid
        self._test('Any X,Y WHERE X login "syt", Y login "adim"', {'x': ueid},
                   {self.system: {'Y': s[0], 'X': s[0]},
                    self.ldap: {'Y': s[0], 'X': s[0]}}, True)

    def test_complex_aggregat(self):
        solindexes = set(range(len([e for e in self.schema.entities() if not e.final])))
        self._test('Any MAX(X)',
                   {self.system: {'X': solindexes}}, False)

    def test_complex_optional(self):
        ueid = self.session.user.eid
        self._test('Any U WHERE WF wf_info_for X, X eid %(x)s, WF owned_by U?, WF from_state FS', {'x': ueid},
                   {self.system: {'WF': s[0], 'FS': s[0], 'U': s[0],
                                  'from_state': s[0], 'owned_by': s[0], 'wf_info_for': s[0],
                                  'x': s[0]}},
                   False)

    def test_exists4(self):
        """
        State S could come from both rql source and system source,
        but since X cannot come from the rql source, the solution
        {self.cards : 'S'} must be removed
        """
        self._test('Any G,L WHERE X in_group G, X login L, G name "managers", '
                   'EXISTS(X copain T, T login L, T login in ("comme", "cochon")) OR '
                   'EXISTS(X in_state S, S name "pascontent", NOT X copain T2, T2 login "billy")',
                   {self.system: {'X': s[0], 'S': s[0], 'T2': s[0], 'T': s[0], 'G': s[0], 'copain': s[0], 'in_group': s[0]},
                    self.ldap: {'X': s[0], 'T2': s[0], 'T': s[0]}},
                   True)

    def test_relation_need_split(self):
        self._test('Any X, S WHERE X in_state S',
                   {self.system: {'X': s[0, 1, 2], 'S': s[0, 1, 2]},
                    self.cards: {'X': s[2], 'S': s[2]}},
                   True)

    def test_not_relation_need_split(self):
        self._test('Any SN WHERE NOT X in_state S, S name SN',
                   {self.cards: {'X': s[2], 'S': s[0, 1, 2]},
                    self.system: {'X': s[0, 1, 2], 'S': s[0, 1, 2]}},
                   True)

    def test_not_relation_no_split_external(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        # similar to the above test but with an eid coming from the external source.
        # the same plan may be used, since we won't find any record in the system source
        # linking 9999999 to a state
        self._test('Any SN WHERE NOT X in_state S, X eid %(x)s, S name SN',
                   {'x': 999999},
                   {self.cards: {'x': s[0], 'S': s[0]},
                    self.system: {'x': s[0], 'S': s[0]}},
                   False)

    def test_relation_restriction_ambigous_need_split(self):
        self._test('Any X,T WHERE X in_state S, S name "pending", T tags X',
                   {self.system: {'X': s[0, 1, 2], 'S': s[0, 1, 2], 'T': s[0, 1, 2], 'tags': s[0, 1, 2]},
                    self.cards: {'X': s[2], 'S': s[2]}},
                   True)

    def test_simplified_var(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        # need access to source since X table has to be accessed because of the outer join
        self._test('Any U WHERE U in_group G, (G name IN ("managers", "logilab") OR (X require_permission P?, P name "bla", P require_group G)), X eid %(x)s, U eid %(u)s',
                   {'x': 999999, 'u': self.session.user.eid},
                   {self.system: {'P': s[0], 'G': s[0],
                                  'require_permission': s[0], 'in_group': s[0], 'P': s[0], 'require_group': s[0],
                                  'u': s[0]},
                    self.cards: {'X': s[0]}},
                   True)

    def test_delete_relation1(self):
        ueid = self.session.user.eid
        self._test('Any X, Y WHERE X created_by Y, X eid %(x)s, NOT Y eid %(y)s',
                   {'x': ueid, 'y': ueid},
                   {self.system: {'Y': s[0], 'created_by': s[0], 'x': s[0]}},
                   False)

    def test_crossed_relation_eid_1_needattr(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        ueid = self.session.user.eid
        self._test('Any Y,T WHERE X eid %(x)s, X multisource_crossed_rel Y, Y type T',
                   {'x': 999999,},
                   {self.cards: {'Y': s[0]}, self.system: {'Y': s[0], 'x': s[0]}},
                   True)

    def test_crossed_relation_eid_1_invariant(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   {'x': 999999},
                   {self.system: {'Y': s[0], 'x': s[0]}},
                   False)

    def test_crossed_relation_eid_2_invariant(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   {'x': 999999,},
                   {self.cards: {'Y': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]},
                    self.system: {'Y': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]}},
                   False)

    def test_version_crossed_depends_on_1(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any X,AD,AE WHERE E eid %(x)s, E multisource_crossed_rel X, X in_state AD, AD name AE',
                   {'x': 999999},
                   {self.cards: {'X': s[0], 'AD': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]},
                    self.system: {'X': s[0], 'AD': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]}},
                   True)

    def test_version_crossed_depends_on_2(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('Any X,AD,AE WHERE E eid %(x)s, E multisource_crossed_rel X, X in_state AD, AD name AE',
                   {'x': 999999},
                   {self.cards: {'X': s[0], 'AD': s[0]},
                    self.system: {'X': s[0], 'AD': s[0], 'x': s[0]}},
                    True)

    def test_simplified_var_3(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        repo._type_source_cache[999998] = ('State', 'cards', 999998, 'cards')
        self._test('Any S,T WHERE S eid %(s)s, N eid %(n)s, N type T, N is Note, S is State',
                   {'n': 999999, 's': 999998},
                   {self.cards: {'s': s[0], 'N': s[0]}}, False)



class MSPlannerTC(BaseMSPlannerTC):

    def setUp(self):
        BaseMSPlannerTC.setUp(self)
        self.planner = MSPlanner(self.o.schema, self.repo.vreg.rqlhelper)
        for cached in ('rel_type_sources', 'can_cross_relation', 'is_multi_sources_relation'):
            clear_cache(self.repo, cached)

    _test = test_plan

    def test_simple_system_only(self):
        """retrieve entities only supported by the system source
        """
        self._test('CWGroup X',
                   [('OneFetchStep', [('Any X WHERE X is CWGroup', [{'X': 'CWGroup'}])],
                     None, None, [self.system], {}, [])])

    def test_simple_system_only_limit(self):
        """retrieve entities only supported by the system source
        """
        self._test('CWGroup X LIMIT 10',
                   [('OneFetchStep', [('Any X LIMIT 10 WHERE X is CWGroup', [{'X': 'CWGroup'}])],
                     10, None, [self.system], {}, [])])

    def test_simple_system_only_limit_offset(self):
        """retrieve entities only supported by the system source
        """
        self._test('CWGroup X LIMIT 10 OFFSET 10',
                   [('OneFetchStep', [('Any X LIMIT 10 OFFSET 10 WHERE X is CWGroup', [{'X': 'CWGroup'}])],
                     10, 10, [self.system], {}, [])])

    def test_simple_system_ldap(self):
        """retrieve CWUser X from both sources and return concatenation of results
        """
        self._test('CWUser X',
                   [('OneFetchStep', [('Any X WHERE X is CWUser', [{'X': 'CWUser'}])],
                     None, None, [self.ldap, self.system], {}, [])])

    def test_simple_system_ldap_limit(self):
        """retrieve CWUser X from both sources and return concatenation of results
        """
        self._test('CWUser X LIMIT 10',
                   [('OneFetchStep', [('Any X LIMIT 10 WHERE X is CWUser', [{'X': 'CWUser'}])],
                     10, None, [self.ldap, self.system], {}, [])])

    def test_simple_system_ldap_limit_offset(self):
        """retrieve CWUser X from both sources and return concatenation of results
        """
        self._test('CWUser X LIMIT 10 OFFSET 10',
                   [('OneFetchStep', [('Any X LIMIT 10 OFFSET 10 WHERE X is CWUser', [{'X': 'CWUser'}])],
                     10, 10, [self.ldap, self.system], {}, [])])

    def test_simple_system_ldap_ordered_limit_offset(self):
        """retrieve CWUser X from both sources and return concatenation of results
        """
        self._test('CWUser X ORDERBY X LIMIT 10 OFFSET 10',
                   [('AggrStep', 'SELECT table0.C0 FROM table0\nORDER BY table0.C0\nLIMIT 10\nOFFSET 10', None, [
                       ('FetchStep', [('Any X WHERE X is CWUser', [{'X': 'CWUser'}])],
                        [self.ldap, self.system], {}, {'X': 'table0.C0'}, []),
                       ]),
                   ])
    def test_simple_system_ldap_aggregat(self):
        """retrieve CWUser X from both sources and return concatenation of results
        """
        # COUNT(X) is kept in sub-step and transformed into SUM(X) in the AggrStep
        self._test('Any COUNT(X) WHERE X is CWUser',
                   [('AggrStep', 'SELECT SUM(table0.C0) FROM table0', None, [
                       ('FetchStep', [('Any COUNT(X) WHERE X is CWUser', [{'X': 'CWUser'}])],
                        [self.ldap, self.system], {}, {'COUNT(X)': 'table0.C0'}, []),
                       ]),
                   ])

    def test_simple_system_rql(self):
        """retrieve Card X from both sources and return concatenation of results
        """
        self._test('Any X, XT WHERE X is Card, X title XT',
                   [('OneFetchStep', [('Any X,XT WHERE X is Card, X title XT', [{'X': 'Card', 'XT': 'String'}])],
                     None, None, [self.cards, self.system], {}, [])])

    def test_simple_eid_specified(self):
        """retrieve CWUser X from system source (eid is specified, can locate the entity)
        """
        ueid = self.session.user.eid
        self._test('Any X,L WHERE X eid %(x)s, X login L',
                   [('OneFetchStep', [('Any X,L WHERE X eid %s, X login L'%ueid, [{'X': 'CWUser', 'L': 'String'}])],
                     None, None, [self.system], {}, [])],
                   {'x': ueid})

    def test_simple_eid_invariant(self):
        """retrieve CWUser X from system source (eid is specified, can locate the entity)
        """
        ueid = self.session.user.eid
        self._test('Any X WHERE X eid %(x)s',
                   [('OneFetchStep', [('Any %s'%ueid, [{}])],
                     None, None, [self.system], {}, [])],
                   {'x': ueid})

    def test_simple_invariant(self):
        """retrieve CWUser X from system source only (X is invariant and in_group not supported by ldap source)
        """
        self._test('Any X WHERE X is CWUser, X in_group G, G name "users"',
                   [('OneFetchStep', [('Any X WHERE X is CWUser, X in_group G, G name "users"',
                                       [{'X': 'CWUser', 'G': 'CWGroup'}])],
                     None, None, [self.system], {}, [])])

    def test_complex_base(self):
        """
        1. retrieve Any X, L WHERE X is CWUser, X login L from system and ldap sources, store
           concatenation of results into a temporary table
        2. return the result of Any X, L WHERE X is TMP, X login LX in_group G,
           G name 'users' on the system source
        """
        self._test('Any X,L WHERE X is CWUser, X in_group G, X login L, G name "users"',
                   [('FetchStep', [('Any X,L WHERE X login L, X is CWUser', [{'X': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None,
                     {'X': 'table0.C0', 'X.login': 'table0.C1', 'L': 'table0.C1'}, []),
                    ('OneFetchStep', [('Any X,L WHERE X in_group G, X login L, G name "users", G is CWGroup, X is CWUser',
                                       [{'X': 'CWUser', 'L': 'String', 'G': 'CWGroup'}])],
                     None, None, [self.system],
                     {'X': 'table0.C0', 'X.login': 'table0.C1', 'L': 'table0.C1'}, [])
                    ])

    def test_complex_base_limit_offset(self):
        """
        1. retrieve Any X, L WHERE X is CWUser, X login L from system and ldap sources, store
           concatenation of results into a temporary table
        2. return the result of Any X, L WHERE X is TMP, X login LX in_group G,
           G name 'users' on the system source
        """
        self._test('Any X,L LIMIT 10 OFFSET 10 WHERE X is CWUser, X in_group G, X login L, G name "users"',
                   [('FetchStep', [('Any X,L WHERE X login L, X is CWUser', [{'X': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None,
                     {'X': 'table0.C0', 'X.login': 'table0.C1', 'L': 'table0.C1'}, []),
                    ('OneFetchStep', [('Any X,L LIMIT 10 OFFSET 10 WHERE X in_group G, X login L, G name "users", G is CWGroup, X is CWUser',
                                       [{'X': 'CWUser', 'L': 'String', 'G': 'CWGroup'}])],
                     10, 10,
                     [self.system], {'X': 'table0.C0', 'X.login': 'table0.C1', 'L': 'table0.C1'}, [])
                    ])

    def test_complex_ordered(self):
        self._test('Any L ORDERBY L WHERE X login L',
                   [('AggrStep', 'SELECT table0.C0 FROM table0\nORDER BY table0.C0', None,
                     [('FetchStep', [('Any L WHERE X login L, X is CWUser',
                                      [{'X': 'CWUser', 'L': 'String'}])],
                       [self.ldap, self.system], {}, {'X.login': 'table0.C0', 'L': 'table0.C0'}, []),
                      ])
                    ])

    def test_complex_ordered_limit_offset(self):
        self._test('Any L ORDERBY L LIMIT 10 OFFSET 10 WHERE X login L',
                   [('AggrStep', 'SELECT table0.C0 FROM table0\nORDER BY table0.C0\nLIMIT 10\nOFFSET 10', None,
                     [('FetchStep', [('Any L WHERE X login L, X is CWUser',
                                      [{'X': 'CWUser', 'L': 'String'}])],
                       [self.ldap, self.system], {}, {'X.login': 'table0.C0', 'L': 'table0.C0'}, []),
                      ])
                    ])

    def test_complex_invariant_ordered(self):
        """
        1. retrieve Any X,AA WHERE X modification_date AA from system and ldap sources, store
           concatenation of results into a temporary table
        2. return the result of Any X,AA ORDERBY AA WHERE %s owned_by X, X modification_date AA
           on the system source

        herrr, this is what is expected by the XXX :(, not the actual result (which is correct anyway)
        """
        ueid = self.session.user.eid
        self._test('Any X,AA ORDERBY AA WHERE E eid %(x)s, E owned_by X, X modification_date AA',
                   [('FetchStep',
                     [('Any X,AA WHERE X modification_date AA, X is CWUser',
                       [{'AA': 'Datetime', 'X': 'CWUser'}])],
                     [self.ldap, self.system], None,
                     {'AA': 'table0.C1', 'X': 'table0.C0', 'X.modification_date': 'table0.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,AA ORDERBY AA WHERE %s owned_by X, X modification_date AA, X is CWUser' % ueid,
                       [{'AA': 'Datetime', 'X': 'CWUser'}])],
                     None, None, [self.system],
                     {'AA': 'table0.C1', 'X': 'table0.C0', 'X.modification_date': 'table0.C1'}, []),
                    ],
                   {'x': ueid})

    def test_complex_invariant(self):
        """
        1. retrieve Any X,L,AA WHERE X login L, X modification_date AA from system and ldap sources, store
           concatenation of results into a temporary table
        2. return the result of Any X,L,AA WHERE %s owned_by X, X login L, X modification_date AA
           on the system source
        """
        ueid = self.session.user.eid
        self._test('Any X,L,AA WHERE E eid %(x)s, E owned_by X, X login L, X modification_date AA',
                   [('FetchStep', [('Any X,L,AA WHERE X login L, X modification_date AA, X is CWUser',
                                    [{'AA': 'Datetime', 'X': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None,
                     {'AA': 'table0.C2', 'X': 'table0.C0', 'X.login': 'table0.C1', 'X.modification_date': 'table0.C2', 'L': 'table0.C1'}, []),
                    ('OneFetchStep', [('Any X,L,AA WHERE %s owned_by X, X login L, X modification_date AA, X is CWUser'%ueid,
                                       [{'AA': 'Datetime', 'X': 'CWUser', 'L': 'String'}])],
                     None, None, [self.system],
                     {'AA': 'table0.C2', 'X': 'table0.C0', 'X.login': 'table0.C1', 'X.modification_date': 'table0.C2', 'L': 'table0.C1'}, [])],
                   {'x': ueid})

    def test_complex_ambigous(self):
        """retrieve CWUser X from system and ldap sources, Person X from system source only
        """
        self._test('Any X,F WHERE X firstname F',
                   [('UnionStep', None, None, [
                       ('OneFetchStep', [('Any X,F WHERE X firstname F, X is CWUser',
                                          [{'X': 'CWUser', 'F': 'String'}])],
                        None, None, [self.ldap, self.system], {}, []),
                       ('OneFetchStep', [('Any X,F WHERE X firstname F, X is Personne',
                                          [{'X': 'Personne', 'F': 'String'}])],
                        None, None, [self.system], {}, []),
                       ]),
                    ])

    def test_complex_ambigous_limit_offset(self):
        """retrieve CWUser X from system and ldap sources, Person X from system source only
        """
        self._test('Any X,F LIMIT 10 OFFSET 10 WHERE X firstname F',
                   [('UnionStep', 10, 10, [
                       ('OneFetchStep', [('Any X,F WHERE X firstname F, X is CWUser',
                                          [{'X': 'CWUser', 'F': 'String'}])],
                        None, None,
                        [self.ldap, self.system], {}, []),
                       ('OneFetchStep', [('Any X,F WHERE X firstname F, X is Personne',
                                          [{'X': 'Personne', 'F': 'String'}])],
                        None, None, [self.system], {}, []),
                       ]),
                    ])

    def test_complex_ambigous_ordered(self):
        """
        1. retrieve CWUser X from system and ldap sources, Person X from system source only, store
           each result in the same temp table
        2. return content of the table sorted
        """
        self._test('Any X,F ORDERBY F WHERE X firstname F',
                   [('AggrStep', 'SELECT table0.C0, table0.C1 FROM table0\nORDER BY table0.C1', None,
                     [('FetchStep', [('Any X,F WHERE X firstname F, X is CWUser',
                                      [{'X': 'CWUser', 'F': 'String'}])],
                       [self.ldap, self.system], {},
                       {'X': 'table0.C0', 'X.firstname': 'table0.C1', 'F': 'table0.C1'}, []),
                      ('FetchStep', [('Any X,F WHERE X firstname F, X is Personne',
                                      [{'X': 'Personne', 'F': 'String'}])],
                       [self.system], {},
                       {'X': 'table0.C0', 'X.firstname': 'table0.C1', 'F': 'table0.C1'}, []),
                      ]),
                    ])

    def test_complex_multiple(self):
        """
        1. retrieve Any X,A,Y,B WHERE X login A, Y login B from system and ldap sources, store
           cartesian product of results into a temporary table
        2. return the result of Any X,Y WHERE X login 'syt', Y login 'adim'
           on the system source
        """
        ueid = self.session.user.eid
        self._test('Any X,Y WHERE X login "syt", Y login "adim"',
                   [('FetchStep',
                     [('Any X WHERE X login "syt", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None,
                     {'X': 'table0.C0'}, []),
                    ('FetchStep',
                     [('Any Y WHERE Y login "adim", Y is CWUser', [{'Y': 'CWUser'}])],
                     [self.ldap, self.system], None,
                     {'Y': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any X,Y WHERE X is CWUser, Y is CWUser', [{'X': 'CWUser', 'Y': 'CWUser'}])],
                     None, None, [self.system],
                     {'X': 'table0.C0', 'Y': 'table1.C0'}, [])
                    ], {'x': ueid})

    def test_complex_multiple_limit_offset(self):
        """
        1. retrieve Any X,A,Y,B WHERE X login A, Y login B from system and ldap sources, store
           cartesian product of results into a temporary table
        2. return the result of Any X,Y WHERE X login 'syt', Y login 'adim'
           on the system source
        """
        self._test('Any X,Y LIMIT 10 OFFSET 10 WHERE X login "syt", Y login "adim"',
                   [('FetchStep',
                     [('Any X WHERE X login "syt", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('FetchStep',
                     [('Any Y WHERE Y login "adim", Y is CWUser', [{'Y': 'CWUser'}])],
                     [self.ldap, self.system], None, {'Y': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any X,Y LIMIT 10 OFFSET 10 WHERE X is CWUser, Y is CWUser', [{'X': 'CWUser', 'Y': 'CWUser'}])],
                     10, 10, [self.system],
                     {'X': 'table0.C0', 'Y': 'table1.C0'}, [])
                    ])

    def test_complex_aggregat(self):
        self._test('Any MAX(X)',
                   [('OneFetchStep',
                     [('Any MAX(X)', X_ALL_SOLS)],
                     None, None, [self.system], {}, [])
                    ])

    def test_complex_typed_aggregat(self):
        self._test('Any MAX(X) WHERE X is Card',
                   [('AggrStep', 'SELECT MAX(table0.C0) FROM table0',  None,
                     [('FetchStep',
                       [('Any MAX(X) WHERE X is Card', [{'X': 'Card'}])],
                       [self.cards, self.system], {}, {'MAX(X)': 'table0.C0'}, [])
                      ])
                    ])

    def test_complex_greater_eid(self):
        self._test('Any X WHERE X eid > 12',
                   [('OneFetchStep',
                     [('Any X WHERE X eid > 12', X_ALL_SOLS)],
                     None, None, [self.system], {}, [])
                    ])

    def test_complex_greater_typed_eid(self):
        self._test('Any X WHERE X eid > 12, X is Card',
                   [('OneFetchStep',
                     [('Any X WHERE X eid > 12, X is Card', [{'X': 'Card'}])],
                     None, None, [self.system], {}, [])
                    ])

    def test_complex_optional(self):
        ueid = self.session.user.eid
        self._test('Any U WHERE WF wf_info_for X, X eid %(x)s, WF owned_by U?, WF from_state FS',
                   [('OneFetchStep', [('Any U WHERE WF wf_info_for %s, WF owned_by U?, WF from_state FS' % ueid,
                                       [{'WF': 'TrInfo', 'FS': 'State', 'U': 'CWUser'}])],
                     None, None, [self.system], {}, [])],
                   {'x': ueid})

    def test_complex_optional(self):
        ueid = self.session.user.eid
        self._test('Any U WHERE WF wf_info_for X, X eid %(x)s, WF owned_by U?, WF from_state FS',
                   [('OneFetchStep', [('Any U WHERE WF wf_info_for %s, WF owned_by U?, WF from_state FS' % ueid,
                                       [{'WF': 'TrInfo', 'FS': 'State', 'U': 'CWUser'}])],
                     None, None, [self.system], {}, [])],
                   {'x': ueid})


    def test_3sources_ambigous(self):
        self._test('Any X,T WHERE X owned_by U, U login "syt", X title T, X is IN(Bookmark, Card, EmailThread)',
                   [('FetchStep', [('Any X,T WHERE X title T, X is Card', [{'X': 'Card', 'T': 'String'}])],
                     [self.cards, self.system], None,
                     {'T': 'table0.C1', 'X': 'table0.C0', 'X.title': 'table0.C1'}, []),
                    ('FetchStep', [('Any U WHERE U login "syt", U is CWUser', [{'U': 'CWUser'}])],
                     [self.ldap, self.system], None,
                     {'U': 'table1.C0'}, []),
                    ('UnionStep', None, None, [
                        ('OneFetchStep', [('Any X,T WHERE X owned_by U, X title T, U is CWUser, X is IN(Bookmark, EmailThread)',
                                           [{'T': 'String', 'U': 'CWUser', 'X': 'Bookmark'},
                                            {'T': 'String', 'U': 'CWUser', 'X': 'EmailThread'}])],
                         None, None, [self.system], {'U': 'table1.C0'}, []),
                        ('OneFetchStep', [('Any X,T WHERE X owned_by U, X title T, U is CWUser, X is Card',
                                           [{'X': 'Card', 'U': 'CWUser', 'T': 'String'}])],
                         None, None, [self.system],
                         {'X': 'table0.C0', 'X.title': 'table0.C1', 'T': 'table0.C1', 'U': 'table1.C0'}, []),
                        ]),
                    ])

    def test_restricted_max(self):
        # dumb query to emulate the one generated by svnfile.entities.rql_revision_content
        self._test('Any V, MAX(VR) WHERE V is Card, V creation_date VR, '
                   '(V creation_date TODAY OR (V creation_date < TODAY AND NOT EXISTS('
                   'X is Card, X creation_date < TODAY, X creation_date >= VR)))',
                   [('FetchStep', [('Any VR WHERE X creation_date < TODAY, X creation_date VR, X is Card',
                                    [{'X': 'Card', 'VR': 'Datetime'}])],
                     [self.cards, self.system], None,
                     {'VR': 'table0.C0', 'X.creation_date': 'table0.C0'}, []),
                    ('FetchStep', [('Any V,VR WHERE V creation_date VR, V is Card',
                                    [{'VR': 'Datetime', 'V': 'Card'}])],
                     [self.cards, self.system], None,
                     {'VR': 'table1.C1', 'V': 'table1.C0', 'V.creation_date': 'table1.C1'}, []),
                    ('OneFetchStep', [('Any V,MAX(VR) WHERE V creation_date VR, (V creation_date TODAY) OR (V creation_date < TODAY, NOT EXISTS(X creation_date >= VR, X is Card)), V is Card',
                                       [{'X': 'Card', 'VR': 'Datetime', 'V': 'Card'}])],
                     None, None, [self.system],
                     {'VR': 'table1.C1', 'V': 'table1.C0', 'V.creation_date': 'table1.C1', 'X.creation_date': 'table0.C0'}, [])
                    ])

    def test_outer_supported_rel1(self):
        # both system and rql support all variables, can be
        self._test('Any X, R WHERE X is Note, X in_state S, X type R, '
                   'NOT EXISTS(Y is Note, Y in_state S, Y type R, X identity Y)',
                   [('OneFetchStep', [('Any X,R WHERE X is Note, X in_state S, X type R, NOT EXISTS(Y is Note, Y in_state S, Y type R, X identity Y), S is State',
                                       [{'Y': 'Note', 'X': 'Note', 'S': 'State', 'R': 'String'}])],
                     None, None,
                     [self.cards, self.system], {}, [])
                    ])

    def test_not_identity(self):
        ueid = self.session.user.eid
        self._test('Any X WHERE NOT X identity U, U eid %s, X is CWUser' % ueid,
                   [('OneFetchStep',
                     [('Any X WHERE NOT X identity %s, X is CWUser' % ueid, [{'X': 'CWUser'}])],
                     None, None,
                     [self.ldap, self.system], {}, [])
                    ])

    def test_outer_supported_rel2(self):
        self._test('Any X, MAX(R) GROUPBY X WHERE X in_state S, X login R, '
                   'NOT EXISTS(Y is Note, Y in_state S, Y type R)',
                   [('FetchStep', [('Any A,R WHERE Y in_state A, Y type R, A is State, Y is Note',
                                    [{'Y': 'Note', 'A': 'State', 'R': 'String'}])],
                     [self.cards, self.system], None,
                     {'A': 'table0.C0', 'R': 'table0.C1', 'Y.type': 'table0.C1'}, []),
                    ('FetchStep', [('Any X,R WHERE X login R, X is CWUser', [{'X': 'CWUser', 'R': 'String'}])],
                     [self.ldap, self.system], None,
                     {'X': 'table1.C0', 'X.login': 'table1.C1', 'R': 'table1.C1'}, []),
                    ('OneFetchStep', [('Any X,MAX(R) GROUPBY X WHERE X in_state S, X login R, NOT EXISTS(Y type R, S identity A, A is State, Y is Note), S is State, X is CWUser',
                                       [{'Y': 'Note', 'X': 'CWUser', 'S': 'State', 'R': 'String', 'A': 'State'}])],
                     None, None, [self.system],
                     {'A': 'table0.C0', 'X': 'table1.C0', 'X.login': 'table1.C1', 'R': 'table1.C1', 'Y.type': 'table0.C1'}, [])
                    ])

    def test_security_has_text(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X WHERE X has_text "bla"',
                   [('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                     [self.cards, self.system], None, {'E': 'table0.C0'}, []),
                    ('UnionStep', None, None,
                     [('OneFetchStep',
                       [(u'Any X WHERE X has_text "bla", (EXISTS(X owned_by %(ueid)s)) OR ((((EXISTS(D concerne C?, C owned_by %(ueid)s, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by %(ueid)s, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by %(ueid)s, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by %(ueid)s, X identity J, E is Note, J is Affaire))), X is Affaire' % {'ueid': ueid},
                         [{'C': 'Division', 'E': 'Note', 'D': 'Affaire', 'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire', 'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire'}])],
                       None, None, [self.system], {'E': 'table0.C0'}, []),
                      ('OneFetchStep',
                       [('Any X WHERE X has_text "bla", EXISTS(X owned_by %s), X is IN(Basket, CWUser)' % ueid,
                         [{'X': 'Basket'}, {'X': 'CWUser'}]),
                        ('Any X WHERE X has_text "bla", X is IN(Card, Comment, Division, Email, EmailThread, File, Folder, Note, Personne, Societe, SubDivision, Tag)',
                         [{'X': 'Card'}, {'X': 'Comment'},
                          {'X': 'Division'}, {'X': 'Email'}, {'X': 'EmailThread'},
                          {'X': 'File'}, {'X': 'Folder'},
                          {'X': 'Note'}, {'X': 'Personne'}, {'X': 'Societe'},
                          {'X': 'SubDivision'}, {'X': 'Tag'}]),],
                       None, None, [self.system], {}, []),
                      ])
                     ])

    def test_security_has_text_limit_offset(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        # note: same as the above query but because of the subquery usage, the
        # display differs (not printing solutions for each union)
        self._test('Any X LIMIT 10 OFFSET 10 WHERE X has_text "bla"',
                   [('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                      [self.cards, self.system], None, {'E': 'table1.C0'}, []),
                     ('UnionFetchStep', [
                        ('FetchStep', [('Any X WHERE X has_text "bla", (EXISTS(X owned_by %(ueid)s)) OR ((((EXISTS(D concerne C?, C owned_by %(ueid)s, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by %(ueid)s, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by %(ueid)s, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by %(ueid)s, X identity J, E is Note, J is Affaire))), X is Affaire' % {'ueid': ueid},
                                            [{'C': 'Division', 'E': 'Note', 'D': 'Affaire', 'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire', 'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire'}])],
                          [self.system], {'E': 'table1.C0'}, {'X': 'table0.C0'}, []),
                         ('FetchStep',
                          [('Any X WHERE X has_text "bla", EXISTS(X owned_by %s), X is IN(Basket, CWUser)' % ueid,
                            [{'X': 'Basket'}, {'X': 'CWUser'}]),
                           ('Any X WHERE X has_text "bla", X is IN(Card, Comment, Division, Email, EmailThread, File, Folder, Note, Personne, Societe, SubDivision, Tag)',
                            [{'X': 'Card'}, {'X': 'Comment'},
                             {'X': 'Division'}, {'X': 'Email'}, {'X': 'EmailThread'},
                             {'X': 'File'}, {'X': 'Folder'},
                             {'X': 'Note'}, {'X': 'Personne'}, {'X': 'Societe'},
                             {'X': 'SubDivision'}, {'X': 'Tag'}])],
                          [self.system], {}, {'X': 'table0.C0'}, []),
                         ]),
                    ('OneFetchStep',
                     [('Any X LIMIT 10 OFFSET 10',
                       [{'X': 'Affaire'}, {'X': 'Basket'},
                        {'X': 'CWUser'}, {'X': 'Card'}, {'X': 'Comment'},
                        {'X': 'Division'}, {'X': 'Email'}, {'X': 'EmailThread'},
                        {'X': 'File'}, {'X': 'Folder'},
                        {'X': 'Note'}, {'X': 'Personne'}, {'X': 'Societe'},
                        {'X': 'SubDivision'}, {'X': 'Tag'}])],
                     10, 10, [self.system], {'X': 'table0.C0'}, [])
                     ])

    def test_security_user(self):
        """a guest user trying to see another user: EXISTS(X owned_by U) is automatically inserted"""
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X WHERE X login "bla"',
                   [('FetchStep',
                     [('Any X WHERE X login "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('OneFetchStep',
                     [('Any X WHERE EXISTS(X owned_by %s), X is CWUser' % ueid, [{'X': 'CWUser'}])],
                     None, None, [self.system], {'X': 'table0.C0'}, [])])

    def test_security_complex_has_text(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X WHERE X has_text "bla", X firstname "bla"',
                   [('FetchStep', [('Any X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('UnionStep', None, None, [
                        ('OneFetchStep', [('Any X WHERE X has_text "bla", EXISTS(X owned_by %s), X is CWUser' % ueid, [{'X': 'CWUser'}])],
                         None, None, [self.system], {'X': 'table0.C0'}, []),
                        ('OneFetchStep', [('Any X WHERE X has_text "bla", X firstname "bla", X is Personne', [{'X': 'Personne'}])],
                         None, None, [self.system], {}, []),
                        ]),
                    ])

    def test_security_complex_has_text_limit_offset(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X LIMIT 10 OFFSET 10 WHERE X has_text "bla", X firstname "bla"',
                   [('FetchStep', [('Any X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table1.C0'}, []),
                    ('UnionFetchStep', [
                        ('FetchStep', [('Any X WHERE X has_text "bla", EXISTS(X owned_by %s), X is CWUser' % ueid, [{'X': 'CWUser'}])],
                         [self.system], {'X': 'table1.C0'}, {'X': 'table0.C0'}, []),
                        ('FetchStep', [('Any X WHERE X has_text "bla", X firstname "bla", X is Personne', [{'X': 'Personne'}])],
                         [self.system], {}, {'X': 'table0.C0'}, []),
                        ]),
                     ('OneFetchStep',
                      [('Any X LIMIT 10 OFFSET 10', [{'X': 'CWUser'}, {'X': 'Personne'}])],
                      10, 10, [self.system], {'X': 'table0.C0'}, [])
                    ])

    def test_security_complex_aggregat(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        ALL_SOLS = X_ALL_SOLS[:]
        ALL_SOLS.remove({'X': 'CWSourceHostConfig'}) # not authorized
        ALL_SOLS.remove({'X': 'CWSourceSchemaConfig'}) # not authorized
        ALL_SOLS.remove({'X': 'CWDataImport'}) # not authorized
        self._test('Any MAX(X)',
                   [('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                     [self.cards, self.system],  None, {'E': 'table1.C0'}, []),
                    ('FetchStep', [('Any X WHERE X is IN(CWUser)', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table2.C0'}, []),
                    ('UnionFetchStep', [
                        ('FetchStep', [('Any X WHERE EXISTS(%s use_email X), X is EmailAddress' % ueid,
                                        [{'X': 'EmailAddress'}])],
                          [self.system], {}, {'X': 'table0.C0'}, []),
                        ('UnionFetchStep',
                         [('FetchStep', [('Any X WHERE X is IN(Card, Note, State)',
                                          [{'X': 'Card'}, {'X': 'Note'}, {'X': 'State'}])],
                           [self.cards, self.system], {}, {'X': 'table0.C0'}, []),
                          ('FetchStep',
                           [('Any X WHERE X is IN(BaseTransition, Bookmark, CWAttribute, CWCache, CWConstraint, CWConstraintType, CWEType, CWGroup, CWPermission, CWProperty, CWRType, CWRelation, CWSource, CWUniqueTogetherConstraint, Comment, Division, Email, EmailPart, EmailThread, ExternalUri, File, Folder, Old, Personne, RQLExpression, Societe, SubDivision, SubWorkflowExitPoint, Tag, TrInfo, Transition, Workflow, WorkflowTransition)',
                             [{'X': 'BaseTransition'}, {'X': 'Bookmark'},
                              {'X': 'CWAttribute'}, {'X': 'CWCache'},
                              {'X': 'CWConstraint'}, {'X': 'CWConstraintType'},
                              {'X': 'CWEType'}, {'X': 'CWGroup'},
                              {'X': 'CWPermission'}, {'X': 'CWProperty'},
                              {'X': 'CWRType'}, {'X': 'CWRelation'},
                              {'X': 'CWSource'},
                              {'X': 'CWUniqueTogetherConstraint'},
                              {'X': 'Comment'}, {'X': 'Division'},
                              {'X': 'Email'},
                              {'X': 'EmailPart'}, {'X': 'EmailThread'},
                              {'X': 'ExternalUri'}, {'X': 'File'},
                              {'X': 'Folder'}, {'X': 'Old'},
                              {'X': 'Personne'}, {'X': 'RQLExpression'},
                              {'X': 'Societe'}, {'X': 'SubDivision'},
                              {'X': 'SubWorkflowExitPoint'}, {'X': 'Tag'},
                              {'X': 'TrInfo'}, {'X': 'Transition'},
                              {'X': 'Workflow'}, {'X': 'WorkflowTransition'}])],
                           [self.system], {}, {'X': 'table0.C0'}, []),
                          ]),
                        ('FetchStep', [('Any X WHERE (EXISTS(X owned_by %(ueid)s)) OR ((((EXISTS(D concerne C?, C owned_by %(ueid)s, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by %(ueid)s, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by %(ueid)s, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by %(ueid)s, X identity J, E is Note, J is Affaire))), X is Affaire' % {'ueid': ueid},
                                        [{'C': 'Division', 'E': 'Note', 'D': 'Affaire', 'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire', 'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire'}])],
                         [self.system], {'E': 'table1.C0'}, {'X': 'table0.C0'}, []),
                        ('UnionFetchStep', [
                                ('FetchStep', [('Any X WHERE EXISTS(X owned_by %s), X is Basket' % ueid,
                                                [{'X': 'Basket'}])],
                                 [self.system], {}, {'X': 'table0.C0'}, []),
                                ('FetchStep', [('Any X WHERE EXISTS(X owned_by %s), X is CWUser' % ueid,
                                                [{'X': 'CWUser'}])],
                                 [self.system], {'X': 'table2.C0'}, {'X': 'table0.C0'}, []),
                                ]),
                        ]),
                    ('OneFetchStep', [('Any MAX(X)', ALL_SOLS)],
                     None, None, [self.system], {'X': 'table0.C0'}, [])
                    ])

    def test_security_complex_aggregat2(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        X_ET_ALL_SOLS = []
        for s in X_ALL_SOLS:
            if s in ({'X': 'CWSourceHostConfig'}, {'X': 'CWSourceSchemaConfig'}, {'X': 'CWDataImport'}):
                continue # not authorized
            ets = {'ET': 'CWEType'}
            ets.update(s)
            X_ET_ALL_SOLS.append(ets)
        self._test('Any ET, COUNT(X) GROUPBY ET ORDERBY ET WHERE X is ET',
                   [('FetchStep', [('Any X WHERE X is IN(Card, Note, State)',
                                    [{'X': 'Card'}, {'X': 'Note'}, {'X': 'State'}])],
                     [self.cards, self.system], None, {'X': 'table1.C0'}, []),
                    ('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                     [self.cards, self.system],  None, {'E': 'table2.C0'}, []),
                    ('FetchStep', [('Any X WHERE X is IN(CWUser)', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table3.C0'}, []),
                    ('UnionFetchStep',
                     [('FetchStep', [('Any ET,X WHERE X is ET, EXISTS(%s use_email X), ET is CWEType, X is EmailAddress' % ueid,
                                      [{'ET': 'CWEType', 'X': 'EmailAddress'}]),
                                     ],
                       [self.system], {}, {'ET': 'table0.C0', 'X': 'table0.C1'}, []),
                      # extra UnionFetchStep could be avoided but has no cost, so don't care
                      ('UnionFetchStep',
                       [('FetchStep', [('Any ET,X WHERE X is ET, ET is CWEType, X is IN(BaseTransition, Bookmark, CWAttribute, CWCache, CWConstraint, CWConstraintType, CWEType, CWGroup, CWPermission, CWProperty, CWRType, CWRelation, CWSource, CWUniqueTogetherConstraint, Comment, Division, Email, EmailPart, EmailThread, ExternalUri, File, Folder, Old, Personne, RQLExpression, Societe, SubDivision, SubWorkflowExitPoint, Tag, TrInfo, Transition, Workflow, WorkflowTransition)',
                                        [{'X': 'BaseTransition', 'ET': 'CWEType'},
                                         {'X': 'Bookmark', 'ET': 'CWEType'}, {'X': 'CWAttribute', 'ET': 'CWEType'},
                                         {'X': 'CWCache', 'ET': 'CWEType'}, {'X': 'CWConstraint', 'ET': 'CWEType'},
                                         {'X': 'CWConstraintType', 'ET': 'CWEType'},
                                         {'X': 'CWEType', 'ET': 'CWEType'},
                                         {'X': 'CWGroup', 'ET': 'CWEType'}, {'X': 'CWPermission', 'ET': 'CWEType'},
                                         {'X': 'CWProperty', 'ET': 'CWEType'}, {'X': 'CWRType', 'ET': 'CWEType'},
                                         {'X': 'CWSource', 'ET': 'CWEType'},
                                         {'X': 'CWRelation', 'ET': 'CWEType'},
                                         {'X': 'CWUniqueTogetherConstraint', 'ET': 'CWEType'},
                                         {'X': 'Comment', 'ET': 'CWEType'},
                                         {'X': 'Division', 'ET': 'CWEType'}, {'X': 'Email', 'ET': 'CWEType'},
                                         {'X': 'EmailPart', 'ET': 'CWEType'},
                                         {'X': 'EmailThread', 'ET': 'CWEType'}, {'X': 'ExternalUri', 'ET': 'CWEType'},
                                         {'X': 'File', 'ET': 'CWEType'}, {'X': 'Folder', 'ET': 'CWEType'},
                                         {'X': 'Old', 'ET': 'CWEType'}, {'X': 'Personne', 'ET': 'CWEType'},
                                         {'X': 'RQLExpression', 'ET': 'CWEType'}, {'X': 'Societe', 'ET': 'CWEType'},
                                         {'X': 'SubDivision', 'ET': 'CWEType'}, {'X': 'SubWorkflowExitPoint', 'ET': 'CWEType'},
                                         {'X': 'Tag', 'ET': 'CWEType'}, {'X': 'TrInfo', 'ET': 'CWEType'},
                                         {'X': 'Transition', 'ET': 'CWEType'}, {'X': 'Workflow', 'ET': 'CWEType'},
                                         {'X': 'WorkflowTransition', 'ET': 'CWEType'}])],
                         [self.system], {}, {'ET': 'table0.C0', 'X': 'table0.C1'}, []),
                        ('FetchStep',
                         [('Any ET,X WHERE X is ET, ET is CWEType, X is IN(Card, Note, State)',
                           [{'ET': 'CWEType', 'X': 'Card'},
                            {'ET': 'CWEType', 'X': 'Note'},
                            {'ET': 'CWEType', 'X': 'State'}])],
                         [self.system], {'X': 'table1.C0'}, {'ET': 'table0.C0', 'X': 'table0.C1'}, []),
                        ]),

                      ('FetchStep', [('Any ET,X WHERE X is ET, (EXISTS(X owned_by %(ueid)s)) OR ((((EXISTS(D concerne C?, C owned_by %(ueid)s, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by %(ueid)s, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by %(ueid)s, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by %(ueid)s, X identity J, E is Note, J is Affaire))), ET is CWEType, X is Affaire' % {'ueid': ueid},
                                      [{'C': 'Division', 'E': 'Note', 'D': 'Affaire',
                                        'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire',
                                        'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire',
                                        'ET': 'CWEType'}])],
                       [self.system], {'E': 'table2.C0'}, {'ET': 'table0.C0', 'X': 'table0.C1'},
                       []),
                      ('UnionFetchStep', [
                                ('FetchStep', [('Any ET,X WHERE X is ET, EXISTS(X owned_by %s), ET is CWEType, X is Basket' % ueid,
                                                [{'ET': 'CWEType', 'X': 'Basket'}])],
                                 [self.system], {}, {'ET': 'table0.C0', 'X': 'table0.C1'}, []),
                                ('FetchStep', [('Any ET,X WHERE X is ET, EXISTS(X owned_by %s), ET is CWEType, X is CWUser' % ueid,
                                                [{'ET': 'CWEType', 'X': 'CWUser'}])],
                                 [self.system], {'X': 'table3.C0'}, {'ET': 'table0.C0', 'X': 'table0.C1'}, []),
                                ]),
                    ]),
                    ('OneFetchStep',
                     [('Any ET,COUNT(X) GROUPBY ET ORDERBY ET', X_ET_ALL_SOLS)],
                     None, None, [self.system], {'ET': 'table0.C0', 'X': 'table0.C1'}, [])
                    ])

    def test_security_3sources(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X, XT WHERE X is Card, X owned_by U, X title XT, U login "syt"',
                   [('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any U WHERE U login "syt", U is CWUser', [{'U': 'CWUser'}])],
                     [self.ldap, self.system], None, {'U': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any X,XT WHERE X owned_by U, X title XT, EXISTS(U owned_by %s), U is CWUser, X is Card' % ueid,
                       [{'X': 'Card', 'U': 'CWUser', 'XT': 'String'}])],
                     None, None, [self.system],
                     {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1', 'U': 'table1.C0'}, [])
                    ])

    def test_security_3sources_identity(self):
        self.restore_orig_cwuser_security()
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X, XT WHERE X is Card, X owned_by U, X title XT, U login "syt"',
                   [('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,XT WHERE X owned_by U, X title XT, U login "syt", EXISTS(U identity %s), U is CWUser, X is Card' % ueid,
                       [{'U': 'CWUser', 'X': 'Card', 'XT': 'String'}])],
                     None, None, [self.system], {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, [])
                    ])

    def test_security_3sources_identity_optional_var(self):
        self.restore_orig_cwuser_security()
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X,XT,U WHERE X is Card, X owned_by U?, X title XT, U login L',
                   [('FetchStep',
                     [('Any U,L WHERE U login L, EXISTS(U identity %s), U is CWUser' % ueid,
                       [{'L': 'String', u'U': 'CWUser'}])],
                     [self.system], {}, {'L': 'table0.C1', 'U': 'table0.C0', 'U.login': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table1.C0', 'X.title': 'table1.C1', 'XT': 'table1.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,XT,U WHERE X owned_by U?, X title XT, X is Card',
                       [{'X': 'Card', 'U': 'CWUser', 'XT': 'String'}])],
                     None, None, [self.system], {'L': 'table0.C1',
                                                 'U': 'table0.C0',
                                                 'X': 'table1.C0',
                                                 'X.title': 'table1.C1',
                                                 'XT': 'table1.C1'}, [])
                    ])

    def test_security_3sources_limit_offset(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X, XT LIMIT 10 OFFSET 10 WHERE X is Card, X owned_by U, X title XT, U login "syt"',
                   [('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any U WHERE U login "syt", U is CWUser', [{'U': 'CWUser'}])],
                     [self.ldap, self.system], None, {'U': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any X,XT LIMIT 10 OFFSET 10 WHERE X owned_by U, X title XT, EXISTS(U owned_by %s), U is CWUser, X is Card' % ueid,
                       [{'X': 'Card', 'U': 'CWUser', 'XT': 'String'}])],
                     10, 10, [self.system],
                     {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1', 'U': 'table1.C0'}, [])
                    ])

    def test_exists_base(self):
        self._test('Any X,L,S WHERE X in_state S, X login L, EXISTS(X in_group G, G name "bougloup")',
                   [('FetchStep', [('Any X,L WHERE X login L, X is CWUser', [{'X': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0', 'X.login': 'table0.C1', 'L': 'table0.C1'}, []),
                    ('OneFetchStep', [("Any X,L,S WHERE X in_state S, X login L, "
                                      'EXISTS(X in_group G, G name "bougloup", G is CWGroup), S is State, X is CWUser',
                                       [{'X': 'CWUser', 'L': 'String', 'S': 'State', 'G': 'CWGroup'}])],
                     None, None, [self.system],
                     {'X': 'table0.C0', 'X.login': 'table0.C1', 'L': 'table0.C1'}, [])])

    def test_exists_complex(self):
        self._test('Any G WHERE X in_group G, G name "managers", EXISTS(X copain T, T login in ("comme", "cochon"))',
                   [('FetchStep', [('Any T WHERE T login IN("comme", "cochon"), T is CWUser', [{'T': 'CWUser'}])],
                     [self.ldap, self.system], None, {'T': 'table0.C0'}, []),
                    ('OneFetchStep',
                     [('Any G WHERE X in_group G, G name "managers", EXISTS(X copain T, T is CWUser), G is CWGroup, X is CWUser',
                       [{'X': 'CWUser', 'T': 'CWUser', 'G': 'CWGroup'}])],
                     None, None, [self.system], {'T': 'table0.C0'}, [])])

    def test_exists3(self):
        self._test('Any G,L WHERE X in_group G, X login L, G name "managers", EXISTS(X copain T, T login in ("comme", "cochon"))',
                   [('FetchStep',
                     [('Any T WHERE T login IN("comme", "cochon"), T is CWUser',
                       [{'T': 'CWUser'}])],
                     [self.ldap, self.system], None, {'T': 'table0.C0'}, []),
                    ('FetchStep',
                     [('Any L,X WHERE X login L, X is CWUser', [{'X': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None,
                     {'X': 'table1.C1', 'X.login': 'table1.C0', 'L': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any G,L WHERE X in_group G, X login L, G name "managers", EXISTS(X copain T, T is CWUser), G is CWGroup, X is CWUser',
                       [{'G': 'CWGroup', 'L': 'String', 'T': 'CWUser', 'X': 'CWUser'}])],
                     None, None,
                     [self.system], {'T': 'table0.C0', 'X': 'table1.C1', 'X.login': 'table1.C0', 'L': 'table1.C0'}, [])])

    def test_exists4(self):
        self._test('Any G,L WHERE X in_group G, X login L, G name "managers", '
                   'EXISTS(X copain T, T login L, T login in ("comme", "cochon")) OR '
                   'EXISTS(X in_state S, S name "pascontent", NOT X copain T2, T2 login "billy")',
                   [('FetchStep',
                     [('Any T,L WHERE T login L, T login IN("comme", "cochon"), T is CWUser', [{'T': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None,
                     {'T': 'table0.C0', 'T.login': 'table0.C1', 'L': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any T2 WHERE T2 login "billy", T2 is CWUser', [{'T2': 'CWUser'}])],
                     [self.ldap, self.system], None, {'T2': 'table1.C0'}, []),
                    ('FetchStep',
                     [('Any L,X WHERE X login L, X is CWUser', [{'X': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None, {'X': 'table2.C1', 'X.login': 'table2.C0', 'L': 'table2.C0'}, []),
                    ('OneFetchStep',
                     [('Any G,L WHERE X in_group G, X login L, G name "managers", (EXISTS(X copain T, T login L, T is CWUser)) OR (EXISTS(X in_state S, S name "pascontent", NOT EXISTS(X copain T2), S is State)), G is CWGroup, T2 is CWUser, X is CWUser',
                       [{'G': 'CWGroup', 'L': 'String', 'S': 'State', 'T': 'CWUser', 'T2': 'CWUser', 'X': 'CWUser'}])],
                     None, None, [self.system],
                     {'T2': 'table1.C0', 'L': 'table2.C0',
                      'T': 'table0.C0', 'T.login': 'table0.C1', 'X': 'table2.C1', 'X.login': 'table2.C0'}, [])])

    def test_exists5(self):
        self._test('Any GN,L WHERE X in_group G, X login L, G name GN, '
                   'EXISTS(X copain T, T login in ("comme", "cochon")) AND '
                   'NOT EXISTS(X copain T2, T2 login "billy")',
                   [('FetchStep', [('Any T WHERE T login IN("comme", "cochon"), T is CWUser',
                                    [{'T': 'CWUser'}])],
                     [self.ldap, self.system], None, {'T': 'table0.C0'}, []),
                    ('FetchStep', [('Any T2 WHERE T2 login "billy", T2 is CWUser', [{'T2': 'CWUser'}])],
                     [self.ldap, self.system], None, {'T2': 'table1.C0'}, []),
                    ('FetchStep', [('Any L,X WHERE X login L, X is CWUser', [{'X': 'CWUser', 'L': 'String'}])],
                     [self.ldap, self.system], None,
                     {'X': 'table2.C1', 'X.login': 'table2.C0', 'L': 'table2.C0'}, []),
                    ('OneFetchStep', [('Any GN,L WHERE X in_group G, X login L, G name GN, EXISTS(X copain T, T is CWUser), NOT EXISTS(X copain T2, T2 is CWUser), G is CWGroup, X is CWUser',
                       [{'G': 'CWGroup', 'GN': 'String', 'L': 'String', 'T': 'CWUser', 'T2': 'CWUser', 'X': 'CWUser'}])],
                     None, None, [self.system],
                     {'T': 'table0.C0', 'T2': 'table1.C0',
                      'X': 'table2.C1', 'X.login': 'table2.C0', 'L': 'table2.C0'}, [])])

    def test_exists_security_no_invariant(self):
        ueid = self.session.user.eid
        self._test('Any X,AA,AB,AC,AD ORDERBY AA WHERE X is CWUser, X login AA, X firstname AB, X surname AC, X modification_date AD, A eid %(B)s, \
    EXISTS(((X identity A) OR \
            (EXISTS(X in_group C, C name IN("managers", "staff"), C is CWGroup))) OR \
            (EXISTS(X in_group D, A in_group D, NOT D name "users", D is CWGroup)))',
               [('FetchStep', [('Any X,AA,AB,AC,AD WHERE X login AA, X firstname AB, X surname AC, X modification_date AD, X is CWUser',
                                [{'AA': 'String', 'AB': 'String', 'AC': 'String', 'AD': 'Datetime',
                                  'X': 'CWUser'}])],
                 [self.ldap, self.system], None, {'AA': 'table0.C1', 'AB': 'table0.C2',
                                                  'AC': 'table0.C3', 'AD': 'table0.C4',
                                                  'X': 'table0.C0',
                                                  'X.firstname': 'table0.C2',
                                                  'X.login': 'table0.C1',
                                                  'X.modification_date': 'table0.C4',
                                                  'X.surname': 'table0.C3'}, []),
                ('OneFetchStep', [('Any X,AA,AB,AC,AD ORDERBY AA WHERE X login AA, X firstname AB, X surname AC, X modification_date AD, EXISTS(((X identity %(ueid)s) OR (EXISTS(X in_group C, C name IN("managers", "staff"), C is CWGroup))) OR (EXISTS(X in_group D, %(ueid)s in_group D, NOT D name "users", D is CWGroup))), X is CWUser' % {'ueid': ueid},
                                   [{'AA': 'String', 'AB': 'String', 'AC': 'String', 'AD': 'Datetime',
                                     'C': 'CWGroup', 'D': 'CWGroup', 'X': 'CWUser'}])],
                 None, None, [self.system],
                 {'AA': 'table0.C1', 'AB': 'table0.C2', 'AC': 'table0.C3', 'AD': 'table0.C4',
                  'X': 'table0.C0',
                  'X.firstname': 'table0.C2', 'X.login': 'table0.C1', 'X.modification_date': 'table0.C4', 'X.surname': 'table0.C3'},
                 [])],
                   {'B': ueid})

    def test_relation_need_split(self):
        self._test('Any X, S WHERE X in_state S',
                   [('UnionStep', None, None, [
                       ('OneFetchStep', [('Any X,S WHERE X in_state S, S is State, X is IN(Affaire, CWUser)',
                                          [{'X': 'Affaire', 'S': 'State'}, {'X': 'CWUser', 'S': 'State'}])],
                        None, None, [self.system], {}, []),
                       ('OneFetchStep', [('Any X,S WHERE X in_state S, S is State, X is Note',
                                          [{'X': 'Note', 'S': 'State'}])],
                        None, None, [self.cards, self.system], {}, []),
                    ])])

    def test_relation_selection_need_split(self):
        self._test('Any X,S,U WHERE X in_state S, X todo_by U',
                   [('FetchStep', [('Any X,S WHERE X in_state S, S is State, X is Note',
                                    [{'X': 'Note', 'S': 'State'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'S': 'table0.C1'}, []),
                     ('UnionStep', None, None,
                      [('OneFetchStep', [('Any X,S,U WHERE X in_state S, X todo_by U, S is State, U is Personne, X is Affaire',
                                          [{'X': 'Affaire', 'S': 'State', 'U': 'Personne'}])],
                        None, None, [self.system], {}, []),
                       ('OneFetchStep', [('Any X,S,U WHERE X todo_by U, S is State, U is CWUser, X is Note',
                                          [{'X': 'Note', 'S': 'State', 'U': 'CWUser'}])],
                        None, None, [self.system], {'X': 'table0.C0', 'S': 'table0.C1'}, []),
                       ])
                    ])

    def test_relation_restriction_need_split(self):
        self._test('Any X,U WHERE X in_state S, S name "pending", X todo_by U',
                   [('FetchStep', [('Any X WHERE X in_state S, S name "pending", S is State, X is Note',
                                    [{'X': 'Note', 'S': 'State'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0'}, []),
                     ('UnionStep', None, None,
                      [('OneFetchStep', [('Any X,U WHERE X todo_by U, U is CWUser, X is Note',
                                          [{'X': 'Note', 'U': 'CWUser'}])],
                        None, None, [self.system], {'X': 'table0.C0'}, []),
                       ('OneFetchStep', [('Any X,U WHERE X in_state S, S name "pending", X todo_by U, S is State, U is Personne, X is Affaire',
                                          [{'S': 'State', 'U': 'Personne', 'X': 'Affaire'}])],
                        None, None, [self.system], {}, [])
                       ])
                    ])

    def test_relation_restriction_ambigous_need_split(self):
        self._test('Any X,T WHERE X in_state S, S name "pending", T tags X',
                   [('FetchStep', [('Any X WHERE X in_state S, S name "pending", S is State, X is Note',
                                    [{'X': 'Note', 'S': 'State'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0'}, []),
                    ('UnionStep', None, None, [
                        ('OneFetchStep', [('Any X,T WHERE T tags X, T is Tag, X is Note',
                                           [{'X': 'Note', 'T': 'Tag'}])],
                         None, None,
                         [self.system], {'X': 'table0.C0'}, []),
                        ('OneFetchStep', [('Any X,T WHERE X in_state S, S name "pending", T tags X, S is State, T is Tag, X is IN(Affaire, CWUser)',
                                           [{'X': 'Affaire', 'S': 'State', 'T': 'Tag'},
                                            {'X': 'CWUser', 'S': 'State', 'T': 'Tag'}])],
                         None, None,
                         [self.system], {}, []),
                        ])
                    ])

    def test_not_relation_no_split_internal(self):
        ueid = self.session.user.eid
        # NOT on a relation supported by rql and system source: we want to get
        # all states (eg from both sources) which are not related to entity with the
        # given eid. The "NOT X in_state S, X eid %(x)s" expression is necessarily true
        # in the source where %(x)s is not coming from and will be removed during rql
        # generation for the external source
        self._test('Any SN WHERE NOT X in_state S, X eid %(x)s, S name SN',
                   [('OneFetchStep', [('Any SN WHERE NOT EXISTS(%s in_state S), S name SN, S is State' % ueid,
                                       [{'S': 'State', 'SN': 'String'}])],
                     None, None, [self.cards, self.system], {}, [])],
                   {'x': ueid})

    def test_not_relation_no_split_external(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        # similar to the above test but with an eid coming from the external source.
        # the same plan may be used, since we won't find any record in the system source
        # linking 9999999 to a state
        self._test('Any SN WHERE NOT X in_state S, X eid %(x)s, S name SN',
                   [('OneFetchStep', [('Any SN WHERE NOT EXISTS(999999 in_state S), S name SN, S is State',
                                       [{'S': 'State', 'SN': 'String'}])],
                     None, None, [self.cards, self.system], {}, [])],
                   {'x': 999999})

    def test_not_relation_need_split(self):
        self._test('Any SN WHERE NOT X in_state S, S name SN',
                   [('FetchStep', [('Any SN,S WHERE S name SN, S is State',
                                    [{'S': 'State', 'SN': 'String'}])],
                     [self.cards, self.system], None, {'S': 'table0.C1', 'S.name': 'table0.C0', 'SN': 'table0.C0'},
                     []),
                    ('IntersectStep', None, None,
                     [('OneFetchStep',
                       [('Any SN WHERE NOT EXISTS(X in_state S, X is Note), S name SN, S is State',
                         [{'S': 'State', 'SN': 'String', 'X': 'Note'}])],
                       None, None, [self.cards, self.system], {},
                       []),
                      ('OneFetchStep',
                       [('Any SN WHERE NOT EXISTS(X in_state S, X is IN(Affaire, CWUser)), S name SN, S is State',
                         [{'S': 'State', 'SN': 'String', 'X': 'Affaire'},
                          {'S': 'State', 'SN': 'String', 'X': 'CWUser'}])],
                       None, None, [self.system], {'S': 'table0.C1', 'S.name': 'table0.C0', 'SN': 'table0.C0'},
                       []),]
                     )])

    def test_external_attributes_and_relation(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any A,B,C,D WHERE A eid %(x)s,A creation_date B,A modification_date C, A todo_by D?',
                   [('FetchStep', [('Any A,B,C WHERE A eid 999999, A creation_date B, A modification_date C, A is Note',
                                    [{'A': 'Note', 'C': 'Datetime', 'B': 'Datetime'}])],
                     [self.cards], None,
                     {'A': 'table0.C0', 'A.creation_date': 'table0.C1', 'A.modification_date': 'table0.C2', 'C': 'table0.C2', 'B': 'table0.C1'}, []),
                    #('FetchStep', [('Any D WHERE D is CWUser', [{'D': 'CWUser'}])],
                    # [self.ldap, self.system], None, {'D': 'table1.C0'}, []),
                    ('OneFetchStep', [('Any A,B,C,D WHERE A creation_date B, A modification_date C, A todo_by D?, A is Note, D is CWUser',
                                       [{'A': 'Note', 'C': 'Datetime', 'B': 'Datetime', 'D': 'CWUser'}])],
                     None, None, [self.system],
                     {'A': 'table0.C0', 'A.creation_date': 'table0.C1', 'A.modification_date': 'table0.C2', 'C': 'table0.C2', 'B': 'table0.C1'}, [])],
                   {'x': 999999})


    def test_simplified_var_1(self):
        ueid = self.session.user.eid
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        # need access to cards source since X table has to be accessed because of the outer join
        self._test('Any U WHERE U in_group G, (G name IN ("managers", "logilab") OR '
                   '(X require_permission P?, P name "bla", P require_group G)), X eid %(x)s, U eid %(u)s',
                   [('FetchStep',
                     [('Any 999999', [{}])], [self.cards],
                     None, {u'%(x)s': 'table0.C0'}, []),
                    ('OneFetchStep',
                     [(u'Any 6 WHERE 6 in_group G, (G name IN("managers", "logilab")) OR '
                       '(X require_permission P?, P name "bla", P require_group G), '
                       'G is CWGroup, P is CWPermission, X is Note',
                       [{'G': 'CWGroup', 'P': 'CWPermission', 'X': 'Note'}])],
                     None, None, [self.system], {u'%(x)s': 'table0.C0'}, [])],
                   {'x': 999999, 'u': ueid})

    def test_simplified_var_2(self):
        ueid = self.session.user.eid
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        # no need access to source since X is invariant
        self._test('Any U WHERE U in_group G, (G name IN ("managers", "logilab") OR '
                   '(X require_permission P, P name "bla", P require_group G)), X eid %(x)s, U eid %(u)s',
                   [('OneFetchStep', [('Any %s WHERE %s in_group G, (G name IN("managers", "logilab")) OR (999999 require_permission P, P name "bla", P require_group G)' % (ueid, ueid),
                                       [{'G': 'CWGroup', 'P': 'CWPermission'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999, 'u': ueid})

    def test_has_text(self):
        self._test('Card X WHERE X has_text "toto"',
                   [('OneFetchStep', [('Any X WHERE X has_text "toto", X is Card',
                                       [{'X': 'Card'}])],
                     None, None, [self.system], {}, [])])

    def test_has_text_3(self):
        self._test('Any X WHERE X has_text "toto", X title "zoubidou", X is IN (Card, EmailThread)',
                   [('FetchStep', [(u'Any X WHERE X title "zoubidou", X is Card',
                                    [{'X': 'Card'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0'}, []),
                    ('UnionStep', None, None, [
                        ('OneFetchStep', [(u'Any X WHERE X has_text "toto", X is Card',
                                           [{'X': 'Card'}])],
                         None, None, [self.system], {'X': 'table0.C0'}, []),
                        ('OneFetchStep', [(u'Any X WHERE X has_text "toto", X title "zoubidou", X is EmailThread',
                                           [{'X': 'EmailThread'}])],
                         None, None, [self.system], {}, []),
                        ]),
                    ])

    def test_has_text_orderby_rank(self):
        self._test('Any X ORDERBY FTIRANK(X) WHERE X has_text "bla", X firstname "bla"',
                   [('FetchStep', [('Any X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('AggrStep', 'SELECT table1.C1 FROM table1\nORDER BY table1.C0', None, [
                        ('FetchStep', [('Any FTIRANK(X),X WHERE X has_text "bla", X is CWUser',
                                        [{'X': 'CWUser'}])],
                         [self.system], {'X': 'table0.C0'}, {'FTIRANK(X)': 'table1.C0', 'X': 'table1.C1'}, []),
                        ('FetchStep', [('Any FTIRANK(X),X WHERE X has_text "bla", X firstname "bla", X is Personne',
                                        [{'X': 'Personne'}])],
                         [self.system], {}, {'FTIRANK(X)': 'table1.C0', 'X': 'table1.C1'}, []),
                        ]),
                    ])

    def test_security_has_text_orderby_rank(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X ORDERBY FTIRANK(X) WHERE X has_text "bla", X firstname "bla"',
                   [('FetchStep', [('Any X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table1.C0'}, []),
                    ('UnionFetchStep',
                     [('FetchStep', [('Any X WHERE X firstname "bla", X is Personne', [{'X': 'Personne'}])],
                       [self.system], {}, {'X': 'table0.C0'}, []),
                      ('FetchStep', [('Any X WHERE EXISTS(X owned_by %s), X is CWUser' % ueid, [{'X': 'CWUser'}])],
                       [self.system], {'X': 'table1.C0'}, {'X': 'table0.C0'}, [])]),
                    ('OneFetchStep', [('Any X ORDERBY FTIRANK(X) WHERE X has_text "bla"',
                                       [{'X': 'CWUser'}, {'X': 'Personne'}])],
                     None, None, [self.system], {'X': 'table0.C0'}, []),
                    ])

    def test_has_text_select_rank(self):
        self._test('Any X, FTIRANK(X) WHERE X has_text "bla", X firstname "bla"',
                   # XXX unecessary duplicate selection
                   [('FetchStep', [('Any X,X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C1'}, []),
                    ('UnionStep', None, None, [
                        ('OneFetchStep', [('Any X,FTIRANK(X) WHERE X has_text "bla", X is CWUser', [{'X': 'CWUser'}])],
                         None, None, [self.system], {'X': 'table0.C1'}, []),
                        ('OneFetchStep', [('Any X,FTIRANK(X) WHERE X has_text "bla", X firstname "bla", X is Personne', [{'X': 'Personne'}])],
                         None, None, [self.system], {}, []),
                        ]),
                    ])

    def test_security_has_text_select_rank(self):
        # use a guest user
        self.session = self.user_groups_session('guests')
        ueid = self.session.user.eid
        self._test('Any X, FTIRANK(X) WHERE X has_text "bla", X firstname "bla"',
                   [('FetchStep', [('Any X,X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C1'}, []),
                    ('UnionStep', None, None, [
                        ('OneFetchStep', [('Any X,FTIRANK(X) WHERE X has_text "bla", EXISTS(X owned_by %s), X is CWUser' % ueid, [{'X': 'CWUser'}])],
                         None, None, [self.system], {'X': 'table0.C1'}, []),
                        ('OneFetchStep', [('Any X,FTIRANK(X) WHERE X has_text "bla", X firstname "bla", X is Personne', [{'X': 'Personne'}])],
                         None, None, [self.system], {}, []),
                        ]),
                    ])

    def test_sort_func(self):
        self._test('Note X ORDERBY DUMB_SORT(RF) WHERE X type RF',
                   [('AggrStep', 'SELECT table0.C0 FROM table0\nORDER BY DUMB_SORT(table0.C1)', None, [
                       ('FetchStep', [('Any X,RF WHERE X type RF, X is Note',
                                       [{'X': 'Note', 'RF': 'String'}])],
                        [self.cards, self.system], {}, {'X': 'table0.C0', 'X.type': 'table0.C1', 'RF': 'table0.C1'}, []),
                       ])
                    ])

    def test_ambigous_sort_func(self):
        self._test('Any X ORDERBY DUMB_SORT(RF) WHERE X title RF, X is IN (Bookmark, Card, EmailThread)',
                   [('AggrStep', 'SELECT table0.C0 FROM table0\nORDER BY DUMB_SORT(table0.C1)', None,
                     [('FetchStep', [('Any X,RF WHERE X title RF, X is Card',
                                      [{'X': 'Card', 'RF': 'String'}])],
                       [self.cards, self.system], {},
                       {'X': 'table0.C0', 'X.title': 'table0.C1', 'RF': 'table0.C1'}, []),
                      ('FetchStep', [('Any X,RF WHERE X title RF, X is IN(Bookmark, EmailThread)',
                                      [{'RF': 'String', 'X': 'Bookmark'},
                                       {'RF': 'String', 'X': 'EmailThread'}])],
                       [self.system], {},
                       {'X': 'table0.C0', 'X.title': 'table0.C1', 'RF': 'table0.C1'}, []),
                      ]),
                   ])

    def test_attr_unification_1(self):
        self._test('Any X,Y WHERE X is Bookmark, Y is Card, X title T, Y title T',
                   [('FetchStep',
                     [('Any Y,T WHERE Y title T, Y is Card', [{'T': 'String', 'Y': 'Card'}])],
                     [self.cards, self.system], None,
                     {'T': 'table0.C1', 'Y': 'table0.C0', 'Y.title': 'table0.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,Y WHERE X title T, Y title T, X is Bookmark, Y is Card',
                       [{'T': 'String', 'X': 'Bookmark', 'Y': 'Card'}])],
                     None, None, [self.system],
                     {'T': 'table0.C1', 'Y': 'table0.C0', 'Y.title': 'table0.C1'}, [])
                    ])

    def test_attr_unification_2(self):
        self._test('Any X,Y WHERE X is Note, Y is Card, X type T, Y title T',
                   [('FetchStep',
                     [('Any X,T WHERE X type T, X is Note', [{'T': 'String', 'X': 'Note'}])],
                     [self.cards, self.system], None,
                     {'T': 'table0.C1', 'X': 'table0.C0', 'X.type': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any Y,T WHERE Y title T, Y is Card', [{'T': 'String', 'Y': 'Card'}])],
                     [self.cards, self.system], None,
                     {'T': 'table1.C1', 'Y': 'table1.C0', 'Y.title': 'table1.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,Y WHERE X type T, Y title T, X is Note, Y is Card',
                       [{'T': 'String', 'X': 'Note', 'Y': 'Card'}])],
                     None, None, [self.system],
                     {'T': 'table1.C1',
                      'X': 'table0.C0', 'X.type': 'table0.C1',
                      'Y': 'table1.C0', 'Y.title': 'table1.C1'}, [])
                    ])

    def test_attr_unification_neq_1(self):
        self._test('Any X,Y WHERE X is Bookmark, Y is Card, X creation_date D, Y creation_date > D',
                   [('FetchStep',
                     [('Any Y,D WHERE Y creation_date D, Y is Card',
                       [{'D': 'Datetime', 'Y': 'Card'}])],
                     [self.cards,self.system], None,
                     {'D': 'table0.C1', 'Y': 'table0.C0', 'Y.creation_date': 'table0.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,Y WHERE X creation_date D, Y creation_date > D, X is Bookmark, Y is Card',
                       [{'D': 'Datetime', 'X': 'Bookmark', 'Y': 'Card'}])], None, None,
                     [self.system],
                     {'D': 'table0.C1', 'Y': 'table0.C0', 'Y.creation_date': 'table0.C1'}, [])
                   ])

    def test_subquery_1(self):
        ueid = self.session.user.eid
        self._test('DISTINCT Any B,C ORDERBY C WHERE A created_by B, B login C, EXISTS(B owned_by D), D eid %(E)s '
                   'WITH A,N BEING ((Any X,N WHERE X is Tag, X name N) UNION (Any X,T WHERE X is Bookmark, X title T))',
                   [('FetchStep', [('Any X,N WHERE X is Tag, X name N', [{'N': 'String', 'X': 'Tag'}]),
                                   ('Any X,T WHERE X is Bookmark, X title T',
                                    [{'T': 'String', 'X': 'Bookmark'}])],
                     [self.system], {}, {'N': 'table0.C1', 'X': 'table0.C0', 'X.name': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any B,C WHERE B login C, B is CWUser', [{'B': 'CWUser', 'C': 'String'}])],
                     [self.ldap, self.system], None, {'B': 'table1.C0', 'B.login': 'table1.C1', 'C': 'table1.C1'}, []),
                    ('OneFetchStep', [('DISTINCT Any B,C ORDERBY C WHERE A created_by B, B login C, EXISTS(B owned_by %s), B is CWUser, A is IN(Bookmark, Tag)' % ueid,
                                       [{'A': 'Bookmark', 'B': 'CWUser', 'C': 'String'},
                                        {'A': 'Tag', 'B': 'CWUser', 'C': 'String'}])],
                     None, None, [self.system],
                     {'A': 'table0.C0',
                      'B': 'table1.C0', 'B.login': 'table1.C1',
                      'C': 'table1.C1',
                      'N': 'table0.C1'},
                     [])],
                   {'E': ueid})

    def test_subquery_2(self):
        ueid = self.session.user.eid
        self._test('DISTINCT Any B,C ORDERBY C WHERE A created_by B, B login C, EXISTS(B owned_by D), D eid %(E)s '
                   'WITH A,N BEING ((Any X,N WHERE X is Tag, X name N) UNION (Any X,T WHERE X is Card, X title T))',
                   [('UnionFetchStep',
                     [('FetchStep', [('Any X,N WHERE X is Tag, X name N', [{'N': 'String', 'X': 'Tag'}])],
                       [self.system], {},
                       {'N': 'table0.C1',
                        'T': 'table0.C1',
                        'X': 'table0.C0',
                        'X.name': 'table0.C1',
                        'X.title': 'table0.C1'}, []),
                      ('FetchStep', [('Any X,T WHERE X is Card, X title T',
                                      [{'T': 'String', 'X': 'Card'}])],
                       [self.cards, self.system], {},
                       {'N': 'table0.C1',
                        'T': 'table0.C1',
                        'X': 'table0.C0',
                        'X.name': 'table0.C1',
                        'X.title': 'table0.C1'}, []),
                      ]),
                    ('FetchStep',
                     [('Any B,C WHERE B login C, B is CWUser', [{'B': 'CWUser', 'C': 'String'}])],
                     [self.ldap, self.system], None, {'B': 'table1.C0', 'B.login': 'table1.C1', 'C': 'table1.C1'}, []),
                    ('OneFetchStep', [('DISTINCT Any B,C ORDERBY C WHERE A created_by B, B login C, EXISTS(B owned_by %s), B is CWUser, A is IN(Card, Tag)' % ueid,
                                       [{'A': 'Card', 'B': 'CWUser', 'C': 'String'},
                                        {'A': 'Tag', 'B': 'CWUser', 'C': 'String'}])],
                     None, None, [self.system],
                     {'A': 'table0.C0',
                      'B': 'table1.C0', 'B.login': 'table1.C1',
                      'C': 'table1.C1',
                      'N': 'table0.C1'},
                     [])],
                   {'E': ueid})

    def test_eid_dont_cross_relation_1(self):
        repo._type_source_cache[999999] = ('Personne', 'system', 999999, 'system')
        self._test('Any Y,YT WHERE X eid %(x)s, X fiche Y, Y title YT',
                   [('OneFetchStep', [('Any Y,YT WHERE X eid 999999, X fiche Y, Y title YT',
                                       [{'X': 'Personne', 'Y': 'Card', 'YT': 'String'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999})

    def test_eid_dont_cross_relation_2(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self.cards.dont_cross_relations.add('concerne')
        try:
            self._test('Any Y,S,YT,X WHERE Y concerne X, Y in_state S, X eid 999999, Y ref YT',
                   [('OneFetchStep', [('Any Y,S,YT,999999 WHERE Y concerne 999999, Y in_state S, Y ref YT',
                                       [{'Y': 'Affaire', 'YT': 'String', 'S': 'State'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999})
        finally:
            self.cards.dont_cross_relations.remove('concerne')


    # external source w/ .cross_relations == ['multisource_crossed_rel'] ######

    def test_crossed_relation_eid_1_invariant(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   [('OneFetchStep', [('Any Y WHERE 999999 multisource_crossed_rel Y', [{u'Y': 'Note'}])],
                      None, None, [self.system], {}, [])
                    ],
                   {'x': 999999,})

    def test_crossed_relation_eid_1_needattr(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('Any Y,T WHERE X eid %(x)s, X multisource_crossed_rel Y, Y type T',
                   [('FetchStep', [('Any Y,T WHERE Y type T, Y is Note', [{'T': 'String', 'Y': 'Note'}])],
                     [self.cards, self.system], None,
                     {'T': 'table0.C1', 'Y': 'table0.C0', 'Y.type': 'table0.C1'}, []),
                    ('OneFetchStep', [('Any Y,T WHERE 999999 multisource_crossed_rel Y, Y type T, Y is Note',
                                       [{'T': 'String', 'Y': 'Note'}])],
                     None, None, [self.system],
                     {'T': 'table0.C1', 'Y': 'table0.C0', 'Y.type': 'table0.C1'}, []),
                    ],
                   {'x': 999999,})

    def test_crossed_relation_eid_2_invariant(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   [('OneFetchStep', [('Any Y WHERE 999999 multisource_crossed_rel Y, Y is Note', [{'Y': 'Note'}])],
                      None, None, [self.cards, self.system], {}, [])
                    ],
                   {'x': 999999,})

    def test_crossed_relation_eid_2_needattr(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any Y,T WHERE X eid %(x)s, X multisource_crossed_rel Y, Y type T',
                   [('OneFetchStep', [('Any Y,T WHERE 999999 multisource_crossed_rel Y, Y type T, Y is Note',
                                       [{'T': 'String', 'Y': 'Note'}])],
                     None, None, [self.cards, self.system], {},
                     []),
                    ],
                   {'x': 999999,})

    def test_crossed_relation_eid_not_1(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('Any Y WHERE X eid %(x)s, NOT X multisource_crossed_rel Y',
                   [('FetchStep', [('Any Y WHERE Y is Note', [{'Y': 'Note'}])],
                     [self.cards, self.system], None, {'Y': 'table0.C0'}, []),
                    ('OneFetchStep', [('Any Y WHERE NOT EXISTS(999999 multisource_crossed_rel Y), Y is Note',
                                       [{'Y': 'Note'}])],
                     None, None, [self.system],
                     {'Y': 'table0.C0'},  [])],
                   {'x': 999999,})

#     def test_crossed_relation_eid_not_2(self):
#         repo._type_source_cache[999999] = ('Note', 'cards', 999999)
#         self._test('Any Y WHERE X eid %(x)s, NOT X multisource_crossed_rel Y',
#                    [],
#                    {'x': 999999,})

    def test_crossed_relation_base_XXXFIXME(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('Any X,Y,T WHERE X multisource_crossed_rel Y, Y type T, X type T',
                   [('FetchStep', [('Any X,T WHERE X type T, X is Note', [{'T': 'String', 'X': 'Note'}])],
                     [self.cards, self.system], None,
                     {'T': 'table0.C1', 'X': 'table0.C0', 'X.type': 'table0.C1'}, []),
                    ('FetchStep',  [('Any Y,T WHERE Y type T, Y is Note', [{'T': 'String', 'Y': 'Note'}])],
                     [self.cards, self.system], None,
                     {'T': 'table1.C1', 'Y': 'table1.C0', 'Y.type': 'table1.C1'},  []),
                    ('FetchStep', [('Any X,Y WHERE X multisource_crossed_rel Y, X is Note, Y is Note',
                                    [{'X': 'Note', 'Y': 'Note'}])],
                     [self.cards, self.system], None,
                     {'X': 'table2.C0', 'Y': 'table2.C1'},
                     []),
                    ('OneFetchStep', [('Any X,Y,T WHERE X multisource_crossed_rel Y, Y type T, X type T, '
                                       'X is Note, Y is Note, Y identity A, X identity B, A is Note, B is Note',
                                       [{u'A': 'Note', u'B': 'Note', 'T': 'String', 'X': 'Note', 'Y': 'Note'}])],
                     None, None,
                     [self.system],
                     {'A': 'table1.C0',
                      'B': 'table0.C0',
                      'T': 'table1.C1',
                      'X': 'table2.C0',
                      'X.type': 'table0.C1',
                      'Y': 'table2.C1',
                      'Y.type': 'table1.C1'},
                     []),
                    ],
                    {'x': 999999,})

    def test_crossed_relation_noeid_needattr(self):
        # http://www.cubicweb.org/ticket/1382452
        self._test('DISTINCT Any DEP WHERE DEP is Note, P type "cubicweb-foo", P multisource_crossed_rel DEP, DEP type LIKE "cubicweb%"',
                   [('FetchStep', [(u'Any DEP WHERE DEP type LIKE "cubicweb%", DEP is Note',
                                    [{'DEP': 'Note'}])],
                     [self.cards, self.system], None,
                     {'DEP': 'table0.C0'},
                     []),
                    ('FetchStep', [(u'Any P WHERE P type "cubicweb-foo", P is Note', [{'P': 'Note'}])],
                     [self.cards, self.system], None, {'P': 'table1.C0'},
                     []),
                    ('FetchStep', [('Any DEP,P WHERE P multisource_crossed_rel DEP, DEP is Note, P is Note',
                                    [{'DEP': 'Note', 'P': 'Note'}])],
                     [self.cards, self.system], None, {'DEP': 'table2.C0', 'P': 'table2.C1'},
                     []),
                    ('OneFetchStep',
                     [('DISTINCT Any DEP WHERE P multisource_crossed_rel DEP, DEP is Note, '
                       'P is Note, DEP identity A, P identity B, A is Note, B is Note',
                       [{u'A': 'Note', u'B': 'Note', 'DEP': 'Note', 'P': 'Note'}])],
                     None, None, [self.system],
                     {'A': 'table0.C0', 'B': 'table1.C0', 'DEP': 'table2.C0', 'P': 'table2.C1'},
                     [])])

    def test_crossed_relation_noeid_invariant(self):
        # see comment in http://www.cubicweb.org/ticket/1382452
        self.schema.add_relation_def(
            RelationDefinition(subject='Note', name='multisource_crossed_rel', object='Affaire'))
        self.repo.set_schema(self.schema)
        try:
            self._test('DISTINCT Any P,DEP WHERE P type "cubicweb-foo", P multisource_crossed_rel DEP',
                       [('FetchStep',
                         [('Any DEP WHERE DEP is Note', [{'DEP': 'Note'}])],
                         [self.cards, self.system], None, {'DEP': 'table0.C0'}, []),
                        ('FetchStep',
                         [(u'Any P WHERE P type "cubicweb-foo", P is Note', [{'P': 'Note'}])],
                         [self.cards, self.system], None, {'P': 'table1.C0'}, []),
                        ('UnionStep', None, None,
                         [('OneFetchStep',
                           [('DISTINCT Any P,DEP WHERE P multisource_crossed_rel DEP, DEP is Note, P is Note',
                             [{'DEP': 'Note', 'P': 'Note'}])],
                           None, None, [self.cards], None, []),
                          ('OneFetchStep',
                           [('DISTINCT Any P,DEP WHERE P multisource_crossed_rel DEP, DEP is Note, P is Note',
                             [{'DEP': 'Note', 'P': 'Note'}])],
                           None, None, [self.system],
                           {'DEP': 'table0.C0', 'P': 'table1.C0'},
                           []),
                          ('OneFetchStep',
                           [('DISTINCT Any P,DEP WHERE P multisource_crossed_rel DEP, DEP is Affaire, P is Note',
                             [{'DEP': 'Affaire', 'P': 'Note'}])],
                           None, None, [self.system], {'P': 'table1.C0'},
                           [])])
                        ])
        finally:
            self.schema.del_relation_def('Note', 'multisource_crossed_rel', 'Affaire')
            self.repo.set_schema(self.schema)

    # edition queries tests ###################################################

    def test_insert_simplified_var_1(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        repo._type_source_cache[999998] = ('State', 'system', None, 'system')
        self._test('INSERT Note X: X in_state S, X type T WHERE S eid %(s)s, N eid %(n)s, N type T',
                   [('InsertStep',
                     [('InsertRelationsStep',
                       [('OneFetchStep', [('Any T WHERE N eid 999999, N type T, N is Note',
                                           [{'N': 'Note', 'T': 'String'}])],
                        None, None, [self.cards], {}, [])])
                      ])
                    ],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_2(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        repo._type_source_cache[999998] = ('State', 'system', None, 'system')
        self._test('INSERT Note X: X in_state S, X type T, X migrated_from N WHERE S eid %(s)s, N eid %(n)s, N type T',
                   [('InsertStep',
                     [('InsertRelationsStep',
                       [('OneFetchStep', [('Any T WHERE N eid 999999, N type T, N is Note',
                                           [{'N': 'Note', 'T': 'String'}])],
                         None, None, [self.cards], {}, [])
                        ])
                      ])
                    ],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_3(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        repo._type_source_cache[999998] = ('State', 'cards', 999998, 'cards')
        self._test('INSERT Note X: X in_state S, X type T WHERE S eid %(s)s, N eid %(n)s, N type T',
                   [('InsertStep',
                     [('InsertRelationsStep',
                       [('OneFetchStep', [('Any T WHERE N eid 999999, N type T, N is Note',
                                           [{'N': 'Note', 'T': 'String'}])],
                         None, None, [self.cards], {}, [])]
                       )]
                     )],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_4(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        repo._type_source_cache[999998] = ('State', 'system', None, 'system')
        self._test('INSERT Note X: X in_state S, X type "bla", X migrated_from N WHERE S eid %(s)s, N eid %(n)s',
                   [('InsertStep',
                      [('InsertRelationsStep',
                        [('OneFetchStep',
                          [('Any 999999', [{}])],
                          None, None,
                          [self.system], {},
                          [])])]
                     )],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_5(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        repo._type_source_cache[999998] = ('State', 'system', None, 'system')
        self._test('INSERT Note X: X in_state S, X type "bla", X migrated_from N WHERE S eid %(s)s, N eid %(n)s, A concerne N',
                   [('InsertStep',
                     [('InsertRelationsStep',
                       [('OneFetchStep',
                         [('Any A WHERE A concerne 999999, A is Affaire',
                           [{'A': 'Affaire'}])],
                         None, None, [self.system], {}, []),
                        ]),
                      ])
                    ],
                   {'n': 999999, 's': 999998})

    def test_delete_relation1(self):
        ueid = self.session.user.eid
        self._test('DELETE X created_by Y WHERE X eid %(x)s, NOT Y eid %(y)s',
                   [('DeleteRelationsStep', [
                       ('OneFetchStep', [('Any %s,Y WHERE %s created_by Y, NOT Y eid %s, Y is CWUser' % (ueid, ueid, ueid),
                                          [{'Y': 'CWUser'}])],
                        None, None, [self.system], {}, []),
                       ]),
                    ],
                   {'x': ueid, 'y': ueid})

    def test_delete_relation2(self):
        ueid = self.session.user.eid
        self._test('DELETE X created_by Y WHERE X eid %(x)s, NOT Y login "syt"',
                   [('FetchStep', [('Any Y WHERE NOT Y login "syt", Y is CWUser', [{'Y': 'CWUser'}])],
                     [self.ldap, self.system], None, {'Y': 'table0.C0'}, []),
                    ('DeleteRelationsStep', [
                        ('OneFetchStep', [('Any %s,Y WHERE %s created_by Y, Y is CWUser'%(ueid,ueid), [{'Y': 'CWUser'}])],
                         None, None, [self.system], {'Y': 'table0.C0'}, []),
                        ]),
                    ],
                   {'x': ueid, 'y': ueid})

    def test_delete_relation3(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self.assertRaises(
            BadRQLQuery, self._test,
            'DELETE Y multisource_inlined_rel X WHERE X eid %(x)s, '
            'NOT (Y cw_source S, S name %(source)s)', [],
            {'x': 999999, 'source': 'cards'})

    def test_delete_relation4(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self.assertRaises(
            BadRQLQuery, self._test,
            'DELETE X multisource_inlined_rel Y WHERE Y is Note, X eid %(x)s, '
            'NOT (Y cw_source S, S name %(source)s)', [],
            {'x': 999999, 'source': 'cards'})

    def test_delete_entity1(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('DELETE Note X WHERE X eid %(x)s, NOT Y multisource_rel X',
                   [('DeleteEntitiesStep',
                     [('OneFetchStep', [('Any 999999 WHERE NOT EXISTS(Y multisource_rel 999999), Y is IN(Card, Note)',
                                         [{'Y': 'Card'}, {'Y': 'Note'}])],
                       None, None, [self.system], {}, [])
                      ])
                    ],
                   {'x': 999999})

    def test_delete_entity2(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('DELETE Note X WHERE X eid %(x)s, NOT X multisource_inlined_rel Y',
                   [('DeleteEntitiesStep',
                     [('OneFetchStep', [('Any X WHERE X eid 999999, NOT X multisource_inlined_rel Y, X is Note, Y is IN(Affaire, Note)',
                                         [{'X': 'Note', 'Y': 'Affaire'}, {'X': 'Note', 'Y': 'Note'}])],
                       None, None, [self.system], {}, [])
                      ])
                    ],
                   {'x': 999999})

    def test_update(self):
        self._test('SET X copain Y WHERE X login "comme", Y login "cochon"',
                   [('FetchStep',
                     [('Any X WHERE X login "comme", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('FetchStep',
                     [('Any Y WHERE Y login "cochon", Y is CWUser', [{'Y': 'CWUser'}])],
                     [self.ldap, self.system], None, {'Y': 'table1.C0'}, []),
                    ('UpdateStep',
                     [('OneFetchStep',
                       [('DISTINCT Any X,Y WHERE X is CWUser, Y is CWUser',
                         [{'X': 'CWUser', 'Y': 'CWUser'}])],
                       None, None, [self.system], {'X': 'table0.C0', 'Y': 'table1.C0'}, [])
                      ])
                    ])

    def test_update2(self):
        self._test('SET U in_group G WHERE G name ~= "bougloup%", U login "admin"',
                   [('FetchStep', [('Any U WHERE U login "admin", U is CWUser', [{'U': 'CWUser'}])],
                     [self.ldap, self.system], None, {'U': 'table0.C0'}, []),
                     ('UpdateStep', [
                        ('OneFetchStep', [('DISTINCT Any U,G WHERE G name ILIKE "bougloup%", G is CWGroup, U is CWUser',
                                           [{'U': 'CWUser', 'G': 'CWGroup'}])],
                         None, None, [self.system], {'U': 'table0.C0'}, []),
                        ]),
                    ])

    def test_update3(self):
        anoneid = self.user_groups_session('guests').user.eid
        # since we are adding a in_state relation for an entity in the system
        # source, states should only be searched in the system source as well
        self._test('SET X in_state S WHERE X eid %(x)s, S name "deactivated"',
                   [('UpdateStep', [
                       ('OneFetchStep', [('DISTINCT Any S WHERE S name "deactivated", S is State',
                                          [{'S': 'State'}])],
                        None, None, [self.system], {}, []),
                       ]),
                    ],
                   {'x': anoneid})

#     def test_update4(self):
#         # since we are adding a in_state relation with a state from the system
#         # source, CWUser should only be searched only in the system source as well
#         rset = self.execute('State X WHERE X name "activated"')
#         assert len(rset) == 1, rset
#         activatedeid = rset[0][0]
#         self._test('SET X in_state S WHERE X is CWUser, S eid %s' % activatedeid,
#                    [('UpdateStep', [
#                        ('OneFetchStep', [('DISTINCT Any X,%s WHERE X is CWUser' % activatedeid,
#                                           [{'X': 'CWUser'}])],
#                         None, None, [self.system], {}, []),
#                        ]),
#                     ])

    def test_ldap_user_related_to_invariant_and_dont_cross_rel(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self.cards.dont_cross_relations.add('created_by')
        try:
            self._test('Any X,XL WHERE E eid %(x)s, E created_by X, X login XL',
                   [('FetchStep', [('Any X,XL WHERE X login XL, X is CWUser',
                                    [{'X': 'CWUser', 'XL': 'String'}])],
                     [self.ldap, self.system], None,
                     {'X': 'table0.C0', 'X.login': 'table0.C1', 'XL': 'table0.C1'},
                     []),
                    ('OneFetchStep',
                     [('Any X,XL WHERE 999999 created_by X, X login XL, X is CWUser',
                       [{'X': 'CWUser', 'XL': 'String'}])],
                     None, None,
                     [self.system],
                     {'X': 'table0.C0', 'X.login': 'table0.C1', 'XL': 'table0.C1'},
                     [])],
                       {'x': 999999})
        finally:
            self.cards.dont_cross_relations.remove('created_by')

    def test_ambigous_cross_relation(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self.cards.support_relations['see_also'] = True
        self.cards.cross_relations.add('see_also')
        try:
            self._test('Any X,AA ORDERBY AA WHERE E eid %(x)s, E see_also X, X modification_date AA',
                       [('AggrStep',
                         'SELECT table0.C0, table0.C1 FROM table0\nORDER BY table0.C1',
                         None,
                         [('FetchStep',
                           [('Any X,AA WHERE 999999 see_also X, X modification_date AA, X is Note',
                             [{'AA': 'Datetime', 'X': 'Note'}])], [self.cards, self.system], {},
                           {'AA': 'table0.C1', 'X': 'table0.C0',
                            'X.modification_date': 'table0.C1'},
                           []),
                          ('FetchStep',
                           [('Any X,AA WHERE 999999 see_also X, X modification_date AA, X is Bookmark',
                             [{'AA': 'Datetime', 'X': 'Bookmark'}])],
                           [self.system], {},
                           {'AA': 'table0.C1', 'X': 'table0.C0',
                            'X.modification_date': 'table0.C1'},
                           [])])],
                         {'x': 999999})
        finally:
            del self.cards.support_relations['see_also']
            self.cards.cross_relations.remove('see_also')

    def test_state_of_cross(self):
        self._test('DELETE State X WHERE NOT X state_of Y',
                   [('DeleteEntitiesStep',
                     [('OneFetchStep',
                       [('Any X WHERE NOT X state_of Y, X is State, Y is Workflow',
                         [{'X': 'State', 'Y': 'Workflow'}])],
                       None, None, [self.system], {}, [])])]
                   )


    def test_source_specified_0_0(self):
        self._test('Card X WHERE X cw_source S, S eid 1',
                   [('OneFetchStep', [('Any X WHERE X cw_source 1, X is Card',
                                       [{'X': 'Card'}])],
                     None, None,
                     [self.system],{}, [])
                    ])

    def test_source_specified_0_1(self):
        self._test('Any X, S WHERE X is Card, X cw_source S, S eid 1',
                   [('OneFetchStep', [('Any X,1 WHERE X is Card, X cw_source 1',
                                       [{'X': 'Card'}])],
                     None, None,
                     [self.system],{}, [])
                    ])

    def test_source_specified_1_0(self):
        self._test('Card X WHERE X cw_source S, S name "system"',
                   [('OneFetchStep', [('Any X WHERE X cw_source S, S name "system", X is Card',
                                       [{'X': 'Card', 'S': 'CWSource'}])],
                     None, None,
                     [self.system],{}, [])
                    ])

    def test_source_specified_1_1(self):
        self._test('Any X, SN WHERE X is Card, X cw_source S, S name "system", S name SN',
                   [('OneFetchStep', [('Any X,SN WHERE X is Card, X cw_source S, S name "system", '
                                       'S name SN',
                                       [{'S': 'CWSource', 'SN': 'String', 'X': 'Card'}])],
                     None, None, [self.system], {}, [])
                    ])

    def test_source_specified_1_2(self):
        self._test('Card X WHERE X cw_source S, S name "datafeed"',
                   [('OneFetchStep', [('Any X WHERE X cw_source S, S name "datafeed", X is Card',
                                       [{'X': 'Card', 'S': 'CWSource'}])],
                     None, None,
                     [self.system],{}, [])
                    ])

    def test_source_specified_1_3(self):
        self._test('Any X, SN WHERE X is Card, X cw_source S, S name "datafeed", S name SN',
                   [('OneFetchStep', [('Any X,SN WHERE X is Card, X cw_source S, S name "datafeed", '
                                       'S name SN',
                                       [{'S': 'CWSource', 'SN': 'String', 'X': 'Card'}])],
                     None, None, [self.system], {}, [])
                    ])

    def test_source_specified_1_4(self):
        sols = []
        for sol in X_ALL_SOLS:
            sol = sol.copy()
            sol['S'] = 'CWSource'
            sols.append(sol)
        self._test('Any X WHERE X cw_source S, S name "cards"',
                   [('OneFetchStep', [('Any X WHERE X cw_source S, S name "cards"',
                                       sols)],
                     None, None,
                     [self.system],{}, [])
                    ])

    def test_source_specified_2_0(self):
        # self._test('Card X WHERE X cw_source S, NOT S eid 1',
        #            [('OneFetchStep', [('Any X WHERE X is Card',
        #                                [{'X': 'Card'}])],
        #              None, None,
        #              [self.cards],{}, [])
        #             ])
        self._test('Card X WHERE NOT X cw_source S, S eid 1',
                   [('OneFetchStep', [('Any X WHERE X is Card',
                                       [{'X': 'Card'}])],
                     None, None,
                     [self.cards],{}, [])
                    ])

    def test_source_specified_2_1(self):
        self._test('Card X WHERE X cw_source S, NOT S name "system"',
                   [('OneFetchStep', [('Any X WHERE X is Card',
                                       [{'X': 'Card'}])],
                     None, None,
                     [self.cards],{}, [])
                    ])
        self._test('Card X WHERE NOT X cw_source S, S name "system"',
                   [('OneFetchStep', [('Any X WHERE X is Card',
                                       [{'X': 'Card'}])],
                     None, None,
                     [self.cards],{}, [])
                    ])

    def test_source_specified_3_1(self):
        self._test('Any X,XT WHERE X is Card, X title XT, X cw_source S, S name "cards"',
                   [('OneFetchStep',
                     [('Any X,XT WHERE X is Card, X title XT',
                       [{'X': 'Card', 'XT': 'String'}])],
                     None, None, [self.cards], {}, [])
                    ])

    def test_source_specified_3_2(self):
        self._test('Any X,XT WHERE X is Card, X title XT, X cw_source S, S name "datafeed"',
                   [('OneFetchStep',
                     [('Any X,XT WHERE X is Card, X title XT, X cw_source S, S name "datafeed"',
                       [{'X': 'Card', 'XT': 'String', 'S': 'CWSource'}])],
                     None, None, [self.system], {}, [])
                    ])

    def test_source_specified_3_3(self):
        self.skipTest('oops')
        self._test('Any STN WHERE X is Note, X type XT, X in_state ST, ST name STN, X cw_source S, S name "cards"',
                   [('OneFetchStep',
                     [('Any X,XT WHERE X is Card, X title XT',
                       [{'X': 'Card', 'XT': 'String'}])],
                     None, None, [self.cards], {}, [])
                    ])

    def test_source_conflict_1(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        with self.assertRaises(BadRQLQuery) as cm:
            self._test('Any X WHERE X cw_source S, S name "system", X eid %(x)s',
                       [], {'x': 999999})
        self.assertEqual(str(cm.exception), 'source conflict for term %(x)s')

    def test_source_conflict_2(self):
        with self.assertRaises(BadRQLQuery) as cm:
            self._test('Card X WHERE X cw_source S, S name "systeme"', [])
        self.assertEqual(str(cm.exception), 'source conflict for term X')

    def test_source_conflict_3(self):
        self.skipTest('oops')
        self._test('CWSource X WHERE X cw_source S, S name "cards"',
                   [('OneFetchStep',
                     [(u'Any X WHERE X cw_source S, S name "cards", X is CWSource',
                       [{'S': 'CWSource', 'X': 'CWSource'}])],
                     None, None,
                     [self.system],
                     {}, [])])


    def test_ambigous_cross_relation_source_specified(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self.cards.support_relations['see_also'] = True
        self.cards.cross_relations.add('see_also')
        try:
            self._test('Any X,AA ORDERBY AA WHERE E eid %(x)s, E see_also X, X modification_date AA',
                       [('AggrStep',
                         'SELECT table0.C0, table0.C1 FROM table0\nORDER BY table0.C1',
                         None,
                         [('FetchStep',
                           [('Any X,AA WHERE 999999 see_also X, X modification_date AA, X is Note',
                             [{'AA': 'Datetime', 'X': 'Note'}])], [self.cards, self.system], {},
                           {'AA': 'table0.C1', 'X': 'table0.C0',
                            'X.modification_date': 'table0.C1'},
                           []),
                          ('FetchStep',
                           [('Any X,AA WHERE 999999 see_also X, X modification_date AA, X is Bookmark',
                             [{'AA': 'Datetime', 'X': 'Bookmark'}])],
                           [self.system], {},
                           {'AA': 'table0.C1', 'X': 'table0.C0',
                            'X.modification_date': 'table0.C1'},
                           [])])],
                         {'x': 999999})
        finally:
            del self.cards.support_relations['see_also']
            self.cards.cross_relations.remove('see_also')

    # non regression tests ####################################################

    def test_nonregr1(self):
        self._test('Any X, Y WHERE X copain Y, X login "syt", Y login "cochon"',
                   [('FetchStep',
                     [('Any X WHERE X login "syt", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('FetchStep',
                     [('Any Y WHERE Y login "cochon", Y is CWUser', [{'Y': 'CWUser'}])],
                     [self.ldap, self.system], None, {'Y': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any X,Y WHERE X copain Y, X is CWUser, Y is CWUser',
                       [{'X': 'CWUser', 'Y': 'CWUser'}])],
                     None, None, [self.system], {'X': 'table0.C0', 'Y': 'table1.C0'}, [])
                    ])

    def test_nonregr2(self):
        iworkflowable = self.session.user.cw_adapt_to('IWorkflowable')
        iworkflowable.fire_transition('deactivate')
        treid = iworkflowable.latest_trinfo().eid
        self._test('Any X ORDERBY D DESC WHERE E eid %(x)s, E wf_info_for X, X modification_date D',
                   [('FetchStep', [('Any X,D WHERE X modification_date D, X is Note',
                                    [{'X': 'Note', 'D': 'Datetime'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.modification_date': 'table0.C1', 'D': 'table0.C1'}, []),
                    ('FetchStep', [('Any X,D WHERE X modification_date D, X is CWUser',
                                    [{'X': 'CWUser', 'D': 'Datetime'}])],
                     [self.ldap, self.system], None, {'X': 'table1.C0', 'X.modification_date': 'table1.C1', 'D': 'table1.C1'}, []),
                    ('AggrStep', 'SELECT table2.C0 FROM table2\nORDER BY table2.C1 DESC', None, [
                        ('FetchStep', [('Any X,D WHERE E eid %s, E wf_info_for X, X modification_date D, E is TrInfo, X is Affaire'%treid,
                                        [{'X': 'Affaire', 'E': 'TrInfo', 'D': 'Datetime'}])],
                         [self.system],
                         {},
                         {'X': 'table2.C0', 'X.modification_date': 'table2.C1', 'D': 'table2.C1', 'E.wf_info_for': 'table2.C0'}, []),
                        ('FetchStep', [('Any X,D WHERE E eid %s, E wf_info_for X, X modification_date D, E is TrInfo, X is CWUser'%treid,
                                        [{'X': 'CWUser', 'E': 'TrInfo', 'D': 'Datetime'}])],
                         [self.system],
                         {'X': 'table1.C0', 'X.modification_date': 'table1.C1', 'D': 'table1.C1'},
                         {'X': 'table2.C0', 'X.modification_date': 'table2.C1', 'D': 'table2.C1', 'E.wf_info_for': 'table2.C0'}, []),
                        ('FetchStep', [('Any X,D WHERE E eid %s, E wf_info_for X, X modification_date D, E is TrInfo, X is Note'%treid,
                                        [{'X': 'Note', 'E': 'TrInfo', 'D': 'Datetime'}])],
                         [self.system],
                         {'X': 'table0.C0', 'X.modification_date': 'table0.C1', 'D': 'table0.C1'},
                         {'X': 'table2.C0', 'X.modification_date': 'table2.C1', 'D': 'table2.C1', 'E.wf_info_for': 'table2.C0'}, []),
                        ]),
                    ],
                   {'x': treid})

    def test_nonregr3(self):
        # original jpl query:
        # Any X, NOW - CD, P WHERE P is Project, U interested_in P, U is CWUser, U login "sthenault", X concerns P, X creation_date CD ORDERBY CD DESC LIMIT 5
        self._test('Any X, NOW - CD, P ORDERBY CD DESC LIMIT 5 WHERE P bookmarked_by U, U login "admin", P is X, X creation_date CD',
                   [('FetchStep', [('Any U WHERE U login "admin", U is CWUser', [{'U': 'CWUser'}])],
                     [self.ldap, self.system], None, {'U': 'table0.C0'}, []),
                    ('OneFetchStep', [('Any X,(NOW - CD),P ORDERBY CD DESC LIMIT 5 WHERE P bookmarked_by U, P is X, X creation_date CD, P is Bookmark, U is CWUser, X is CWEType',
                                       [{'P': 'Bookmark', 'U': 'CWUser', 'X': 'CWEType', 'CD': 'Datetime'}])],
                     5, None,  [self.system], {'U': 'table0.C0'}, [])]
                   )

    def test_nonregr4(self):
        ueid = self.session.user.eid
        self._test('Any U ORDERBY D DESC WHERE WF wf_info_for X, WF creation_date D, WF from_state FS, '
                   'WF owned_by U?, X eid %(x)s',
                   [#('FetchStep', [('Any U WHERE U is CWUser', [{'U': 'CWUser'}])],
                    # [self.ldap, self.system], None, {'U': 'table0.C0'}, []),
                    ('OneFetchStep', [('Any U ORDERBY D DESC WHERE WF wf_info_for %s, WF creation_date D, WF from_state FS, WF owned_by U?' % ueid,
                                       [{'WF': 'TrInfo', 'FS': 'State', 'U': 'CWUser', 'D': 'Datetime'}])],
                     None, None,
                     [self.system], {}, [])],
                   {'x': ueid})

    def test_nonregr5(self):
        # original jpl query:
        # DISTINCT Version V WHERE MB done_in MV, MV eid %(x)s,
        # MB depends_on B, B done_in V, V version_of P, NOT P eid %(p)s'
        cardeid = self.execute('INSERT Card X: X title "hop"')[0][0]
        noteeid = self.execute('INSERT Note X')[0][0]
        self._test('DISTINCT Card V WHERE MB documented_by MV, MV eid %(x)s, '
                   'MB depends_on B, B documented_by V, V multisource_rel P, NOT P eid %(p)s',
                   [('FetchStep', [('Any V WHERE V multisource_rel P, NOT P eid %s, P is Note, V is Card'%noteeid,
                                    [{'P': 'Note', 'V': 'Card'}])],
                     [self.cards, self.system], None, {'V': 'table0.C0'}, []),
                    ('OneFetchStep', [('DISTINCT Any V WHERE MB documented_by %s, MB depends_on B, B documented_by V, B is Affaire, MB is Affaire, V is Card'%cardeid,
                                       [{'B': 'Affaire', 'MB': 'Affaire', 'V': 'Card'}])],
                     None, None, [self.system], {'V': 'table0.C0'}, [])],
                   {'x': cardeid, 'p': noteeid})

    def test_nonregr6(self):
        self._test('Any X WHERE X concerne Y',
                   [('OneFetchStep', [('Any X WHERE X concerne Y',
                                       [{'Y': 'Division', 'X': 'Affaire'},
                                        {'Y': 'Note', 'X': 'Affaire'},
                                        {'Y': 'Societe', 'X': 'Affaire'},
                                        {'Y': 'SubDivision', 'X': 'Affaire'},
                                        {'Y': 'Affaire', 'X': 'Personne'}])],
                     None,  None, [self.system], {}, [])
                    ])
        self._test('Any X WHERE X concerne Y, Y is Note',
                   [('FetchStep', [('Any Y WHERE Y is Note', [{'Y': 'Note'}])],
                      [self.cards, self.system], None, {'Y': 'table0.C0'}, []),
                    ('OneFetchStep', [('Any X WHERE X concerne Y, X is Affaire, Y is Note',
                                       [{'X': 'Affaire', 'Y': 'Note'}])],
                     None, None, [self.system], {'Y': 'table0.C0'}, [])
                    ])

    def test_nonregr7(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any S,SUM(DUR),SUM(I),(SUM(I) - SUM(DUR)),MIN(DI),MAX(DI) GROUPBY S ORDERBY S WHERE A is Affaire, A duration DUR, A invoiced I, A modification_date DI, A in_state S, S name SN, (EXISTS(A concerne WP, W multisource_rel WP)) OR (EXISTS(A concerne W)), W eid %(n)s',
                   [('FetchStep', [('Any WP WHERE 999999 multisource_rel WP, WP is Note', [{'WP': 'Note'}])],
                     [self.cards], None, {'WP': u'table0.C0'}, []),
                    ('OneFetchStep', [('Any S,SUM(DUR),SUM(I),(SUM(I) - SUM(DUR)),MIN(DI),MAX(DI) GROUPBY S ORDERBY S WHERE A duration DUR, A invoiced I, A modification_date DI, A in_state S, S name SN, (EXISTS(A concerne WP, WP is Note)) OR (EXISTS(A concerne 999999)), A is Affaire, S is State',
                                       [{'A': 'Affaire', 'DI': 'Datetime', 'DUR': 'Int', 'I': 'Float', 'S': 'State', 'SN': 'String', 'WP': 'Note'}])],
                     None, None, [self.system], {'WP': u'table0.C0'}, [])],
                   {'n': 999999})

    def test_nonregr8(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any X,Z WHERE X eid %(x)s, X multisource_rel Y, Z concerne X',
                   [('FetchStep', [('Any 999999 WHERE 999999 multisource_rel Y, Y is Note',
                                    [{'Y': 'Note'}])],
                     [self.cards],
                     None, {u'%(x)s': 'table0.C0'},
                     []),
                    ('OneFetchStep', [('Any 999999,Z WHERE Z concerne 999999, Z is Affaire',
                                       [{'Z': 'Affaire'}])],
                     None, None, [self.system],
                     {u'%(x)s': 'table0.C0'}, []),
                    ],
                   {'x': 999999})

    def test_nonregr9(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        repo._type_source_cache[999998] = ('Note', 'cards', 999998, 'cards')
        self._test('SET X migrated_from Y WHERE X eid %(x)s, Y multisource_rel Z, Z eid %(z)s, Y migrated_from Z',
                   [('FetchStep', [('Any Y WHERE Y multisource_rel 999998, Y is Note', [{'Y': 'Note'}])],
                     [self.cards], None, {'Y': u'table0.C0'}, []),
                    ('UpdateStep',
                     [('OneFetchStep', [('DISTINCT Any Y WHERE Y migrated_from 999998, Y is Note',
                                         [{'Y': 'Note'}])],
                       None, None, [self.system],
                       {'Y': u'table0.C0'}, [])])],
                   {'x': 999999, 'z': 999998})

    def test_nonregr10(self):
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999999, 'ldap')
        self._test('Any X,AA,AB ORDERBY AA WHERE E eid %(x)s, E owned_by X, X login AA, X modification_date AB',
                   [('FetchStep',
                     [('Any X,AA,AB WHERE X login AA, X modification_date AB, X is CWUser',
                       [{'AA': 'String', 'AB': 'Datetime', 'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'AA': 'table0.C1', 'AB': 'table0.C2',
                                                      'X': 'table0.C0', 'X.login': 'table0.C1', 'X.modification_date': 'table0.C2'},
                     []),
                    ('OneFetchStep',
                     [('Any X,AA,AB ORDERBY AA WHERE 999999 owned_by X, X login AA, X modification_date AB, X is CWUser',
                       [{'AA': 'String', 'AB': 'Datetime', 'X': 'CWUser'}])],
                     None, None, [self.system], {'AA': 'table0.C1', 'AB': 'table0.C2',
                                                 'X': 'table0.C0', 'X.login': 'table0.C1', 'X.modification_date': 'table0.C2'},
                     [])
                    ],
                   {'x': 999999})

    def test_nonregr11(self):
        repo._type_source_cache[999999] = ('Bookmark', 'system', 999999, 'system')
        self._test('SET X bookmarked_by Y WHERE X eid %(x)s, Y login "hop"',
                   [('UpdateStep',
                     [('OneFetchStep', [('DISTINCT Any Y WHERE Y login "hop", Y is CWUser', [{'Y': 'CWUser'}])],
                       None, None, [self.ldap, self.system], {}, [])]
                     )],
                   {'x': 999999})

    def test_nonregr12(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any X ORDERBY Z DESC WHERE X modification_date Z, E eid %(x)s, E see_also X',
                   [('FetchStep', [('Any X,Z WHERE X modification_date Z, X is Note',
                                    [{'X': 'Note', 'Z': 'Datetime'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.modification_date': 'table0.C1', 'Z': 'table0.C1'},
                     []),
                    ('AggrStep', 'SELECT table1.C0 FROM table1\nORDER BY table1.C1 DESC', None,
                     [('FetchStep', [('Any X,Z WHERE X modification_date Z, 999999 see_also X, X is Bookmark',
                                      [{'X': 'Bookmark', 'Z': 'Datetime'}])],
                       [self.system], {},   {'X': 'table1.C0', 'X.modification_date': 'table1.C1',
                                             'Z': 'table1.C1'},
                       []),
                      ('FetchStep', [('Any X,Z WHERE X modification_date Z, 999999 see_also X, X is Note',
                                      [{'X': 'Note', 'Z': 'Datetime'}])],
                       [self.system], {'X': 'table0.C0', 'X.modification_date': 'table0.C1',
                                       'Z': 'table0.C1'},
                       {'X': 'table1.C0', 'X.modification_date': 'table1.C1',
                        'Z': 'table1.C1'},
                       [])]
                      )],
                   {'x': 999999})

    def test_nonregr13_1(self):
        ueid = self.session.user.eid
        # identity wrapped into exists:
        # should'nt propagate constraint that U is in the same source as ME
        self._test('Any B,U,UL GROUPBY B,U,UL WHERE B created_by U?, B is File '
                   'WITH U,UL BEING (Any U,UL WHERE ME eid %(x)s, (EXISTS(U identity ME) '
                   'OR (EXISTS(U in_group G, G name IN("managers", "staff")))) '
                   'OR (EXISTS(U in_group H, ME in_group H, NOT H name "users")), U login UL, U is CWUser)',
                   [('FetchStep', [('Any U,UL WHERE U login UL, U is CWUser',
                                    [{'U': 'CWUser', 'UL': 'String'}])],
                     [self.ldap, self.system], None,
                     {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                     []),
                    ('FetchStep', [('Any U,UL WHERE ((EXISTS(U identity %s)) OR (EXISTS(U in_group G, G name IN("managers", "staff"), G is CWGroup))) OR (EXISTS(U in_group H, %s in_group H, NOT H name "users", H is CWGroup)), U login UL, U is CWUser' % (ueid, ueid),
                                    [{'G': 'CWGroup', 'H': 'CWGroup', 'U': 'CWUser', 'UL': 'String'}])],
                     [self.system],
                     {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                     {'U': 'table1.C0', 'U.login': 'table1.C1', 'UL': 'table1.C1'},
                     []),
                    ('OneFetchStep', [('Any B,U,UL GROUPBY B,U,UL WHERE B created_by U?, B is File',
                                       [{'B': 'File', 'U': 'CWUser', 'UL': 'String'}])],
                     None, None, [self.system],
                     {'U': 'table1.C0', 'UL': 'table1.C1'},
                     [])],
                   {'x': ueid})

    def test_nonregr13_2(self):
        # identity *not* wrapped into exists.
        #
        # XXX this test fail since in this case, in "U identity 5" U and 5 are
        # from the same scope so constraints are applied (telling the U should
        # come from the same source as user with eid 5).
        #
        # IMO this is normal, unless we introduce a special case for the
        # identity relation. BUT I think it's better to leave it as is and to
        # explain constraint propagation rules, and so why this should be
        # wrapped in exists() if used in multi-source
        self.skipTest('take a look at me if you wish')
        ueid = self.session.user.eid
        self._test('Any B,U,UL GROUPBY B,U,UL WHERE B created_by U?, B is File '
                   'WITH U,UL BEING (Any U,UL WHERE ME eid %(x)s, (U identity ME '
                   'OR (EXISTS(U in_group G, G name IN("managers", "staff")))) '
                   'OR (EXISTS(U in_group H, ME in_group H, NOT H name "users")), U login UL, U is CWUser)',
                   [('FetchStep', [('Any U,UL WHERE U login UL, U is CWUser',
                                    [{'U': 'CWUser', 'UL': 'String'}])],
                     [self.ldap, self.system], None,
                     {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                     []),
                    ('FetchStep', [('Any U,UL WHERE ((U identity %s) OR (EXISTS(U in_group G, G name IN("managers", "staff"), G is CWGroup))) OR (EXISTS(U in_group H, %s in_group H, NOT H name "users", H is CWGroup)), U login UL, U is CWUser' % (ueid, ueid),
                                    [{'G': 'CWGroup', 'H': 'CWGroup', 'U': 'CWUser', 'UL': 'String'}])],
                     [self.system],
                     {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                     {'U': 'table1.C0', 'U.login': 'table1.C1', 'UL': 'table1.C1'},
                     []),
                    ('OneFetchStep', [('Any B,U,UL GROUPBY B,U,UL WHERE B created_by U?, B is File',
                                       [{'B': 'File', 'U': 'CWUser', 'UL': 'String'}])],
                     None, None, [self.system],
                     {'U': 'table1.C0', 'UL': 'table1.C1'},
                     [])],
                   {'x': self.session.user.eid})

    def test_nonregr14_1(self):
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999999, 'ldap')
        self._test('Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                   [('OneFetchStep', [('Any 999999 WHERE 999999 owned_by 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999, 'u': 999999})

    def test_nonregr14_2(self):
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999999, 'ldap')
        repo._type_source_cache[999998] = ('Note', 'system', 999998, 'system')
        self._test('Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                   [('OneFetchStep', [('Any 999998 WHERE 999998 owned_by 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999998, 'u': 999999})

    def test_nonregr14_3(self):
        repo._type_source_cache[999999] = ('CWUser', 'system', 999999, 'system')
        repo._type_source_cache[999998] = ('CWUser', 'ldap', 999998, 'ldap')
        self._test('Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                   [('OneFetchStep', [('Any 999998 WHERE 999998 owned_by 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999998, 'u': 999999})

    def test_nonregr_identity_no_source_access_1(self):
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999998, 'ldap')
        self._test('Any S WHERE S identity U, S eid %(s)s, U eid %(u)s',
                   [('OneFetchStep', [('Any 999999 WHERE 999999 identity 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'s': 999999, 'u': 999999})

    def test_nonregr_identity_no_source_access_2(self):
        repo._type_source_cache[999999] = ('EmailAddress', 'system', 999999, 'system')
        repo._type_source_cache[999998] = ('CWUser', 'ldap', 999998, 'ldap')
        self._test('Any X WHERE O use_email X, ((EXISTS(O identity U)) OR (EXISTS(O in_group G, G name IN("managers", "staff")))) OR (EXISTS(O in_group G2, U in_group G2, NOT G2 name "users")), X eid %(x)s, U eid %(u)s',
                   [('OneFetchStep', [('Any 999999 WHERE O use_email 999999, ((EXISTS(O identity 999998)) OR (EXISTS(O in_group G, G name IN("managers", "staff")))) OR (EXISTS(O in_group G2, 999998 in_group G2, NOT G2 name "users"))',
                                       [{'G': 'CWGroup', 'G2': 'CWGroup', 'O': 'CWUser'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999, 'u': 999998})

    def test_nonregr_similar_subquery(self):
        repo._type_source_cache[999999] = ('Personne', 'system', 999999, 'system')
        self._test('Any T,TD,U,T,UL WITH T,TD,U,UL BEING ('
                   '(Any T,TD,U,UL WHERE X eid %(x)s, T comments X, T content TD, T created_by U?, U login UL)'
                   ' UNION '
                   '(Any T,TD,U,UL WHERE X eid %(x)s, X connait P, T comments P, T content TD, T created_by U?, U login UL))',
                   # XXX optimization: use a OneFetchStep with a UNION of both queries
                   [('FetchStep', [('Any U,UL WHERE U login UL, U is CWUser',
                                    [{'U': 'CWUser', 'UL': 'String'}])],
                     [self.ldap, self.system], None,
                     {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                     []),
                    ('UnionFetchStep',
                     [('FetchStep',
                       [('Any T,TD,U,UL WHERE T comments 999999, T content TD, T created_by U?, U login UL, T is Comment, U is CWUser',
                         [{'T': 'Comment', 'TD': 'String', 'U': 'CWUser', 'UL': 'String'}])],
                       [self.system],
                       {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                       {'T': 'table1.C0',
                        'T.content': 'table1.C1',
                        'TD': 'table1.C1',
                        'U': 'table1.C2',
                        'U.login': 'table1.C3',
                        'UL': 'table1.C3'},
                       []),
                      ('FetchStep',
                       [('Any T,TD,U,UL WHERE 999999 connait P, T comments P, T content TD, T created_by U?, U login UL, P is Personne, T is Comment, U is CWUser',
                         [{'P': 'Personne',
                           'T': 'Comment',
                           'TD': 'String',
                           'U': 'CWUser',
                           'UL': 'String'}])],
                       [self.system],
                       {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                       {'T': 'table1.C0',
                        'T.content': 'table1.C1',
                        'TD': 'table1.C1',
                        'U': 'table1.C2',
                        'U.login': 'table1.C3',
                        'UL': 'table1.C3'},
                       [])]),
                    ('OneFetchStep',
                     [('Any T,TD,U,T,UL',
                       [{'T': 'Comment', 'TD': 'String', 'U': 'CWUser', 'UL': 'String'}])],
                     None, None,
                     [self.system],
                     {'T': 'table1.C0', 'TD': 'table1.C1', 'U': 'table1.C2', 'UL': 'table1.C3'},
                     [])],
                   {'x': 999999})

    def test_nonregr_dont_readd_already_processed_relation(self):
        self._test('Any WO,D,SO WHERE WO is Note, D tags WO, WO in_state SO',
                   [('FetchStep',
                     [('Any WO,SO WHERE WO in_state SO, SO is State, WO is Note',
                       [{'SO': 'State', 'WO': 'Note'}])],
                     [self.cards, self.system], None,
                     {'SO': 'table0.C1', 'WO': 'table0.C0'},
                     []),
                    ('OneFetchStep',
                     [('Any WO,D,SO WHERE D tags WO, D is Tag, SO is State, WO is Note',
                       [{'D': 'Tag', 'SO': 'State', 'WO': 'Note'}])],
                     None, None, [self.system],
                     {'SO': 'table0.C1', 'WO': 'table0.C0'},
                     [])
                    ])

class MSPlannerTwoSameExternalSourcesTC(BasePlannerTC):
    """test planner related feature on a 3-sources repository:

    * 2 rql sources supporting Card
    """

    def setUp(self):
        self.__class__.repo = repo
        self.setup()
        self.add_source(FakeCardSource, 'cards')
        self.add_source(FakeCardSource, 'cards2')
        self.planner = MSPlanner(self.o.schema, self.repo.vreg.rqlhelper)
        assert repo.sources_by_uri['cards2'].support_relation('multisource_crossed_rel')
        assert 'multisource_crossed_rel' in repo.sources_by_uri['cards2'].cross_relations
        assert repo.sources_by_uri['cards'].support_relation('multisource_crossed_rel')
        assert 'multisource_crossed_rel' in repo.sources_by_uri['cards'].cross_relations
    _test = test_plan


    def test_linked_external_entities(self):
        repo._type_source_cache[999999] = ('Tag', 'system', 999999, 'system')
        self._test('Any X,XT WHERE X is Card, X title XT, T tags X, T eid %(t)s',
                   [('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.cards2, self.system],
                     None, {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'},
                     []),
                    ('OneFetchStep',
                     [('Any X,XT WHERE X title XT, 999999 tags X, X is Card',
                       [{'X': 'Card', 'XT': 'String'}])],
                     None, None, [self.system],
                     {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'},
                     [])],
                   {'t': 999999})

    def test_version_depends_on(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any X,AD,AE WHERE E eid %(x)s, E migrated_from X, X in_state AD, AD name AE',
                   [('FetchStep', [('Any X,AD,AE WHERE X in_state AD, AD name AE, AD is State, X is Note',
                                    [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                     [self.cards, self.cards2, self.system],
                     None, {'AD': 'table0.C1', 'AD.name': 'table0.C2',
                            'AE': 'table0.C2', 'X': 'table0.C0'},
                     []),
                    ('OneFetchStep', [('Any X,AD,AE WHERE 999999 migrated_from X, AD name AE, AD is State, X is Note',
                                       [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                     None, None, [self.system],
                     {'AD': 'table0.C1', 'AD.name': 'table0.C2', 'AE': 'table0.C2', 'X': 'table0.C0'},
                     [])],
                   {'x': 999999})

    def test_version_crossed_depends_on_1(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any X,AD,AE WHERE E eid %(x)s, E multisource_crossed_rel X, X in_state AD, AD name AE',
                   [('FetchStep', [('Any X,AD,AE WHERE X in_state AD, AD name AE, AD is State, X is Note',
                                    [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                     [self.cards, self.cards2, self.system],
                     None, {'AD': 'table0.C1', 'AD.name': 'table0.C2',
                            'AE': 'table0.C2', 'X': 'table0.C0'},
                     []),
                    ('UnionStep', None, None,
                     [('OneFetchStep', [('Any X,AD,AE WHERE 999999 multisource_crossed_rel X, AD name AE, AD is State, X is Note',
                                         [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                       None, None, [self.cards], None,
                       []),
                      ('OneFetchStep', [('Any X,AD,AE WHERE 999999 multisource_crossed_rel X, AD name AE, AD is State, X is Note',
                                         [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                       None, None, [self.system],
                       {'AD': 'table0.C1', 'AD.name': 'table0.C2',
                        'AE': 'table0.C2', 'X': 'table0.C0'},
                       [])]
                     )],
                   {'x': 999999})

    def test_version_crossed_depends_on_2(self):
        self.repo._type_source_cache[999999] = ('Note', 'system', 999999, 'system')
        self._test('Any X,AD,AE WHERE E eid %(x)s, E multisource_crossed_rel X, X in_state AD, AD name AE',
                   [('FetchStep', [('Any X,AD,AE WHERE X in_state AD, AD name AE, AD is State, X is Note',
                                    [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                     [self.cards, self.cards2, self.system],
                     None, {'AD': 'table0.C1', 'AD.name': 'table0.C2',
                            'AE': 'table0.C2', 'X': 'table0.C0'},
                     []),
                    ('OneFetchStep', [('Any X,AD,AE WHERE 999999 multisource_crossed_rel X, AD name AE, AD is State, X is Note',
                                       [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                     None, None, [self.system],
                     {'AD': 'table0.C1', 'AD.name': 'table0.C2', 'AE': 'table0.C2', 'X': 'table0.C0'},
                     [])],
                   {'x': 999999})

    def test_version_crossed_depends_on_3(self):
        self._test('Any X,AD,AE WHERE E multisource_crossed_rel X, X in_state AD, AD name AE, E is Note',
                   [('FetchStep', [('Any X,AD,AE WHERE X in_state AD, AD name AE, AD is State, X is Note',
                                    [{'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                     [self.cards, self.cards2, self.system],
                     None, {'AD': 'table0.C1', 'AD.name': 'table0.C2',
                            'AE': 'table0.C2', 'X': 'table0.C0'},
                     []),
                    ('FetchStep', [('Any E WHERE E is Note', [{'E': 'Note'}])],
                     [self.cards, self.cards2, self.system],
                     None, {'E': 'table1.C0'},
                     []),
                    ('UnionStep', None, None,
                     [('OneFetchStep', [('Any X,AD,AE WHERE E multisource_crossed_rel X, AD name AE, AD is State, E is Note, X is Note',
                                         [{'AD': 'State', 'AE': 'String', 'E': 'Note', 'X': 'Note'}])],
                       None, None, [self.cards, self.cards2], None,
                       []),
                      ('OneFetchStep', [('Any X,AD,AE WHERE E multisource_crossed_rel X, AD name AE, AD is State, E is Note, X is Note',
                                         [{'AD': 'State', 'AE': 'String', 'E': 'Note', 'X': 'Note'}])],
                       None, None, [self.system],
                       {'AD': 'table0.C1',
                        'AD.name': 'table0.C2',
                        'AE': 'table0.C2',
                        'E': 'table1.C0',
                        'X': 'table0.C0'},
                       [])]
                     )]
                   )

    def test_version_crossed_depends_on_4(self):
        self._test('Any X,AD,AE WHERE EXISTS(E multisource_crossed_rel X), X in_state AD, AD name AE, E is Note',
                   [('FetchStep',
                     [('Any X,AD,AE WHERE X in_state AD, AD name AE, AD is State, X is Note',
                       [{'X': 'Note', 'AD': 'State', 'AE': 'String'}])],
                     [self.cards, self.cards2, self.system], None,
                     {'X': 'table0.C0',
                      'AD': 'table0.C1',
                      'AD.name': 'table0.C2',
                      'AE': 'table0.C2'},
                     []),
                    ('FetchStep',
                     [('Any A WHERE E multisource_crossed_rel A, A is Note, E is Note',
                       [{'A': 'Note', 'E': 'Note'}])],
                     [self.cards, self.cards2, self.system], None,
                     {'A': 'table1.C0'},
                     []),
                    ('OneFetchStep',
                     [('Any X,AD,AE WHERE EXISTS(X identity A), AD name AE, A is Note, AD is State, X is Note',
                       [{'A': 'Note', 'AD': 'State', 'AE': 'String', 'X': 'Note'}])],
                     None, None,
                     [self.system],
                     {'A': 'table1.C0',
                      'AD': 'table0.C1',
                      'AD.name': 'table0.C2',
                      'AE': 'table0.C2',
                      'X': 'table0.C0'},
                     []
                     )]
                       )

    def test_nonregr_dont_cross_rel_source_filtering_1(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any S WHERE E eid %(x)s, E in_state S, NOT S name "moved"',
                   [('OneFetchStep', [('Any S WHERE 999999 in_state S, NOT S name "moved", S is State',
                                       [{'S': 'State'}])],
                     None, None, [self.cards], {}, []
                     )],
                   {'x': 999999})

    def test_nonregr_dont_cross_rel_source_filtering_2(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any X,AA,AB WHERE E eid %(x)s, E in_state X, X name AA, X modification_date AB',
                   [('OneFetchStep', [('Any X,AA,AB WHERE 999999 in_state X, X name AA, X modification_date AB, X is State',
                                       [{'AA': 'String', 'AB': 'Datetime', 'X': 'State'}])],
                     None, None, [self.cards], {}, []
                     )],
                   {'x': 999999})

    def test_nonregr_eid_query(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Any X WHERE X eid 999999',
                   [('OneFetchStep', [('Any 999999', [{}])],
                     None, None, [self.system], {}, []
                     )],
                   {'x': 999999})


    def test_nonregr_not_is(self):
        self._test("Any X WHERE X owned_by U, U login 'anon', NOT X is Comment",
                   [('FetchStep', [('Any X WHERE X is IN(Card, Note, State)',
                                    [{'X': 'Note'}, {'X': 'State'}, {'X': 'Card'}])],
                     [self.cards, self.cards2, self.system],
                     None, {'X': 'table0.C0'}, []),
                    ('UnionStep', None, None,
                     [('OneFetchStep',
                       [(u'Any X WHERE X owned_by U, U login "anon", U is CWUser, X is IN(Affaire, BaseTransition, Basket, Bookmark, CWAttribute, CWCache, CWConstraint, CWConstraintType, CWDataImport, CWEType, CWGroup, CWPermission, CWProperty, CWRType, CWRelation, CWSource, CWSourceHostConfig, CWSourceSchemaConfig, CWUniqueTogetherConstraint, CWUser, Division, Email, EmailAddress, EmailPart, EmailThread, ExternalUri, File, Folder, Old, Personne, RQLExpression, Societe, SubDivision, SubWorkflowExitPoint, Tag, TrInfo, Transition, Workflow, WorkflowTransition)',
                         [{'U': 'CWUser', 'X': 'Affaire'},
                          {'U': 'CWUser', 'X': 'BaseTransition'},
                          {'U': 'CWUser', 'X': 'Basket'},
                          {'U': 'CWUser', 'X': 'Bookmark'},
                          {'U': 'CWUser', 'X': 'CWAttribute'},
                          {'U': 'CWUser', 'X': 'CWCache'},
                          {'U': 'CWUser', 'X': 'CWConstraint'},
                          {'U': 'CWUser', 'X': 'CWConstraintType'},
                          {'U': 'CWUser', 'X': 'CWDataImport'},
                          {'U': 'CWUser', 'X': 'CWEType'},
                          {'U': 'CWUser', 'X': 'CWGroup'},
                          {'U': 'CWUser', 'X': 'CWPermission'},
                          {'U': 'CWUser', 'X': 'CWProperty'},
                          {'U': 'CWUser', 'X': 'CWRType'},
                          {'U': 'CWUser', 'X': 'CWRelation'},
                          {'U': 'CWUser', 'X': 'CWSource'},
                          {'U': 'CWUser', 'X': 'CWSourceHostConfig'},
                          {'U': 'CWUser', 'X': 'CWSourceSchemaConfig'},
                          {'U': 'CWUser', 'X': 'CWUniqueTogetherConstraint'},
                          {'U': 'CWUser', 'X': 'CWUser'},
                          {'U': 'CWUser', 'X': 'Division'},
                          {'U': 'CWUser', 'X': 'Email'},
                          {'U': 'CWUser', 'X': 'EmailAddress'},
                          {'U': 'CWUser', 'X': 'EmailPart'},
                          {'U': 'CWUser', 'X': 'EmailThread'},
                          {'U': 'CWUser', 'X': 'ExternalUri'},
                          {'U': 'CWUser', 'X': 'File'},
                          {'U': 'CWUser', 'X': 'Folder'},
                          {'U': 'CWUser', 'X': 'Old'},
                          {'U': 'CWUser', 'X': 'Personne'},
                          {'U': 'CWUser', 'X': 'RQLExpression'},
                          {'U': 'CWUser', 'X': 'Societe'},
                          {'U': 'CWUser', 'X': 'SubDivision'},
                          {'U': 'CWUser', 'X': 'SubWorkflowExitPoint'},
                          {'U': 'CWUser', 'X': 'Tag'},
                          {'U': 'CWUser', 'X': 'TrInfo'},
                          {'U': 'CWUser', 'X': 'Transition'},
                          {'U': 'CWUser', 'X': 'Workflow'},
                          {'U': 'CWUser', 'X': 'WorkflowTransition'}])],
                       None, None,
                       [self.system], {}, []),
                      ('OneFetchStep',
                       [(u'Any X WHERE X owned_by U, U login "anon", U is CWUser, X is IN(Card, Note, State)',
                         [{'U': 'CWUser', 'X': 'Note'},
                          {'U': 'CWUser', 'X': 'State'},
                          {'U': 'CWUser', 'X': 'Card'}])],
                       None, None,
                       [self.system], {'X': 'table0.C0'}, [])
                      ])
                    ])

    def test_remove_from_deleted_source_1(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self._test('Note X WHERE X eid 999999, NOT X cw_source Y',
                   [('OneFetchStep',
                     [('Any 999999 WHERE NOT EXISTS(999999 cw_source Y)',
                       [{'Y': 'CWSource'}])],
                     None, None, [self.system], {}, [])
                    ])

    def test_remove_from_deleted_source_2(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999, 'cards')
        self.repo._type_source_cache[999998] = ('Note', 'cards', 999998, 'cards')
        self._test('Note X WHERE X eid IN (999998, 999999), NOT X cw_source Y',
                   [('FetchStep',
                     [('Any X WHERE X eid IN(999998, 999999), X is Note',
                       [{'X': 'Note'}])],
                     [self.cards], None, {'X': 'table0.C0'}, []),
                    ('OneFetchStep',
                     [('Any X WHERE NOT EXISTS(X cw_source Y, Y is CWSource), X is Note',
                       [{'X': 'Note', 'Y': 'CWSource'}])],
                         None, None, [self.system],{'X': 'table0.C0'}, [])
                        ])


class FakeVCSSource(AbstractSource):
    uri = 'ccc'
    support_entities = {'Card': True, 'Note': True}
    support_relations = {'multisource_inlined_rel': True,
                         'multisource_rel': True}

    def syntax_tree_search(self, *args, **kwargs):
        return []

class MSPlannerVCSSource(BasePlannerTC):

    def setUp(self):
        self.__class__.repo = repo
        self.setup()
        self.add_source(FakeVCSSource, 'vcs')
        self.planner = MSPlanner(self.o.schema, self.repo.vreg.rqlhelper)
    _test = test_plan

    def test_multisource_inlined_rel_skipped(self):
        self._test('Any MAX(VC) '
                   'WHERE VC multisource_inlined_rel R2, R para %(branch)s, VC in_state S, S name "published", '
                   '(EXISTS(R identity R2)) OR (EXISTS(R multisource_rel R2))',
                   [('FetchStep', [('Any VC WHERE VC multisource_inlined_rel R2, R para "???", (EXISTS(R identity R2)) OR (EXISTS(R multisource_rel R2)), R is Note, R2 is Note, VC is Note',
                                    [{'R': 'Note', 'R2': 'Note', 'VC': 'Note'}])],
                     [self.vcs, self.system], None,
                     {'VC': 'table0.C0'},
                     []),
                    ('OneFetchStep', [(u'Any MAX(VC) WHERE VC in_state S, S name "published", S is State, VC is Note',
                                       [{'S': 'State', 'VC': 'Note'}])],
                     None, None, [self.system],
                     {'VC': 'table0.C0'},
                     [])
                    ])

    def test_fully_simplified_extsource(self):
        self.repo._type_source_cache[999998] = ('Note', 'vcs', 999998, 'vcs')
        self.repo._type_source_cache[999999] = ('Note', 'vcs', 999999, 'vcs')
        self._test('Any X, Y WHERE NOT X multisource_rel Y, X eid 999998, Y eid 999999',
                   [('OneFetchStep', [('Any 999998,999999 WHERE NOT EXISTS(999998 multisource_rel 999999)', [{}])],
                     None, None, [self.vcs], {}, [])
                    ])

    def test_nonregr_fully_simplified_extsource(self):
        self.repo._type_source_cache[999998] = ('Note', 'vcs', 999998, 'vcs')
        self.repo._type_source_cache[999999] = ('Note', 'vcs', 999999, 'vcs')
        self.repo._type_source_cache[1000000] = ('Note', 'system', 1000000, 'system')
        self._test('DISTINCT Any T,FALSE,L,M WHERE L eid 1000000, M eid 999999, T eid 999998',
                   [('OneFetchStep', [('DISTINCT Any 999998,FALSE,1000000,999999', [{}])],
                     None, None, [self.system], {}, [])
                    ])


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
