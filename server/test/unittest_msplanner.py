"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.decorators import clear_cache
from cubicweb.devtools import init_test_database
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
    uri = 'zzz'
    support_entities = {'CWUser': False}
    support_relations = {}
    def syntax_tree_search(self, *args, **kwargs):
        return []


class FakeCardSource(AbstractSource):
    uri = 'ccc'
    support_entities = {'Card': True, 'Note': True, 'State': True}
    support_relations = {'in_state': True, 'multisource_rel': True, 'multisource_inlined_rel': True,
                         'multisource_crossed_rel': True}
    dont_cross_relations = set(('fiche', 'state_of'))
    cross_relations = set(('multisource_crossed_rel',))

    def syntax_tree_search(self, *args, **kwargs):
        return []

X_ALL_SOLS = sorted([{'X': 'Affaire'}, {'X': 'BaseTransition'}, {'X': 'Basket'},
                     {'X': 'Bookmark'}, {'X': 'CWAttribute'}, {'X': 'CWCache'},
                     {'X': 'CWConstraint'}, {'X': 'CWConstraintType'}, {'X': 'CWEType'},
                     {'X': 'CWGroup'}, {'X': 'CWPermission'}, {'X': 'CWProperty'},
                     {'X': 'CWRType'}, {'X': 'CWRelation'}, {'X': 'CWUser'},
                     {'X': 'Card'}, {'X': 'Comment'}, {'X': 'Division'},
                     {'X': 'Email'}, {'X': 'EmailAddress'}, {'X': 'EmailPart'},
                     {'X': 'EmailThread'}, {'X': 'ExternalUri'}, {'X': 'File'},
                     {'X': 'Folder'}, {'X': 'Image'}, {'X': 'Note'},
                     {'X': 'Personne'}, {'X': 'RQLExpression'}, {'X': 'Societe'},
                     {'X': 'State'}, {'X': 'SubDivision'}, {'X': 'SubWorkflowExitPoint'},
                     {'X': 'Tag'}, {'X': 'TrInfo'}, {'X': 'Transition'},
                     {'X': 'Workflow'}, {'X': 'WorkflowTransition'}])


# keep cnx so it's not garbage collected and the associated session is closed
repo, cnx = init_test_database('sqlite')

