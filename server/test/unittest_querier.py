# -*- coding: iso-8859-1 -*-
# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for modules cubicweb.server.querier and cubicweb.server.ssplanner
"""

from datetime import date, datetime, timedelta, tzinfo

from logilab.common.testlib import TestCase, unittest_main
from rql import BadRQLQuery, RQLSyntaxError

from cubicweb import QueryError, Unauthorized, Binary
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.utils import crypt_password
from cubicweb.server.querier import manual_build_descr, _make_description
from cubicweb.devtools import get_test_db_handler, TestServerConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.repotest import tuplify, BaseQuerierTC

class FixedOffset(tzinfo):
    def __init__(self, hours=0):
        self.hours = hours
    def utcoffset(self, dt):
        return timedelta(hours=self.hours)
    def dst(self, dt):
        return timedelta(0)


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


def setUpClass(cls, *args):
    global repo, cnx
    config = TestServerConfiguration(apphome=UtilsTC.datadir)
    handler = get_test_db_handler(config)
    handler.build_db_cache()
    repo, cnx = handler.get_repo_and_cnx()
    cls.repo = repo

def tearDownClass(cls, *args):
    global repo, cnx
    cnx.close()
    repo.shutdown()
    del repo, cnx


class Variable:
    def __init__(self, name):
        self.name = name
        self.children = []

    def get_type(self, solution, args=None):
        return solution[self.name]
    def as_string(self):
        return self.name

class Function:
    def __init__(self, name, varname):
        self.name = name
        self.children = [Variable(varname)]
    def get_type(self, solution, args=None):
        return 'Int'

class MakeDescriptionTC(TestCase):
    def test_known_values(self):
        solution = {'A': 'Int', 'B': 'CWUser'}
        self.assertEqual(_make_description((Function('max', 'A'), Variable('B')), {}, solution),
                          ['Int','CWUser'])


class UtilsTC(BaseQuerierTC):
    setUpClass = classmethod(setUpClass)
    tearDownClass = classmethod(tearDownClass)

    def get_max_eid(self):
        # no need for cleanup here
        return None
    def cleanup(self):
        # no need for cleanup here
        pass

    def test_preprocess_1(self):
        with self.session.new_cnx() as cnx:
            reid = cnx.execute('Any X WHERE X is CWRType, X name "owned_by"')[0][0]
            rqlst = self._prepare(cnx, 'Any COUNT(RDEF) WHERE RDEF relation_type X, X eid %(x)s',
                                  {'x': reid})
            self.assertEqual([{'RDEF': 'CWAttribute'}, {'RDEF': 'CWRelation'}],
                             rqlst.solutions)

    def test_preprocess_2(self):
        with self.session.new_cnx() as cnx:
            teid = cnx.execute("INSERT Tag X: X name 'tag'")[0][0]
            #geid = self.execute("CWGroup G WHERE G name 'users'")[0][0]
            #self.execute("SET X tags Y WHERE X eid %(t)s, Y eid %(g)s",
            #             {'g': geid, 't': teid}, 'g')
            rqlst = self._prepare(cnx, 'Any X WHERE E eid %(x)s, E tags X', {'x': teid})
            # the query may be optimized, should keep only one solution
            # (any one, etype will be discarded)
            self.assertEqual(1, len(rqlst.solutions))

    def assertRQLEqual(self, expected, got):
        from rql import parse
        self.assertMultiLineEqual(unicode(parse(expected)),
                                  unicode(parse(got)))

    def test_preprocess_security(self):
        s = self.user_groups_session('users')
        with s.new_cnx() as cnx:
            plan = self._prepare_plan(cnx, 'Any ETN,COUNT(X) GROUPBY ETN '
                                      'WHERE X is ET, ET name ETN')
            union = plan.rqlst
            plan.preprocess(union)
            self.assertEqual(len(union.children), 1)
            self.assertEqual(len(union.children[0].with_), 1)
            subq = union.children[0].with_[0].query
            self.assertEqual(len(subq.children), 4)
            self.assertEqual([t.as_string() for t in union.children[0].selection],
                              ['ETN','COUNT(X)'])
            self.assertEqual([t.as_string() for t in union.children[0].groupby],
                              ['ETN'])
            partrqls = sorted(((rqlst.as_string(), rqlst.solutions) for rqlst in subq.children))
            rql, solutions = partrqls[0]
            self.assertRQLEqual(rql,
                                'Any ETN,X WHERE X is ET, ET name ETN, (EXISTS(X owned_by %(B)s))'
                                ' OR ((((EXISTS(D concerne C?, C owned_by %(B)s, '
                                '               X identity D, C is Division, D is Affaire))'
                                ' OR (EXISTS(H concerne G?, G owned_by %(B)s, G is SubDivision, '
                                '            X identity H, H is Affaire)))'
                                ' OR (EXISTS(I concerne F?, F owned_by %(B)s, F is Societe, '
                                '            X identity I, I is Affaire)))'
                                ' OR (EXISTS(J concerne E?, E owned_by %(B)s, E is Note, '
                                '            X identity J, J is Affaire)))'
                                ', ET is CWEType, X is Affaire')
            self.assertEqual(solutions, [{'C': 'Division',
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
            self.assertRQLEqual(rql,  'Any ETN,X WHERE X is ET, ET name ETN, ET is CWEType, '
                                'X is IN(BaseTransition, Bookmark, CWAttribute, CWCache, CWComputedRType, '
                                '        CWConstraint, CWConstraintType, CWEType, CWGroup, CWPermission, CWProperty, '
                                '        CWRType, CWRelation, CWSource, CWUniqueTogetherConstraint, CWUser, Card, '
                                '        Comment, Division, Email, EmailPart, EmailThread, ExternalUri, File, Folder, '
                                '        Frozable, Note, Old, Personne, RQLExpression, Societe, State, SubDivision, '
                                '        SubWorkflowExitPoint, Tag, TrInfo, Transition, Workflow, WorkflowTransition)')
            self.assertListEqual(sorted(solutions),
                                  sorted([{'X': 'BaseTransition', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Bookmark', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Card', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Comment', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Division', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWCache', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWComputedRType', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWConstraint', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWConstraintType', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWEType', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWAttribute', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWGroup', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWRelation', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWPermission', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWProperty', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWRType', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWSource', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWUniqueTogetherConstraint', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'CWUser', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Email', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'EmailPart', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'EmailThread', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'ExternalUri', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'File', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Folder', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Frozable', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Note', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Old', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Personne', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'RQLExpression', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Societe', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'State', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'SubDivision', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'SubWorkflowExitPoint', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Tag', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Transition', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'TrInfo', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'Workflow', 'ETN': 'String', 'ET': 'CWEType'},
                                          {'X': 'WorkflowTransition', 'ETN': 'String', 'ET': 'CWEType'}]))
            rql, solutions = partrqls[2]
            self.assertEqual(rql,
                             'Any ETN,X WHERE X is ET, ET name ETN, EXISTS(%(D)s use_email X), '
                             'ET is CWEType, X is EmailAddress')
            self.assertEqual(solutions, [{'X': 'EmailAddress', 'ET': 'CWEType', 'ETN': 'String'}])
            rql, solutions = partrqls[3]
            self.assertEqual(rql,
                              'Any ETN,X WHERE X is ET, ET name ETN, EXISTS(X owned_by %(C)s), '
                              'ET is CWEType, X is Basket')
            self.assertEqual(solutions, [{'X': 'Basket', 'ET': 'CWEType', 'ETN': 'String'}])

    def test_preprocess_security_aggregat(self):
        s = self.user_groups_session('users')
        with s.new_cnx() as cnx:
            plan = self._prepare_plan(cnx, 'Any MAX(X)')
            union = plan.rqlst
            plan.preprocess(union)
            self.assertEqual(len(union.children), 1)
            self.assertEqual(len(union.children[0].with_), 1)
            subq = union.children[0].with_[0].query
            self.assertEqual(len(subq.children), 4)
            self.assertEqual([t.as_string() for t in union.children[0].selection],
                              ['MAX(X)'])

    def test_preprocess_nonregr(self):
        with self.session.new_cnx() as cnx:
            rqlst = self._prepare(cnx, 'Any S ORDERBY SI WHERE NOT S ecrit_par O, S para SI')
            self.assertEqual(len(rqlst.solutions), 1)

    def test_build_description(self):
        # should return an empty result set
        rset = self.qexecute('Any X WHERE X eid %(x)s', {'x': self.session.user.eid})
        self.assertEqual(rset.description[0][0], 'CWUser')
        rset = self.qexecute('Any 1')
        self.assertEqual(rset.description[0][0], 'Int')
        rset = self.qexecute('Any TRUE')
        self.assertEqual(rset.description[0][0], 'Boolean')
        rset = self.qexecute('Any "hop"')
        self.assertEqual(rset.description[0][0], 'String')
        rset = self.qexecute('Any TODAY')
        self.assertEqual(rset.description[0][0], 'Date')
        rset = self.qexecute('Any NOW')
        self.assertEqual(rset.description[0][0], 'Datetime')
        rset = self.qexecute('Any %(x)s', {'x': 1})
        self.assertEqual(rset.description[0][0], 'Int')
        rset = self.qexecute('Any %(x)s', {'x': 1L})
        self.assertEqual(rset.description[0][0], 'Int')
        rset = self.qexecute('Any %(x)s', {'x': True})
        self.assertEqual(rset.description[0][0], 'Boolean')
        rset = self.qexecute('Any %(x)s', {'x': 1.0})
        self.assertEqual(rset.description[0][0], 'Float')
        rset = self.qexecute('Any %(x)s', {'x': datetime.now()})
        self.assertEqual(rset.description[0][0], 'Datetime')
        rset = self.qexecute('Any %(x)s', {'x': 'str'})
        self.assertEqual(rset.description[0][0], 'String')
        rset = self.qexecute('Any %(x)s', {'x': u'str'})
        self.assertEqual(rset.description[0][0], 'String')

    def test_build_descr1(self):
        with self.session.new_cnx() as cnx:
            rset = cnx.execute('(Any U,L WHERE U login L) UNION '
                               '(Any G,N WHERE G name N, G is CWGroup)')
            # rset.req = self.session
            orig_length = len(rset)
            rset.rows[0][0] = 9999999
            description = manual_build_descr(cnx, rset.syntax_tree(), None, rset.rows)
            self.assertEqual(len(description), orig_length - 1)
            self.assertEqual(len(rset.rows), orig_length - 1)
            self.assertNotEqual(rset.rows[0][0], 9999999)

    def test_build_descr2(self):
        rset = self.qexecute('Any X,Y WITH X,Y BEING ((Any G,NULL WHERE G is CWGroup) UNION '
                             '(Any U,G WHERE U in_group G))')
        for x, y in rset.description:
            if y is not None:
                self.assertEqual(y, 'CWGroup')

    def test_build_descr3(self):
        rset = self.qexecute('(Any G,NULL WHERE G is CWGroup) UNION '
                             '(Any U,G WHERE U in_group G)')
        for x, y in rset.description:
            if y is not None:
                self.assertEqual(y, 'CWGroup')


class QuerierTC(BaseQuerierTC):
    setUpClass = classmethod(setUpClass)
    tearDownClass = classmethod(tearDownClass)

    def test_encoding_pb(self):
        self.assertRaises(RQLSyntaxError, self.qexecute,
                          'Any X WHERE X is CWRType, X name "öwned_by"')

    def test_unknown_eid(self):
        # should return an empty result set
        self.assertFalse(self.qexecute('Any X WHERE X eid 99999999'))

    def test_typed_eid(self):
        # should return an empty result set
        rset = self.qexecute('Any X WHERE X eid %(x)s', {'x': '1'})
        self.assertIsInstance(rset[0][0], (int, long))

    def test_bytes_storage(self):
        feid = self.qexecute('INSERT File X: X data_name "foo.pdf", '
                             'X data_format "text/plain", X data %(data)s',
                            {'data': Binary("xxx")})[0][0]
        fdata = self.qexecute('Any D WHERE X data D, X eid %(x)s', {'x': feid})[0][0]
        self.assertIsInstance(fdata, Binary)
        self.assertEqual(fdata.getvalue(), 'xxx')

    # selection queries tests #################################################

    def test_select_1(self):
        rset = self.qexecute('Any X ORDERBY X WHERE X is CWGroup')
        result, descr = rset.rows, rset.description
        self.assertEqual(tuplify(result), [(2,), (3,), (4,), (5,)])
        self.assertEqual(descr, [('CWGroup',), ('CWGroup',), ('CWGroup',), ('CWGroup',)])

    def test_select_2(self):
        rset = self.qexecute('Any X ORDERBY N WHERE X is CWGroup, X name N')
        self.assertEqual(tuplify(rset.rows), [(2,), (3,), (4,), (5,)])
        self.assertEqual(rset.description, [('CWGroup',), ('CWGroup',), ('CWGroup',), ('CWGroup',)])
        rset = self.qexecute('Any X ORDERBY N DESC WHERE X is CWGroup, X name N')
        self.assertEqual(tuplify(rset.rows), [(5,), (4,), (3,), (2,)])

    def test_select_3(self):
        rset = self.qexecute('Any N GROUPBY N WHERE X is CWGroup, X name N')
        result, descr = rset.rows, rset.description
        result.sort()
        self.assertEqual(tuplify(result), [('guests',), ('managers',), ('owners',), ('users',)])
        self.assertEqual(descr, [('String',), ('String',), ('String',), ('String',)])

    def test_select_is(self):
        rset = self.qexecute('Any X, TN ORDERBY TN LIMIT 10 WHERE X is T, T name TN')
        result, descr = rset.rows, rset.description
        self.assertEqual(result[0][1], descr[0][0])

    def test_select_is_aggr(self):
        rset = self.qexecute('Any TN, COUNT(X) GROUPBY TN ORDERBY 2 DESC WHERE X is T, T name TN')
        result, descr = rset.rows, rset.description
        self.assertEqual(descr[0][0], 'String')
        self.assertEqual(descr[0][1], 'Int')
        self.assertEqual(result[0][0], 'RQLExpression') # XXX may change as schema evolve

    def test_select_groupby_orderby(self):
        rset = self.qexecute('Any N GROUPBY N ORDERBY N WHERE X is CWGroup, X name N')
        self.assertEqual(tuplify(rset.rows), [('guests',), ('managers',), ('owners',), ('users',)])
        self.assertEqual(rset.description, [('String',), ('String',), ('String',), ('String',)])

    def test_select_complex_groupby(self):
        rset = self.qexecute('Any N GROUPBY N WHERE X name N')
        rset = self.qexecute('Any N,MAX(D) GROUPBY N LIMIT 5 WHERE X name N, X creation_date D')

    def test_select_inlined_groupby(self):
        seid = self.qexecute('State X WHERE X name "deactivated"')[0][0]
        rset = self.qexecute('Any U,L,S GROUPBY U,L,S WHERE X in_state S, U login L, S eid %s' % seid)

    def test_select_groupby_funccall(self):
        rset = self.qexecute('Any YEAR(CD), COUNT(X) GROUPBY YEAR(CD) '
                             'WHERE X is CWUser, X creation_date CD')
        self.assertListEqual(rset.rows, [[date.today().year, 2]])

    def test_select_groupby_colnumber(self):
        rset = self.qexecute('Any YEAR(CD), COUNT(X) GROUPBY 1 '
                             'WHERE X is CWUser, X creation_date CD')
        self.assertListEqual(rset.rows, [[date.today().year, 2]])

    def test_select_complex_orderby(self):
        rset1 = self.qexecute('Any N ORDERBY N WHERE X name N')
        self.assertEqual(sorted(rset1.rows), rset1.rows)
        rset = self.qexecute('Any N ORDERBY N LIMIT 5 OFFSET 1 WHERE X name N')
        self.assertEqual(rset.rows[0][0], rset1.rows[1][0])
        self.assertEqual(len(rset), 5)

    def test_select_5(self):
        rset = self.qexecute('Any X, TMP ORDERBY TMP WHERE X name TMP, X is CWGroup')
        self.assertEqual(tuplify(rset.rows),
                         [(2, 'guests',),
                          (3, 'managers',),
                          (4, 'owners',),
                          (5, 'users',)])
        self.assertEqual(rset.description,
                         [('CWGroup', 'String',),
                          ('CWGroup', 'String',),
                          ('CWGroup', 'String',),
                          ('CWGroup', 'String',)])

    def test_select_6(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")[0]
        rset = self.qexecute('Any Y where X name TMP, Y nom in (TMP, "bidule")')
        #self.assertEqual(rset.description, [('Personne',), ('Personne',)])
        self.assertIn(('Personne',), rset.description)
        rset = self.qexecute('DISTINCT Any Y where X name TMP, Y nom in (TMP, "bidule")')
        self.assertIn(('Personne',), rset.description)

    def test_select_not_attr(self):
        peid = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        seid = self.qexecute("INSERT Societe X: X nom 'chouette'")[0][0]
        rset = self.qexecute('Personne X WHERE NOT X nom "bidule"')
        self.assertEqual(len(rset.rows), 0, rset.rows)
        rset = self.qexecute('Personne X WHERE NOT X nom "bid"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        self.qexecute("SET P travaille S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.qexecute('Personne X WHERE NOT X travaille S')
        self.assertEqual(len(rset.rows), 0, rset.rows)

    def test_select_is_in(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Societe X: X nom 'chouette'")
        self.assertEqual(len(self.qexecute("Any X WHERE X is IN (Personne, Societe)")),
                          2)

    def test_select_not_rel(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Societe X: X nom 'chouette'")
        self.qexecute("INSERT Personne X: X nom 'autre'")
        self.qexecute("SET P travaille S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.qexecute('Personne X WHERE NOT X travaille S')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        rset = self.qexecute('Personne X WHERE NOT X travaille S, S nom "chouette"')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_nonregr_inlined(self):
        self.qexecute("INSERT Note X: X para 'bidule'")
        self.qexecute("INSERT Personne X: X nom 'chouette'")
        self.qexecute("INSERT Personne X: X nom 'autre'")
        self.qexecute("SET X ecrit_par P WHERE X para 'bidule', P nom 'chouette'")
        rset = self.qexecute('Any U,T ORDERBY T DESC WHERE U is CWUser, '
                             'N ecrit_par U, N type T')#, {'x': self.ueid})
        self.assertEqual(len(rset.rows), 0)

    def test_select_nonregr_edition_not(self):
        groupeids = set((2, 3, 4))
        groupreadperms = set(r[0] for r in self.qexecute('Any Y WHERE X name "CWGroup", '
                                                         'Y eid IN(2, 3, 4), X read_permission Y'))
        rset = self.qexecute('DISTINCT Any Y WHERE X is CWEType, X name "CWGroup", '
                             'Y eid IN(2, 3, 4), NOT X read_permission Y')
        self.assertEqual(sorted(r[0] for r in rset.rows), sorted(groupeids - groupreadperms))
        rset = self.qexecute('DISTINCT Any Y WHERE X name "CWGroup", '
                             'Y eid IN(2, 3, 4), NOT X read_permission Y')
        self.assertEqual(sorted(r[0] for r in rset.rows), sorted(groupeids - groupreadperms))

    def test_select_outer_join(self):
        peid1 = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        peid2 = self.qexecute("INSERT Personne X: X nom 'autre'")[0][0]
        seid1 = self.qexecute("INSERT Societe X: X nom 'chouette'")[0][0]
        seid2 = self.qexecute("INSERT Societe X: X nom 'chouetos'")[0][0]
        rset = self.qexecute('Any X,S ORDERBY X WHERE X travaille S?')
        self.assertEqual(rset.rows, [[peid1, None], [peid2, None]])
        self.qexecute("SET P travaille S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.qexecute('Any X,S ORDERBY X WHERE X travaille S?')
        self.assertEqual(rset.rows, [[peid1, seid1], [peid2, None]])
        rset = self.qexecute('Any S,X ORDERBY S WHERE X? travaille S')
        self.assertEqual(rset.rows, [[seid1, peid1], [seid2, None]])

    def test_select_outer_join_optimized(self):
        peid1 = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        rset = self.qexecute('Any X WHERE X eid %(x)s, P? connait X', {'x':peid1})
        self.assertEqual(rset.rows, [[peid1]])
        rset = self.qexecute('Any X WHERE X eid %(x)s, X require_permission P?',
                            {'x':peid1})
        self.assertEqual(rset.rows, [[peid1]])

    def test_select_left_outer_join(self):
        rset = self.qexecute('DISTINCT Any G WHERE U? in_group G')
        self.assertEqual(len(rset), 4)
        rset = self.qexecute('DISTINCT Any G WHERE U? in_group G, U eid %(x)s',
                            {'x': self.session.user.eid})
        self.assertEqual(len(rset), 4)

    def test_select_ambigous_outer_join(self):
        teid = self.qexecute("INSERT Tag X: X name 'tag'")[0][0]
        self.qexecute("INSERT Tag X: X name 'tagbis'")[0][0]
        geid = self.qexecute("CWGroup G WHERE G name 'users'")[0][0]
        self.qexecute("SET X tags Y WHERE X eid %(t)s, Y eid %(g)s",
                     {'g': geid, 't': teid})
        rset = self.qexecute("Any GN,TN ORDERBY GN WHERE T? tags G, T name TN, G name GN")
        self.assertIn(['users', 'tag'], rset.rows)
        self.assertIn(['activated', None], rset.rows)
        rset = self.qexecute("Any GN,TN ORDERBY GN WHERE T tags G?, T name TN, G name GN")
        self.assertEqual(rset.rows, [[None, 'tagbis'], ['users', 'tag']])

    def test_select_not_inline_rel(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Note X: X type 'a'")
        self.qexecute("INSERT Note X: X type 'b'")
        self.qexecute("SET X ecrit_par Y WHERE X type 'a', Y nom 'bidule'")
        rset = self.qexecute('Note X WHERE NOT X ecrit_par P')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_not_unlinked_multiple_solutions(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Note X: X type 'a'")
        self.qexecute("INSERT Note X: X type 'b'")
        self.qexecute("SET Y evaluee X WHERE X type 'a', Y nom 'bidule'")
        rset = self.qexecute('Note X WHERE NOT Y evaluee X')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_date_extraction(self):
        self.qexecute("INSERT Personne X: X nom 'foo', X datenaiss %(d)s",
                     {'d': datetime(2001, 2,3, 12,13)})
        test_data = [('YEAR', 2001), ('MONTH', 2), ('DAY', 3),
                     ('HOUR', 12), ('MINUTE', 13), ('WEEKDAY', 6)]
        for funcname, result in test_data:
            rset = self.qexecute('Any %s(D) WHERE X is Personne, X datenaiss D'
                                % funcname)
            self.assertEqual(len(rset.rows), 1)
            self.assertEqual(rset.rows[0][0], result)
            self.assertEqual(rset.description, [('Int',)])

    def test_regexp_based_pattern_matching(self):
        peid1 = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        peid2 = self.qexecute("INSERT Personne X: X nom 'cidule'")[0][0]
        rset = self.qexecute('Any X WHERE X is Personne, X nom REGEXP "^b"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        self.assertEqual(rset.rows[0][0], peid1)
        rset = self.qexecute('Any X WHERE X is Personne, X nom REGEXP "idu"')
        self.assertEqual(len(rset.rows), 2, rset.rows)

    def test_select_aggregat_count(self):
        rset = self.qexecute('Any COUNT(X)')
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(len(rset.rows[0]), 1)
        self.assertEqual(rset.description, [('Int',)])

    def test_select_aggregat_sum(self):
        rset = self.qexecute('Any SUM(O) WHERE X ordernum O')
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(len(rset.rows[0]), 1)
        self.assertEqual(rset.description, [('Int',)])

    def test_select_aggregat_min(self):
        rset = self.qexecute('Any MIN(X) WHERE X is Personne')
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(len(rset.rows[0]), 1)
        self.assertEqual(rset.description, [('Personne',)])
        rset = self.qexecute('Any MIN(O) WHERE X ordernum O')
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(len(rset.rows[0]), 1)
        self.assertEqual(rset.description, [('Int',)])

    def test_select_aggregat_max(self):
        rset = self.qexecute('Any MAX(X) WHERE X is Personne')
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(len(rset.rows[0]), 1)
        self.assertEqual(rset.description, [('Personne',)])
        rset = self.qexecute('Any MAX(O) WHERE X ordernum O')
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(len(rset.rows[0]), 1)
        self.assertEqual(rset.description, [('Int',)])

    def test_select_custom_aggregat_concat_string(self):
        rset = self.qexecute('Any GROUP_CONCAT(N) WHERE X is CWGroup, X name N')
        self.assertTrue(rset)
        self.assertEqual(sorted(rset[0][0].split(', ')), ['guests', 'managers',
                                                             'owners', 'users'])

    def test_select_custom_regproc_limit_size(self):
        rset = self.qexecute('Any TEXT_LIMIT_SIZE(N, 3) WHERE X is CWGroup, X name N, X name "managers"')
        self.assertTrue(rset)
        self.assertEqual(rset[0][0], 'man...')
        self.qexecute("INSERT Basket X: X name 'bidule', X description '<b>hop hop</b>', X description_format 'text/html'")
        rset = self.qexecute('Any LIMIT_SIZE(D, DF, 3) WHERE X is Basket, X description D, X description_format DF')
        self.assertTrue(rset)
        self.assertEqual(rset[0][0], 'hop...')

    def test_select_regproc_orderby(self):
        rset = self.qexecute('DISTINCT Any X,N ORDERBY GROUP_SORT_VALUE(N) WHERE X is CWGroup, X name N, X name "managers"')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset[0][1], 'managers')
        rset = self.qexecute('Any X,N ORDERBY GROUP_SORT_VALUE(N) WHERE X is CWGroup, X name N, NOT U in_group X, U login "admin"')
        self.assertEqual(len(rset), 3)
        self.assertEqual(rset[0][1], 'owners')

    def test_select_aggregat_sort(self):
        rset = self.qexecute('Any G, COUNT(U) GROUPBY G ORDERBY 2 WHERE U in_group G')
        self.assertEqual(len(rset.rows), 2)
        self.assertEqual(len(rset.rows[0]), 2)
        self.assertEqual(rset.description[0], ('CWGroup', 'Int',))

    def test_select_aggregat_having(self):
        rset = self.qexecute('Any N,COUNT(RDEF) GROUPBY N ORDERBY 2,N '
                            'WHERE RT name N, RDEF relation_type RT '
                            'HAVING COUNT(RDEF) > 10')
        self.assertListEqual(rset.rows,
                              [[u'description_format', 13],
                               [u'description', 14],
                               [u'name', 19],
                               [u'created_by', 45],
                               [u'creation_date', 45],
                               [u'cw_source', 45],
                               [u'cwuri', 45],
                               [u'in_basket', 45],
                               [u'is', 45],
                               [u'is_instance_of', 45],
                               [u'modification_date', 45],
                               [u'owned_by', 45]])

    def test_select_aggregat_having_dumb(self):
        # dumb but should not raise an error
        rset = self.qexecute('Any U,COUNT(X) GROUPBY U '
                            'WHERE U eid %(x)s, X owned_by U '
                            'HAVING COUNT(X) > 10', {'x': self.ueid})
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(rset.rows[0][0], self.ueid)

    def test_select_having_non_aggregat_1(self):
        rset = self.qexecute('Any L WHERE X login L, X creation_date CD '
                            'HAVING YEAR(CD) = %s' % date.today().year)
        self.assertListEqual(rset.rows,
                              [[u'admin'],
                               [u'anon']])

    def test_select_having_non_aggregat_2(self):
        rset = self.qexecute('Any L GROUPBY L WHERE X login L, X in_group G, '
                            'X creation_date CD HAVING YEAR(CD) = %s OR COUNT(G) > 1'
                            % date.today().year)
        self.assertListEqual(rset.rows,
                              [[u'admin'],
                               [u'anon']])

    def test_select_complex_sort(self):
        """need sqlite including http://www.sqlite.org/cvstrac/tktview?tn=3773 fix"""
        rset = self.qexecute('Any X ORDERBY X,D LIMIT 5 WHERE X creation_date D')
        result = rset.rows
        result.sort()
        self.assertEqual(tuplify(result), [(1,), (2,), (3,), (4,), (5,)])

    def test_select_upper(self):
        rset = self.qexecute('Any X, UPPER(L) ORDERBY L WHERE X is CWUser, X login L')
        self.assertEqual(len(rset.rows), 2)
        self.assertEqual(rset.rows[0][1], 'ADMIN')
        self.assertEqual(rset.description[0], ('CWUser', 'String',))
        self.assertEqual(rset.rows[1][1], 'ANON')
        self.assertEqual(rset.description[1], ('CWUser', 'String',))
        eid = rset.rows[0][0]
        rset = self.qexecute('Any UPPER(L) WHERE X eid %s, X login L'%eid)
        self.assertEqual(rset.rows[0][0], 'ADMIN')
        self.assertEqual(rset.description, [('String',)])

    def test_select_float_abs(self):
        # test positive number
        eid = self.qexecute('INSERT Affaire A: A invoiced %(i)s', {'i': 1.2})[0][0]
        rset = self.qexecute('Any ABS(I) WHERE X eid %(x)s, X invoiced I', {'x': eid})
        self.assertEqual(rset.rows[0][0], 1.2)
        # test negative number
        eid = self.qexecute('INSERT Affaire A: A invoiced %(i)s', {'i': -1.2})[0][0]
        rset = self.qexecute('Any ABS(I) WHERE X eid %(x)s, X invoiced I', {'x': eid})
        self.assertEqual(rset.rows[0][0], 1.2)

    def test_select_int_abs(self):
        # test positive number
        eid = self.qexecute('INSERT Affaire A: A duration %(d)s', {'d': 12})[0][0]
        rset = self.qexecute('Any ABS(D) WHERE X eid %(x)s, X duration D', {'x': eid})
        self.assertEqual(rset.rows[0][0], 12)
        # test negative number
        eid = self.qexecute('INSERT Affaire A: A duration %(d)s', {'d': -12})[0][0]
        rset = self.qexecute('Any ABS(D) WHERE X eid %(x)s, X duration D', {'x': eid})
        self.assertEqual(rset.rows[0][0], 12)

