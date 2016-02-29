# coding: utf-8
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
"""unit tests for module cubicweb.utils"""

from six import string_types
from six.moves import cPickle as pickle
from six.moves.urllib.parse import urlsplit

from rql import parse

from logilab.common.testlib import TestCase, unittest_main, mock_object

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.rset import NotAnEntity, ResultSet, attr_desc_iterator
from cubicweb import NoResultError, MultipleResultsError


def pprelcachedict(d):
    res = {}
    for k, (rset, related) in d.items():
        res[k] = sorted(v.eid for v in related)
    return sorted(res.items())


class AttrDescIteratorTC(TestCase):
    """TestCase for cubicweb.rset.attr_desc_iterator"""

    def test_relations_description(self):
        """tests relations_description() function"""
        queries = {
            'Any U,L,M where U is CWUser, U login L, U mail M' : [(1, 'login', 'subject'), (2, 'mail', 'subject')],
            'Any U,L,M where U is CWUser, L is Foo, U mail M' : [(2, 'mail', 'subject')],
            'Any C,P where C is Company, C employs P' : [(1, 'employs', 'subject')],
            'Any C,P where C is Company, P employed_by P' : [],
            'Any C where C is Company, C employs P' : [],
            }
        for rql, relations in queries.items():
            result = list(attr_desc_iterator(parse(rql).children[0], 0, 0))
            self.assertEqual((rql, result), (rql, relations))

    def test_relations_description_indexed(self):
        """tests relations_description() function"""
        queries = {
            'Any C,U,P,L,M where C is Company, C employs P, U is CWUser, U login L, U mail M' :
            {0: [(2,'employs', 'subject')], 1: [(3,'login', 'subject'), (4,'mail', 'subject')]},
            }
        for rql, results in queries.items():
            for idx, relations in results.items():
                result = list(attr_desc_iterator(parse(rql).children[0], idx, idx))
                self.assertEqual(result, relations)

    def test_subquery_callfunc(self):
        rql = ('Any A,B,C,COUNT(D) GROUPBY A,B,C WITH A,B,C,D BEING '
               '(Any YEAR(CD), MONTH(CD), S, X WHERE X is CWUser, X creation_date CD, X in_state S)')
        rqlst = parse(rql)
        select, col = rqlst.locate_subquery(2, 'CWUser', None)
        result = list(attr_desc_iterator(select, col, 2))
        self.assertEqual(result, [])

    def test_subquery_callfunc_2(self):
        rql = ('Any X,S,L WHERE X in_state S WITH X, L BEING (Any X,MAX(L) GROUPBY X WHERE X is CWUser, T wf_info_for X, T creation_date L)')
        rqlst = parse(rql)
        select, col = rqlst.locate_subquery(0, 'CWUser', None)
        result = list(attr_desc_iterator(select, col, 0))
        self.assertEqual(result, [(1, 'in_state', 'subject')])


