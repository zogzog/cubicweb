# -*- coding: iso-8859-1 -*-
"""unit tests for modules cubicweb.server.querier and cubicweb.server.querier_steps
"""
from datetime import date, datetime

from logilab.common.testlib import TestCase, unittest_main
from rql import BadRQLQuery, RQLSyntaxError

from cubicweb import QueryError, Unauthorized
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.utils import crypt_password
from cubicweb.server.sources.native import make_schema
from cubicweb.devtools import init_test_database
from cubicweb.devtools.repotest import tuplify, BaseQuerierTC

from unittest_session import Variable


# register priority/severity sorting registered procedure
from rql.utils import register_function, FunctionDescr

class group_sort_value(FunctionDescr):
    supported_backends = ('sqlite',)
    rtype = 'Int'
try:
    register_function(group_sort_value)
except AssertionError:
    pass
from cubicweb.server.sqlutils import SQL_CONNECT_HOOKS
def init_sqlite_connexion(cnx):
    def group_sort_value(text):
        return {"managers": "3", "users": "2", "guests":  "1", "owners": "0"}[text]
    cnx.create_function("GROUP_SORT_VALUE", 1, group_sort_value)
SQL_CONNECT_HOOKS['sqlite'].append(init_sqlite_connexion)


from logilab.common.adbh import _GenericAdvFuncHelper
TYPEMAP = _GenericAdvFuncHelper.TYPE_MAPPING

class MakeSchemaTC(TestCase):
    def test_known_values(self):
        solution = {'A': 'String', 'B': 'CWUser'}
        self.assertEquals(make_schema((Variable('A'), Variable('B')), solution,
                                      'table0', TYPEMAP),
                          ('C0 text,C1 integer', {'A': 'table0.C0', 'B': 'table0.C1'}))


repo, cnx = init_test_database('sqlite')



class UtilsTC(BaseQuerierTC):
    repo = repo

    def get_max_eid(self):
        # no need for cleanup here
        return None
    def cleanup(self):
        # no need for cleanup here
        pass

    def test_preprocess_1(self):
        reid = self.execute('Any X WHERE X is CWRType, X name "owned_by"')[0][0]
        rqlst = self._prepare('Any COUNT(RDEF) WHERE RDEF relation_type X, X eid %(x)s', {'x': reid})
        self.assertEquals(rqlst.solutions, [{'RDEF': 'CWAttribute'}, {'RDEF': 'CWRelation'}])

    def test_preprocess_2(self):
        teid = self.execute("INSERT Tag X: X name 'tag'")[0][0]
        #geid = self.execute("CWGroup G WHERE G name 'users'")[0][0]
        #self.execute("SET X tags Y WHERE X eid %(t)s, Y eid %(g)s",
        #             {'g': geid, 't': teid}, 'g')
        rqlst = self._prepare('Any X WHERE E eid %(x)s, E tags X', {'x': teid})
        # the query may be optimized, should keep only one solution
        # (any one, etype will be discarded)
        self.assertEquals(len(rqlst.solutions), 1)

    def test_preprocess_security(self):
        plan = self._prepare_plan('Any ETN,COUNT(X) GROUPBY ETN '
                                  'WHERE X is ET, ET name ETN')
        plan.session = self._user_session(('users',))[1]
        union = plan.rqlst
        plan.preprocess(union)
        self.assertEquals(len(union.children), 1)
        self.assertEquals(len(union.children[0].with_), 1)
        subq = union.children[0].with_[0].query
        self.assertEquals(len(subq.children), 3)
        self.assertEquals([t.as_string() for t in union.children[0].selection],
                          ['ETN','COUNT(X)'])
        self.assertEquals([t.as_string() for t in union.children[0].groupby],
                          ['ETN'])
        partrqls = sorted(((rqlst.as_string(), rqlst.solutions) for rqlst in subq.children))
        rql, solutions = partrqls[0]
        self.assertEquals(rql,
                          'Any ETN,X WHERE X is ET, ET name ETN, (EXISTS(X owned_by %(B)s))'
                          ' OR ((((EXISTS(D concerne C?, C owned_by %(B)s, X identity D, C is Division, D is Affaire))'
                          ' OR (EXISTS(H concerne G?, G owned_by %(B)s, G is SubDivision, X identity H, H is Affaire)))'
                          ' OR (EXISTS(I concerne F?, F owned_by %(B)s, F is Societe, X identity I, I is Affaire)))'
                          ' OR (EXISTS(J concerne E?, E owned_by %(B)s, E is Note, X identity J, J is Affaire)))'
                          ', ET is CWEType, X is Affaire')
        self.assertEquals(solutions, [{'C': 'Division',
                                       'D': 'Affaire',
                                       'E': 'Note',
                                       'F': 'Societe',
                                       'G': 'SubDivision',
                                       'H': 'Affaire',
                                       'I': 'Affaire',
                                       'J': 'Affaire',
                                       'X': 'Affaire',
                                       'ET': 'CWEType', 'ETN': 'String'}])
        rql, solutions = partrqls[1]
        self.assertEquals(rql,  'Any ETN,X WHERE X is ET, ET name ETN, ET is CWEType, '
                          'X is IN(Bookmark, CWAttribute, CWCache, CWConstraint, CWConstraintType, CWEType, CWGroup, CWPermission, CWProperty, CWRType, CWRelation, CWUser, Card, Comment, Division, Email, EmailAddress, EmailPart, EmailThread, File, Folder, Image, Note, Personne, RQLExpression, Societe, State, SubDivision, Tag, TrInfo, Transition)')
        self.assertListEquals(sorted(solutions),
                              sorted([{'X': 'Bookmark', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Card', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Comment', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Division', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWCache', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWConstraint', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWConstraintType', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWEType', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWAttribute', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWGroup', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Email', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'EmailAddress', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'EmailPart', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'EmailThread', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWRelation', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWPermission', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWProperty', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWRType', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'CWUser', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'File', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Folder', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Image', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Note', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Personne', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'RQLExpression', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Societe', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'State', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'SubDivision', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Tag', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'Transition', 'ETN': 'String', 'ET': 'CWEType'},
                                      {'X': 'TrInfo', 'ETN': 'String', 'ET': 'CWEType'}]))
        rql, solutions = partrqls[2]
        self.assertEquals(rql,
                          'Any ETN,X WHERE X is ET, ET name ETN, EXISTS(X owned_by %(C)s), '
                          'ET is CWEType, X is Basket')
        self.assertEquals(solutions, [{'ET': 'CWEType',
                                       'X': 'Basket',
                                       'ETN': 'String',
                                       }])

    def test_preprocess_security_aggregat(self):
        plan = self._prepare_plan('Any MAX(X)')
        plan.session = self._user_session(('users',))[1]
        union = plan.rqlst
        plan.preprocess(union)
        self.assertEquals(len(union.children), 1)
        self.assertEquals(len(union.children[0].with_), 1)
        subq = union.children[0].with_[0].query
        self.assertEquals(len(subq.children), 3)
        self.assertEquals([t.as_string() for t in union.children[0].selection],
                          ['MAX(X)'])

    def test_preprocess_nonregr(self):
        rqlst = self._prepare('Any S ORDERBY SI WHERE NOT S ecrit_par O, S para SI')
        self.assertEquals(len(rqlst.solutions), 1)

    def test_build_description(self):
        # should return an empty result set
        rset = self.execute('Any X WHERE X eid %(x)s', {'x': self.session.user.eid})
        self.assertEquals(rset.description[0][0], 'CWUser')
        rset = self.execute('Any 1')
        self.assertEquals(rset.description[0][0], 'Int')
        rset = self.execute('Any TRUE')
        self.assertEquals(rset.description[0][0], 'Boolean')
        rset = self.execute('Any "hop"')
        self.assertEquals(rset.description[0][0], 'String')
        rset = self.execute('Any TODAY')
        self.assertEquals(rset.description[0][0], 'Date')
        rset = self.execute('Any NOW')
        self.assertEquals(rset.description[0][0], 'Datetime')
        rset = self.execute('Any %(x)s', {'x': 1})
        self.assertEquals(rset.description[0][0], 'Int')
        rset = self.execute('Any %(x)s', {'x': 1L})
        self.assertEquals(rset.description[0][0], 'Int')
        rset = self.execute('Any %(x)s', {'x': True})
        self.assertEquals(rset.description[0][0], 'Boolean')
        rset = self.execute('Any %(x)s', {'x': 1.0})
        self.assertEquals(rset.description[0][0], 'Float')
        rset = self.execute('Any %(x)s', {'x': datetime.now()})
        self.assertEquals(rset.description[0][0], 'Datetime')
        rset = self.execute('Any %(x)s', {'x': 'str'})
        self.assertEquals(rset.description[0][0], 'String')
        rset = self.execute('Any %(x)s', {'x': u'str'})
        self.assertEquals(rset.description[0][0], 'String')