##     def test_select_simplified(self):
##         ueid = self.session.user.eid
##         rset = self.qexecute('Any L WHERE %s login L'%ueid)
##         self.assertEqual(rset.rows[0][0], 'admin')
##         rset = self.qexecute('Any L WHERE %(x)s login L', {'x':ueid})
##         self.assertEqual(rset.rows[0][0], 'admin')

    def test_select_searchable_text_1(self):
        rset = self.qexecute(u"INSERT Personne X: X nom 'bidüle'")
        rset = self.qexecute(u"INSERT Societe X: X nom 'bidüle'")
        rset = self.qexecute("INSERT Societe X: X nom 'chouette'")
        rset = self.qexecute('Any X where X has_text %(text)s', {'text': u'bidüle'})
        self.assertEqual(len(rset.rows), 2, rset.rows)
        rset = self.qexecute(u'Any N where N has_text "bidüle"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        biduleeids = [r[0] for r in rset.rows]
        rset = self.qexecute(u'Any N where NOT N has_text "bidüle"')
        self.assertFalse([r[0] for r in rset.rows if r[0] in biduleeids])
        # duh?
        rset = self.qexecute('Any X WHERE X has_text %(text)s', {'text': u'ça'})

    def test_select_searchable_text_2(self):
        rset = self.qexecute("INSERT Personne X: X nom 'bidule'")
        rset = self.qexecute("INSERT Personne X: X nom 'chouette'")
        rset = self.qexecute("INSERT Societe X: X nom 'bidule'")
        rset = self.qexecute('Personne N where N has_text "bidule"')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_searchable_text_3(self):
        rset = self.qexecute("INSERT Personne X: X nom 'bidule', X sexe 'M'")
        rset = self.qexecute("INSERT Personne X: X nom 'bidule', X sexe 'F'")
        rset = self.qexecute("INSERT Societe X: X nom 'bidule'")
        rset = self.qexecute('Any X where X has_text "bidule" and X sexe "M"')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_multiple_searchable_text(self):
        self.qexecute(u"INSERT Personne X: X nom 'bidüle'")
        self.qexecute("INSERT Societe X: X nom 'chouette', S travaille X")
        self.qexecute(u"INSERT Personne X: X nom 'bidüle'")
        rset = self.qexecute('Personne X WHERE X has_text %(text)s, X travaille S, S has_text %(text2)s',
                            {'text': u'bidüle',
                             'text2': u'chouette',}
                            )
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_no_descr(self):
        rset = self.qexecute('Any X WHERE X is CWGroup', build_descr=0)
        rset.rows.sort()
        self.assertEqual(tuplify(rset.rows), [(2,), (3,), (4,), (5,)])
        self.assertEqual(rset.description, ())

    def test_select_limit_offset(self):
        rset = self.qexecute('CWGroup X ORDERBY N LIMIT 2 WHERE X name N')
        self.assertEqual(tuplify(rset.rows), [(2,), (3,)])
        self.assertEqual(rset.description, [('CWGroup',), ('CWGroup',)])
        rset = self.qexecute('CWGroup X ORDERBY N LIMIT 2 OFFSET 2 WHERE X name N')
        self.assertEqual(tuplify(rset.rows), [(4,), (5,)])

    def test_select_symmetric(self):
        self.qexecute("INSERT Personne X: X nom 'machin'")
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Personne X: X nom 'chouette'")
        self.qexecute("INSERT Personne X: X nom 'trucmuche'")
        self.qexecute("SET X connait Y WHERE X nom 'chouette', Y nom 'bidule'")
        self.qexecute("SET X connait Y WHERE X nom 'machin', Y nom 'chouette'")
        rset = self.qexecute('Any P WHERE P connait P2')
        self.assertEqual(len(rset.rows), 4, rset.rows)
        rset = self.qexecute('Any P WHERE NOT P connait P2')
        self.assertEqual(len(rset.rows), 1, rset.rows) # trucmuche
        rset = self.qexecute('Any P WHERE P connait P2, P2 nom "bidule"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        rset = self.qexecute('Any P WHERE P2 connait P, P2 nom "bidule"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        rset = self.qexecute('Any P WHERE P connait P2, P2 nom "chouette"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        rset = self.qexecute('Any P WHERE P2 connait P, P2 nom "chouette"')
        self.assertEqual(len(rset.rows), 2, rset.rows)

    def test_select_inline(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Note X: X type 'a'")
        self.qexecute("SET X ecrit_par Y WHERE X type 'a', Y nom 'bidule'")
        rset = self.qexecute('Any N where N ecrit_par X, X nom "bidule"')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_creation_date(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        rset = self.qexecute('Any D WHERE X nom "bidule", X creation_date D')
        self.assertEqual(len(rset.rows), 1)

    def test_select_or_relation(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Personne X: X nom 'chouette'")
        self.qexecute("INSERT Societe X: X nom 'logilab'")
        self.qexecute("INSERT Societe X: X nom 'caesium'")
        self.qexecute("SET P travaille S WHERE P nom 'bidule', S nom 'logilab'")
        rset = self.qexecute('DISTINCT Any P WHERE P travaille S1 OR P travaille S2, '
                             'S1 nom "logilab", S2 nom "caesium"')
        self.assertEqual(len(rset.rows), 1)
        self.qexecute("SET P travaille S WHERE P nom 'chouette', S nom 'caesium'")
        rset = self.qexecute('DISTINCT Any P WHERE P travaille S1 OR P travaille S2, '
                             'S1 nom "logilab", S2 nom "caesium"')
        self.assertEqual(len(rset.rows), 2)

    def test_select_or_sym_relation(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Personne X: X nom 'chouette'")
        self.qexecute("INSERT Personne X: X nom 'truc'")
        self.qexecute("SET P connait S WHERE P nom 'bidule', S nom 'chouette'")
        rset = self.qexecute('DISTINCT Any P WHERE S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        rset = self.qexecute('DISTINCT Any P WHERE P connait S or S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        self.qexecute("SET P connait S WHERE P nom 'chouette', S nom 'truc'")
        rset = self.qexecute('DISTINCT Any P WHERE S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        rset = self.qexecute('DISTINCT Any P WHERE P connait S OR S connait P, S nom "chouette"')
        self.assertEqual(len(rset.rows), 2, rset.rows)

    def test_select_follow_relation(self):
        self.qexecute("INSERT Affaire X: X sujet 'cool'")
        self.qexecute("INSERT Societe X: X nom 'chouette'")
        self.qexecute("SET A concerne S WHERE A is Affaire, S is Societe")
        self.qexecute("INSERT Note X: X para 'truc'")
        self.qexecute("SET S evaluee N WHERE S is Societe, N is Note")
        self.qexecute("INSERT Societe X: X nom 'bidule'")
        self.qexecute("INSERT Note X: X para 'troc'")
        self.qexecute("SET S evaluee N WHERE S nom 'bidule', N para 'troc'")
        rset = self.qexecute('DISTINCT Any A,N WHERE A concerne S, S evaluee N')
        self.assertEqual(len(rset.rows), 1, rset.rows)

    def test_select_ordered_distinct_1(self):
        self.assertRaises(BadRQLQuery,
                          self.qexecute, 'DISTINCT Any S ORDERBY R WHERE A is Affaire, A sujet S, A ref R')

    def test_select_ordered_distinct_2(self):
        self.qexecute("INSERT Affaire X: X sujet 'minor'")
        self.qexecute("INSERT Affaire X: X sujet 'zou'")
        self.qexecute("INSERT Affaire X: X sujet 'abcd'")
        rset = self.qexecute('DISTINCT Any S ORDERBY S WHERE A is Affaire, A sujet S')
        self.assertEqual(rset.rows, [['abcd'], ['minor'], ['zou']])

    def test_select_ordered_distinct_3(self):
        rset = self.qexecute('DISTINCT Any N ORDERBY GROUP_SORT_VALUE(N) WHERE X is CWGroup, X name N')
        self.assertEqual(rset.rows, [['owners'], ['guests'], ['users'], ['managers']])

    def test_select_or_value(self):
        rset = self.qexecute('Any U WHERE U in_group G, G name "owners" OR G name "users"')
        self.assertEqual(len(rset.rows), 0)
        rset = self.qexecute('Any U WHERE U in_group G, G name "guests" OR G name "managers"')
        self.assertEqual(len(rset.rows), 2)

    def test_select_explicit_eid(self):
        rset = self.qexecute('Any X,E WHERE X owned_by U, X eid E, U eid %(u)s',
                             {'u': self.session.user.eid})
        self.assertTrue(rset)
        self.assertEqual(rset.description[0][1], 'Int')

#     def test_select_rewritten_optional(self):
#         eid = self.qexecute("INSERT Affaire X: X sujet 'cool'")[0][0]
#         rset = self.qexecute('Any X WHERE X eid %(x)s, EXISTS(X owned_by U) OR EXISTS(X concerne S?, S owned_by U)',
#                             {'x': eid}, 'x')
#         self.assertEqual(rset.rows, [[eid]])

    def test_today_bug(self):
        self.qexecute("INSERT Tag X: X name 'bidule', X creation_date NOW")
        self.qexecute("INSERT Tag Y: Y name 'toto'")
        rset = self.qexecute("Any D WHERE X name in ('bidule', 'toto') , X creation_date D")
        self.assertIsInstance(rset.rows[0][0], datetime)
        rset = self.qexecute('Tag X WHERE X creation_date TODAY')
        self.assertEqual(len(rset.rows), 2)
        rset = self.qexecute('Any MAX(D) WHERE X is Tag, X creation_date D')
        self.assertIsInstance(rset[0][0], datetime)

    def test_today(self):
        self.qexecute("INSERT Tag X: X name 'bidule', X creation_date TODAY")
        self.qexecute("INSERT Tag Y: Y name 'toto'")
        rset = self.qexecute('Tag X WHERE X creation_date TODAY')
        self.assertEqual(len(rset.rows), 2)

    def test_select_boolean(self):
        rset = self.qexecute('Any N WHERE X is CWEType, X name N, X final %(val)s',
                            {'val': True})
        self.assertEqual(sorted(r[0] for r in rset.rows), ['BigInt', 'Boolean', 'Bytes',
                                                           'Date', 'Datetime',
                                                           'Decimal', 'Float',
                                                           'Int', 'Interval',
                                                           'Password', 'String',
                                                           'TZDatetime', 'TZTime',
                                                           'Time'])
        rset = self.qexecute('Any N WHERE X is CWEType, X name N, X final TRUE')
        self.assertEqual(sorted(r[0] for r in rset.rows), ['BigInt', 'Boolean', 'Bytes',
                                                           'Date', 'Datetime',
                                                           'Decimal', 'Float',
                                                           'Int', 'Interval',
                                                           'Password', 'String',
                                                           'TZDatetime', 'TZTime',
                                                           'Time'])
        with self.session.new_cnx() as cnx:
            cnx.create_entity('Personne', nom=u'louis', test=True)
            self.assertEqual(len(cnx.execute('Any X WHERE X test %(val)s', {'val': True})), 1)
            self.assertEqual(len(cnx.execute('Any X WHERE X test TRUE')), 1)
            self.assertEqual(len(cnx.execute('Any X WHERE X test %(val)s', {'val': False})), 0)
            self.assertEqual(len(cnx.execute('Any X WHERE X test FALSE')), 0)

    def test_select_constant(self):
        rset = self.qexecute('Any X, "toto" ORDERBY X WHERE X is CWGroup')
        self.assertEqual(rset.rows,
                          map(list, zip((2,3,4,5), ('toto','toto','toto','toto',))))
        self.assertIsInstance(rset[0][1], unicode)
        self.assertEqual(rset.description,
                          zip(('CWGroup', 'CWGroup', 'CWGroup', 'CWGroup'),
                              ('String', 'String', 'String', 'String',)))
        rset = self.qexecute('Any X, %(value)s ORDERBY X WHERE X is CWGroup', {'value': 'toto'})
        self.assertEqual(rset.rows,
                          map(list, zip((2,3,4,5), ('toto','toto','toto','toto',))))
        self.assertIsInstance(rset[0][1], unicode)
        self.assertEqual(rset.description,
                          zip(('CWGroup', 'CWGroup', 'CWGroup', 'CWGroup'),
                              ('String', 'String', 'String', 'String',)))
        rset = self.qexecute('Any X,GN WHERE X is CWUser, G is CWGroup, X login "syt", '
                             'X in_group G, G name GN')

    def test_select_union(self):
        rset = self.qexecute('Any X,N ORDERBY N WITH X,N BEING '
                            '((Any X,N WHERE X name N, X transition_of WF, WF workflow_of E, E name %(name)s)'
                            ' UNION '
                            '(Any X,N WHERE X name N, X state_of WF, WF workflow_of E, E name %(name)s))',
                            {'name': 'CWUser'})
        self.assertEqual([x[1] for x in rset.rows],
                          ['activate', 'activated', 'deactivate', 'deactivated'])
        self.assertEqual(rset.description,
                          [('Transition', 'String'), ('State', 'String'),
                           ('Transition', 'String'), ('State', 'String')])

    def test_select_union_aggregat(self):
        # meaningless, the goal in to have group by done on different attribute
        # for each sub-query
        self.qexecute('(Any N,COUNT(X) GROUPBY N WHERE X name N, X is State)'
                     ' UNION '
                     '(Any N,COUNT(X) GROUPBY N ORDERBY 2 WHERE X login N)')

    def test_select_union_aggregat_independant_group(self):
        with self.session.new_cnx() as cnx:
            cnx.execute('INSERT State X: X name "hop"')
            cnx.execute('INSERT State X: X name "hop"')
            cnx.execute('INSERT Transition X: X name "hop"')
            cnx.execute('INSERT Transition X: X name "hop"')
            rset = cnx.execute('Any N,NX ORDERBY 2 WITH N,NX BEING '
                               '((Any N,COUNT(X) GROUPBY N WHERE X name N, '
                               '  X is State HAVING COUNT(X)>1)'
                               ' UNION '
                               '(Any N,COUNT(X) GROUPBY N WHERE X name N, '
                               ' X is Transition HAVING COUNT(X)>1))')
            self.assertEqual(rset.rows, [[u'hop', 2], [u'hop', 2]])

    def test_select_union_selection_with_diff_variables(self):
        rset = self.qexecute('(Any N WHERE X name N, X is State)'
                            ' UNION '
                            '(Any NN WHERE XX name NN, XX is Transition)')
        self.assertEqual(sorted(r[0] for r in rset.rows),
                          ['abort', 'activate', 'activated', 'ben non',
                           'deactivate', 'deactivated', 'done', 'en cours',
                           'end', 'finie', 'markasdone', 'pitetre', 'redoit',
                           'start', 'todo'])

    def test_select_union_description_diff_var(self):
        eid1 = self.qexecute('CWGroup X WHERE X name "managers"')[0][0]
        eid2 = self.qexecute('CWUser X WHERE X login "admin"')[0][0]
        rset = self.qexecute('(Any X WHERE X eid %(x)s)'
                            ' UNION '
                            '(Any Y WHERE Y eid %(y)s)',
                            {'x': eid1, 'y': eid2})
        self.assertEqual(rset.description[:], [('CWGroup',), ('CWUser',)])

    def test_exists(self):
        geid = self.qexecute("INSERT CWGroup X: X name 'lulufanclub'")[0][0]
        self.qexecute("SET U in_group G WHERE G name 'lulufanclub'")
        peid = self.qexecute("INSERT Personne X: X prenom 'lulu', X nom 'petit'")[0][0]
        rset = self.qexecute("Any X WHERE X prenom 'lulu',"
                            "EXISTS (U in_group G, G name 'lulufanclub' OR G name 'managers');")
        self.assertEqual(rset.rows, [[peid]])

    def test_identity(self):
        eid = self.qexecute('Any X WHERE X identity Y, Y eid 1')[0][0]
        self.assertEqual(eid, 1)
        eid = self.qexecute('Any X WHERE Y identity X, Y eid 1')[0][0]
        self.assertEqual(eid, 1)
        login = self.qexecute('Any L WHERE X login "admin", X identity Y, Y login L')[0][0]
        self.assertEqual(login, 'admin')

    def test_select_date_mathexp(self):
        rset = self.qexecute('Any X, TODAY - CD WHERE X is CWUser, X creation_date CD')
        self.assertTrue(rset)
        self.assertEqual(rset.description[0][1], 'Interval')
        eid, = self.qexecute("INSERT Personne X: X nom 'bidule'")[0]
        rset = self.qexecute('Any X, NOW - CD WHERE X is Personne, X creation_date CD')
        self.assertEqual(rset.description[0][1], 'Interval')

    def test_select_subquery_aggregat_1(self):
        # percent users by groups
        self.qexecute('SET X in_group G WHERE G name "users"')
        rset = self.qexecute('Any GN, COUNT(X)*100/T GROUPBY GN ORDERBY 2,1'
                            ' WHERE G name GN, X in_group G'
                            ' WITH T BEING (Any COUNT(U) WHERE U is CWUser)')
        self.assertEqual(rset.rows, [[u'guests', 50], [u'managers', 50], [u'users', 100]])
        self.assertEqual(rset.description, [('String', 'Int'), ('String', 'Int'), ('String', 'Int')])

    def test_select_subquery_aggregat_2(self):
        expected = self.qexecute('Any X, 0, COUNT(T) GROUPBY X '
                                'WHERE X is Workflow, T transition_of X').rows
        rset = self.qexecute('''
Any P1,B,E WHERE P1 identity P2 WITH
  P1,B BEING (Any P,COUNT(T) GROUPBY P WHERE P is Workflow, T is Transition,
              T? transition_of P, T type "auto"),
  P2,E BEING (Any P,COUNT(T) GROUPBY P WHERE P is Workflow, T is Transition,
              T? transition_of P, T type "normal")''')
        self.assertEqual(sorted(rset.rows), sorted(expected))

    def test_select_subquery_const(self):
        rset = self.qexecute('Any X WITH X BEING ((Any NULL) UNION (Any "toto"))')
        self.assertEqual(rset.rows, [[None], ['toto']])
        self.assertEqual(rset.description, [(None,), ('String',)])

    # insertion queries tests #################################################

    def test_insert_is(self):
        eid, = self.qexecute("INSERT Personne X: X nom 'bidule'")[0]
        etype, = self.qexecute("Any TN WHERE X is T, X eid %s, T name TN" % eid)[0]
        self.assertEqual(etype, 'Personne')
        self.qexecute("INSERT Personne X: X nom 'managers'")

    def test_insert_1(self):
        rset = self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(rset.description, [('Personne',)])
        rset = self.qexecute('Personne X WHERE X nom "bidule"')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne',)])

    def test_insert_1_multiple(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Personne X: X nom 'chouette'")
        rset = self.qexecute("INSERT Societe Y: Y nom N, P travaille Y WHERE P nom N")
        self.assertEqual(len(rset.rows), 2)
        self.assertEqual(rset.description, [('Societe',), ('Societe',)])

    def test_insert_2(self):
        rset = self.qexecute("INSERT Personne X, Personne Y: X nom 'bidule', Y nom 'tutu'")
        self.assertEqual(rset.description, [('Personne', 'Personne')])
        rset = self.qexecute('Personne X WHERE X nom "bidule" or X nom "tutu"')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne',), ('Personne',)])

    def test_insert_3(self):
        self.qexecute("INSERT Personne X: X nom Y WHERE U login 'admin', U login Y")
        rset = self.qexecute('Personne X WHERE X nom "admin"')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne',)])

    def test_insert_4(self):
        self.qexecute("INSERT Societe Y: Y nom 'toto'")
        self.qexecute("INSERT Personne X: X nom 'bidule', X travaille Y WHERE Y nom 'toto'")
        rset = self.qexecute('Any X, Y WHERE X nom "bidule", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne', 'Societe',)])

    def test_insert_4bis(self):
        peid = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        seid = self.qexecute("INSERT Societe Y: Y nom 'toto', X travaille Y WHERE X eid %(x)s",
                             {'x': str(peid)})[0][0]
        self.assertEqual(len(self.qexecute('Any X, Y WHERE X travaille Y')), 1)
        self.qexecute("INSERT Personne X: X nom 'chouette', X travaille Y WHERE Y eid %(x)s",
                      {'x': str(seid)})
        self.assertEqual(len(self.qexecute('Any X, Y WHERE X travaille Y')), 2)

    def test_insert_4ter(self):
        peid = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        seid = self.qexecute("INSERT Societe Y: Y nom 'toto', X travaille Y WHERE X eid %(x)s",
                             {'x': unicode(peid)})[0][0]
        self.assertEqual(len(self.qexecute('Any X, Y WHERE X travaille Y')), 1)
        self.qexecute("INSERT Personne X: X nom 'chouette', X travaille Y WHERE Y eid %(x)s",
                      {'x': unicode(seid)})
        self.assertEqual(len(self.qexecute('Any X, Y WHERE X travaille Y')), 2)

    def test_insert_5(self):
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Societe Y: Y nom 'toto', X travaille Y WHERE X nom 'bidule'")
        rset = self.qexecute('Any X, Y WHERE X nom "bidule", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne', 'Societe',)])

    def test_insert_5bis(self):
        peid = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        self.qexecute("INSERT Societe Y: Y nom 'toto', X travaille Y WHERE X eid %(x)s",
                     {'x': peid})
        rset = self.qexecute('Any X, Y WHERE X nom "bidule", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne', 'Societe',)])

    def test_insert_6(self):
        self.qexecute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto', X travaille Y")
        rset = self.qexecute('Any X, Y WHERE X nom "bidule", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne', 'Societe',)])

    def test_insert_7(self):
        self.qexecute("INSERT Personne X, Societe Y: X nom N, Y nom 'toto', "
                      "X travaille Y WHERE U login 'admin', U login N")
        rset = self.qexecute('Any X, Y WHERE X nom "admin", Y nom "toto", X travaille Y')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne', 'Societe',)])

    def test_insert_7_2(self):
        self.qexecute("INSERT Personne X, Societe Y: X nom N, Y nom 'toto', "
                      "X travaille Y WHERE U login N")
        rset = self.qexecute('Any X, Y WHERE Y nom "toto", X travaille Y')
        self.assertEqual(len(rset), 2)
        self.assertEqual(rset.description, [('Personne', 'Societe',),
                                             ('Personne', 'Societe',)])

    def test_insert_8(self):
        self.qexecute("INSERT Societe Y, Personne X: Y nom N, X nom 'toto', X travaille Y "
                      "WHERE U login 'admin', U login N")
        rset = self.qexecute('Any X, Y WHERE X nom "toto", Y nom "admin", X travaille Y')
        self.assert_(rset.rows)
        self.assertEqual(rset.description, [('Personne', 'Societe',)])

    def test_insert_9(self):
        self.qexecute("INSERT Societe X: X nom  'Lo'")
        self.qexecute("INSERT Societe X: X nom  'Gi'")
        self.qexecute("INSERT SubDivision X: X nom  'Lab'")
        rset = self.qexecute("INSERT Personne X: X nom N, X travaille Y, X travaille_subdivision Z "
                             "WHERE Y is Societe, Z is SubDivision, Y nom N")
        self.assertEqual(len(rset), 2)
        self.assertEqual(rset.description, [('Personne',), ('Personne',)])
        # self.assertSetEqual(set(x.nom for x in rset.entities()),
        #                      ['Lo', 'Gi'])
        # self.assertSetEqual(set(y.nom for x in rset.entities() for y in x.travaille),
        #                      ['Lo', 'Gi'])
        # self.assertEqual([y.nom for x in rset.entities() for y in x.travaille_subdivision],
        #                      ['Lab', 'Lab'])

    def test_insert_query_error(self):
        self.assertRaises(Exception,
                          self.qexecute,
                          "INSERT Personne X: X nom 'toto', X is Personne")
        self.assertRaises(Exception,
                          self.qexecute,
                          "INSERT Personne X: X nom 'toto', X is_instance_of Personne")
        self.assertRaises(QueryError,
                          self.qexecute,
                          "INSERT Personne X: X nom 'toto', X has_text 'tutu'")

        self.assertRaises(QueryError,
                          self.qexecute,
                          "INSERT CWUser X: X login 'toto', X eid %s" % cnx.user(self.session).eid)

    def test_insertion_description_with_where(self):
        rset = self.qexecute('INSERT CWUser E, EmailAddress EM: E login "X", E upassword "X", '
                            'E primary_email EM, EM address "X", E in_group G '
                            'WHERE G name "managers"')
        self.assertEqual(list(rset.description[0]), ['CWUser', 'EmailAddress'])

    # deletion queries tests ##################################################

    def test_delete_1(self):
        self.qexecute("INSERT Personne Y: Y nom 'toto'")
        rset = self.qexecute('Personne X WHERE X nom "toto"')
        self.assertEqual(len(rset.rows), 1)
        drset = self.qexecute("DELETE Personne Y WHERE Y nom 'toto'")
        self.assertEqual(drset.rows, rset.rows)
        rset = self.qexecute('Personne X WHERE X nom "toto"')
        self.assertEqual(len(rset.rows), 0)

    def test_delete_2(self):
        rset = self.qexecute("INSERT Personne X, Personne Y, Societe Z : "
                             "X nom 'syt', Y nom 'adim', Z nom 'Logilab', X travaille Z, Y travaille Z")
        self.assertEqual(len(rset), 1)
        self.assertEqual(len(rset[0]), 3)
        self.assertEqual(rset.description[0], ('Personne', 'Personne', 'Societe'))
        self.assertEqual(self.qexecute('Any N WHERE X nom N, X eid %s'% rset[0][0])[0][0], 'syt')
        rset = self.qexecute('Personne X WHERE X travaille Y, Y nom "Logilab"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        self.qexecute("DELETE X travaille Y WHERE X is Personne, Y nom 'Logilabo'")
        rset = self.qexecute('Personne X WHERE X travaille Y, Y nom "Logilab"')
        self.assertEqual(len(rset.rows), 2, rset.rows)
        self.qexecute("DELETE X travaille Y WHERE X is Personne, Y nom 'Logilab'")
        rset = self.qexecute('Personne X WHERE X travaille Y, Y nom "Logilab"')
        self.assertEqual(len(rset.rows), 0, rset.rows)

    def test_delete_3(self):
        s = self.user_groups_session('users')
        with s.new_cnx() as cnx:
            with cnx.ensure_cnx_set:
                peid, = self.o.execute(cnx, "INSERT Personne P: P nom 'toto'")[0]
                seid, = self.o.execute(cnx, "INSERT Societe S: S nom 'logilab'")[0]
                self.o.execute(cnx, "SET P travaille S")
                cnx.commit()
        rset = self.qexecute('Personne P WHERE P travaille S')
        self.assertEqual(len(rset.rows), 1)
        self.qexecute("DELETE X travaille Y WHERE X eid %s, Y eid %s" % (peid, seid))
        rset = self.qexecute('Personne P WHERE P travaille S')
        self.assertEqual(len(rset.rows), 0)

    def test_delete_symmetric(self):
        teid1 = self.qexecute("INSERT Folder T: T name 'toto'")[0][0]
        teid2 = self.qexecute("INSERT Folder T: T name 'tutu'")[0][0]
        self.qexecute('SET X see_also Y WHERE X eid %s, Y eid %s' % (teid1, teid2))
        rset = self.qexecute('Any X,Y WHERE X see_also Y')
        self.assertEqual(len(rset) , 2, rset.rows)
        self.qexecute('DELETE X see_also Y WHERE X eid %s, Y eid %s' % (teid1, teid2))
        rset = self.qexecute('Any X,Y WHERE X see_also Y')
        self.assertEqual(len(rset) , 0)
        self.qexecute('SET X see_also Y WHERE X eid %s, Y eid %s' % (teid1, teid2))
        rset = self.qexecute('Any X,Y WHERE X see_also Y')
        self.assertEqual(len(rset) , 2)
        self.qexecute('DELETE X see_also Y WHERE X eid %s, Y eid %s' % (teid2, teid1))
        rset = self.qexecute('Any X,Y WHERE X see_also Y')
        self.assertEqual(len(rset) , 0)

    def test_nonregr_delete_cache(self):
        """test that relations are properly cleaned when an entity is deleted
        (using cachekey on sql generation returned always the same query for an eid,
        whatever the relation)
        """
        aeid, = self.qexecute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')[0]
        # XXX would be nice if the rql below was enough...
        #'INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y'
        eeid, = self.qexecute('INSERT Email X: X messageid "<1234>", X subject "test", '
                              'X sender Y, X recipients Y WHERE Y is EmailAddress')[0]
        self.qexecute("DELETE Email X")
        with self.session.new_cnx() as cnx:
            with cnx.ensure_cnx_set:
                sqlc = cnx.cnxset.cu
                sqlc.execute('SELECT * FROM recipients_relation')
                self.assertEqual(len(sqlc.fetchall()), 0)
                sqlc.execute('SELECT * FROM owned_by_relation WHERE eid_from=%s'%eeid)
                self.assertEqual(len(sqlc.fetchall()), 0)

    def test_nonregr_delete_cache2(self):
        eid = self.qexecute("INSERT Folder T: T name 'toto'")[0][0]
        # fill the cache
        self.qexecute("Any X WHERE X eid %(x)s", {'x': eid})
        self.qexecute("Any X WHERE X eid %s" % eid)
        self.qexecute("Folder X WHERE X eid %(x)s", {'x': eid})
        self.qexecute("Folder X WHERE X eid %s" % eid)
        self.qexecute("DELETE Folder T WHERE T eid %s" % eid)
        rset = self.qexecute("Any X WHERE X eid %(x)s", {'x': eid})
        self.assertEqual(rset.rows, [])
        rset = self.qexecute("Any X WHERE X eid %s" % eid)
        self.assertEqual(rset.rows, [])
        rset = self.qexecute("Folder X WHERE X eid %(x)s", {'x': eid})
        self.assertEqual(rset.rows, [])
        rset = self.qexecute("Folder X WHERE X eid %s" %eid)
        self.assertEqual(rset.rows, [])

    # update queries tests ####################################################

    def test_update_1(self):
        peid = self.qexecute("INSERT Personne Y: Y nom 'toto'")[0][0]
        rset = self.qexecute('Personne X WHERE X nom "toto"')
        self.assertEqual(len(rset.rows), 1)
        rset = self.qexecute("SET X nom 'tutu', X prenom 'original' WHERE X is Personne, X nom 'toto'")
        self.assertEqual(tuplify(rset.rows), [(peid, 'tutu', 'original')])
        rset = self.qexecute('Any Y, Z WHERE X is Personne, X nom Y, X prenom Z')
        self.assertEqual(tuplify(rset.rows), [('tutu', 'original')])

    def test_update_2(self):
        peid, seid = self.qexecute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto'")[0]
        rset = self.qexecute("SET X travaille Y WHERE X nom 'bidule', Y nom 'toto'")
        self.assertEqual(tuplify(rset.rows), [(peid, seid)])
        rset = self.qexecute('Any X, Y WHERE X travaille Y')
        self.assertEqual(len(rset.rows), 1)

    def test_update_2bis(self):
        rset = self.qexecute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto'")
        eid1, eid2 = rset[0][0], rset[0][1]
        self.qexecute("SET X travaille Y WHERE X eid %(x)s, Y eid %(y)s",
                      {'x': str(eid1), 'y': str(eid2)})
        rset = self.qexecute('Any X, Y WHERE X travaille Y')
        self.assertEqual(len(rset.rows), 1)
        # test add of an existant relation but with NOT X rel Y protection
        self.assertFalse(self.qexecute("SET X travaille Y WHERE X eid %(x)s, Y eid %(y)s,"
                                 "NOT X travaille Y",
                                 {'x': str(eid1), 'y': str(eid2)}))

    def test_update_2ter(self):
        rset = self.qexecute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto'")
        eid1, eid2 = rset[0][0], rset[0][1]
        self.qexecute("SET X travaille Y WHERE X eid %(x)s, Y eid %(y)s",
                      {'x': unicode(eid1), 'y': unicode(eid2)})
        rset = self.qexecute('Any X, Y WHERE X travaille Y')
        self.assertEqual(len(rset.rows), 1)

    def test_update_multiple1(self):
        peid1 = self.qexecute("INSERT Personne Y: Y nom 'tutu'")[0][0]
        peid2 = self.qexecute("INSERT Personne Y: Y nom 'toto'")[0][0]
        self.qexecute("SET X nom 'tutu', Y nom 'toto' WHERE X nom 'toto', Y nom 'tutu'")
        self.assertEqual(self.qexecute('Any X WHERE X nom "toto"').rows, [[peid1]])
        self.assertEqual(self.qexecute('Any X WHERE X nom "tutu"').rows, [[peid2]])

    def test_update_multiple2(self):
        with self.session.new_cnx() as cnx:
            ueid = cnx.execute("INSERT CWUser X: X login 'bob', X upassword 'toto'")[0][0]
            peid1 = cnx.execute("INSERT Personne Y: Y nom 'turlu'")[0][0]
            peid2 = cnx.execute("INSERT Personne Y: Y nom 'tutu'")[0][0]
            cnx.execute('SET P1 owned_by U, P2 owned_by U '
                        'WHERE P1 eid %s, P2 eid %s, U eid %s' % (peid1, peid2, ueid))
            self.assertTrue(cnx.execute('Any X WHERE X eid %s, X owned_by U, U eid %s'
                                          % (peid1, ueid)))
            self.assertTrue(cnx.execute('Any X WHERE X eid %s, X owned_by U, U eid %s'
                                          % (peid2, ueid)))

    def test_update_math_expr(self):
        orders = [r[0] for r in self.qexecute('Any O ORDERBY O WHERE ST name "Personne", '
                                              'X from_entity ST, X ordernum O')]
        for i,v in enumerate(orders):
            if v != orders[0]:
                splitidx = i
                break
        self.qexecute('SET X ordernum Y+1 WHERE X from_entity SE, SE name "Personne", '
                      'X ordernum Y, X ordernum >= %(order)s',
                     {'order': orders[splitidx]})
        orders2 = [r[0] for r in self.qexecute('Any O ORDERBY O WHERE ST name "Personne", '
                                               'X from_entity ST, X ordernum O')]
        orders = orders[:splitidx] + [o+1 for o in orders[splitidx:]]
        self.assertEqual(orders2, orders)

    def test_update_string_concat(self):
        beid = self.qexecute("INSERT Bookmark Y: Y title 'toto', Y path '/view'")[0][0]
        self.qexecute('SET X title XN + %(suffix)s WHERE X is Bookmark, X title XN',
                      {'suffix': u'-moved'})
        newname = self.qexecute('Any XN WHERE X eid %(x)s, X title XN', {'x': beid})[0][0]
        self.assertEqual(newname, 'toto-moved')

    def test_update_not_exists(self):
        rset = self.qexecute("INSERT Personne X, Societe Y: X nom 'bidule', Y nom 'toto'")
        eid1, eid2 = rset[0][0], rset[0][1]
        rset = self.qexecute("SET X travaille Y WHERE X eid %(x)s, Y eid %(y)s, "
                            "NOT EXISTS(Z ecrit_par X)",
                            {'x': unicode(eid1), 'y': unicode(eid2)})
        self.assertEqual(tuplify(rset.rows), [(eid1, eid2)])

    def test_update_query_error(self):
        self.qexecute("INSERT Personne Y: Y nom 'toto'")
        self.assertRaises(Exception, self.qexecute, "SET X nom 'toto', X is Personne")
        self.assertRaises(QueryError, self.qexecute, "SET X nom 'toto', X has_text 'tutu' "
                          "WHERE X is Personne")
        self.assertRaises(QueryError,
                          self.qexecute,
                          "SET X login 'tutu', X eid %s" % cnx.user(self.session).eid)


    # HAVING on write queries test #############################################

    def test_update_having(self):
        peid1 = self.qexecute("INSERT Personne Y: Y nom 'hop', Y tel 1")[0][0]
        peid2 = self.qexecute("INSERT Personne Y: Y nom 'hop', Y tel 2")[0][0]
        rset = self.qexecute("SET X tel 3 WHERE X tel TEL HAVING TEL&1=1")
        self.assertEqual(tuplify(rset.rows), [(peid1, 3)])

    def test_insert_having(self):
        self.skipTest('unsupported yet')
        self.qexecute("INSERT Personne Y: Y nom 'hop', Y tel 1")[0][0]
        self.assertFalse(self.qexecute("INSERT Personne Y: Y nom 'hop', Y tel 2 "
                                       "WHERE X tel XT HAVING XT&2=2"))
        self.assertTrue(self.qexecute("INSERT Personne Y: Y nom 'hop', Y tel 2 "
                                      "WHERE X tel XT HAVING XT&1=1"))

    def test_delete_having(self):
        self.qexecute("INSERT Personne Y: Y nom 'hop', Y tel 1")[0][0]
        self.assertFalse(self.qexecute("DELETE Personne Y WHERE X tel XT HAVING XT&2=2"))
        self.assertTrue(self.qexecute("DELETE Personne Y WHERE X tel XT HAVING XT&1=1"))

    # upassword encryption tests #################################################

    def test_insert_upassword(self):
        rset = self.qexecute("INSERT CWUser X: X login 'bob', X upassword 'toto', "
                             "X in_group G WHERE G name 'users'")
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(rset.description, [('CWUser',)])
        self.assertRaises(Unauthorized,
                          self.qexecute, "Any P WHERE X is CWUser, X login 'bob', X upassword P")
        with self.session.new_cnx() as cnx:
            with cnx.ensure_cnx_set:
                cursor = cnx.cnxset.cu
                cursor.execute("SELECT %supassword from %sCWUser WHERE %slogin='bob'"
                               % (SQL_PREFIX, SQL_PREFIX, SQL_PREFIX))
                passwd = str(cursor.fetchone()[0])
                self.assertEqual(passwd, crypt_password('toto', passwd))
        rset = self.qexecute("Any X WHERE X is CWUser, X login 'bob', X upassword %(pwd)s",
                            {'pwd': Binary(passwd)})
        self.assertEqual(len(rset.rows), 1)
        self.assertEqual(rset.description, [('CWUser',)])

    def test_update_upassword(self):
        with self.session.new_cnx() as cnx:
            with cnx.ensure_cnx_set:
                rset = cnx.execute("INSERT CWUser X: X login 'bob', X upassword %(pwd)s",
                                   {'pwd': 'toto'})
                self.assertEqual(rset.description[0][0], 'CWUser')
                rset = cnx.execute("SET X upassword %(pwd)s WHERE X is CWUser, X login 'bob'",
                                   {'pwd': 'tutu'})
                cursor = cnx.cnxset.cu
                cursor.execute("SELECT %supassword from %sCWUser WHERE %slogin='bob'"
                               % (SQL_PREFIX, SQL_PREFIX, SQL_PREFIX))
                passwd = str(cursor.fetchone()[0])
                self.assertEqual(passwd, crypt_password('tutu', passwd))
                rset = cnx.execute("Any X WHERE X is CWUser, X login 'bob', X upassword %(pwd)s",
                                   {'pwd': Binary(passwd)})
                self.assertEqual(len(rset.rows), 1)
                self.assertEqual(rset.description, [('CWUser',)])

    # ZT datetime tests ########################################################

    def test_tz_datetime(self):
        self.qexecute("INSERT Personne X: X nom 'bob', X tzdatenaiss %(date)s",
                     {'date': datetime(1977, 6, 7, 2, 0, tzinfo=FixedOffset(1))})
        datenaiss = self.qexecute("Any XD WHERE X nom 'bob', X tzdatenaiss XD")[0][0]
        self.assertEqual(datenaiss.tzinfo, None)
        self.assertEqual(datenaiss.utctimetuple()[:5], (1977, 6, 7, 1, 0))

    # non regression tests #####################################################

    def test_nonregr_1(self):
        teid = self.qexecute("INSERT Tag X: X name 'tag'")[0][0]
        self.qexecute("SET X tags Y WHERE X name 'tag', Y is State, Y name 'activated'")
        rset = self.qexecute('Any X WHERE T tags X')
        self.assertEqual(len(rset.rows), 1, rset.rows)
        rset = self.qexecute('Any T WHERE T tags X, X is State')
        self.assertEqual(rset.rows, [[teid]])
        rset = self.qexecute('Any T WHERE T tags X')
        self.assertEqual(rset.rows, [[teid]])

    def test_nonregr_2(self):
        teid = self.qexecute("INSERT Tag X: X name 'tag'")[0][0]
        geid = self.qexecute("CWGroup G WHERE G name 'users'")[0][0]
        self.qexecute("SET X tags Y WHERE X eid %(t)s, Y eid %(g)s",
                       {'g': geid, 't': teid})
        rset = self.qexecute('Any X WHERE E eid %(x)s, E tags X',
                              {'x': teid})
        self.assertEqual(rset.rows, [[geid]])

    def test_nonregr_3(self):
        """bad sql generated on the second query (destination_state is not
        detected as an inlined relation)
        """
        rset = self.qexecute('Any S,ES,T WHERE S state_of WF, WF workflow_of ET, ET name "CWUser",'
                             'ES allowed_transition T, T destination_state S')
        self.assertEqual(len(rset.rows), 2)

    def test_nonregr_4(self):
        # fix variables'type, else we get (nb of entity types with a 'name' attribute)**3
        # union queries and that make for instance a 266Ko sql query which is refused
        # by the server (or client lib)
        rset = self.qexecute('Any ER,SE,OE WHERE SE name "Comment", ER name "comments", OE name "Comment",'
                            'ER is CWRType, SE is CWEType, OE is CWEType')
        self.assertEqual(len(rset), 1)

    def test_nonregr_5(self):
        # jpl #15505: equivalent queries returning different result sets
        teid1 = self.qexecute("INSERT Folder X: X name 'hop'")[0][0]
        teid2 = self.qexecute("INSERT Folder X: X name 'hip'")[0][0]
        neid = self.qexecute("INSERT Note X: X todo_by U, X filed_under T "
                             "WHERE U login 'admin', T name 'hop'")[0][0]
        weid = self.qexecute("INSERT Affaire X: X concerne N, X filed_under T "
                             "WHERE N is Note, T name 'hip'")[0][0]
        rset1 = self.qexecute('Any N,U WHERE N filed_under T, T eid %s,'
                             'N todo_by U, W concerne N,'
                             'W is Affaire, W filed_under A, A eid %s' % (teid1, teid2))
        rset2 = self.qexecute('Any N,U WHERE N filed_under T, T eid %s,'
                             'N todo_by U, W concerne N,'
                             'W filed_under A, A eid %s' % (teid1, teid2))
        rset3 = self.qexecute('Any N,U WHERE N todo_by U, T eid %s,'
                             'N filed_under T, W concerne N,'
                             'W is Affaire, W filed_under A, A eid %s' % (teid1, teid2))
        rset4 = self.qexecute('Any N,U WHERE N todo_by U, T eid %s,'
                             'N filed_under T, W concerne N,'
                             'W filed_under A, A eid %s' % (teid1, teid2))
        self.assertEqual(rset1.rows, rset2.rows)
        self.assertEqual(rset1.rows, rset3.rows)
        self.assertEqual(rset1.rows, rset4.rows)

    def test_nonregr_6(self):
        self.qexecute('Any N,COUNT(S) GROUPBY N ORDERBY COUNT(N) WHERE S name N, S is State')

    def test_sqlite_encoding(self):
        """XXX this test was trying to show a bug on use of lower which only
        occurs with non ascii string and misconfigured locale
        """
        self.qexecute("INSERT Tag X: X name %(name)s,"
                       "X modification_date %(modification_date)s,"
                       "X creation_date %(creation_date)s",
                       {'name': u'éname0',
                        'modification_date': '2003/03/12 11:00',
                        'creation_date': '2000/07/03 11:00'})
        rset = self.qexecute('Any lower(N) ORDERBY LOWER(N) WHERE X is Tag, X name N,'
                            'X owned_by U, U eid %(x)s',
                            {'x':self.session.user.eid})
        self.assertEqual(rset.rows, [[u'\xe9name0']])


    def test_nonregr_description(self):
        """check that a correct description is built in case where infered
        solutions may be "fusionned" into one by the querier while all solutions
        are needed to build the result's description
        """
        self.qexecute("INSERT Personne X: X nom 'bidule'")
        self.qexecute("INSERT Societe Y: Y nom 'toto'")
        beid = self.qexecute("INSERT Basket B: B name 'mybasket'")[0][0]
        self.qexecute("SET X in_basket B WHERE X is Personne")
        self.qexecute("SET X in_basket B WHERE X is Societe")
        rset = self.qexecute('Any X WHERE X in_basket B, B eid %s' % beid)
        self.assertEqual(len(rset), 2)
        self.assertEqual(rset.description, [('Personne',), ('Societe',)])


    def test_nonregr_cache_1(self):
        peid = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        beid = self.qexecute("INSERT Basket X: X name 'tag'")[0][0]
        self.qexecute("SET X in_basket Y WHERE X is Personne, Y eid %(y)s",
                       {'y': beid})
        rset = self.qexecute("Any X WHERE X in_basket B, B eid %(x)s",
                       {'x': beid})
        self.assertEqual(rset.rows, [[peid]])
        rset = self.qexecute("Any X WHERE X in_basket B, B eid %(x)s",
                       {'x': beid})
        self.assertEqual(rset.rows, [[peid]])

    def test_nonregr_has_text_cache(self):
        eid1 = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        eid2 = self.qexecute("INSERT Personne X: X nom 'tag'")[0][0]
        rset = self.qexecute("Any X WHERE X has_text %(text)s", {'text': 'bidule'})
        self.assertEqual(rset.rows, [[eid1]])
        rset = self.qexecute("Any X WHERE X has_text %(text)s", {'text': 'tag'})
        self.assertEqual(rset.rows, [[eid2]])

    def test_nonregr_sortterm_management(self):
        """Error: Variable has no attribute 'sql' in rql2sql.py (visit_variable)

        cause: old variable ref inserted into a fresh rqlst copy
        (in RQLSpliter._complex_select_plan)

        need sqlite including http://www.sqlite.org/cvstrac/tktview?tn=3773 fix
        """
        self.qexecute('Any X ORDERBY D DESC WHERE X creation_date D')

    def test_nonregr_extra_joins(self):
        ueid = self.session.user.eid
        teid1 = self.qexecute("INSERT Folder X: X name 'folder1'")[0][0]
        teid2 = self.qexecute("INSERT Folder X: X name 'folder2'")[0][0]
        neid1 = self.qexecute("INSERT Note X: X para 'note1'")[0][0]
        neid2 = self.qexecute("INSERT Note X: X para 'note2'")[0][0]
        self.qexecute("SET X filed_under Y WHERE X eid %s, Y eid %s"
                       % (neid1, teid1))
        self.qexecute("SET X filed_under Y WHERE X eid %s, Y eid %s"
                       % (neid2, teid2))
        self.qexecute("SET X todo_by Y WHERE X is Note, Y eid %s" % ueid)
        rset = self.qexecute('Any N WHERE N todo_by U, N is Note, U eid %s, N filed_under T, T eid %s'
                             % (ueid, teid1))
        self.assertEqual(len(rset), 1)

    def test_nonregr_XXX(self):
        teid = self.qexecute('Transition S WHERE S name "deactivate"')[0][0]
        rset = self.qexecute('Any O WHERE O is State, '
                             'S eid %(x)s, S transition_of ET, O state_of ET', {'x': teid})
        self.assertEqual(len(rset), 2)
        rset = self.qexecute('Any O WHERE O is State, NOT S destination_state O, '
                             'S eid %(x)s, S transition_of ET, O state_of ET', {'x': teid})
        self.assertEqual(len(rset), 1)


    def test_nonregr_set_datetime(self):
        # huum, psycopg specific
        self.qexecute('SET X creation_date %(date)s WHERE X eid 1', {'date': date.today()})

    def test_nonregr_u_owned_by_u(self):
        ueid = self.qexecute("INSERT CWUser X: X login 'bob', X upassword 'toto', X in_group G "
                             "WHERE G name 'users'")[0][0]
        rset = self.qexecute("CWUser U")
        self.assertEqual(len(rset), 3) # bob + admin + anon
        rset = self.qexecute("Any U WHERE NOT U owned_by U")
        # even admin created at repo initialization time should belong to itself
        self.assertEqual(len(rset), 0)

    def test_nonreg_update_index(self):
        # this is the kind of queries generated by "cubicweb-ctl db-check -ry"
        self.qexecute("SET X description D WHERE X is State, X description D")

    def test_nonregr_is(self):
        uteid = self.qexecute('Any ET WHERE ET name "CWUser"')[0][0]
        self.qexecute('Any X, ET WHERE X is ET, ET eid %s' % uteid)

    def test_nonregr_orderby(self):
        seid = self.qexecute('Any X WHERE X name "activated"')[0][0]
        self.qexecute('Any X,S, MAX(T) GROUPBY X,S ORDERBY S '
                      'WHERE X is CWUser, T tags X, S eid IN(%s), X in_state S' % seid)

    def test_nonregr_solution_cache(self):
        self.skipTest('XXX should be fixed or documented') # (doesn't occur if cache key is provided.)
        rset = self.qexecute('Any X WHERE X is CWUser, X eid %(x)s', {'x':self.ueid})
        self.assertEqual(len(rset), 1)
        rset = self.qexecute('Any X WHERE X is CWUser, X eid %(x)s', {'x':12345})
        self.assertEqual(len(rset), 0)

    def test_nonregr_final_norestr(self):
        self.assertRaises(BadRQLQuery, self.qexecute, 'Date X')

    def test_nonregr_eid_cmp(self):
        peid1 = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        peid2 = self.qexecute("INSERT Personne X: X nom 'bidule'")[0][0]
        rset = self.qexecute('Any X,Y WHERE X is Personne, Y is Personne, '
                             'X nom XD, Y nom XD, X eid Z, Y eid > Z')
        self.assertEqual(rset.rows, [[peid1, peid2]])
        rset = self.qexecute('Any X,Y WHERE X nom XD, Y nom XD, X eid Z, Y eid > Z')
        self.assertEqual(rset.rows, [[peid1, peid2]])

    def test_nonregr_has_text_ambiguity_1(self):
        peid = self.qexecute("INSERT CWUser X: X login 'bidule', X upassword 'bidule', "
                             "X in_group G WHERE G name 'users'")[0][0]
        aeid = self.qexecute("INSERT Affaire X: X ref 'bidule'")[0][0]
        rset = self.qexecute('Any X WHERE X is CWUser, X has_text "bidule"')
        self.assertEqual(rset.rows, [[peid]])
        rset = self.qexecute('Any X WHERE X is CWUser, X has_text "bidule", '
                             'X in_state S, S name SN')
        self.assertEqual(rset.rows, [[peid]])


    def test_nonregr_sql_cache(self):
        # different SQL generated when 'name' is None or not (IS NULL).
        self.assertFalse(self.qexecute('Any X WHERE X is CWEType, X name %(name)s',
                                       {'name': None}))
        self.assertTrue(self.qexecute('Any X WHERE X is CWEType, X name %(name)s',
                                      {'name': 'CWEType'}))


class NonRegressionTC(CubicWebTC):

    def test_has_text_security_cache_bug(self):
        with self.admin_access.repo_cnx() as cnx:
            self.create_user(cnx, 'user', ('users',))
            aff1 = cnx.create_entity('Societe', nom=u'aff1')
            aff2 = cnx.create_entity('Societe', nom=u'aff2')
            cnx.commit()
        with self.new_access('user').repo_cnx() as cnx:
            res = cnx.execute('Any X WHERE X has_text %(text)s', {'text': 'aff1'})
            self.assertEqual(res.rows, [[aff1.eid]])
            res = cnx.execute('Any X WHERE X has_text %(text)s', {'text': 'aff2'})
            self.assertEqual(res.rows, [[aff2.eid]])

    def test_set_relations_eid(self):
        with self.admin_access.repo_cnx() as cnx:
            # create 3 email addresses
            a1 = cnx.create_entity('EmailAddress', address=u'a1')
            a2 = cnx.create_entity('EmailAddress', address=u'a2')
            a3 = cnx.create_entity('EmailAddress', address=u'a3')
            # SET relations using '>=' operator on eids
            cnx.execute('SET U use_email A WHERE U login "admin", A eid >= %s' % a2.eid)
            self.assertEqual(
                [[a2.eid], [a3.eid]],
                cnx.execute('Any A ORDERBY A WHERE U use_email A, U login "admin"').rows)
            # DELETE
            cnx.execute('DELETE U use_email A WHERE U login "admin", A eid > %s' % a2.eid)
            self.assertEqual(
                [[a2.eid]],
                cnx.execute('Any A ORDERBY A WHERE U use_email A, U login "admin"').rows)
            cnx.execute('DELETE U use_email A WHERE U login "admin"')
            # SET relations using '<' operator on eids
            cnx.execute('SET U use_email A WHERE U login "admin", A eid < %s' % a2.eid)
            self.assertEqual(
                [[a1.eid]],
                cnx.execute('Any A ORDERBY A WHERE U use_email A, U login "admin"').rows)

if __name__ == '__main__':
    unittest_main()