class BaseMSPlannerTC(BasePlannerTC):
    """test planner related feature on a 3-sources repository:

    * system source supporting everything
    * ldap source supporting CWUser
    * rql source supporting Card
    """
    repo = repo

    def setUp(self):
        #_QuerierTC.setUp(self)
        self.setup()
        # hijack Affaire security
        affreadperms = list(self.schema['Affaire']._groups['read'])
        self.prevrqlexpr_affaire = affreadperms[-1]
        # add access to type attribute so S can't be invariant
        affreadperms[-1] = ERQLExpression('X concerne S?, S owned_by U, S type "X"')
        self.schema['Affaire']._groups['read'] = tuple(affreadperms)
        # hijack CWUser security
        userreadperms = list(self.schema['CWUser']._groups['read'])
        self.prevrqlexpr_user = userreadperms[-1]
        userreadperms[-1] = ERQLExpression('X owned_by U')
        self.schema['CWUser']._groups['read'] = tuple(userreadperms)
        self.add_source(FakeUserROSource, 'ldap')
        self.add_source(FakeCardSource, 'cards')

    def tearDown(self):
        super(BaseMSPlannerTC, self).tearDown()
        # restore hijacked security
        self.restore_orig_affaire_security()
        self.restore_orig_euser_security()

    def restore_orig_affaire_security(self):
        affreadperms = list(self.schema['Affaire']._groups['read'])
        affreadperms[-1] = self.prevrqlexpr_affaire
        self.schema['Affaire']._groups['read'] = tuple(affreadperms)
        clear_cache(self.schema['Affaire'], 'ERSchema_get_rqlexprs')

    def restore_orig_euser_security(self):
        userreadperms = list(self.schema['CWUser']._groups['read'])
        userreadperms[-1] = self.prevrqlexpr_user
        self.schema['CWUser']._groups['read'] = tuple(userreadperms)
        clear_cache(self.schema['CWUser'], 'ERSchema_get_rqlexprs')


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
            for var in sourcevars.keys():
                solindices = sourcevars.pop(var)
                sourcevars[var._ms_table_key()] = solindices
        self.assertEquals(ppi._sourcesterms, sourcesterms)
        self.assertEquals(ppi.needsplit, needsplit)


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
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
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
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any U WHERE U in_group G, (G name IN ("managers", "logilab") OR (X require_permission P?, P name "bla", P require_group G)), X eid %(x)s, U eid %(u)s',
                   {'x': 999999, 'u': self.session.user.eid},
                   {self.system: {'P': s[0], 'G': s[0], 'X': s[0],
                                  'require_permission': s[0], 'in_group': s[0], 'P': s[0], 'require_group': s[0],
                                  'u': s[0]}},
                   False)

    def test_delete_relation1(self):
        ueid = self.session.user.eid
        self._test('Any X, Y WHERE X created_by Y, X eid %(x)s, NOT Y eid %(y)s',
                   {'x': ueid, 'y': ueid},
                   {self.system: {'Y': s[0], 'created_by': s[0], 'x': s[0]}},
                   False)

    def test_crossed_relation_eid_1_needattr(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
        ueid = self.session.user.eid
        self._test('Any Y,T WHERE X eid %(x)s, X multisource_crossed_rel Y, Y type T',
                   {'x': 999999,},
                   {self.cards: {'Y': s[0]}, self.system: {'Y': s[0], 'x': s[0]}},
                   True)

    def test_crossed_relation_eid_1_invariant(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   {'x': 999999},
                   {self.system: {'Y': s[0], 'x': s[0]}},
                   False)

    def test_crossed_relation_eid_2_invariant(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   {'x': 999999,},
                   {self.cards: {'Y': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]},
                    self.system: {'Y': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]}},
                   False)

    def test_version_crossed_depends_on_1(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any X,AD,AE WHERE E eid %(x)s, E multisource_crossed_rel X, X in_state AD, AD name AE',
                   {'x': 999999},
                   {self.cards: {'X': s[0], 'AD': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]},
                    self.system: {'X': s[0], 'AD': s[0], 'multisource_crossed_rel': s[0], 'x': s[0]}},
                   True)

    def test_version_crossed_depends_on_2(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
        self._test('Any X,AD,AE WHERE E eid %(x)s, E multisource_crossed_rel X, X in_state AD, AD name AE',
                   {'x': 999999},
                   {self.cards: {'X': s[0], 'AD': s[0]},
                    self.system: {'X': s[0], 'AD': s[0], 'x': s[0]}},
                    True)

    def test_simplified_var_3(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        repo._type_source_cache[999998] = ('State', 'cards', 999998)
        self._test('Any S,T WHERE S eid %(s)s, N eid %(n)s, N type T, N is Note, S is State',
                   {'n': 999999, 's': 999998},
                   {self.cards: {'s': s[0], 'N': s[0]}}, False)



class MSPlannerTC(BaseMSPlannerTC):

    def setUp(self):
        BaseMSPlannerTC.setUp(self)
        self.planner = MSPlanner(self.o.schema, self.repo.vreg.rqlhelper)

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
                   [('AggrStep', 'Any X ORDERBY X', 10, 10, 'table0', None, [
                       ('FetchStep', [('Any X WHERE X is CWUser', [{'X': 'CWUser'}])],
                        [self.ldap, self.system], {}, {'X': 'table0.C0'}, []),
                       ]),
                   ])
    def test_simple_system_ldap_aggregat(self):
        """retrieve CWUser X from both sources and return concatenation of results
        """
        # COUNT(X) is kept in sub-step and transformed into SUM(X) in the AggrStep
        self._test('Any COUNT(X) WHERE X is CWUser',
                   [('AggrStep', 'Any COUNT(X)', None, None, 'table0', None, [
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
                   [('AggrStep', 'Any L ORDERBY L', None, None, 'table0', None,
                     [('FetchStep', [('Any L WHERE X login L, X is CWUser',
                                      [{'X': 'CWUser', 'L': 'String'}])],
                       [self.ldap, self.system], {}, {'X.login': 'table0.C0', 'L': 'table0.C0'}, []),
                      ])
                    ])

    def test_complex_ordered_limit_offset(self):
        self._test('Any L ORDERBY L LIMIT 10 OFFSET 10 WHERE X login L',
                   [('AggrStep', 'Any L ORDERBY L', 10, 10, 'table0', None,
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
                     [('Any X,AA ORDERBY AA WHERE 5 owned_by X, X modification_date AA, X is CWUser',
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
                   [('AggrStep', 'Any X,F ORDERBY F', None, None, 'table0', None,
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
        ueid = self.session.user.eid
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
                    ], {'x': ueid})

    def test_complex_aggregat(self):
        self._test('Any MAX(X)',
                   [('OneFetchStep',
                     [('Any MAX(X)', X_ALL_SOLS)],
                     None, None, [self.system], {}, [])
                    ])

    def test_complex_typed_aggregat(self):
        self._test('Any MAX(X) WHERE X is Card',
                   [('AggrStep', 'Any MAX(X)', None, None, 'table0',  None,
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
                   [('OneFetchStep', [('Any U WHERE WF wf_info_for 5, WF owned_by U?, WF from_state FS',
                                       [{'WF': 'TrInfo', 'FS': 'State', 'U': 'CWUser'}])],
                     None, None, [self.system], {}, [])],
                   {'x': ueid})

    def test_complex_optional(self):
        ueid = self.session.user.eid
        self._test('Any U WHERE WF wf_info_for X, X eid %(x)s, WF owned_by U?, WF from_state FS',
                   [('OneFetchStep', [('Any U WHERE WF wf_info_for 5, WF owned_by U?, WF from_state FS',
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
        # both system and rql support all variables, can be
        self._test('Any X WHERE NOT X identity U, U eid %s' % self.session.user.eid,
                   [('OneFetchStep',
                     [('Any X WHERE NOT X identity 5, X is CWUser', [{'X': 'CWUser'}])],
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
        self.session = self._user_session()[1]
        self._test('Any X WHERE X has_text "bla"',
                   [('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                     [self.cards, self.system], None, {'E': 'table0.C0'}, []),
                    ('UnionStep', None, None,
                     [('OneFetchStep',
                       [(u'Any X WHERE X has_text "bla", (EXISTS(X owned_by 5)) OR ((((EXISTS(D concerne C?, C owned_by 5, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by 5, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by 5, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by 5, X identity J, E is Note, J is Affaire))), X is Affaire',
                         [{'C': 'Division', 'E': 'Note', 'D': 'Affaire', 'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire', 'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire'}])],
                       None, None, [self.system], {'E': 'table0.C0'}, []),
                      ('OneFetchStep',
                       [('Any X WHERE X has_text "bla", EXISTS(X owned_by 5), X is Basket',
                         [{'X': 'Basket'}]),
                        ('Any X WHERE X has_text "bla", EXISTS(X owned_by 5), X is CWUser',
                         [{'X': 'CWUser'}]),
                        ('Any X WHERE X has_text "bla", X is IN(BaseTransition, Card, Comment, Division, Email, EmailThread, File, Folder, Image, Note, Personne, Societe, State, SubDivision, Tag, Transition, Workflow, WorkflowTransition)',
                         [{'X': 'BaseTransition'}, {'X': 'Card'}, {'X': 'Comment'},
                          {'X': 'Division'}, {'X': 'Email'}, {'X': 'EmailThread'},
                          {'X': 'File'}, {'X': 'Folder'}, {'X': 'Image'},
                          {'X': 'Note'}, {'X': 'Personne'}, {'X': 'Societe'},
                          {'X': 'State'}, {'X': 'SubDivision'}, {'X': 'Tag'},
                          {'X': 'Transition'}, {'X': 'Workflow'}, {'X': 'WorkflowTransition'}]),],
                       None, None, [self.system], {}, []),
                      ])
                     ])

    def test_security_has_text_limit_offset(self):
        # use a guest user
        self.session = self._user_session()[1]
        # note: same as the above query but because of the subquery usage, the display differs (not printing solutions for each union)
        self._test('Any X LIMIT 10 OFFSET 10 WHERE X has_text "bla"',
                   [('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                      [self.cards, self.system], None, {'E': 'table1.C0'}, []),
                     ('UnionFetchStep', [
                         ('FetchStep', [('Any X WHERE X has_text "bla", (EXISTS(X owned_by 5)) OR ((((EXISTS(D concerne C?, C owned_by 5, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by 5, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by 5, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by 5, X identity J, E is Note, J is Affaire))), X is Affaire',
                                            [{'C': 'Division', 'E': 'Note', 'D': 'Affaire', 'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire', 'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire'}])],
                          [self.system], {'E': 'table1.C0'}, {'X': 'table0.C0'}, []),
                         ('FetchStep',
                          [('Any X WHERE X has_text "bla", EXISTS(X owned_by 5), X is Basket',
                            [{'X': 'Basket'}]),
                           ('Any X WHERE X has_text "bla", EXISTS(X owned_by 5), X is CWUser',
                            [{'X': 'CWUser'}]),
                           ('Any X WHERE X has_text "bla", X is IN(BaseTransition, Card, Comment, Division, Email, EmailThread, File, Folder, Image, Note, Personne, Societe, State, SubDivision, Tag, Transition, Workflow, WorkflowTransition)',
                            [{'X': 'BaseTransition'}, {'X': 'Card'}, {'X': 'Comment'},
                             {'X': 'Division'}, {'X': 'Email'}, {'X': 'EmailThread'},
                             {'X': 'File'}, {'X': 'Folder'}, {'X': 'Image'},
                             {'X': 'Note'}, {'X': 'Personne'}, {'X': 'Societe'},
                             {'X': 'State'}, {'X': 'SubDivision'}, {'X': 'Tag'},
                             {'X': 'Transition'}, {'X': 'Workflow'}, {'X': 'WorkflowTransition'}])],
                          [self.system], {}, {'X': 'table0.C0'}, []),
                         ]),
                    ('OneFetchStep',
                     [('Any X LIMIT 10 OFFSET 10',
                       [{'X': 'Affaire'}, {'X': 'BaseTransition'}, {'X': 'Basket'},
                        {'X': 'CWUser'}, {'X': 'Card'}, {'X': 'Comment'},
                        {'X': 'Division'}, {'X': 'Email'}, {'X': 'EmailThread'},
                        {'X': 'File'}, {'X': 'Folder'}, {'X': 'Image'},
                        {'X': 'Note'}, {'X': 'Personne'}, {'X': 'Societe'},
                        {'X': 'State'}, {'X': 'SubDivision'}, {'X': 'Tag'},
                        {'X': 'Transition'}, {'X': 'Workflow'}, {'X': 'WorkflowTransition'}])],
                     10, 10, [self.system], {'X': 'table0.C0'}, [])
                     ])

    def test_security_user(self):
        """a guest user trying to see another user: EXISTS(X owned_by U) is automatically inserted"""
        # use a guest user
        self.session = self._user_session()[1]
        self._test('Any X WHERE X login "bla"',
                   [('FetchStep',
                     [('Any X WHERE X login "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('OneFetchStep',
                     [('Any X WHERE EXISTS(X owned_by 5), X is CWUser', [{'X': 'CWUser'}])],
                     None, None, [self.system], {'X': 'table0.C0'}, [])])

    def test_security_complex_has_text(self):
        # use a guest user
        self.session = self._user_session()[1]
        self._test('Any X WHERE X has_text "bla", X firstname "bla"',
                   [('FetchStep', [('Any X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table0.C0'}, []),
                    ('UnionStep', None, None, [
                        ('OneFetchStep', [('Any X WHERE X has_text "bla", EXISTS(X owned_by 5), X is CWUser', [{'X': 'CWUser'}])],
                         None, None, [self.system], {'X': 'table0.C0'}, []),
                        ('OneFetchStep', [('Any X WHERE X has_text "bla", X firstname "bla", X is Personne', [{'X': 'Personne'}])],
                         None, None, [self.system], {}, []),
                        ]),
                    ])

    def test_security_complex_has_text_limit_offset(self):
        # use a guest user
        self.session = self._user_session()[1]
        self._test('Any X LIMIT 10 OFFSET 10 WHERE X has_text "bla", X firstname "bla"',
                   [('FetchStep', [('Any X WHERE X firstname "bla", X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table1.C0'}, []),
                    ('UnionFetchStep', [
                        ('FetchStep', [('Any X WHERE X has_text "bla", EXISTS(X owned_by 5), X is CWUser', [{'X': 'CWUser'}])],
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
        self.session = self._user_session()[1]
        self._test('Any MAX(X)',
                   [('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                     [self.cards, self.system],  None, {'E': 'table1.C0'}, []),
                    ('FetchStep', [('Any X WHERE X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table2.C0'}, []),
                    ('UnionFetchStep', [
                        ('FetchStep', [('Any X WHERE EXISTS(X owned_by 5), X is Basket', [{'X': 'Basket'}])],
                          [self.system], {}, {'X': 'table0.C0'}, []),
                        ('UnionFetchStep',
                         [('FetchStep', [('Any X WHERE X is IN(Card, Note, State)',
                                          [{'X': 'Card'}, {'X': 'Note'}, {'X': 'State'}])],
                           [self.cards, self.system], {}, {'X': 'table0.C0'}, []),
                          ('FetchStep',
                           [('Any X WHERE X is IN(BaseTransition, Bookmark, CWAttribute, CWCache, CWConstraint, CWConstraintType, CWEType, CWGroup, CWPermission, CWProperty, CWRType, CWRelation, Comment, Division, Email, EmailAddress, EmailPart, EmailThread, ExternalUri, File, Folder, Image, Personne, RQLExpression, Societe, SubDivision, SubWorkflowExitPoint, Tag, TrInfo, Transition, Workflow, WorkflowTransition)',
                             [{'X': 'BaseTransition'}, {'X': 'Bookmark'},
                              {'X': 'CWAttribute'}, {'X': 'CWCache'},
                              {'X': 'CWConstraint'}, {'X': 'CWConstraintType'},
                              {'X': 'CWEType'}, {'X': 'CWGroup'},
                              {'X': 'CWPermission'}, {'X': 'CWProperty'},
                              {'X': 'CWRType'}, {'X': 'CWRelation'},
                              {'X': 'Comment'}, {'X': 'Division'},
                              {'X': 'Email'}, {'X': 'EmailAddress'},
                              {'X': 'EmailPart'}, {'X': 'EmailThread'},
                              {'X': 'ExternalUri'}, {'X': 'File'},
                              {'X': 'Folder'}, {'X': 'Image'},
                              {'X': 'Personne'}, {'X': 'RQLExpression'},
                              {'X': 'Societe'}, {'X': 'SubDivision'},
                              {'X': 'SubWorkflowExitPoint'}, {'X': 'Tag'},
                              {'X': 'TrInfo'}, {'X': 'Transition'},
                              {'X': 'Workflow'}, {'X': 'WorkflowTransition'}])],
                           [self.system], {}, {'X': 'table0.C0'}, []),
                          ]),
                        ('FetchStep', [('Any X WHERE EXISTS(X owned_by 5), X is CWUser', [{'X': 'CWUser'}])],
                         [self.system], {'X': 'table2.C0'}, {'X': 'table0.C0'}, []),
                        ('FetchStep', [('Any X WHERE (EXISTS(X owned_by 5)) OR ((((EXISTS(D concerne C?, C owned_by 5, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by 5, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by 5, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by 5, X identity J, E is Note, J is Affaire))), X is Affaire',
                                        [{'C': 'Division', 'E': 'Note', 'D': 'Affaire', 'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire', 'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire'}])],
                         [self.system], {'E': 'table1.C0'}, {'X': 'table0.C0'}, []),
                        ]),
                    ('OneFetchStep', [('Any MAX(X)', X_ALL_SOLS)],
                     None, None, [self.system], {'X': 'table0.C0'}, [])
                    ])

    def test_security_complex_aggregat2(self):
        # use a guest user
        self.session = self._user_session()[1]
        X_ET_ALL_SOLS = []
        for s in X_ALL_SOLS:
            ets = {'ET': 'CWEType'}
            ets.update(s)
            X_ET_ALL_SOLS.append(ets)
        self._test('Any ET, COUNT(X) GROUPBY ET ORDERBY ET WHERE X is ET',
                   [('FetchStep', [('Any X WHERE X is IN(Card, Note, State)',
                                    [{'X': 'Card'}, {'X': 'Note'}, {'X': 'State'}])],
                     [self.cards, self.system], None, {'X': 'table1.C0'}, []),
                    ('FetchStep', [('Any E WHERE E type "X", E is Note', [{'E': 'Note'}])],
                     [self.cards, self.system],  None, {'E': 'table2.C0'}, []),
                    ('FetchStep', [('Any X WHERE X is CWUser', [{'X': 'CWUser'}])],
                     [self.ldap, self.system], None, {'X': 'table3.C0'}, []),
                    ('UnionFetchStep',
                     [('FetchStep', [('Any ET,X WHERE X is ET, EXISTS(X owned_by 5), ET is CWEType, X is Basket',
                                      [{'ET': 'CWEType', 'X': 'Basket'}])],
                       [self.system], {}, {'ET': 'table0.C0', 'X': 'table0.C1'}, []),
                      ('FetchStep', [('Any ET,X WHERE X is ET, (EXISTS(X owned_by 5)) OR ((((EXISTS(D concerne C?, C owned_by 5, C type "X", X identity D, C is Division, D is Affaire)) OR (EXISTS(H concerne G?, G owned_by 5, G type "X", X identity H, G is SubDivision, H is Affaire))) OR (EXISTS(I concerne F?, F owned_by 5, F type "X", X identity I, F is Societe, I is Affaire))) OR (EXISTS(J concerne E?, E owned_by 5, X identity J, E is Note, J is Affaire))), ET is CWEType, X is Affaire',
                                      [{'C': 'Division', 'E': 'Note', 'D': 'Affaire',
                                        'G': 'SubDivision', 'F': 'Societe', 'I': 'Affaire',
                                        'H': 'Affaire', 'J': 'Affaire', 'X': 'Affaire',
                                        'ET': 'CWEType'}])],
                       [self.system], {'E': 'table2.C0'}, {'ET': 'table0.C0', 'X': 'table0.C1'},
                       []),
                      ('FetchStep', [('Any ET,X WHERE X is ET, EXISTS(X owned_by 5), ET is CWEType, X is CWUser',
                                      [{'ET': 'CWEType', 'X': 'CWUser'}])],
                       [self.system], {'X': 'table3.C0'}, {'ET': 'table0.C0', 'X': 'table0.C1'}, []),
                      # extra UnionFetchStep could be avoided but has no cost, so don't care
                      ('UnionFetchStep',
                       [('FetchStep', [('Any ET,X WHERE X is ET, ET is CWEType, X is IN(BaseTransition, Bookmark, CWAttribute, CWCache, CWConstraint, CWConstraintType, CWEType, CWGroup, CWPermission, CWProperty, CWRType, CWRelation, Comment, Division, Email, EmailAddress, EmailPart, EmailThread, ExternalUri, File, Folder, Image, Personne, RQLExpression, Societe, SubDivision, SubWorkflowExitPoint, Tag, TrInfo, Transition, Workflow, WorkflowTransition)',
                                        [{'X': 'BaseTransition', 'ET': 'CWEType'},
                                         {'X': 'Bookmark', 'ET': 'CWEType'}, {'X': 'CWAttribute', 'ET': 'CWEType'},
                                         {'X': 'CWCache', 'ET': 'CWEType'}, {'X': 'CWConstraint', 'ET': 'CWEType'},
                                         {'X': 'CWConstraintType', 'ET': 'CWEType'}, {'X': 'CWEType', 'ET': 'CWEType'},
                                         {'X': 'CWGroup', 'ET': 'CWEType'}, {'X': 'CWPermission', 'ET': 'CWEType'},
                                         {'X': 'CWProperty', 'ET': 'CWEType'}, {'X': 'CWRType', 'ET': 'CWEType'},
                                         {'X': 'CWRelation', 'ET': 'CWEType'}, {'X': 'Comment', 'ET': 'CWEType'},
                                         {'X': 'Division', 'ET': 'CWEType'}, {'X': 'Email', 'ET': 'CWEType'},
                                         {'X': 'EmailAddress', 'ET': 'CWEType'}, {'X': 'EmailPart', 'ET': 'CWEType'},
                                         {'X': 'EmailThread', 'ET': 'CWEType'}, {'X': 'ExternalUri', 'ET': 'CWEType'},
                                         {'X': 'File', 'ET': 'CWEType'}, {'X': 'Folder', 'ET': 'CWEType'},
                                         {'X': 'Image', 'ET': 'CWEType'}, {'X': 'Personne', 'ET': 'CWEType'},
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
                    ]),
                    ('OneFetchStep',
                     [('Any ET,COUNT(X) GROUPBY ET ORDERBY ET', X_ET_ALL_SOLS)],
                     None, None, [self.system], {'ET': 'table0.C0', 'X': 'table0.C1'}, [])
                    ])

    def test_security_3sources(self):
        # use a guest user
        self.session = self._user_session()[1]
        self._test('Any X, XT WHERE X is Card, X owned_by U, X title XT, U login "syt"',
                   [('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any U WHERE U login "syt", U is CWUser', [{'U': 'CWUser'}])],
                     [self.ldap, self.system], None, {'U': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any X,XT WHERE X owned_by U, X title XT, EXISTS(U owned_by 5), U is CWUser, X is Card',
                       [{'X': 'Card', 'U': 'CWUser', 'XT': 'String'}])],
                     None, None, [self.system],
                     {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1', 'U': 'table1.C0'}, [])
                    ])

    def test_security_3sources_identity(self):
        self.restore_orig_euser_security()
        # use a guest user
        self.session = self._user_session()[1]
        self._test('Any X, XT WHERE X is Card, X owned_by U, X title XT, U login "syt"',
                   [('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,XT WHERE X owned_by U, X title XT, U login "syt", EXISTS(U identity 5), U is CWUser, X is Card',
                       [{'U': 'CWUser', 'X': 'Card', 'XT': 'String'}])],
                     None, None, [self.system], {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, [])
                    ])

    def test_security_3sources_identity_optional_var(self):
        self.restore_orig_euser_security()
        # use a guest user
        self.session = self._user_session()[1]
        self._test('Any X,XT,U WHERE X is Card, X owned_by U?, X title XT, U login L',
                   [('FetchStep',
                     [('Any U,L WHERE U identity 5, U login L, U is CWUser',
                       [{'L': 'String', u'U': 'CWUser'}])],
                     [self.system], {}, {'L': 'table0.C1', 'U': 'table0.C0', 'U.login': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table1.C0', 'X.title': 'table1.C1', 'XT': 'table1.C1'}, []),
                    ('OneFetchStep',
                     [('Any X,XT,U WHERE X owned_by U?, X title XT, X is Card',
                       [{'X': 'Card', 'XT': 'String'}])],
                     None, None, [self.system], {'L': 'table0.C1',
                                                 'U': 'table0.C0',
                                                 'X': 'table1.C0',
                                                 'X.title': 'table1.C1',
                                                 'XT': 'table1.C1'}, [])
                    ])

    def test_security_3sources_limit_offset(self):
        # use a guest user
        self.session = self._user_session()[1]
        self._test('Any X, XT LIMIT 10 OFFSET 10 WHERE X is Card, X owned_by U, X title XT, U login "syt"',
                   [('FetchStep',
                     [('Any X,XT WHERE X title XT, X is Card', [{'X': 'Card', 'XT': 'String'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.title': 'table0.C1', 'XT': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any U WHERE U login "syt", U is CWUser', [{'U': 'CWUser'}])],
                     [self.ldap, self.system], None, {'U': 'table1.C0'}, []),
                    ('OneFetchStep',
                     [('Any X,XT LIMIT 10 OFFSET 10 WHERE X owned_by U, X title XT, EXISTS(U owned_by 5), U is CWUser, X is Card',
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
                     [('Any G,L WHERE X in_group G, X login L, G name "managers", (EXISTS(X copain T, T login L, T is CWUser)) OR (EXISTS(X in_state S, S name "pascontent", NOT X copain T2, S is State, T2 is CWUser)), G is CWGroup, X is CWUser',
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
                ('OneFetchStep', [('Any X,AA,AB,AC,AD ORDERBY AA WHERE X login AA, X firstname AB, X surname AC, X modification_date AD, EXISTS(((X identity 5) OR (EXISTS(X in_group C, C name IN("managers", "staff"), C is CWGroup))) OR (EXISTS(X in_group D, 5 in_group D, NOT D name "users", D is CWGroup))), X is CWUser',
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
                      [('OneFetchStep', [('Any X,S,U WHERE X in_state S, X todo_by U, S is State, U is CWUser, X is Note',
                                          [{'X': 'Note', 'S': 'State', 'U': 'CWUser'}])],
                        None, None, [self.system], {'X': 'table0.C0', 'S': 'table0.C1'}, []),
                       ('OneFetchStep', [('Any X,S,U WHERE X in_state S, X todo_by U, S is State, U is Personne, X is Affaire',
                                          [{'X': 'Affaire', 'S': 'State', 'U': 'Personne'}])],
                        None, None, [self.system], {}, []),
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
                   [('OneFetchStep', [('Any SN WHERE NOT 5 in_state S, S name SN, S is State',
                                       [{'S': 'State', 'SN': 'String'}])],
                     None, None, [self.cards, self.system], {}, [])],
                   {'x': ueid})

    def test_not_relation_no_split_external(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        # similar to the above test but with an eid coming from the external source.
        # the same plan may be used, since we won't find any record in the system source
        # linking 9999999 to a state
        self._test('Any SN WHERE NOT X in_state S, X eid %(x)s, S name SN',
                   [('OneFetchStep', [('Any SN WHERE NOT 999999 in_state S, S name SN, S is State',
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
                       [('Any SN WHERE NOT X in_state S, S name SN, S is State, X is Note',
                         [{'S': 'State', 'SN': 'String', 'X': 'Note'}])],
                       None, None, [self.cards, self.system], {},
                       []),
                      ('OneFetchStep',
                       [('Any SN WHERE NOT X in_state S, S name SN, S is State, X is IN(Affaire, CWUser)',
                         [{'S': 'State', 'SN': 'String', 'X': 'Affaire'},
                          {'S': 'State', 'SN': 'String', 'X': 'CWUser'}])],
                       None, None, [self.system], {'S': 'table0.C1', 'S.name': 'table0.C0', 'SN': 'table0.C0'},
                       []),]
                     )])

    def test_external_attributes_and_relation(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
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


    def test_simplified_var(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any U WHERE U in_group G, (G name IN ("managers", "logilab") OR (X require_permission P?, P name "bla", P require_group G)), X eid %(x)s, U eid %(u)s',
                   [('OneFetchStep', [('Any 5 WHERE 5 in_group G, (G name IN("managers", "logilab")) OR (X require_permission P?, P name "bla", P require_group G), X eid 999999',
                                       [{'X': 'Note', 'G': 'CWGroup', 'P': 'CWPermission'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999, 'u': self.session.user.eid})

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

    def test_sort_func(self):
        self._test('Note X ORDERBY DUMB_SORT(RF) WHERE X type RF',
                   [('AggrStep', 'Any X ORDERBY DUMB_SORT(RF)', None, None, 'table0', None, [
                       ('FetchStep', [('Any X,RF WHERE X type RF, X is Note',
                                       [{'X': 'Note', 'RF': 'String'}])],
                        [self.cards, self.system], {}, {'X': 'table0.C0', 'X.type': 'table0.C1', 'RF': 'table0.C1'}, []),
                       ])
                    ])

    def test_ambigous_sort_func(self):
        self._test('Any X ORDERBY DUMB_SORT(RF) WHERE X title RF, X is IN (Bookmark, Card, EmailThread)',
                   [('AggrStep', 'Any X ORDERBY DUMB_SORT(RF)',
                     None, None, 'table0', None,
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
        self._test('DISTINCT Any B,C ORDERBY C WHERE A created_by B, B login C, EXISTS(B owned_by D), D eid %(E)s '
                   'WITH A,N BEING ((Any X,N WHERE X is Tag, X name N) UNION (Any X,T WHERE X is Bookmark, X title T))',
                   [('FetchStep', [('Any X,N WHERE X is Tag, X name N', [{'N': 'String', 'X': 'Tag'}]),
                                   ('Any X,T WHERE X is Bookmark, X title T',
                                    [{'T': 'String', 'X': 'Bookmark'}])],
                     [self.system], {}, {'N': 'table0.C1', 'X': 'table0.C0', 'X.name': 'table0.C1'}, []),
                    ('FetchStep',
                     [('Any B,C WHERE B login C, B is CWUser', [{'B': 'CWUser', 'C': 'String'}])],
                     [self.ldap, self.system], None, {'B': 'table1.C0', 'B.login': 'table1.C1', 'C': 'table1.C1'}, []),
                    ('OneFetchStep', [('DISTINCT Any B,C ORDERBY C WHERE A created_by B, B login C, EXISTS(B owned_by 5), B is CWUser',
                                       [{'A': 'Bookmark', 'B': 'CWUser', 'C': 'String'},
                                        {'A': 'Tag', 'B': 'CWUser', 'C': 'String'}])],
                     None, None, [self.system],
                     {'A': 'table0.C0',
                      'B': 'table1.C0', 'B.login': 'table1.C1',
                      'C': 'table1.C1',
                      'N': 'table0.C1'},
                     [])],
                   {'E': self.session.user.eid})

    def test_subquery_2(self):
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
                    ('OneFetchStep', [('DISTINCT Any B,C ORDERBY C WHERE A created_by B, B login C, EXISTS(B owned_by 5), B is CWUser',
                                       [{'A': 'Card', 'B': 'CWUser', 'C': 'String'},
                                        {'A': 'Tag', 'B': 'CWUser', 'C': 'String'}])],
                     None, None, [self.system],
                     {'A': 'table0.C0',
                      'B': 'table1.C0', 'B.login': 'table1.C1',
                      'C': 'table1.C1',
                      'N': 'table0.C1'},
                     [])],
                   {'E': self.session.user.eid})

    def test_eid_dont_cross_relation(self):
        repo._type_source_cache[999999] = ('Personne', 'system', 999999)
        self._test('Any Y,YT WHERE X eid %(x)s, X fiche Y, Y title YT',
                   [('OneFetchStep', [('Any Y,YT WHERE X eid 999999, X fiche Y, Y title YT',
                                       [{'X': 'Personne', 'Y': 'Card', 'YT': 'String'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999})


    # external source w/ .cross_relations == ['multisource_crossed_rel'] ######

    def test_crossed_relation_eid_1_invariant(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   [('OneFetchStep', [('Any Y WHERE 999999 multisource_crossed_rel Y', [{u'Y': 'Note'}])],
                      None, None, [self.system], {}, [])
                    ],
                   {'x': 999999,})

    def test_crossed_relation_eid_1_needattr(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
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
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any Y WHERE X eid %(x)s, X multisource_crossed_rel Y',
                   [('OneFetchStep', [('Any Y WHERE 999999 multisource_crossed_rel Y, Y is Note', [{'Y': 'Note'}])],
                      None, None, [self.cards, self.system], {}, [])
                    ],
                   {'x': 999999,})

    def test_crossed_relation_eid_2_needattr(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any Y,T WHERE X eid %(x)s, X multisource_crossed_rel Y, Y type T',
                   [('FetchStep', [('Any Y,T WHERE Y type T, Y is Note', [{'T': 'String', 'Y': 'Note'}])],
                     [self.cards, self.system], None,
                     {'T': 'table0.C1', 'Y': 'table0.C0', 'Y.type': 'table0.C1'}, []),
                    ('UnionStep', None, None,
                     [('OneFetchStep', [('Any Y,T WHERE 999999 multisource_crossed_rel Y, Y type T, Y is Note',
                                         [{'T': 'String', 'Y': 'Note'}])],
                       None, None, [self.cards], None,
                       []),
                      ('OneFetchStep', [('Any Y,T WHERE 999999 multisource_crossed_rel Y, Y type T, Y is Note',
                                         [{'T': 'String', 'Y': 'Note'}])],
                       None, None, [self.system],
                       {'T': 'table0.C1', 'Y': 'table0.C0', 'Y.type': 'table0.C1'},
                       [])]
                     )],
                   {'x': 999999,})

    def test_crossed_relation_eid_not_1(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
        self._test('Any Y WHERE X eid %(x)s, NOT X multisource_crossed_rel Y',
                   [('FetchStep', [('Any Y WHERE Y is Note', [{'Y': 'Note'}])],
                     [self.cards, self.system], None, {'Y': 'table0.C0'}, []),
                    ('OneFetchStep', [('Any Y WHERE NOT 999999 multisource_crossed_rel Y, Y is Note',
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
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
        self._test('Any X,Y,T WHERE X multisource_crossed_rel Y, Y type T, X type T',
                   [('FetchStep', [('Any X,T WHERE X type T, X is Note', [{'T': 'String', 'X': 'Note'}])],
                     [self.cards, self.system], None,
                     {'T': 'table0.C1', 'X': 'table0.C0', 'X.type': 'table0.C1'}, []),
                    ('FetchStep',  [('Any Y,T WHERE Y type T, Y is Note', [{'T': 'String', 'Y': 'Note'}])],
                     [self.cards, self.system], None,
                     {'T': 'table1.C1', 'Y': 'table1.C0', 'Y.type': 'table1.C1'},  []),
                    ('UnionStep', None,  None,
                     [('OneFetchStep', [('Any X,Y,T WHERE X multisource_crossed_rel Y, Y type T, X type T, X is Note, Y is Note',
                                         [{'T': 'String', 'X': 'Note', 'Y': 'Note'}])],
                       None, None, [self.cards], None,
                       []),
                      ('OneFetchStep', [('Any X,Y,T WHERE X multisource_crossed_rel Y, Y type T, X type T, X is Note, Y is Note',
                                         [{'T': 'String', 'X': 'Note', 'Y': 'Note'}])],
                       None, None, [self.system],
                       {'T': 'table1.C1', 'X': 'table0.C0', 'X.type': 'table0.C1',
                        'Y': 'table1.C0', 'Y.type': 'table1.C1'},
                       [])]
                     )],
                    {'x': 999999,})

    # edition queries tests ###################################################

    def test_insert_simplified_var_1(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        repo._type_source_cache[999998] = ('State', 'system', None)
        self._test('INSERT Note X: X in_state S, X type T WHERE S eid %(s)s, N eid %(n)s, N type T',
                   [('FetchStep', [('Any T WHERE N eid 999999, N type T, N is Note',
                                    [{'N': 'Note', 'T': 'String'}])],
                     [self.cards], None, {'N.type': 'table0.C0', 'T': 'table0.C0'}, []),
                    ('InsertStep',
                     [('RelationsStep',
                       [('OneFetchStep', [('Any 999998,T WHERE N type T, N is Note',
                                           [{'N': 'Note', 'T': 'String'}])],
                        None, None, [self.system],
                        {'N.type': 'table0.C0', 'T': 'table0.C0'}, [])])
                      ])
                    ],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_2(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        repo._type_source_cache[999998] = ('State', 'system', None)
        self._test('INSERT Note X: X in_state S, X type T, X migrated_from N WHERE S eid %(s)s, N eid %(n)s, N type T',
                   [('FetchStep', [('Any T,N WHERE N eid 999999, N type T, N is Note',
                                    [{'N': 'Note', 'T': 'String'}])],
                     [self.cards], None, {'N': 'table0.C1', 'N.type': 'table0.C0', 'T': 'table0.C0'}, []),
                    ('InsertStep',
                     [('RelationsStep',
                       [('OneFetchStep', [('Any 999998,T,N WHERE N type T, N is Note',
                                           [{'N': 'Note', 'T': 'String'}])],
                         None, None, [self.system],
                         {'N': 'table0.C1', 'N.type': 'table0.C0', 'T': 'table0.C0'}, [])
                        ])
                      ])
                    ],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_3(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        repo._type_source_cache[999998] = ('State', 'cards', 999998)
        self._test('INSERT Note X: X in_state S, X type T WHERE S eid %(s)s, N eid %(n)s, N type T',
                   [('InsertStep',
                     [('RelationsStep',
                       [('OneFetchStep', [('Any 999998,T WHERE N eid 999999, N type T, N is Note',
                                           [{'N': 'Note', 'T': 'String'}])],
                         None, None, [self.cards], {}, [])]
                       )]
                     )],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_4(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        repo._type_source_cache[999998] = ('State', 'system', None)
        self._test('INSERT Note X: X in_state S, X type "bla", X migrated_from N WHERE S eid %(s)s, N eid %(n)s',
                   [('InsertStep',
                     [('RelationsStep',
                       [('OneFetchStep', [('Any 999998,999999', [{}])],
                         None, None, [self.system], {}, [])]
                       )]
                     )],
                   {'n': 999999, 's': 999998})

    def test_insert_simplified_var_5(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        repo._type_source_cache[999998] = ('State', 'system', None)
        self._test('INSERT Note X: X in_state S, X type "bla", X migrated_from N WHERE S eid %(s)s, N eid %(n)s, A concerne N',
                   [('InsertStep',
                     [('RelationsStep',
                       [('OneFetchStep', [('Any 999998,999999 WHERE A concerne 999999, A is Affaire',
                                           [{'A': 'Affaire'}])],
                         None, None, [self.system], {}, [])]
                       )]
                     )],
                   {'n': 999999, 's': 999998})

    def test_delete_relation1(self):
        ueid = self.session.user.eid
        self._test('DELETE X created_by Y WHERE X eid %(x)s, NOT Y eid %(y)s',
                   [('DeleteRelationsStep', [
                       ('OneFetchStep', [('Any 5,Y WHERE %s created_by Y, NOT Y eid %s, Y is CWUser'%(ueid, ueid),
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

    def test_delete_entity1(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
        self._test('DELETE Note X WHERE X eid %(x)s, NOT Y multisource_rel X',
                   [('DeleteEntitiesStep',
                     [('OneFetchStep', [('Any 999999 WHERE NOT Y multisource_rel 999999, Y is IN(Card, Note)',
                                         [{'Y': 'Card'}, {'Y': 'Note'}])],
                       None, None, [self.system], {}, [])
                      ])
                    ],
                   {'x': 999999})

    def test_delete_entity2(self):
        repo._type_source_cache[999999] = ('Note', 'system', 999999)
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
        anoneid = self._user_session()[1].user.eid
        # since we are adding a in_state relation for an entity in the system
        # source, states should only be searched in the system source as well
        self._test('SET X in_state S WHERE X eid %(x)s, S name "deactivated"',
                   [('UpdateStep', [
                       ('OneFetchStep', [('DISTINCT Any 5,S WHERE S name "deactivated", S is State',
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
        self.session.user.fire_transition('deactivate')
        treid = self.session.user.latest_trinfo().eid
        self._test('Any X ORDERBY D DESC WHERE E eid %(x)s, E wf_info_for X, X modification_date D',
                   [('FetchStep', [('Any X,D WHERE X modification_date D, X is Note',
                                    [{'X': 'Note', 'D': 'Datetime'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.modification_date': 'table0.C1', 'D': 'table0.C1'}, []),
                    ('FetchStep', [('Any X,D WHERE X modification_date D, X is CWUser',
                                    [{'X': 'CWUser', 'D': 'Datetime'}])],
                     [self.ldap, self.system], None, {'X': 'table1.C0', 'X.modification_date': 'table1.C1', 'D': 'table1.C1'}, []),
                    ('AggrStep', 'Any X ORDERBY D DESC', None, None, 'table2', None, [
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
        self._test('Any U ORDERBY D DESC WHERE WF wf_info_for X, WF creation_date D, WF from_state FS, '
                   'WF owned_by U?, X eid %(x)s',
                   [#('FetchStep', [('Any U WHERE U is CWUser', [{'U': 'CWUser'}])],
                    # [self.ldap, self.system], None, {'U': 'table0.C0'}, []),
                    ('OneFetchStep', [('Any U ORDERBY D DESC WHERE WF wf_info_for 5, WF creation_date D, WF from_state FS, WF owned_by U?',
                                       [{'WF': 'TrInfo', 'FS': 'State', 'U': 'CWUser', 'D': 'Datetime'}])],
                     None, None,
                     [self.system], {}, [])],
                   {'x': self.session.user.eid})

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
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any S,SUM(DUR),SUM(I),(SUM(I) - SUM(DUR)),MIN(DI),MAX(DI) GROUPBY S ORDERBY S WHERE A is Affaire, A duration DUR, A invoiced I, A modification_date DI, A in_state S, S name SN, (EXISTS(A concerne WP, W multisource_rel WP)) OR (EXISTS(A concerne W)), W eid %(n)s',
                   [('FetchStep', [('Any WP WHERE 999999 multisource_rel WP, WP is Note', [{'WP': 'Note'}])],
                     [self.cards], None, {'WP': u'table0.C0'}, []),
                    ('OneFetchStep', [('Any S,SUM(DUR),SUM(I),(SUM(I) - SUM(DUR)),MIN(DI),MAX(DI) GROUPBY S ORDERBY S WHERE A duration DUR, A invoiced I, A modification_date DI, A in_state S, S name SN, (EXISTS(A concerne WP, WP is Note)) OR (EXISTS(A concerne 999999)), A is Affaire, S is State',
                                       [{'A': 'Affaire', 'DI': 'Datetime', 'DUR': 'Int', 'I': 'Int', 'S': 'State', 'SN': 'String', 'WP': 'Note'}])],
                     None, None, [self.system], {'WP': u'table0.C0'}, [])],
                   {'n': 999999})

    def test_nonregr8(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any X,Z WHERE X eid %(x)s, X multisource_rel Y, Z concerne X',
                   [('FetchStep', [('Any  WHERE 999999 multisource_rel Y, Y is Note', [{'Y': 'Note'}])],
                     [self.cards], None, {}, []),
                    ('OneFetchStep', [('Any 999999,Z WHERE Z concerne 999999, Z is Affaire',
                                       [{'Z': 'Affaire'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999})

    def test_nonregr9(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        repo._type_source_cache[999998] = ('Note', 'cards', 999998)
        self._test('SET X migrated_from Y WHERE X eid %(x)s, Y multisource_rel Z, Z eid %(z)s, Y migrated_from Z',
                   [('FetchStep', [('Any Y WHERE Y multisource_rel 999998, Y is Note', [{'Y': 'Note'}])],
                     [self.cards], None, {'Y': u'table0.C0'}, []),
                    ('UpdateStep',
                     [('OneFetchStep', [('DISTINCT Any 999999,Y WHERE Y migrated_from 999998, Y is Note',
                                         [{'Y': 'Note'}])],
                       None, None, [self.system],
                       {'Y': u'table0.C0'}, [])])],
                   {'x': 999999, 'z': 999998})

    def test_nonregr10(self):
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999999)
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
        repo._type_source_cache[999999] = ('Bookmark', 'system', 999999)
        self._test('SET X bookmarked_by Y WHERE X eid %(x)s, Y login "hop"',
                   [('FetchStep',
                     [('Any Y WHERE Y login "hop", Y is CWUser', [{'Y': 'CWUser'}])],
                     [self.ldap, self.system],
                     None, {'Y': 'table0.C0'}, []),
                    ('UpdateStep',
                     [('OneFetchStep', [('DISTINCT Any 999999,Y WHERE Y is CWUser', [{'Y': 'CWUser'}])],
                       None, None, [self.system], {'Y': 'table0.C0'},
                       [])]
                     )],
                   {'x': 999999})

    def test_nonregr12(self):
        repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any X ORDERBY Z DESC WHERE X modification_date Z, E eid %(x)s, E see_also X',
                   [('FetchStep', [('Any X,Z WHERE X modification_date Z, X is Note',
                                    [{'X': 'Note', 'Z': 'Datetime'}])],
                     [self.cards, self.system], None, {'X': 'table0.C0', 'X.modification_date': 'table0.C1', 'Z': 'table0.C1'},
                     []),
                    ('AggrStep', 'Any X ORDERBY Z DESC',
                     None, None, 'table1', None,
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
                    ('FetchStep', [('Any U,UL WHERE ((EXISTS(U identity 5)) OR (EXISTS(U in_group G, G name IN("managers", "staff"), G is CWGroup))) OR (EXISTS(U in_group H, 5 in_group H, NOT H name "users", H is CWGroup)), U login UL, U is CWUser',
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
        self.skip('take a look at me if you wish')
        self._test('Any B,U,UL GROUPBY B,U,UL WHERE B created_by U?, B is File '
                   'WITH U,UL BEING (Any U,UL WHERE ME eid %(x)s, (U identity ME '
                   'OR (EXISTS(U in_group G, G name IN("managers", "staff")))) '
                   'OR (EXISTS(U in_group H, ME in_group H, NOT H name "users")), U login UL, U is CWUser)',
                   [('FetchStep', [('Any U,UL WHERE U login UL, U is CWUser',
                                    [{'U': 'CWUser', 'UL': 'String'}])],
                     [self.ldap, self.system], None,
                     {'U': 'table0.C0', 'U.login': 'table0.C1', 'UL': 'table0.C1'},
                     []),
                    ('FetchStep', [('Any U,UL WHERE ((U identity 5) OR (EXISTS(U in_group G, G name IN("managers", "staff"), G is CWGroup))) OR (EXISTS(U in_group H, 5 in_group H, NOT H name "users", H is CWGroup)), U login UL, U is CWUser',
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
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999999)
        self._test('Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                   [('OneFetchStep', [('Any 999999 WHERE 999999 owned_by 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999, 'u': 999999})

    def test_nonregr14_2(self):
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999999)
        repo._type_source_cache[999998] = ('Note', 'system', 999998)
        self._test('Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                   [('OneFetchStep', [('Any 999998 WHERE 999998 owned_by 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999998, 'u': 999999})

    def test_nonregr14_3(self):
        repo._type_source_cache[999999] = ('CWUser', 'system', 999999)
        repo._type_source_cache[999998] = ('CWUser', 'ldap', 999998)
        self._test('Any X WHERE X eid %(x)s, X owned_by U, U eid %(u)s',
                   [('OneFetchStep', [('Any 999998 WHERE 999998 owned_by 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999998, 'u': 999999})

    def test_nonregr_identity_no_source_access_1(self):
        repo._type_source_cache[999999] = ('CWUser', 'ldap', 999998)
        self._test('Any S WHERE S identity U, S eid %(s)s, U eid %(u)s',
                   [('OneFetchStep', [('Any 999999 WHERE 999999 identity 999999', [{}])],
                     None, None, [self.system], {}, [])],
                   {'s': 999999, 'u': 999999})

    def test_nonregr_identity_no_source_access_2(self):
        repo._type_source_cache[999999] = ('EmailAddress', 'system', 999999)
        repo._type_source_cache[999998] = ('CWUser', 'ldap', 999998)
        self._test('Any X WHERE O use_email X, ((EXISTS(O identity U)) OR (EXISTS(O in_group G, G name IN("managers", "staff")))) OR (EXISTS(O in_group G2, U in_group G2, NOT G2 name "users")), X eid %(x)s, U eid %(u)s',
                   [('OneFetchStep', [('Any 999999 WHERE O use_email 999999, ((EXISTS(O identity 999998)) OR (EXISTS(O in_group G, G name IN("managers", "staff")))) OR (EXISTS(O in_group G2, 999998 in_group G2, NOT G2 name "users"))',
                                       [{'G': 'CWGroup', 'G2': 'CWGroup', 'O': 'CWUser'}])],
                     None, None, [self.system], {}, [])],
                   {'x': 999999, 'u': 999998})

    def test_state_of_cross(self):
        self._test('DELETE State X WHERE NOT X state_of Y',
                   [('DeleteEntitiesStep',
                     [('OneFetchStep',
                       [('Any X WHERE NOT X state_of Y, X is State, Y is Workflow',
                         [{'X': 'State', 'Y': 'Workflow'}])],
                       None, None, [self.system], {}, [])])]
                   )

class MSPlannerTwoSameExternalSourcesTC(BasePlannerTC):
    """test planner related feature on a 3-sources repository:

    * 2 rql sources supporting Card
    """
    repo = repo

    def setUp(self):
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
        repo._type_source_cache[999999] = ('Tag', 'system', 999999)
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
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999)
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
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999)
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
        self.repo._type_source_cache[999999] = ('Note', 'system', 999999)
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

    def test_nonregr_dont_cross_rel_source_filtering_1(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any S WHERE E eid %(x)s, E in_state S, NOT S name "moved"',
                   [('OneFetchStep', [('Any S WHERE 999999 in_state S, NOT S name "moved", S is State',
                                       [{'S': 'State'}])],
                     None, None, [self.cards], {}, []
                     )],
                   {'x': 999999})

    def test_nonregr_dont_cross_rel_source_filtering_2(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any X,AA,AB WHERE E eid %(x)s, E in_state X, X name AA, X modification_date AB',
                   [('OneFetchStep', [('Any X,AA,AB WHERE 999999 in_state X, X name AA, X modification_date AB, X is State',
                                       [{'AA': 'String', 'AB': 'Datetime', 'X': 'State'}])],
                     None, None, [self.cards], {}, []
                     )],
                   {'x': 999999})

    def test_nonregr_eid_query(self):
        self.repo._type_source_cache[999999] = ('Note', 'cards', 999999)
        self._test('Any X WHERE X eid 999999',
                   [('OneFetchStep', [('Any 999999', [{}])],
                     None, None, [self.system], {}, []
                     )],
                   {'x': 999999})



class FakeVCSSource(AbstractSource):
    uri = 'ccc'
    support_entities = {'Card': True, 'Note': True}
    support_relations = {'multisource_inlined_rel': True,
                         'multisource_rel': True}
    #dont_cross_relations = set(('fiche', 'in_state'))
    #cross_relations = set(('multisource_crossed_rel',))

    def syntax_tree_search(self, *args, **kwargs):
        return []

class MSPlannerVCSSource(BasePlannerTC):
    repo = repo

    def setUp(self):
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
        self.repo._type_source_cache[999998] = ('Note', 'vcs', 999998)
        self.repo._type_source_cache[999999] = ('Note', 'vcs', 999999)
        self._test('Any X, Y WHERE NOT X multisource_rel Y, X eid 999998, Y eid 999999',
                   [('OneFetchStep', [('Any 999998,999999 WHERE NOT 999998 multisource_rel 999999', [{}])],
                     None, None, [self.vcs], {}, [])
                    ])

    def test_nonregr_fully_simplified_extsource(self):
        self.repo._type_source_cache[999998] = ('Note', 'vcs', 999998)
        self.repo._type_source_cache[999999] = ('Note', 'vcs', 999999)
        self.repo._type_source_cache[1000000] = ('Note', 'system', 1000000)
        self._test('DISTINCT Any T,FALSE,L,M WHERE L eid 1000000, M eid 999999, T eid 999998',
                   [('OneFetchStep', [('DISTINCT Any 999998,FALSE,1000000,999999', [{}])],
                     None, None, [self.system], {}, [])
                    ])


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