class QuerierTC(BaseQuerierTC):
    repo = repo

    def test_encoding_pb(self):
        self.assertRaises(RQLSyntaxError, self.execute,
                          'Any X WHERE X is CWRType, X name "öwned_by"')

    def test_unknown_eid(self):
        # should return an empty result set
        self.failIf(self.execute('Any X WHERE X eid 99999999'))

    # selection queries tests #################################################

    def test_select_1(self):
        rset = self.execute('Any X ORDERBY X WHERE X is CWGroup')
        result, descr = rset.rows, rset.description
        self.assertEquals(tuplify(result), [(1,), (2,), (3,), (4,)])
        self.assertEquals(descr, [('CWGroup',), ('CWGroup',), ('CWGroup',), ('CWGroup',)])

    def test_select_2(self):
        rset = self.execute('Any X ORDERBY N WHERE X is CWGroup, X name N')
        self.assertEquals(tuplify(rset.rows), [(3,), (1,), (4,), (2,)])
        self.assertEquals(rset.description, [('CWGroup',), ('CWGroup',), ('CWGroup',), ('CWGroup',)])
        rset = self.execute('Any X ORDERBY N DESC WHERE X is CWGroup, X name N')
        self.assertEquals(tuplify(rset.rows), [(2,), (4,), (1,), (3,)])

    def test_select_3(self):
        rset = self.execute('Any N GROUPBY N WHERE X is CWGroup, X name N')
        result, descr = rset.rows, rset.description
        result.sort()
        self.assertEquals(tuplify(result), [('guests',), ('managers',), ('owners',), ('users',)])
        self.assertEquals(descr, [('String',), ('String',), ('String',), ('String',)])

    def test_select_is(self):
        rset = self.execute('Any X, TN ORDERBY TN LIMIT 10 WHERE X is T, T name TN')
        result, descr = rset.rows, rset.description
        self.assertEquals(result[0][1], descr[0][0])

    def test_select_is_aggr(self):
        rset = self.execute('Any TN, COUNT(X) GROUPBY TN ORDERBY 2 DESC WHERE X is T, T name TN')
        result, descr = rset.rows, rset.description
        self.assertEquals(descr[0][0], 'String')
        self.assertEquals(descr[0][1], 'Int')
        self.assertEquals(result[0][0], 'CWRelation')

    def test_select_groupby_orderby(self):
        rset = self.execute('Any N GROUPBY N ORDERBY N WHERE X is CWGroup, X name N')
        self.assertEquals(tuplify(rset.rows), [('guests',), ('managers',), ('owners',), ('users',)])
        self.assertEquals(rset.description, [('String',), ('String',), ('String',), ('String',)])

    def test_select_complex_groupby(self):
        rset = self.execute('Any N GROUPBY N WHERE X name N')
        rset = self.execute('Any N,MAX(D) GROUPBY N LIMIT 5 WHERE X name N, X creation_date D')

    def test_select_inlined_groupby(self):
        seid = self.execute('State X WHERE X name "deactivated"')[0][0]
        rset = self.execute('Any U,L,S GROUPBY U,L,S WHERE X in_state S, U login L, S eid %s' % seid)

    def test_select_complex_orderby(self):
        rset1 = self.execute('Any N ORDERBY N WHERE X name N')
        self.assertEquals(sorted(rset1.rows), rset1.rows)
        rset = self.execute('Any N ORDERBY N LIMIT 5 OFFSET 1 WHERE X name N')
        self.assertEquals(rset.rows[0][0], rset1.rows[1][0])
        self.assertEquals(len(rset), 5)

    def test_select_5(self):
        rset = self.execute('Any X, TMP ORDERBY TMP WHERE X name TMP, X is CWGroup')
        self.assertEquals(tuplify(rset.rows), [(3, 'guests',), (1, 'managers',), (4, 'owners',), (2, 'users',)])
        self.assertEquals(rset.description, [('CWGroup', 'String',), ('CWGroup', 'String',), ('CWGroup', 'String',), ('CWGroup', 'String',)])

    def test_select_6(self):
        self.execute("INSERT Personne X: X nom 'bidule'")[0]
        rset = self.execute('Any Y where X name TMP, Y nom in (TMP, "bidule")')
        #self.assertEquals(rset.description, [('Personne',), ('Personne',)])
        self.assert_(('Personne',) in rset.description)
        rset = self.execute('DISTINCT Any Y where X name TMP, Y nom in (TMP, "bidule")')
        self.assert_(('Personne',) in rset.description)

    def test_select_not_attr(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Societe X: X nom 'chouette'")
        rset = self.execute('Personne X WHERE NOT X nom "bidule"')
        self.assertEquals(len(rset.rows), 0, rset.rows)
        rset = self.execute('Personne X WHERE NOT X nom "bid"')
        self.assertEquals(len(rset.rows), 1, rset.rows)
        self.execute("SET P travaille S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.execute('Personne X WHERE NOT X travaille S')
        self.assertEquals(len(rset.rows), 0, rset.rows)

    def test_select_is_in(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Societe X: X nom 'chouette'")
        self.assertEquals(len(self.execute("Any X WHERE X is IN (Personne, Societe)")),
                          2)

    def test_select_not_rel(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Societe X: X nom 'chouette'")
        self.execute("INSERT Personne X: X nom 'autre'")
        self.execute("SET P travaille S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.execute('Personne X WHERE NOT X travaille S')
        self.assertEquals(len(rset.rows), 1, rset.rows)
        rset = self.execute('Personne X WHERE NOT X travaille S, S nom "chouette"')
        self.assertEquals(len(rset.rows), 1, rset.rows)

    def test_select_nonregr_inlined(self):
        self.execute("INSERT Note X: X para 'bidule'")
        self.execute("INSERT Personne X: X nom 'chouette'")
        self.execute("INSERT Personne X: X nom 'autre'")
        self.execute("SET X ecrit_par P WHERE X para 'bidule', P nom 'chouette'")
        rset = self.execute('Any U,T ORDERBY T DESC WHERE U is CWUser, '
                            'N ecrit_par U, N type T')#, {'x': self.ueid})
        self.assertEquals(len(rset.rows), 0)

    def test_select_nonregr_edition_not(self):
        groupeids = set((1, 2, 3))
        groupreadperms = set(r[0] for r in self.execute('Any Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), X read_permission Y'))
        rset = self.execute('DISTINCT Any Y WHERE X is CWEType, X name "CWGroup", Y eid IN(1, 2, 3), NOT X read_permission Y')
        self.assertEquals(sorted(r[0] for r in rset.rows), sorted(groupeids - groupreadperms))
        rset = self.execute('DISTINCT Any Y WHERE X name "CWGroup", Y eid IN(1, 2, 3), NOT X read_permission Y')
        self.assertEquals(sorted(r[0] for r in rset.rows), sorted(groupeids - groupreadperms))

    def test_select_outer_join(self):
        peid1 = self.execute("INSERT Personne X: X nom 'bidule'")[0][0]
        peid2 = self.execute("INSERT Personne X: X nom 'autre'")[0][0]
        seid1 = self.execute("INSERT Societe X: X nom 'chouette'")[0][0]
        seid2 = self.execute("INSERT Societe X: X nom 'chouetos'")[0][0]
        rset = self.execute('Any X,S ORDERBY X WHERE X travaille S?')
        self.assertEquals(rset.rows, [[peid1, None], [peid2, None]])
        self.execute("SET P travaille S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.execute('Any X,S ORDERBY X WHERE X travaille S?')
        self.assertEquals(rset.rows, [[peid1, seid1], [peid2, None]])
        rset = self.execute('Any S,X ORDERBY S WHERE X? travaille S')
        self.assertEquals(rset.rows, [[seid1, peid1], [seid2, None]])

    def test_select_outer_join_optimized(self):
        peid1 = self.execute("INSERT Personne X: X nom 'bidule'")[0][0]
        rset = self.execute('Any X WHERE X eid %(x)s, P? connait X', {'x':peid1}, 'x')
        self.assertEquals(rset.rows, [[peid1]])
        rset = self.execute('Any X WHERE X eid %(x)s, X require_permission P?', {'x':peid1}, 'x')
        self.assertEquals(rset.rows, [[peid1]])

    def test_select_left_outer_join(self):
        ueid = self.execute("INSERT CWUser X: X login 'bob', X upassword 'toto', X in_group G "
                            "WHERE G name 'users'")[0][0]
        self.commit()
        try:
            rset = self.execute('Any FS,TS,C,D,U ORDERBY D DESC '
                                'WHERE WF wf_info_for X,'
                                'WF from_state FS?, WF to_state TS, WF comment C,'
                                'WF creation_date D, WF owned_by U, X eid %(x)s',
                                {'x': ueid}, 'x')
            self.assertEquals(len(rset), 1)
            self.execute('SET X in_state S WHERE X eid %(x)s, S name "deactivated"',
                         {'x': ueid}, 'x')
            rset = self.execute('Any FS,TS,C,D,U ORDERBY D DESC '
                                'WHERE WF wf_info_for X,'
                                'WF from_state FS?, WF to_state TS, WF comment C,'
                                'WF creation_date D, WF owned_by U, X eid %(x)s',
                                {'x': ueid}, 'x')
            self.assertEquals(len(rset), 2)
        finally:
            self.execute('DELETE CWUser X WHERE X eid %s' % ueid)
            self.commit()

    def test_select_ambigous_outer_join(self):
        teid = self.execute("INSERT Tag X: X name 'tag'")[0][0]
        self.execute("INSERT Tag X: X name 'tagbis'")[0][0]
        geid = self.execute("CWGroup G WHERE G name 'users'")[0][0]
        self.execute("SET X tags Y WHERE X eid %(t)s, Y eid %(g)s",
                     {'g': geid, 't': teid}, 'g')
        rset = self.execute("Any GN,TN ORDERBY GN WHERE T? tags G, T name TN, G name GN")
        self.failUnless(['users', 'tag'] in rset.rows)
        self.failUnless(['activated', None] in rset.rows)
        rset = self.execute("Any GN,TN ORDERBY GN WHERE T tags G?, T name TN, G name GN")
        self.assertEquals(rset.rows, [[None, 'tagbis'], ['users', 'tag']])

    def test_select_not_inline_rel(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Note X: X type 'a'")
        self.execute("INSERT Note X: X type 'b'")
        self.execute("SET X ecrit_par Y WHERE X type 'a', Y nom 'bidule'")
        rset = self.execute('Note X WHERE NOT X ecrit_par P')
        self.assertEquals(len(rset.rows), 1, rset.rows)

    def test_select_not_unlinked_multiple_solutions(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Note X: X type 'a'")
        self.execute("INSERT Note X: X type 'b'")
        self.execute("SET Y evaluee X WHERE X type 'a', Y nom 'bidule'")
        rset = self.execute('Note X WHERE NOT Y evaluee X')
        self.assertEquals(len(rset.rows), 1, rset.rows)

    def test_select_aggregat_count(self):
        rset = self.execute('Any COUNT(X)')
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(len(rset.rows[0]), 1)
        self.assertEquals(rset.description, [('Int',)])

    def test_select_aggregat_sum(self):
        rset = self.execute('Any SUM(O) WHERE X ordernum O')
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(len(rset.rows[0]), 1)
        self.assertEquals(rset.description, [('Int',)])

    def test_select_aggregat_min(self):
        rset = self.execute('Any MIN(X) WHERE X is Personne')
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(len(rset.rows[0]), 1)
        self.assertEquals(rset.description, [('Personne',)])
        rset = self.execute('Any MIN(O) WHERE X ordernum O')
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(len(rset.rows[0]), 1)
        self.assertEquals(rset.description, [('Int',)])

    def test_select_aggregat_max(self):
        rset = self.execute('Any MAX(X) WHERE X is Personne')
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(len(rset.rows[0]), 1)
        self.assertEquals(rset.description, [('Personne',)])
        rset = self.execute('Any MAX(O) WHERE X ordernum O')
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(len(rset.rows[0]), 1)
        self.assertEquals(rset.description, [('Int',)])

    def test_select_custom_aggregat_concat_string(self):
        rset = self.execute('Any CONCAT_STRINGS(N) WHERE X is CWGroup, X name N')
        self.failUnless(rset)
        self.failUnlessEqual(sorted(rset[0][0].split(', ')), ['guests', 'managers',
                                                             'owners', 'users'])

    def test_select_custom_regproc_limit_size(self):
        rset = self.execute('Any TEXT_LIMIT_SIZE(N, 3) WHERE X is CWGroup, X name N, X name "managers"')
        self.failUnless(rset)
        self.failUnlessEqual(rset[0][0], 'man...')
        self.execute("INSERT Basket X: X name 'bidule', X description '<b>hop hop</b>', X description_format 'text/html'")
        rset = self.execute('Any LIMIT_SIZE(D, DF, 3) WHERE X is Basket, X description D, X description_format DF')
        self.failUnless(rset)
        self.failUnlessEqual(rset[0][0], 'hop...')

    def test_select_regproc_orderby(self):
        rset = self.execute('DISTINCT Any X,N ORDERBY GROUP_SORT_VALUE(N) WHERE X is CWGroup, X name N, X name "managers"')
        self.failUnlessEqual(len(rset), 1)
        self.failUnlessEqual(rset[0][1], 'managers')
        rset = self.execute('Any X,N ORDERBY GROUP_SORT_VALUE(N) WHERE X is CWGroup, X name N, NOT U in_group X, U login "admin"')
        self.failUnlessEqual(len(rset), 3)
        self.failUnlessEqual(rset[0][1], 'owners')

    def test_select_aggregat_sort(self):
        rset = self.execute('Any G, COUNT(U) GROUPBY G ORDERBY 2 WHERE U in_group G')
        self.assertEquals(len(rset.rows), 2)
        self.assertEquals(len(rset.rows[0]), 2)
        self.assertEquals(rset.description[0], ('CWGroup', 'Int',))

    def test_select_aggregat_having(self):
        rset = self.execute('Any N,COUNT(RDEF) GROUPBY N ORDERBY 2,N '
                            'WHERE RT name N, RDEF relation_type RT '
                            'HAVING COUNT(RDEF) > 10')
        self.assertListEquals(rset.rows,
                              [[u'description', 11], ['in_basket', 11],
                               [u'name', 13], [u'created_by', 33],
                               [u'creation_date', 33], [u'is', 33], [u'is_instance_of', 33],
                               [u'modification_date', 33], [u'owned_by', 33]])

    def test_select_aggregat_having_dumb(self):
        # dumb but should not raise an error
        rset = self.execute('Any U,COUNT(X) GROUPBY U '
                            'WHERE U eid %(x)s, X owned_by U '
                            'HAVING COUNT(X) > 10', {'x': self.ueid})
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(rset.rows[0][0], self.ueid)

    def test_select_complex_sort(self):
        self.skip('retry me once http://www.sqlite.org/cvstrac/tktview?tn=3773 is fixed')
        rset = self.execute('Any X ORDERBY X,D LIMIT 5 WHERE X creation_date D')
        result = rset.rows
        result.sort()
        self.assertEquals(tuplify(result), [(1,), (2,), (3,), (4,), (5,)])

    def test_select_upper(self):
        rset = self.execute('Any X, UPPER(L) ORDERBY L WHERE X is CWUser, X login L')
        self.assertEquals(len(rset.rows), 2)
        self.assertEquals(rset.rows[0][1], 'ADMIN')
        self.assertEquals(rset.description[0], ('CWUser', 'String',))
        self.assertEquals(rset.rows[1][1], 'ANON')
        self.assertEquals(rset.description[1], ('CWUser', 'String',))
        eid = rset.rows[0][0]
        rset = self.execute('Any UPPER(L) WHERE X eid %s, X login L'%eid)
        self.assertEquals(rset.rows[0][0], 'ADMIN')
        self.assertEquals(rset.description, [('String',)])

##     def test_select_simplified(self):
##         ueid = self.session.user.eid
##         rset = self.execute('Any L WHERE %s login L'%ueid)
##         self.assertEquals(rset.rows[0][0], 'admin')
##         rset = self.execute('Any L WHERE %(x)s login L', {'x':ueid})
##         self.assertEquals(rset.rows[0][0], 'admin')

    def test_select_searchable_text_1(self):
        rset = self.execute(u"INSERT Personne X: X nom 'bidüle'")
        rset = self.execute(u"INSERT Societe X: X nom 'bidüle'")
        rset = self.execute("INSERT Societe X: X nom 'chouette'")
        self.commit()
        rset = self.execute('Any X where X has_text %(text)s', {'text': u'bidüle'})
        self.assertEquals(len(rset.rows), 2, rset.rows)
        rset = self.execute(u'Any N where N has_text "bidüle"')
        self.assertEquals(len(rset.rows), 2, rset.rows)
        biduleeids = [r[0] for r in rset.rows]
        rset = self.execute(u'Any N where NOT N has_text "bidüle"')
        self.failIf([r[0] for r in rset.rows if r[0] in biduleeids])
        # duh?
        rset = self.execute('Any X WHERE X has_text %(text)s', {'text': u'ça'})

    def test_select_searchable_text_2(self):
        rset = self.execute("INSERT Personne X: X nom 'bidule'")
        rset = self.execute("INSERT Personne X: X nom 'chouette'")
        rset = self.execute("INSERT Societe X: X nom 'bidule'")
        self.commit()
        rset = self.execute('Personne N where N has_text "bidule"')
        self.assertEquals(len(rset.rows), 1, rset.rows)

    def test_select_searchable_text_3(self):
        rset = self.execute("INSERT Personne X: X nom 'bidule', X sexe 'M'")
        rset = self.execute("INSERT Personne X: X nom 'bidule', X sexe 'F'")
        rset = self.execute("INSERT Societe X: X nom 'bidule'")
        self.commit()
        rset = self.execute('Any X where X has_text "bidule" and X sexe "M"')
        self.assertEquals(len(rset.rows), 1, rset.rows)

    def test_select_multiple_searchable_text(self):
        self.execute(u"INSERT Personne X: X nom 'bidüle'")
        self.execute("INSERT Societe X: X nom 'chouette', S travaille X")
        self.execute(u"INSERT Personne X: X nom 'bidüle'")
        self.commit()
        rset = self.execute('Personne X WHERE X has_text %(text)s, X travaille S, S has_text %(text2)s',
                            {'text': u'bidüle',
                             'text2': u'chouette',}
                            )
        self.assertEquals(len(rset.rows), 1, rset.rows)

    def test_select_no_descr(self):
        rset = self.execute('Any X WHERE X is CWGroup', build_descr=0)
        rset.rows.sort()
        self.assertEquals(tuplify(rset.rows), [(1,), (2,), (3,), (4,)])
        self.assertEquals(rset.description, ())

    def test_select_limit_offset(self):
        rset = self.execute('CWGroup X ORDERBY N LIMIT 2 WHERE X name N')
        self.assertEquals(tuplify(rset.rows), [(3,), (1,)])
        self.assertEquals(rset.description, [('CWGroup',), ('CWGroup',)])
        rset = self.execute('CWGroup X ORDERBY N LIMIT 2 OFFSET 2 WHERE X name N')
        self.assertEquals(tuplify(rset.rows), [(4,), (2,)])

    def test_select_symetric(self):
        self.execute("INSERT Personne X: X nom 'machin'")
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Personne X: X nom 'chouette'")
        self.execute("INSERT Personne X: X nom 'trucmuche'")
        self.execute("SET X connait Y WHERE X nom 'chouette', Y nom 'bidule'")
        self.execute("SET X connait Y WHERE X nom 'machin', Y nom 'chouette'")
        rset = self.execute('Any P where P connait P2')
        self.assertEquals(len(rset.rows), 3, rset.rows)
        rset = self.execute('Any P where NOT P connait P2')
        self.assertEquals(len(rset.rows), 1, rset.rows) # trucmuche
        rset = self.execute('Any P where P connait P2, P2 nom "bidule"')
        self.assertEquals(len(rset.rows), 1, rset.rows)
        rset = self.execute('Any P where P2 connait P, P2 nom "bidule"')
        self.assertEquals(len(rset.rows), 1, rset.rows)
        rset = self.execute('Any P where P connait P2, P2 nom "chouette"')
        self.assertEquals(len(rset.rows), 2, rset.rows)
        rset = self.execute('Any P where P2 connait P, P2 nom "chouette"')
        self.assertEquals(len(rset.rows), 2, rset.rows)

    def test_select_inline(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Note X: X type 'a'")
        self.execute("SET X ecrit_par Y WHERE X type 'a', Y nom 'bidule'")
        rset = self.execute('Any N where N ecrit_par X, X nom "bidule"')
        self.assertEquals(len(rset.rows), 1, rset.rows)

    def test_select_creation_date(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        rset = self.execute('Any D WHERE X nom "bidule", X creation_date D')
        self.assertEqual(len(rset.rows), 1)

    def test_select_or_relation(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Personne X: X nom 'chouette'")
        self.execute("INSERT Societe X: X nom 'logilab'")
        self.execute("INSERT Societe X: X nom 'caesium'")
        self.execute("SET P travaille S WHERE P nom 'bidule', S nom 'logilab'")
        rset = self.execute('DISTINCT Any P WHERE P travaille S1 OR P travaille S2, S1 nom "logilab", S2 nom "caesium"')
        self.assertEqual(len(rset.rows), 1)
        self.execute("SET P travaille S WHERE P nom 'chouette', S nom 'caesium'")
        rset = self.execute('DISTINCT Any P WHERE P travaille S1 OR P travaille S2, S1 nom "logilab", S2 nom "caesium"')
        self.assertEqual(len(rset.rows), 2)

    def test_select_or_sym_relation(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Personne X: X nom 'chouette'")
        self.execute("INSERT Personne X: X nom 'truc'")
        self.execute("SET P connait S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.execute('DISTINCT Any P WHERE S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        rset = self.execute('DISTINCT Any P WHERE P connait S or S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        self.execute("SET P connait S WHERE P nom 'chouette', S nom 'truc'")
        rset = self.execute('DISTINCT Any P WHERE S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        rset = self.execute('DISTINCT Any P WHERE P connait S OR S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 2, rset.rows)

    def test_select_follow_relation(self):
        self.execute("INSERT Affaire X: X sujet 'cool'")
        self.execute("INSERT Societe X: X nom 'chouette'")
        self.execute("SET A concerne S WHERE A is Affaire, S is Societe")
        self.execute("INSERT Note X: X para 'truc'")
        self.execute("SET S evaluee N WHERE S is Societe, N is Note")
        self.execute("INSERT Societe X: X nom 'bidule'")
        self.execute("INSERT Note X: X para 'troc'")
        self.execute("SET S evaluee N WHERE S nom 'bidule', N para 'troc'")
        rset = self.execute('DISTINCT Any A,N WHERE A concerne S, S evaluee N')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_ordered_distinct_1(self):
        self.execute("INSERT Affaire X: X sujet 'cool', X ref '1'")
        self.execute("INSERT Affaire X: X sujet 'cool', X ref '2'")
        rset = self.execute('DISTINCT Any S ORDERBY R WHERE A is Affaire, A sujet S, A ref R')
        self.assertEqual(rset.rows, [['cool']])

    def test_select_ordered_distinct_2(self):
        self.execute("INSERT Affaire X: X sujet 'minor'")
        self.execute("INSERT Affaire X: X sujet 'important'")
        self.execute("INSERT Affaire X: X sujet 'normal'")
        self.execute("INSERT Affaire X: X sujet 'zou'")
        self.execute("INSERT Affaire X: X sujet 'abcd'")
        rset = self.execute('DISTINCT Any S ORDERBY S WHERE A is Affaire, A sujet S')
        self.assertEqual(rset.rows, [['abcd'], ['important'], ['minor'], ['normal'], ['zou']])

    def test_select_ordered_distinct_3(self):
        rset = self.execute('DISTINCT Any N ORDERBY GROUP_SORT_VALUE(N) WHERE X is CWGroup, X name N')
        self.assertEqual(rset.rows, [['owners'], ['guests'], ['users'], ['managers']])

    def test_select_or_value(self):
        rset = self.execute('Any U WHERE U in_group G, G name "owners" OR G name "users"')
        self.assertEqual(len(rset.rows), 0)
        rset = self.execute('Any U WHERE U in_group G, G name "guests" OR G name "managers"')
        self.assertEqual(len(rset.rows), 2)

    def test_select_explicit_eid(self):
        rset = self.execute('Any X,E WHERE X owned_by U, X eid E, U eid %(u)s', {'u': self.session.user.eid})
        self.failUnless(rset)
        self.assertEquals(rset.description[0][1], 'Int')

#     def test_select_rewritten_optional(self):
#         eid = self.execute("INSERT Affaire X: X sujet 'cool'")[0][0]
#         rset = self.execute('Any X WHERE X eid %(x)s, EXISTS(X owned_by U) OR EXISTS(X concerne S?, S owned_by U)',
#                             {'x': eid}, 'x')
#         self.assertEquals(rset.rows, [[eid]])

    def test_today_bug(self):
        self.execute("INSERT Tag X: X name 'bidule', X creation_date NOW")
        self.execute("INSERT Tag Y: Y name 'toto'")
        rset = self.execute("Any D WHERE X name in ('bidule', 'toto') , X creation_date D")
        self.assert_(isinstance(rset.rows[0][0], datetime), rset.rows)
        rset = self.execute('Tag X WHERE X creation_date TODAY')
        self.assertEqual(len(rset.rows), 2)
        rset = self.execute('Any MAX(D) WHERE X is Tag, X creation_date D')
        self.failUnless(isinstance(rset[0][0], datetime), type(rset[0][0]))

    def test_today(self):
        self.execute("INSERT Tag X: X name 'bidule', X creation_date TODAY")
        self.execute("INSERT Tag Y: Y name 'toto'")
        rset = self.execute('Tag X WHERE X creation_date TODAY')
        self.assertEqual(len(rset.rows), 2)

    def test_select_boolean(self):
        rset = self.execute('Any N WHERE X is CWEType, X name N, X final %(val)s',
                            {'val': True})
        self.assertEquals(sorted(r[0] for r in rset.rows), ['Boolean', 'Bytes',
                                                            'Date', 'Datetime',
                                                            'Decimal', 'Float',
                                                            'Int', 'Interval',
                                                            'Password', 'String',
                                                            'Time'])
        rset = self.execute('Any N WHERE X is CWEType, X name N, X final TRUE')
        self.assertEquals(sorted(r[0] for r in rset.rows), ['Boolean', 'Bytes',
                                                            'Date', 'Datetime',
                                                            'Decimal', 'Float',
                                                            'Int', 'Interval',
                                                            'Password', 'String',
                                                            'Time'])

    def test_select_constant(self):
        rset = self.execute('Any X, "toto" ORDERBY X WHERE X is CWGroup')
        self.assertEquals(rset.rows,
                          map(list, zip((1,2,3,4), ('toto','toto','toto','toto',))))
        self.assertIsInstance(rset[0][1], unicode)
        self.assertEquals(rset.description,
                          zip(('CWGroup', 'CWGroup', 'CWGroup', 'CWGroup'),
                              ('String', 'String', 'String', 'String',)))
        rset = self.execute('Any X, %(value)s ORDERBY X WHERE X is CWGroup', {'value': 'toto'})
        self.assertEquals(rset.rows,
                          map(list, zip((1,2,3,4), ('toto','toto','toto','toto',))))
        self.assertIsInstance(rset[0][1], unicode)
        self.assertEquals(rset.description,
                          zip(('CWGroup', 'CWGroup', 'CWGroup', 'CWGroup'),
                              ('String', 'String', 'String', 'String',)))
        rset = self.execute('Any X,GN WHERE X is CWUser, G is CWGroup, X login "syt", X in_group G, G name GN')

    def test_select_union(self):
        rset = self.execute('Any X,N ORDERBY N WITH X,N BEING '
                            '((Any X,N WHERE X name N, X transition_of E, E name %(name)s)'
                            ' UNION '
                            '(Any X,N WHERE X name N, X state_of E, E name %(name)s))',
                            {'name': 'CWUser'})
        self.assertEquals([x[1] for x in rset.rows],
                          ['activate', 'activated', 'deactivate', 'deactivated'])
        self.assertEquals(rset.description,
                          [('Transition', 'String'), ('State', 'String'),
                           ('Transition', 'String'), ('State', 'String')])

    def test_select_union_aggregat(self):
        # meaningless, the goal in to have group by done on different attribute
        # for each sub-query
        self.execute('(Any N,COUNT(X) GROUPBY N WHERE X name N, X is State)'
                     ' UNION '
                     '(Any N,COUNT(X) GROUPBY N ORDERBY 2 WHERE X login N)')

    def test_select_union_aggregat_independant_group(self):
        self.execute('INSERT State X: X name "hop"')
        self.execute('INSERT State X: X name "hop"')
        self.execute('INSERT Transition X: X name "hop"')
        self.execute('INSERT Transition X: X name "hop"')
        rset = self.execute('Any N,NX ORDERBY 2 WITH N,NX BEING '
                            '((Any N,COUNT(X) GROUPBY N WHERE X name N, X is State HAVING COUNT(X)>1)'
                            ' UNION '
                            '(Any N,COUNT(X) GROUPBY N WHERE X name N, X is Transition HAVING COUNT(X)>1))')
        self.assertEquals(rset.rows, [[u'hop', 2], [u'hop', 2]])

    def test_select_union_selection_with_diff_variables(self):
        rset = self.execute('(Any N WHERE X name N, X is State)'
                            ' UNION '
                            '(Any NN WHERE XX name NN, XX is Transition)')
        self.assertEquals(sorted(r[0] for r in rset.rows),
                          ['abort', 'activate', 'activated', 'ben non',
                           'deactivate', 'deactivated', 'done', 'en cours',
                           'end', 'finie', 'markasdone', 'pitetre', 'redoit',
                           'start', 'todo'])

    def test_exists(self):
        geid = self.execute("INSERT CWGroup X: X name 'lulufanclub'")[0][0]
        self.execute("SET U in_group G WHERE G name 'lulufanclub'")
        peid = self.execute("INSERT Personne X: X prenom 'lulu', X nom 'petit'")[0][0]
        rset = self.execute("Any X WHERE X prenom 'lulu',"
                            "EXISTS (U in_group G, G name 'lulufanclub' OR G name 'managers');")
        self.assertEquals(rset.rows, [[peid]])

    def test_identity(self):
        eid = self.execute('Any X WHERE X identity Y, Y eid 1')[0][0]
        self.assertEquals(eid, 1)
        eid = self.execute('Any X WHERE Y identity X, Y eid 1')[0][0]
        self.assertEquals(eid, 1)
        login = self.execute('Any L WHERE X login "admin", X identity Y, Y login L')[0][0]
        self.assertEquals(login, 'admin')

    def test_select_date_mathexp(self):
        rset = self.execute('Any X, TODAY - CD WHERE X is CWUser, X creation_date CD')
        self.failUnless(rset)
        self.failUnlessEqual(rset.description[0][1], 'Interval')
        eid, = self.execute("INSERT Personne X: X nom 'bidule'")[0]
        rset = self.execute('Any X, NOW - CD WHERE X is Personne, X creation_date CD')
        self.failUnlessEqual(rset.description[0][1], 'Interval')

    def test_select_subquery_aggregat(self):
        # percent users by groups
        self.execute('SET X in_group G WHERE G name "users"')
        rset = self.execute('Any GN, COUNT(X)*100/T GROUPBY GN ORDERBY 2,1'
                            ' WHERE G name GN, X in_group G'
                            ' WITH T BEING (Any COUNT(U) WHERE U is CWUser)')
        self.assertEquals(rset.rows, [[u'guests', 50], [u'managers', 50], [u'users', 100]])
        self.assertEquals(rset.description, [('String', 'Int'), ('String', 'Int'), ('String', 'Int')])

    def test_select_subquery_const(self):
        rset = self.execute('Any X WITH X BEING ((Any NULL) UNION (Any "toto"))')
        self.assertEquals(rset.rows, [[None], ['toto']])
        self.assertEquals(rset.description, [(None,), ('String',)])

    # insertion queries tests #################################################

    def test_insert_is(self):
        eid, = self.execute("INSERT Personne X: X nom 'bidule'")[0]
        etype, = self.execute("Any TN WHERE X is T, X eid %s, T name TN" % eid)[0]
        self.assertEquals(etype, 'Personne')
        self.execute("INSERT Personne X: X nom 'managers'")

    def test_insert_1(self):
        rset = self.execute("INSERT Personne X: X nom 'bidule'")
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(rset.description, [('Personne',)])
        rset = self.execute('Personne X WHERE X nom "bidule"')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne',)])

    def test_insert_1_multiple(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Personne X: X nom 'chouette'")
        rset = self.execute("INSERT Societe Y: Y nom N, P travaille Y WHERE P nom N")
        self.assertEquals(len(rset.rows), 2)
        self.assertEquals(rset.description, [('Societe',), ('Societe',)])

    def test_insert_2(self):
        rset = self.execute("INSERT Personne X, Personne Y: X nom 'bidule', Y nom 'tutu'")
        self.assertEquals(rset.description, [('Personne', 'Personne')])
        rset = self.execute('Personne X WHERE X nom "bidule" or X nom "tutu"')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne',), ('Personne',)])

    def test_insert_3(self):
        self.execute("INSERT Personne X: X nom Y WHERE U login 'admin', U login Y")
        rset = self.execute('Personne X WHERE X nom "admin"')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne',)])

    def test_insert_4(self):
        self.execute("INSERT Societe Y: Y nom 'toto'")
        self.execute("INSERT Personne X: X nom 'bidule', X travaille Y WHERE Y nom 'toto'")
        rset = self.execute('Any X, Y WHERE X nom "bidule", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne', 'Societe',)])

    def test_insert_4bis(self):
        peid = self.execute("INSERT Personne X: X nom 'bidule'")[0][0]
        seid = self.execute("INSERT Societe Y: Y nom 'toto', X travaille Y WHERE X eid %(x)s",
                             {'x': str(peid)})[0][0]
        self.assertEqual(len(self.execute('Any X, Y WHERE X travaille Y')), 1)
        self.execute("INSERT Personne X: X nom 'chouette', X travaille Y WHERE Y eid %(x)s",
                      {'x': str(seid)})
        self.assertEqual(len(self.execute('Any X, Y WHERE X travaille Y')), 2)

    def test_insert_4ter(self):
        peid = self.execute("INSERT Personne X: X nom 'bidule'")[0][0]
        seid = self.execute("INSERT Societe Y: Y nom 'toto', X travaille Y WHERE X eid %(x)s",
                             {'x': unicode(peid)})[0][0]
        self.assertEqual(len(self.execute('Any X, Y WHERE X travaille Y')), 1)
        self.execute("INSERT Personne X: X nom 'chouette', X travaille Y WHERE Y eid %(x)s",
                      {'x': unicode(seid)})
        self.assertEqual(len(self.execute('Any X, Y WHERE X travaille Y')), 2)

    def test_insert_5(self):
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Societe Y: Y nom 'toto', X travaille Y WHERE X nom 'bidule'")
        rset = self.execute('Any X, Y WHERE X nom "bidule", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne', 'Societe',)])

    def test_insert_6(self):
        self.execute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto', X travaille Y")
        rset = self.execute('Any X, Y WHERE X nom "bidule", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne', 'Societe',)])

    def test_insert_7(self):
        self.execute("INSERT Personne X, Societe Y: X nom N, Y nom 'toto', X travaille Y WHERE U login 'admin', U login N")
        rset = self.execute('Any X, Y WHERE X nom "admin", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne', 'Societe',)])

    def test_insert_8(self):
        self.execute("INSERT Societe Y, Personne X: Y nom N, X nom 'toto', X travaille Y WHERE U login 'admin', U login N")
        rset = self.execute('Any X, Y WHERE X nom "toto", Y nom "admin", X travaille Y')
        self.assert_(rset.rows)
        self.assertEquals(rset.description, [('Personne', 'Societe',)])

    def test_insert_query_error(self):
        self.assertRaises(Exception,
                          self.execute,
                          "INSERT Personne X: X nom 'toto', X is Personne")
        self.assertRaises(Exception,
                          self.execute,
                          "INSERT Personne X: X nom 'toto', X is_instance_of Personne")
        self.assertRaises(QueryError,
                          self.execute,
                          "INSERT Personne X: X nom 'toto', X has_text 'tutu'")

        self.assertRaises(QueryError,
                          self.execute,
                          "INSERT CWUser X: X login 'toto', X eid %s" % cnx.user(self.session).eid)

    def test_insertion_description_with_where(self):
        rset = self.execute('INSERT CWUser E, EmailAddress EM: E login "X", E upassword "X", '
                            'E primary_email EM, EM address "X", E in_group G '
                            'WHERE G name "managers"')
        self.assertEquals(list(rset.description[0]), ['CWUser', 'EmailAddress'])

    # deletion queries tests ##################################################

    def test_delete_1(self):
        self.execute("INSERT Personne Y: Y nom 'toto'")
        rset = self.execute('Personne X WHERE X nom "toto"')
        self.assertEqual(len(rset.rows), 1)
        self.execute("DELETE Personne Y WHERE Y nom 'toto'")
        rset = self.execute('Personne X WHERE X nom "toto"')
        self.assertEqual(len(rset.rows), 0)

    def test_delete_2(self):
        rset = self.execute("INSERT Personne X, Personne Y, Societe Z : X nom 'syt', Y nom 'adim', Z nom 'Logilab', X travaille Z, Y travaille Z")
        self.assertEquals(len(rset), 1)
        self.assertEquals(len(rset[0]), 3)
        self.assertEquals(rset.description[0], ('Personne', 'Personne', 'Societe'))
        self.assertEquals(self.execute('Any N WHERE X nom N, X eid %s'% rset[0][0])[0][0], 'syt')
        rset = self.execute('Personne X WHERE X travaille Y, Y nom "Logilab"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        self.execute("DELETE X travaille Y WHERE X is Personne, Y nom 'Logilabo'")
        rset = self.execute('Personne X WHERE X travaille Y, Y nom "Logilab"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        self.execute("DELETE X travaille Y WHERE X is Personne, Y nom 'Logilab'")
        rset = self.execute('Personne X WHERE X travaille Y, Y nom "Logilab"')
        self.assertEqual(len(rset.rows), 0, rset.rows)

    def test_delete_3(self):
        u, s = self._user_session(('users',))
        peid, = self.o.execute(s, "INSERT Personne P: P nom 'toto'")[0]
        seid, = self.o.execute(s, "INSERT Societe S: S nom 'logilab'")[0]
        self.o.execute(s, "SET P travaille S")
        rset = self.execute('Personne P WHERE P travaille S')
        self.assertEqual(len(rset.rows), 1)
        self.execute("DELETE X travaille Y WHERE X eid %s, Y eid %s" % (peid, seid))
        rset = self.execute('Personne P WHERE P travaille S')
        self.assertEqual(len(rset.rows), 0)

    def test_delete_symetric(self):
        teid1 = self.execute("INSERT Folder T: T name 'toto'")[0][0]
        teid2 = self.execute("INSERT Folder T: T name 'tutu'")[0][0]
        self.execute('SET X see_also Y WHERE X eid %s, Y eid %s' % (teid1, teid2))
        rset = self.execute('Any X,Y WHERE X see_also Y')
        self.assertEquals(len(rset) , 2, rset.rows)
        self.execute('DELETE X see_also Y WHERE X eid %s, Y eid %s' % (teid1, teid2))
        rset = self.execute('Any X,Y WHERE X see_also Y')
        self.assertEquals(len(rset) , 0)
        self.execute('SET X see_also Y WHERE X eid %s, Y eid %s' % (teid1, teid2))
        rset = self.execute('Any X,Y WHERE X see_also Y')
        self.assertEquals(len(rset) , 2)
        self.execute('DELETE X see_also Y WHERE X eid %s, Y eid %s' % (teid2, teid1))
        rset = self.execute('Any X,Y WHERE X see_also Y')
        self.assertEquals(len(rset) , 0)

    def test_nonregr_delete_cache(self):
        """test that relations are properly cleaned when an entity is deleted
        (using cachekey on sql generation returned always the same query for an eid,
        whatever the relation)
        """
        u, s = self._user_session(('users',))
        aeid, = self.o.execute(s, 'INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')[0]
        # XXX would be nice if the rql below was enough...
        #'INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y'
        eeid, = self.o.execute(s, 'INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y WHERE Y is EmailAddress')[0]
        self.o.execute(s, "DELETE Email X")
        sqlc = s.pool['system']
        sqlc.execute('SELECT * FROM recipients_relation')
        self.assertEquals(len(sqlc.fetchall()), 0)
        sqlc.execute('SELECT * FROM owned_by_relation WHERE eid_from=%s'%eeid)
        self.assertEquals(len(sqlc.fetchall()), 0)

    def test_nonregr_delete_cache2(self):
        eid = self.execute("INSERT Folder T: T name 'toto'")[0][0]
        self.commit()
        # fill the cache
        self.execute("Any X WHERE X eid %(x)s", {'x': eid}, 'x')
        self.execute("Any X WHERE X eid %s" %eid)
        self.execute("Folder X WHERE X eid %(x)s", {'x': eid}, 'x')
        self.execute("Folder X WHERE X eid %s" %eid)
        self.execute("DELETE Folder T WHERE T eid %s"%eid)
        self.commit()
        rset = self.execute("Any X WHERE X eid %(x)s", {'x': eid}, 'x')
        self.assertEquals(rset.rows, [])
        rset = self.execute("Any X WHERE X eid %s" %eid)
        self.assertEquals(rset.rows, [])
        rset = self.execute("Folder X WHERE X eid %(x)s", {'x': eid}, 'x')
        self.assertEquals(rset.rows, [])
        rset = self.execute("Folder X WHERE X eid %s" %eid)
        self.assertEquals(rset.rows, [])

    # update queries tests ####################################################

    def test_update_1(self):
        self.execute("INSERT Personne Y: Y nom 'toto'")
        rset = self.execute('Personne X WHERE X nom "toto"')
        self.assertEqual(len(rset.rows), 1)
        self.execute("SET X nom 'tutu', X prenom 'original' WHERE X is Personne, X nom 'toto'")
        rset = self.execute('Any Y, Z WHERE X is Personne, X nom Y, X prenom Z')
        self.assertEqual(tuplify(rset.rows), [('tutu', 'original')])

    def test_update_2(self):
        self.execute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto'")
        #rset = self.execute('Any X, Y WHERE X nom "bidule", Y nom "toto"')
        #self.assertEqual(len(rset.rows), 1)
        #rset = self.execute('Any X, Y WHERE X travaille Y')
        #self.assertEqual(len(rset.rows), 0)
        self.execute("SET X travaille Y WHERE X nom 'bidule', Y nom 'toto'")
        rset = self.execute('Any X, Y WHERE X travaille Y')
        self.assertEqual(len(rset.rows), 1)

    def test_update_2bis(self):
        rset = self.execute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto'")
        eid1, eid2 = rset[0][0], rset[0][1]
        self.execute("SET X travaille Y WHERE X eid %(x)s, Y eid %(y)s",
                      {'x': str(eid1), 'y': str(eid2)})
        rset = self.execute('Any X, Y WHERE X travaille Y')
        self.assertEqual(len(rset.rows), 1)

    def test_update_2ter(self):
        rset = self.execute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto'")
        eid1, eid2 = rset[0][0], rset[0][1]
        self.execute("SET X travaille Y WHERE X eid %(x)s, Y eid %(y)s",
                      {'x': unicode(eid1), 'y': unicode(eid2)})
        rset = self.execute('Any X, Y WHERE X travaille Y')
        self.assertEqual(len(rset.rows), 1)

##     def test_update_4(self):
##         self.execute("SET X know Y WHERE X ami Y")

    def test_update_multiple1(self):
        peid1 = self.execute("INSERT Personne Y: Y nom 'tutu'")[0][0]
        peid2 = self.execute("INSERT Personne Y: Y nom 'toto'")[0][0]
        self.execute("SET X nom 'tutu', Y nom 'toto' WHERE X nom 'toto', Y nom 'tutu'")
        self.assertEquals(self.execute('Any X WHERE X nom "toto"').rows, [[peid1]])
        self.assertEquals(self.execute('Any X WHERE X nom "tutu"').rows, [[peid2]])

    def test_update_multiple2(self):
        ueid = self.execute("INSERT CWUser X: X login 'bob', X upassword 'toto'")[0][0]
        peid1 = self.execute("INSERT Personne Y: Y nom 'turlu'")[0][0]
        peid2 = self.execute("INSERT Personne Y: Y nom 'tutu'")[0][0]
        self.execute('SET P1 owned_by U, P2 owned_by U '
                     'WHERE P1 eid %s, P2 eid %s, U eid %s' % (peid1, peid2, ueid))
        self.failUnless(self.execute('Any X WHERE X eid %s, X owned_by U, U eid %s'
                                       % (peid1, ueid)))
        self.failUnless(self.execute('Any X WHERE X eid %s, X owned_by U, U eid %s'
                                       % (peid2, ueid)))

    def test_update_math_expr(self):
        orders = [r[0] for r in self.execute('Any O ORDERBY O WHERE ST name "Personne", X from_entity ST, X ordernum O')]
        for i,v in enumerate(orders):
            if v != orders[0]:
                splitidx = i
                break
        self.execute('SET X ordernum Y+1 WHERE X from_entity SE, SE name "Personne", X ordernum Y, X ordernum >= %(order)s',
                     {'order': orders[splitidx]})
        orders2 = [r[0] for r in self.execute('Any O ORDERBY O WHERE ST name "Personne", X from_entity ST, X ordernum O')]
        orders = orders[:splitidx] + [o+1 for o in orders[splitidx:]]
        self.assertEquals(orders2, orders)

    def test_update_string_concat(self):
        beid = self.execute("INSERT Bookmark Y: Y title 'toto', Y path '/view'")[0][0]
        self.execute('SET X title XN + %(suffix)s WHERE X is Bookmark, X title XN', {'suffix': u'-moved'})
        newname = self.execute('Any XN WHERE X eid %(x)s, X title XN', {'x': beid}, 'x')[0][0]
        self.assertEquals(newname, 'toto-moved')

    def test_update_query_error(self):
        self.execute("INSERT Personne Y: Y nom 'toto'")
        self.assertRaises(Exception, self.execute, "SET X nom 'toto', X is Personne")
        self.assertRaises(QueryError, self.execute, "SET X nom 'toto', X has_text 'tutu' WHERE X is Personne")
        self.assertRaises(QueryError, self.execute, "SET X login 'tutu', X eid %s" % cnx.user(self.session).eid)


    # upassword encryption tests #################################################

    def test_insert_upassword(self):
        rset = self.execute("INSERT CWUser X: X login 'bob', X upassword 'toto'")
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(rset.description, [('CWUser',)])
        self.assertRaises(Unauthorized,
                          self.execute, "Any P WHERE X is CWUser, X login 'bob', X upassword P")
        cursor = self.pool['system']
        cursor.execute("SELECT %supassword from %sCWUser WHERE %slogin='bob'"
                       % (SQL_PREFIX, SQL_PREFIX, SQL_PREFIX))
        passwd = cursor.fetchone()[0].getvalue()
        self.assertEquals(passwd, crypt_password('toto', passwd[:2]))
        rset = self.execute("Any X WHERE X is CWUser, X login 'bob', X upassword '%s'" % passwd)
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(rset.description, [('CWUser',)])

    def test_update_upassword(self):
        cursor = self.pool['system']
        rset = self.execute("INSERT CWUser X: X login 'bob', X upassword %(pwd)s", {'pwd': 'toto'})
        self.assertEquals(rset.description[0][0], 'CWUser')
        rset = self.execute("SET X upassword %(pwd)s WHERE X is CWUser, X login 'bob'",
                            {'pwd': 'tutu'})
        cursor.execute("SELECT %supassword from %sCWUser WHERE %slogin='bob'"
                       % (SQL_PREFIX, SQL_PREFIX, SQL_PREFIX))
        passwd = cursor.fetchone()[0].getvalue()
        self.assertEquals(passwd, crypt_password('tutu', passwd[:2]))
        rset = self.execute("Any X WHERE X is CWUser, X login 'bob', X upassword '%s'" % passwd)
        self.assertEquals(len(rset.rows), 1)
        self.assertEquals(rset.description, [('CWUser',)])

    # non regression tests ####################################################

    def test_nonregr_1(self):
        teid = self.execute("INSERT Tag X: X name 'tag'")[0][0]
        self.execute("SET X tags Y WHERE X name 'tag', Y is State, Y name 'activated'")
        rset = self.execute('Any X WHERE T tags X')
        self.assertEquals(len(rset.rows), 1, rset.rows)
        rset = self.execute('Any T WHERE T tags X, X is State')
        self.assertEquals(rset.rows, [[teid]])
        rset = self.execute('Any T WHERE T tags X')
        self.assertEquals(rset.rows, [[teid]])

    def test_nonregr_2(self):
        teid = self.execute("INSERT Tag X: X name 'tag'")[0][0]
        geid = self.execute("CWGroup G WHERE G name 'users'")[0][0]
        self.execute("SET X tags Y WHERE X eid %(t)s, Y eid %(g)s",
                       {'g': geid, 't': teid})
        rset = self.execute('Any X WHERE E eid %(x)s, E tags X',
                              {'x': teid})
        self.assertEquals(rset.rows, [[geid]])

    def test_nonregr_3(self):
        """bad sql generated on the second query (destination_state is not
        detected as an inlined relation)
        """
        rset = self.execute('Any S,ES,T WHERE S state_of ET, ET name "CWUser",'
                             'ES allowed_transition T, T destination_state S')
        self.assertEquals(len(rset.rows), 2)

    def test_nonregr_4(self):
        # fix variables'type, else we get (nb of entity types with a 'name' attribute)**3
        # union queries and that make for instance a 266Ko sql query which is refused
        # by the server (or client lib)
        rset = self.execute('Any ER,SE,OE WHERE SE name "Comment", ER name "comments", OE name "Comment",'
                            'ER is CWRType, SE is CWEType, OE is CWEType')
        self.assertEquals(len(rset), 1)

    def test_nonregr_5(self):
        # jpl #15505: equivalent queries returning different result sets
        teid1 = self.execute("INSERT Folder X: X name 'hop'")[0][0]
        teid2 = self.execute("INSERT Folder X: X name 'hip'")[0][0]
        neid = self.execute("INSERT Note X: X todo_by U, X filed_under T WHERE U login 'admin', T name 'hop'")[0][0]
        weid = self.execute("INSERT Affaire X: X concerne N, X filed_under T WHERE N is Note, T name 'hip'")[0][0]
        rset1 = self.execute('Any N,U WHERE N filed_under T, T eid %s,'
                             'N todo_by U, W concerne N,'
                             'W is Affaire, W filed_under A, A eid %s' % (teid1, teid2))
        rset2 = self.execute('Any N,U WHERE N filed_under T, T eid %s,'
                             'N todo_by U, W concerne N,'
                             'W filed_under A, A eid %s' % (teid1, teid2))
        rset3 = self.execute('Any N,U WHERE N todo_by U, T eid %s,'
                             'N filed_under T, W concerne N,'
                             'W is Affaire, W filed_under A, A eid %s' % (teid1, teid2))
        rset4 = self.execute('Any N,U WHERE N todo_by U, T eid %s,'
                             'N filed_under T, W concerne N,'
                             'W filed_under A, A eid %s' % (teid1, teid2))
        self.assertEquals(rset1.rows, rset2.rows)
        self.assertEquals(rset1.rows, rset3.rows)
        self.assertEquals(rset1.rows, rset4.rows)

    def test_nonregr_6(self):
        self.execute('Any N,COUNT(S) GROUPBY N ORDERBY COUNT(N) WHERE S name N, S is State')

    def test_sqlite_encoding(self):
        """XXX this test was trying to show a bug on use of lower which only
        occurs with non ascii string and misconfigured locale
        """
        self.execute("INSERT Tag X: X name %(name)s,"
                       "X modification_date %(modification_date)s,"
                       "X creation_date %(creation_date)s",
                       {'name': u'éname0',
                        'modification_date': '2003/03/12 11:00',
                        'creation_date': '2000/07/03 11:00'})
        rset = self.execute('Any lower(N) ORDERBY LOWER(N) WHERE X is Tag, X name N,'
                            'X owned_by U, U eid %(x)s',
                            {'x':self.session.user.eid}, 'x')
        self.assertEquals(rset.rows, [[u'\xe9name0']])


    def test_nonregr_description(self):
        """check that a correct description is built in case where infered
        solutions may be "fusionned" into one by the querier while all solutions
        are needed to build the result's description
        """
        self.execute("INSERT Personne X: X nom 'bidule'")
        self.execute("INSERT Societe Y: Y nom 'toto'")
        beid = self.execute("INSERT Basket B: B name 'mybasket'")[0][0]
        self.execute("SET X in_basket B WHERE X is Personne")
        self.execute("SET X in_basket B WHERE X is Societe")
        rset = self.execute('Any X WHERE X in_basket B, B eid %s' % beid)
        self.assertEquals(len(rset), 2)
        self.assertEquals(rset.description, [('Personne',), ('Societe',)])


    def test_nonregr_cache_1(self):
        peid = self.execute("INSERT Personne X: X nom 'bidule'")[0][0]
        beid = self.execute("INSERT Basket X: X name 'tag'")[0][0]
        self.execute("SET X in_basket Y WHERE X is Personne, Y eid %(y)s",
                       {'y': beid})
        rset = self.execute("Any X WHERE X in_basket B, B eid %(x)s",
                       {'x': beid})
        self.assertEquals(rset.rows, [[peid]])
        rset = self.execute("Any X WHERE X in_basket B, B eid %(x)s",
                       {'x': beid})
        self.assertEquals(rset.rows, [[peid]])

    def test_nonregr_has_text_cache(self):
        eid1 = self.execute("INSERT Personne X: X nom 'bidule'")[0][0]
        eid2 = self.execute("INSERT Personne X: X nom 'tag'")[0][0]
        self.commit()
        rset = self.execute("Any X WHERE X has_text %(text)s", {'text': 'bidule'})
        self.assertEquals(rset.rows, [[eid1]])
        rset = self.execute("Any X WHERE X has_text %(text)s", {'text': 'tag'})
        self.assertEquals(rset.rows, [[eid2]])

    def test_nonregr_sortterm_management(self):
        """Error: Variable has no attribute 'sql' in rql2sql.py (visit_variable)

        cause: old variable ref inserted into a fresh rqlst copy
        (in RQLSpliter._complex_select_plan)
        """
        self.skip('retry me once http://www.sqlite.org/cvstrac/tktview?tn=3773 is fixed')
        self.execute('Any X ORDERBY D DESC WHERE X creation_date D')

    def test_nonregr_extra_joins(self):
        ueid = self.session.user.eid
        teid1 = self.execute("INSERT Folder X: X name 'folder1'")[0][0]
        teid2 = self.execute("INSERT Folder X: X name 'folder2'")[0][0]
        neid1 = self.execute("INSERT Note X: X para 'note1'")[0][0]
        neid2 = self.execute("INSERT Note X: X para 'note2'")[0][0]
        self.execute("SET X filed_under Y WHERE X eid %s, Y eid %s"
                       % (neid1, teid1))
        self.execute("SET X filed_under Y WHERE X eid %s, Y eid %s"
                       % (neid2, teid2))
        self.execute("SET X todo_by Y WHERE X is Note, Y eid %s" % ueid)
        rset = self.execute('Any N WHERE N todo_by U, N is Note, U eid %s, N filed_under T, T eid %s'
                             % (ueid, teid1))
        self.assertEquals(len(rset), 1)

    def test_nonregr_XXX(self):
        teid = self.execute('Transition S WHERE S name "deactivate"')[0][0]
        rset = self.execute('Any O WHERE O is State, '
                             'S eid %(x)s, S transition_of ET, O state_of ET', {'x': teid})
        self.assertEquals(len(rset), 2)
        rset = self.execute('Any O WHERE O is State, NOT S destination_state O, '
                             'S eid %(x)s, S transition_of ET, O state_of ET', {'x': teid})
        self.assertEquals(len(rset), 1)


    def test_nonregr_set_datetime(self):
        # huum, psycopg specific
        self.execute('SET X creation_date %(date)s WHERE X eid 1', {'date': date.today()})

    def test_nonregr_set_query(self):
        ueid = self.execute("INSERT CWUser X: X login 'bob', X upassword 'toto'")[0][0]
        self.execute("SET E in_group G, E in_state S, "
                      "E firstname %(firstname)s, E surname %(surname)s "
                      "WHERE E eid %(x)s, G name 'users', S name 'activated'",
                      {'x':ueid, 'firstname': u'jean', 'surname': u'paul'}, 'x')

    def test_nonregr_u_owned_by_u(self):
        ueid = self.execute("INSERT CWUser X: X login 'bob', X upassword 'toto', X in_group G "
                             "WHERE G name 'users'")[0][0]
        rset = self.execute("CWUser U")
        self.assertEquals(len(rset), 3) # bob + admin + anon
        rset = self.execute("Any U WHERE NOT U owned_by U")
        self.assertEquals(len(rset), 0) # even admin created at repo initialization time should belong to itself

    def test_nonreg_update_index(self):
        # this is the kind of queries generated by "cubicweb-ctl db-check -ry"
        self.execute("SET X description D WHERE X is State, X description D")

    def test_nonregr_is(self):
        uteid = self.execute('Any ET WHERE ET name "CWUser"')[0][0]
        self.execute('Any X, ET WHERE X is ET, ET eid %s' % uteid)

    def test_nonregr_orderby(self):
        seid = self.execute('Any X WHERE X name "activated"')[0][0]
        self.execute('Any X,S, MAX(T) GROUPBY X,S ORDERBY S WHERE X is CWUser, T tags X, S eid IN(%s), X in_state S' % seid)

    def test_nonregr_solution_cache(self):
        self.skip('XXX should be fixed or documented') # (doesn't occur if cache key is provided.)
        rset = self.execute('Any X WHERE X is CWUser, X eid %(x)s', {'x':self.ueid})
        self.assertEquals(len(rset), 1)
        rset = self.execute('Any X WHERE X is CWUser, X eid %(x)s', {'x':12345})
        self.assertEquals(len(rset), 0)

    def test_nonregr_final_norestr(self):
        self.assertRaises(BadRQLQuery, self.execute, 'Date X')


if __name__ == '__main__':
    unittest_main()