class ResultSetTC(CubicWebTC):

    def setUp(self):
        super(ResultSetTC, self).setUp()
        self.rset = ResultSet([[12, 'adim'], [13, 'syt']],
                              'Any U,L where U is CWUser, U login L',
                              description=[['CWUser', 'String'], ['Bar', 'String']])
        self.rset.req = mock_object(vreg=self.vreg)

    def compare_urls(self, url1, url2):
        info1 = urlsplit(url1)
        info2 = urlsplit(url2)
        self.assertEqual(info1[:3], info2[:3])
        if info1[3] != info2[3]:
            params1 = dict(pair.split('=') for pair in info1[3].split('&'))
            params2 = dict(pair.split('=') for pair in info1[3].split('&'))
            self.assertDictEqual(params1, params2)

    def test_pickle(self):
        del self.rset.req
        rs2 = pickle.loads(pickle.dumps(self.rset))
        self.assertEqual(self.rset.rows, rs2.rows)
        self.assertEqual(self.rset.rowcount, rs2.rowcount)
        self.assertEqual(self.rset.rql, rs2.rql)
        self.assertEqual(self.rset.description, rs2.description)

    def test_build_url(self):
        with self.admin_access.web_request() as req:
            baseurl = req.base_url()
            self.compare_urls(req.build_url('view', vid='foo', rql='yo'),
                              '%sview?vid=foo&rql=yo' % baseurl)
            self.compare_urls(req.build_url('view', _restpath='task/title/go'),
                              '%stask/title/go' % baseurl)
            #self.compare_urls(req.build_url('view', _restpath='/task/title/go'),
            #                  '%stask/title/go' % baseurl)
            # empty _restpath should not crash
            self.compare_urls(req.build_url('view', _restpath=''), baseurl)
            self.assertNotIn('https', req.build_url('view', vid='foo', rql='yo',
                                                      __secure__=True))
            try:
                self.config.global_set_option('https-url', 'https://testing.fr/')
                self.assertTrue('https', req.build_url('view', vid='foo', rql='yo',
                                                         __secure__=True))
                self.compare_urls(req.build_url('view', vid='foo', rql='yo',
                                                __secure__=True),
                                  '%sview?vid=foo&rql=yo' % req.base_url(secure=True))
            finally:
                self.config.global_set_option('https-url', None)


    def test_build(self):
        """test basic build of a ResultSet"""
        rs = ResultSet([1,2,3], 'CWGroup X', description=['CWGroup', 'CWGroup', 'CWGroup'])
        self.assertEqual(rs.rowcount, 3)
        self.assertEqual(rs.rows, [1,2,3])
        self.assertEqual(rs.description, ['CWGroup', 'CWGroup', 'CWGroup'])


    def test_limit(self):
        rs = ResultSet([[12000, 'adim'], [13000, 'syt'], [14000, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        with self.admin_access.web_request() as req:
            rs.req = req
            rs.vreg = self.vreg
            self.assertEqual(rs.limit(2).rows, [[12000, 'adim'], [13000, 'syt']])
            rs2 = rs.limit(2, offset=1)
            self.assertEqual(rs2.rows, [[13000, 'syt'], [14000, 'nico']])
            self.assertEqual(rs2.get_entity(0, 0).cw_row, 0)
            self.assertEqual(rs.limit(2, offset=2).rows, [[14000, 'nico']])
            self.assertEqual(rs.limit(2, offset=3).rows, [])

    def test_limit_2(self):
        with self.admin_access.web_request() as req:
            # drop user from cache for the sake of this test
            req.drop_entity_cache(req.user.eid)
            rs = req.execute('Any E,U WHERE E is CWEType, E created_by U')
            # get entity on row 9. This will fill its created_by relation cache,
            # with cwuser on row 9 as well
            e1 = rs.get_entity(9, 0)
            # get entity on row 10. This will fill its created_by relation cache,
            # with cwuser built on row 9
            e2 = rs.get_entity(10, 0)
            # limit result set from row 10
            rs.limit(1, 10, inplace=True)
            # get back eid
            e = rs.get_entity(0, 0)
            self.assertTrue(e2 is e)
            # rs.limit has properly removed cwuser for request cache, but it's
            # still referenced by e/e2 relation cache
            u = e.created_by[0]
            # now ensure this doesn't trigger IndexError because cwuser.cw_row is 9
            # while now rset has only one row
            u.cw_rset[u.cw_row]

    def test_filter(self):
        rs = ResultSet([[12000, 'adim'], [13000, 'syt'], [14000, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        with self.admin_access.web_request() as req:
            rs.req = req
            rs.vreg = self.vreg
            def test_filter(entity):
                return entity.login != 'nico'

            rs2 = rs.filtered_rset(test_filter)
            self.assertEqual(len(rs2), 2)
            self.assertEqual([login for _, login in rs2], ['adim', 'syt'])
            self.assertEqual(rs2.description, rs.description[1:])

    def test_transform(self):
        rs = ResultSet([[12, 'adim'], [13, 'syt'], [14, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        with self.admin_access.web_request() as req:
            rs.req = req
            def test_transform(row, desc):
                return row[1:], desc[1:]
            rs2 = rs.transformed_rset(test_transform)

            self.assertEqual(len(rs2), 3)
            self.assertEqual(list(rs2), [['adim'],['syt'],['nico']])

    def test_sort(self):
        rs = ResultSet([[12000, 'adim'], [13000, 'syt'], [14000, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        with self.admin_access.web_request() as req:
            rs.req = req
            rs.vreg = self.vreg

            rs2 = rs.sorted_rset(lambda e:e.cw_attr_cache['login'])
            self.assertEqual(len(rs2), 3)
            self.assertEqual([login for _, login in rs2], ['adim', 'nico', 'syt'])
            # make sure rs is unchanged
            self.assertEqual([login for _, login in rs], ['adim', 'syt', 'nico'])

            rs2 = rs.sorted_rset(lambda e:e.cw_attr_cache['login'], reverse=True)
            self.assertEqual(len(rs2), 3)
            self.assertEqual([login for _, login in rs2], ['syt', 'nico', 'adim'])
            # make sure rs is unchanged
            self.assertEqual([login for _, login in rs], ['adim', 'syt', 'nico'])

            rs3 = rs.sorted_rset(lambda row: row[1], col=-1)
            self.assertEqual(len(rs3), 3)
            self.assertEqual([login for _, login in rs3], ['adim', 'nico', 'syt'])
            # make sure rs is unchanged
            self.assertEqual([login for _, login in rs], ['adim', 'syt', 'nico'])

    def test_split(self):
        rs = ResultSet([[12000, 'adim', u'Adim chez les pinguins'],
                        [12000, 'adim', u'Jardiner facile'],
                        [13000, 'syt',  u'Le carrelage en 42 leçons'],
                        [14000, 'nico', u'La tarte tatin en 15 minutes'],
                        [14000, 'nico', u"L'épluchage du castor commun"]],
                       'Any U, L, T WHERE U is CWUser, U login L,'\
                       'D created_by U, D title T',
                       description=[['CWUser', 'String', 'String']] * 5)
        with self.admin_access.web_request() as req:
            rs.req = req
            rs.vreg = self.vreg
            rsets = rs.split_rset(lambda e:e.cw_attr_cache['login'])
            self.assertEqual(len(rsets), 3)
            self.assertEqual([login for _, login,_ in rsets[0]], ['adim', 'adim'])
            self.assertEqual([login for _, login,_ in rsets[1]], ['syt'])
            self.assertEqual([login for _, login,_ in rsets[2]], ['nico', 'nico'])
            # make sure rs is unchanged
            self.assertEqual([login for _, login,_ in rs], ['adim', 'adim', 'syt', 'nico', 'nico'])

            rsets = rs.split_rset(lambda e:e.cw_attr_cache['login'], return_dict=True)
            self.assertEqual(len(rsets), 3)
            self.assertEqual([login for _, login,_ in rsets['nico']], ['nico', 'nico'])
            self.assertEqual([login for _, login,_ in rsets['adim']], ['adim', 'adim'])
            self.assertEqual([login for _, login,_ in rsets['syt']], ['syt'])
            # make sure rs is unchanged
            self.assertEqual([login for _, login,_ in rs], ['adim', 'adim', 'syt', 'nico', 'nico'])

            rsets = rs.split_rset(lambda s: s.count('d'), col=2)
            self.assertEqual(len(rsets), 2)
            self.assertEqual([title for _, _, title in rsets[0]],
                              [u"Adim chez les pinguins",
                               u"Jardiner facile",
                               u"L'épluchage du castor commun",])
            self.assertEqual([title for _, _, title in rsets[1]],
                              [u"Le carrelage en 42 leçons",
                               u"La tarte tatin en 15 minutes",])
            # make sure rs is unchanged
            self.assertEqual([title for _, _, title in rs],
                              [u'Adim chez les pinguins',
                               u'Jardiner facile',
                               u'Le carrelage en 42 leçons',
                               u'La tarte tatin en 15 minutes',
                               u"L'épluchage du castor commun"])

    def test_cached_syntax_tree(self):
        """make sure syntax tree is cached"""
        rqlst1 = self.rset.syntax_tree()
        rqlst2 = self.rset.syntax_tree()
        self.assertIs(rqlst1, rqlst2)

    def test_get_entity_simple(self):
        with self.admin_access.web_request() as req:
            req.create_entity('CWUser', login=u'adim', upassword='adim',
                                         surname=u'di mascio', firstname=u'adrien')
            req.drop_entity_cache()
            e = req.execute('Any X,T WHERE X login "adim", X surname T').get_entity(0, 0)
            self.assertEqual(e.cw_attr_cache['surname'], 'di mascio')
            self.assertRaises(KeyError, e.cw_attr_cache.__getitem__, 'firstname')
            self.assertRaises(KeyError, e.cw_attr_cache.__getitem__, 'creation_date')
            self.assertEqual(pprelcachedict(e._cw_related_cache), [])
            e.complete()
            self.assertEqual(e.cw_attr_cache['firstname'], 'adrien')
            self.assertEqual(pprelcachedict(e._cw_related_cache), [])

    def test_get_entity_advanced(self):
        with self.admin_access.web_request() as req:
            req.create_entity('Bookmark', title=u'zou', path=u'/view')
            req.drop_entity_cache()
            req.execute('SET X bookmarked_by Y WHERE X is Bookmark, Y login "anon"')
            rset = req.execute('Any X,Y,XT,YN WHERE X bookmarked_by Y, X title XT, Y login YN')

            e = rset.get_entity(0, 0)
            self.assertEqual(e.cw_row, 0)
            self.assertEqual(e.cw_col, 0)
            self.assertEqual(e.cw_attr_cache['title'], 'zou')
            self.assertRaises(KeyError, e.cw_attr_cache.__getitem__, 'path')
            other_rset = req.execute('Any X, P WHERE X is Bookmark, X path P')
            # check that get_entity fetches e from the request's cache, and
            # updates it with attributes from the new rset
            self.assertIs(other_rset.get_entity(0, 0), e)
            self.assertIn('path', e.cw_attr_cache)
            self.assertEqual(e.view('text'), 'zou')
            self.assertEqual(pprelcachedict(e._cw_related_cache), [])

            e = rset.get_entity(0, 1)
            self.assertEqual(e.cw_row, 0)
            self.assertEqual(e.cw_col, 1)
            self.assertEqual(e.cw_attr_cache['login'], 'anon')
            self.assertRaises(KeyError, e.cw_attr_cache.__getitem__, 'firstname')
            self.assertEqual(pprelcachedict(e._cw_related_cache),
                              [])
            e.complete()
            self.assertEqual(e.cw_attr_cache['firstname'], None)
            self.assertEqual(e.view('text'), 'anon')
            self.assertEqual(pprelcachedict(e._cw_related_cache),
                              [])

            self.assertRaises(NotAnEntity, rset.get_entity, 0, 2)
            self.assertRaises(NotAnEntity, rset.get_entity, 0, 3)

    def test_get_entity_relation_cache_compt(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X,S WHERE X in_state S, X login "anon"')
            e = rset.get_entity(0, 0)
            seid = req.execute('State X WHERE X name "activated"')[0][0]
            # for_user / in_group are prefetched in CWUser __init__, in_state should
            # be filed from our query rset
            self.assertEqual(pprelcachedict(e._cw_related_cache),
                              [('in_state_subject', [seid])])

    def test_get_entity_advanced_prefilled_cache(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Bookmark', title=u'zou', path=u'path')
            req.cnx.commit()
            rset = req.execute('Any X,U,S,XT,UL,SN WHERE X created_by U, U in_state S, '
                                'X title XT, S name SN, U login UL, X eid %s' % e.eid)
            e = rset.get_entity(0, 0)
            self.assertEqual(e.cw_attr_cache['title'], 'zou')
            self.assertEqual(pprelcachedict(e._cw_related_cache),
                             [('created_by_subject', [req.user.eid])])
            # first level of recursion
            u = e.created_by[0]
            self.assertEqual(u.cw_attr_cache['login'], 'admin')
            self.assertRaises(KeyError, u.cw_attr_cache.__getitem__, 'firstname')
            # second level of recursion
            s = u.in_state[0]
            self.assertEqual(s.cw_attr_cache['name'], 'activated')
            self.assertRaises(KeyError, s.cw_attr_cache.__getitem__, 'description')

    def test_get_entity_recursion(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.create_entity('EmailAddress', address=u'toto',
                              reverse_primary_email=cnx.user.eid)
            cnx.commit()

        # get_entity should fill the caches for user and email, even if both
        # entities are already in the connection's entity cache
        with self.admin_access.repo_cnx() as cnx:
            mail = cnx.find('EmailAddress').one()
            rset = cnx.execute('Any X, E WHERE X primary_email E')
            u = rset.get_entity(0, 0)
            self.assertTrue(u.cw_relation_cached('primary_email', 'subject'))
            self.assertTrue(mail.cw_relation_cached('primary_email', 'object'))

        with self.admin_access.repo_cnx() as cnx:
            mail = cnx.find('EmailAddress').one()
            rset = cnx.execute('Any X, E WHERE X primary_email E')
            rset.get_entity(0, 1)
            self.assertTrue(mail.cw_relation_cached('primary_email', 'object'))
            u = cnx.user
            self.assertTrue(u.cw_relation_cached('primary_email', 'subject'))


    def test_get_entity_cache_with_left_outer_join(self):
        with self.admin_access.web_request() as req:
            eid = req.execute('INSERT CWUser E: E login "joe", E upassword "joe", E in_group G '
                               'WHERE G name "users"')[0][0]
            rset = req.execute('Any X,E WHERE X eid %(x)s, X primary_email E?', {'x': eid})
            e = rset.get_entity(0, 0)
            # if any of the assertion below fails with a KeyError, the relation is not cached
            # related entities should be an empty list
            self.assertEqual(e._cw_related_cache['primary_email_subject'][True], ())
            # related rset should be an empty rset
            cached = e._cw_related_cache['primary_email_subject'][False]
            self.assertIsInstance(cached, ResultSet)
            self.assertEqual(cached.rowcount, 0)


    def test_get_entity_union(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Bookmark', title=u'manger', path=u'path')
            req.drop_entity_cache()
            rset = req.execute('Any X,N ORDERBY N WITH X,N BEING '
                                '((Any X,N WHERE X is Bookmark, X title N)'
                                ' UNION '
                                ' (Any X,N WHERE X is CWGroup, X name N))')
            expected = (('CWGroup', 'guests'), ('CWGroup', 'managers'),
                        ('Bookmark', 'manger'), ('CWGroup', 'owners'),
                        ('CWGroup', 'users'))
            for entity in rset.entities(): # test get_entity for each row actually
                etype, n = expected[entity.cw_row]
                self.assertEqual(entity.cw_etype, etype)
                attr = etype == 'Bookmark' and 'title' or 'name'
                self.assertEqual(entity.cw_attr_cache[attr], n)

    def test_one(self):
        with self.admin_access.web_request() as req:
            req.create_entity('CWUser', login=u'cdevienne',
                                         upassword=u'cdevienne',
                                         surname=u'de Vienne',
                                         firstname=u'Christophe')
            e = req.execute('Any X WHERE X login "cdevienne"').one()

            self.assertEqual(e.surname, u'de Vienne')

            e = req.execute(
                'Any X, N WHERE X login "cdevienne", X surname N').one()
            self.assertEqual(e.surname, u'de Vienne')

            e = req.execute(
                'Any N, X WHERE X login "cdevienne", X surname N').one(col=1)
            self.assertEqual(e.surname, u'de Vienne')

    def test_one_no_rows(self):
        with self.admin_access.web_request() as req:
            with self.assertRaises(NoResultError):
                req.execute('Any X WHERE X login "patanok"').one()

    def test_one_multiple_rows(self):
        with self.admin_access.web_request() as req:
            req.create_entity(
                'CWUser', login=u'cdevienne', upassword=u'cdevienne',
                surname=u'de Vienne', firstname=u'Christophe')

            req.create_entity(
                'CWUser', login=u'adim', upassword='adim', surname=u'di mascio',
                firstname=u'adrien')

            with self.assertRaises(MultipleResultsError):
                req.execute('Any X WHERE X is CWUser').one()

    def test_related_entity_optional(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Bookmark', title=u'aaaa', path=u'path')
            rset = req.execute('Any B,U,L WHERE B bookmarked_by U?, U login L')
            entity, rtype = rset.related_entity(0, 2)
            self.assertEqual(entity, None)
            self.assertEqual(rtype, None)

    def test_related_entity_union_subquery_1(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Bookmark', title=u'aaaa', path=u'path')
            rset = req.execute('Any X,N ORDERBY N WITH X,N BEING '
                                '((Any X,N WHERE X is CWGroup, X name N)'
                                ' UNION '
                                ' (Any X,N WHERE X is Bookmark, X title N))')
            entity, rtype = rset.related_entity(0, 1)
            self.assertEqual(entity.eid, e.eid)
            self.assertEqual(rtype, 'title')
            self.assertEqual(entity.title, 'aaaa')
            entity, rtype = rset.related_entity(1, 1)
            self.assertEqual(entity.cw_etype, 'CWGroup')
            self.assertEqual(rtype, 'name')
            self.assertEqual(entity.name, 'guests')

    def test_related_entity_union_subquery_2(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Bookmark', title=u'aaaa', path=u'path')
            rset = req.execute('Any X,N ORDERBY N WHERE X is Bookmark WITH X,N BEING '
                                '((Any X,N WHERE X is CWGroup, X name N)'
                                ' UNION '
                                ' (Any X,N WHERE X is Bookmark, X title N))')
            entity, rtype = rset.related_entity(0, 1)
            self.assertEqual(entity.eid, e.eid)
            self.assertEqual(rtype, 'title')
            self.assertEqual(entity.title, 'aaaa')

    def test_related_entity_union_subquery_3(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Bookmark', title=u'aaaa', path=u'path')
            rset = req.execute('Any X,N ORDERBY N WITH N,X BEING '
                                '((Any N,X WHERE X is CWGroup, X name N)'
                                ' UNION '
                                ' (Any N,X WHERE X is Bookmark, X title N))')
            entity, rtype = rset.related_entity(0, 1)
            self.assertEqual(entity.eid, e.eid)
            self.assertEqual(rtype, 'title')
            self.assertEqual(entity.title, 'aaaa')

    def test_related_entity_union_subquery_4(self):
        with self.admin_access.web_request() as req:
            e = req.create_entity('Bookmark', title=u'aaaa', path=u'path')
            rset = req.execute('Any X,X, N ORDERBY N WITH X,N BEING '
                                '((Any X,N WHERE X is CWGroup, X name N)'
                                ' UNION '
                                ' (Any X,N WHERE X is Bookmark, X title N))')
            entity, rtype = rset.related_entity(0, 2)
            self.assertEqual(entity.eid, e.eid)
            self.assertEqual(rtype, 'title')
            self.assertEqual(entity.title, 'aaaa')

    def test_related_entity_trap_subquery(self):
        with self.admin_access.web_request() as req:
            req.create_entity('Bookmark', title=u'test bookmark', path=u'')
            req.execute('SET B bookmarked_by U WHERE U login "admin"')
            rset = req.execute('Any B,T,L WHERE B bookmarked_by U, U login L '
                                'WITH B,T BEING (Any B,T WHERE B is Bookmark, B title T)')
            rset.related_entity(0, 2)

    def test_related_entity_subquery_outerjoin(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X,S,L WHERE X in_state S '
                                'WITH X, L BEING (Any X,MAX(L) GROUPBY X '
                                'WHERE X is CWUser, T? wf_info_for X, T creation_date L)')
            self.assertEqual(len(rset), 2)
            rset.related_entity(0, 1)
            rset.related_entity(0, 2)

    def test_entities(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any U,G WHERE U in_group G')
            # make sure we have at least one element
            self.assertTrue(rset)
            self.assertEqual(set(e.e_schema.type for e in rset.entities(0)),
                              set(['CWUser',]))
            self.assertEqual(set(e.e_schema.type for e in rset.entities(1)),
                              set(['CWGroup',]))

    def test_iter_rows_with_entities(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any U,UN,G,GN WHERE U in_group G, U login UN, G name GN')
            # make sure we have at least one element
            self.assertTrue(rset)
            out = list(rset.iter_rows_with_entities())[0]
            self.assertEqual( out[0].login, out[1] )
            self.assertEqual( out[2].name, out[3] )

    def test_printable_rql(self):
        with self.admin_access.web_request() as req:
            rset = req.execute(u'CWEType X WHERE X final FALSE')
            self.assertEqual(rset.printable_rql(),
                              'Any X WHERE X final FALSE, X is CWEType')

    def test_searched_text(self):
        with self.admin_access.web_request() as req:
            rset = req.execute(u'Any X WHERE X has_text "foobar"')
            self.assertEqual(rset.searched_text(), 'foobar')
            rset = req.execute(u'Any X WHERE X has_text %(text)s', {'text' : 'foo'})
            self.assertEqual(rset.searched_text(), 'foo')

    def test_union_limited_rql(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('(Any X,N WHERE X is Bookmark, X title N)'
                                ' UNION '
                                '(Any X,N WHERE X is CWGroup, X name N)')
            rset.limit(2, 10, inplace=True)
            self.assertEqual(rset.limited_rql(),
                              'Any A,B LIMIT 2 OFFSET 10 '
                              'WITH A,B BEING ('
                              '(Any X,N WHERE X is Bookmark, X title N) '
                              'UNION '
                              '(Any X,N WHERE X is CWGroup, X name N)'
                              ')')

    def test_count_users_by_date(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any D, COUNT(U) GROUPBY D WHERE U is CWUser, U creation_date D')
            self.assertEqual(rset.related_entity(0,0), (None, None))

    def test_str(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('(Any X,N WHERE X is CWGroup, X name N)')
            self.assertIsInstance(str(rset), string_types)
            self.assertEqual(len(str(rset).splitlines()), 1)

    def test_repr(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('(Any X,N WHERE X is CWGroup, X name N)')
            self.assertIsInstance(repr(rset), string_types)
            self.assertTrue(len(repr(rset).splitlines()) > 1)

            rset = req.execute('(Any X WHERE X is CWGroup, X name "managers")')
            self.assertIsInstance(str(rset), string_types)
            self.assertEqual(len(str(rset).splitlines()), 1)

    def test_slice(self):
        rs = ResultSet([[12000, 'adim', u'Adim chez les pinguins'],
                        [12000, 'adim', u'Jardiner facile'],
                        [13000, 'syt',  u'Le carrelage en 42 leçons'],
                        [14000, 'nico', u'La tarte tatin en 15 minutes'],
                        [14000, 'nico', u"L'épluchage du castor commun"]],
                       'Any U, L, T WHERE U is CWUser, U login L,'\
                       'D created_by U, D title T',
                       description=[['CWUser', 'String', 'String']] * 5)
        self.assertEqual(rs[1::2],
            [[12000, 'adim', u'Jardiner facile'],
             [14000, 'nico', u'La tarte tatin en 15 minutes']])

    def test_nonregr_symmetric_relation(self):
        # see https://www.cubicweb.org/ticket/4739253
        with self.admin_access.client_cnx() as cnx:
            p1 = cnx.create_entity('Personne', nom=u'sylvain')
            cnx.create_entity('Personne', nom=u'denis', connait=p1)
            cnx.commit()
            rset = cnx.execute('Any X,Y WHERE X connait Y')
            rset.get_entity(0, 1) # used to raise KeyError

if __name__ == '__main__':
    unittest_main()
