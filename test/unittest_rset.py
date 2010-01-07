# coding: utf-8
"""unit tests for module cubicweb.common.utils

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
#from __future__ import with_statement

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.selectors import traced_selection

from urlparse import urlsplit
from rql import parse

from cubicweb.rset import NotAnEntity, ResultSet, attr_desc_iterator


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
            result = list(attr_desc_iterator(parse(rql).children[0]))
            self.assertEquals((rql, result), (rql, relations))

    def test_relations_description_indexed(self):
        """tests relations_description() function"""
        queries = {
            'Any C,U,P,L,M where C is Company, C employs P, U is CWUser, U login L, U mail M' :
            {0: [(2,'employs', 'subject')], 1: [(3,'login', 'subject'), (4,'mail', 'subject')]},
            }
        for rql, results in queries.items():
            for var_index, relations in results.items():
                result = list(attr_desc_iterator(parse(rql).children[0], var_index))
                self.assertEquals(result, relations)



class ResultSetTC(EnvBasedTC):

    def setUp(self):
        super(ResultSetTC, self).setUp()
        self.rset = ResultSet([[12, 'adim'], [13, 'syt']],
                              'Any U,L where U is CWUser, U login L',
                              description=[['CWUser', 'String'], ['Bar', 'String']])
        self.rset.vreg = self.vreg

    def compare_urls(self, url1, url2):
        info1 = urlsplit(url1)
        info2 = urlsplit(url2)
        self.assertEquals(info1[:3], info2[:3])
        if info1[3] != info2[3]:
            params1 = dict(pair.split('=') for pair in info1[3].split('&'))
            params2 = dict(pair.split('=') for pair in info1[3].split('&'))
            self.assertDictEquals(params1, params2)


    def test_build_url(self):
        req = self.request()
        baseurl = req.base_url()
        self.compare_urls(req.build_url('view', vid='foo', rql='yo'),
                          '%sview?vid=foo&rql=yo' % baseurl)
        self.compare_urls(req.build_url('view', _restpath='task/title/go'),
                          '%stask/title/go' % baseurl)
        #self.compare_urls(req.build_url('view', _restpath='/task/title/go'),
        #                  '%stask/title/go' % baseurl)
        # empty _restpath should not crash
        self.compare_urls(req.build_url('view', _restpath=''), baseurl)


    def test_resultset_build(self):
        """test basic build of a ResultSet"""
        rs = ResultSet([1,2,3], 'CWGroup X', description=['CWGroup', 'CWGroup', 'CWGroup'])
        self.assertEquals(rs.rowcount, 3)
        self.assertEquals(rs.rows, [1,2,3])
        self.assertEquals(rs.description, ['CWGroup', 'CWGroup', 'CWGroup'])


    def test_resultset_limit(self):
        rs = ResultSet([[12000, 'adim'], [13000, 'syt'], [14000, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        rs.req = self.request()
        rs.vreg = self.env.vreg

        self.assertEquals(rs.limit(2).rows, [[12000, 'adim'], [13000, 'syt']])
        rs2 = rs.limit(2, offset=1)
        self.assertEquals(rs2.rows, [[13000, 'syt'], [14000, 'nico']])
        self.assertEquals(rs2.get_entity(0, 0).row, 0)
        self.assertEquals(rs.limit(2, offset=2).rows, [[14000, 'nico']])
        self.assertEquals(rs.limit(2, offset=3).rows, [])


    def test_resultset_filter(self):
        rs = ResultSet([[12000, 'adim'], [13000, 'syt'], [14000, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        rs.req = self.request()
        rs.vreg = self.env.vreg
        def test_filter(entity):
            return entity.login != 'nico'

        rs2 = rs.filtered_rset(test_filter)
        self.assertEquals(len(rs2), 2)
        self.assertEquals([login for _, login in rs2], ['adim', 'syt'])

    def test_resultset_transform(self):
        rs = ResultSet([[12, 'adim'], [13, 'syt'], [14, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        rs.req = self.request()
        def test_transform(row, desc):
            return row[1:], desc[1:]
        rs2 = rs.transformed_rset(test_transform)

        self.assertEquals(len(rs2), 3)
        self.assertEquals(list(rs2), [['adim'],['syt'],['nico']])

    def test_resultset_sort(self):
        rs = ResultSet([[12000, 'adim'], [13000, 'syt'], [14000, 'nico']],
                       'Any U,L where U is CWUser, U login L',
                       description=[['CWUser', 'String']] * 3)
        rs.req = self.request()
        rs.vreg = self.env.vreg

        rs2 = rs.sorted_rset(lambda e:e['login'])
        self.assertEquals(len(rs2), 3)
        self.assertEquals([login for _, login in rs2], ['adim', 'nico', 'syt'])
        # make sure rs is unchanged
        self.assertEquals([login for _, login in rs], ['adim', 'syt', 'nico'])

        rs2 = rs.sorted_rset(lambda e:e['login'], reverse=True)
        self.assertEquals(len(rs2), 3)
        self.assertEquals([login for _, login in rs2], ['syt', 'nico', 'adim'])
        # make sure rs is unchanged
        self.assertEquals([login for _, login in rs], ['adim', 'syt', 'nico'])

        rs3 = rs.sorted_rset(lambda row: row[1], col=-1)
        self.assertEquals(len(rs3), 3)
        self.assertEquals([login for _, login in rs3], ['adim', 'nico', 'syt'])
        # make sure rs is unchanged
        self.assertEquals([login for _, login in rs], ['adim', 'syt', 'nico'])

    def test_resultset_split(self):
        rs = ResultSet([[12000, 'adim', u'Adim chez les pinguins'],
                        [12000, 'adim', u'Jardiner facile'],
                        [13000, 'syt',  u'Le carrelage en 42 leçons'],
                        [14000, 'nico', u'La tarte tatin en 15 minutes'],
                        [14000, 'nico', u"L'épluchage du castor commun"]],
                       'Any U, L, T WHERE U is CWUser, U login L,'\
                       'D created_by U, D title T',
                       description=[['CWUser', 'String', 'String']] * 5)
        rs.req = self.request()
        rs.vreg = self.env.vreg

        rsets = rs.split_rset(lambda e:e['login'])
        self.assertEquals(len(rsets), 3)
        self.assertEquals([login for _, login,_ in rsets[0]], ['adim', 'adim'])
        self.assertEquals([login for _, login,_ in rsets[1]], ['syt'])
        self.assertEquals([login for _, login,_ in rsets[2]], ['nico', 'nico'])
        # make sure rs is unchanged
        self.assertEquals([login for _, login,_ in rs], ['adim', 'adim', 'syt', 'nico', 'nico'])

        rsets = rs.split_rset(lambda e:e['login'], return_dict=True)
        self.assertEquals(len(rsets), 3)
        self.assertEquals([login for _, login,_ in rsets['nico']], ['nico', 'nico'])
        self.assertEquals([login for _, login,_ in rsets['adim']], ['adim', 'adim'])
        self.assertEquals([login for _, login,_ in rsets['syt']], ['syt'])
        # make sure rs is unchanged
        self.assertEquals([login for _, login,_ in rs], ['adim', 'adim', 'syt', 'nico', 'nico'])

        rsets = rs.split_rset(lambda s: s.count('d'), col=2)
        self.assertEquals(len(rsets), 2)
        self.assertEquals([title for _, _, title in rsets[0]],
                          [u"Adim chez les pinguins",
                           u"Jardiner facile",
                           u"L'épluchage du castor commun",])
        self.assertEquals([title for _, _, title in rsets[1]],
                          [u"Le carrelage en 42 leçons",
                           u"La tarte tatin en 15 minutes",])
        # make sure rs is unchanged
        self.assertEquals([title for _, _, title in rs],
                          [u'Adim chez les pinguins',
                           u'Jardiner facile',
                           u'Le carrelage en 42 leçons',
                           u'La tarte tatin en 15 minutes',
                           u"L'épluchage du castor commun"])

    def test_cached_syntax_tree(self):
        """make sure syntax tree is cached"""
        rqlst1 = self.rset.syntax_tree()
        rqlst2 = self.rset.syntax_tree()
        self.assert_(rqlst1 is rqlst2)

    def test_get_entity_simple(self):
        self.add_entity('CWUser', login=u'adim', upassword='adim',
                        surname=u'di mascio', firstname=u'adrien')
        e = self.entity('Any X,T WHERE X login "adim", X surname T')
        self.assertEquals(e['surname'], 'di mascio')
        self.assertRaises(KeyError, e.__getitem__, 'firstname')
        self.assertRaises(KeyError, e.__getitem__, 'creation_date')
        self.assertEquals(pprelcachedict(e._related_cache), [])
        e.complete()
        self.assertEquals(e['firstname'], 'adrien')
        self.assertEquals(pprelcachedict(e._related_cache), [])

    def test_get_entity_advanced(self):
        self.add_entity('Bookmark', title=u'zou', path=u'/view')
        self.execute('SET X bookmarked_by Y WHERE X is Bookmark, Y login "anon"')
        rset = self.execute('Any X,Y,XT,YN WHERE X bookmarked_by Y, X title XT, Y login YN')

        e = rset.get_entity(0, 0)
        self.assertEquals(e.row, 0)
        self.assertEquals(e.col, 0)
        self.assertEquals(e['title'], 'zou')
        self.assertRaises(KeyError, e.__getitem__, 'path')
        self.assertEquals(e.view('text'), 'zou')
        self.assertEquals(pprelcachedict(e._related_cache), [])

        e = rset.get_entity(0, 1)
        self.assertEquals(e.row, 0)
        self.assertEquals(e.col, 1)
        self.assertEquals(e['login'], 'anon')
        self.assertRaises(KeyError, e.__getitem__, 'firstname')
        self.assertEquals(pprelcachedict(e._related_cache),
                          [])
        e.complete()
        self.assertEquals(e['firstname'], None)
        self.assertEquals(e.view('text'), 'anon')
        self.assertEquals(pprelcachedict(e._related_cache),
                          [])

        self.assertRaises(NotAnEntity, rset.get_entity, 0, 2)
        self.assertRaises(NotAnEntity, rset.get_entity, 0, 3)

    def test_get_entity_relation_cache_compt(self):
        rset = self.execute('Any X,S WHERE X in_state S, X login "anon"')
        e = rset.get_entity(0, 0)
        seid = self.execute('State X WHERE X name "activated"')[0][0]
        # for_user / in_group are prefetched in CWUser __init__, in_state should
        # be filed from our query rset
        self.assertEquals(pprelcachedict(e._related_cache),
                          [('in_state_subject', [seid])])

    def test_get_entity_advanced_prefilled_cache(self):
        e = self.add_entity('Bookmark', title=u'zou', path=u'path')
        self.commit()
        rset = self.execute('Any X,U,S,XT,UL,SN WHERE X created_by U, U in_state S, '
                            'X title XT, S name SN, U login UL, X eid %s' % e.eid)
        e = rset.get_entity(0, 0)
        self.assertEquals(e['title'], 'zou')
        self.assertEquals(pprelcachedict(e._related_cache),
                          [('created_by_subject', [5])])
        # first level of recursion
        u = e.created_by[0]
        self.assertEquals(u['login'], 'admin')
        self.assertRaises(KeyError, u.__getitem__, 'firstname')
        # second level of recursion
        s = u.in_state[0]
        self.assertEquals(s['name'], 'activated')
        self.assertRaises(KeyError, s.__getitem__, 'description')


    def test_get_entity_cache_with_left_outer_join(self):
        eid = self.execute('INSERT CWUser E: E login "joe", E upassword "joe", E in_group G '
                           'WHERE G name "users"')[0][0]
        rset = self.execute('Any X,E WHERE X eid %(x)s, X primary_email E?', {'x': eid})
        e = rset.get_entity(0, 0)
        # if any of the assertion below fails with a KeyError, the relation is not cached
        # related entities should be an empty list
        self.assertEquals(e.related_cache('primary_email', 'subject', True), ())
        # related rset should be an empty rset
        cached = e.related_cache('primary_email', 'subject', False)
        self.assertIsInstance(cached, ResultSet)
        self.assertEquals(cached.rowcount, 0)


    def test_get_entity_union(self):
        e = self.add_entity('Bookmark', title=u'manger', path=u'path')
        rset = self.execute('Any X,N ORDERBY N WITH X,N BEING '
                            '((Any X,N WHERE X is Bookmark, X title N)'
                            ' UNION '
                            ' (Any X,N WHERE X is CWGroup, X name N))')
        expected = (('CWGroup', 'guests'), ('CWGroup', 'managers'),
                    ('Bookmark', 'manger'), ('CWGroup', 'owners'),
                    ('CWGroup', 'users'))
        for entity in rset.entities(): # test get_entity for each row actually
            etype, n = expected[entity.row]
            self.assertEquals(entity.id, etype)
            attr = etype == 'Bookmark' and 'title' or 'name'
            self.assertEquals(entity[attr], n)

    def test_related_entity_optional(self):
        e = self.add_entity('Bookmark', title=u'aaaa', path=u'path')
        rset = self.execute('Any B,U,L WHERE B bookmarked_by U?, U login L')
        entity, rtype = rset.related_entity(0, 2)
        self.assertEquals(entity, None)
        self.assertEquals(rtype, None)

    def test_related_entity_union_subquery(self):
        e = self.add_entity('Bookmark', title=u'aaaa', path=u'path')
        rset = self.execute('Any X,N ORDERBY N WITH X,N BEING '
                            '((Any X,N WHERE X is CWGroup, X name N)'
                            ' UNION '
                            ' (Any X,N WHERE X is Bookmark, X title N))')
        entity, rtype = rset.related_entity(0, 1)
        self.assertEquals(entity.eid, e.eid)
        self.assertEquals(rtype, 'title')
        entity, rtype = rset.related_entity(1, 1)
        self.assertEquals(entity.id, 'CWGroup')
        self.assertEquals(rtype, 'name')
        #
        rset = self.execute('Any X,N ORDERBY N WHERE X is Bookmark WITH X,N BEING '
                            '((Any X,N WHERE X is CWGroup, X name N)'
                            ' UNION '
                            ' (Any X,N WHERE X is Bookmark, X title N))')
        entity, rtype = rset.related_entity(0, 1)
        self.assertEquals(entity.eid, e.eid)
        self.assertEquals(rtype, 'title')
        #
        rset = self.execute('Any X,N ORDERBY N WITH N,X BEING '
                            '((Any N,X WHERE X is CWGroup, X name N)'
                            ' UNION '
                            ' (Any N,X WHERE X is Bookmark, X title N))')
        entity, rtype = rset.related_entity(0, 1)
        self.assertEquals(entity.eid, e.eid)
        self.assertEquals(rtype, 'title')

    def test_entities(self):
        rset = self.execute('Any U,G WHERE U in_group G')
        # make sure we have at least one element
        self.failUnless(rset)
        self.assertEquals(set(e.e_schema.type for e in rset.entities(0)),
                          set(['CWUser',]))
        self.assertEquals(set(e.e_schema.type for e in rset.entities(1)),
                          set(['CWGroup',]))

    def test_printable_rql(self):
        rset = self.execute(u'CWEType X WHERE X final FALSE')
        self.assertEquals(rset.printable_rql(),
                          'Any X WHERE X final FALSE, X is CWEType')

    def test_searched_text(self):
        rset = self.execute(u'Any X WHERE X has_text "foobar"')
        self.assertEquals(rset.searched_text(), 'foobar')
        rset = self.execute(u'Any X WHERE X has_text %(text)s', {'text' : 'foo'})
        self.assertEquals(rset.searched_text(), 'foo')


if __name__ == '__main__':
    unittest_main()
