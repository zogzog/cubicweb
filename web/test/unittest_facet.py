from logilab.common.date import datetime2ticks
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import facet

class BaseFacetTC(CubicWebTC):

    def prepare_rqlst(self, rql='CWUser X', baserql='Any X WHERE X is CWUser',
                      preparedrql='DISTINCT Any  WHERE X is CWUser',
                      mainvar='X'):
        req = self.request()
        rset = self.execute(rql)
        rqlst = rset.syntax_tree().copy()
        filtered_variable, baserql = facet.init_facets(rset, rqlst.children[0],
                                                       mainvar=mainvar)
        self.assertEqual(filtered_variable.name, mainvar)
        self.assertEqual(baserql, baserql)
        self.assertEqual(rqlst.as_string(), preparedrql)
        return req, rset, rqlst, filtered_variable

    def _in_group_facet(self, cls=facet.RelationFacet, no_relation=False):
        req, rset, rqlst, filtered_variable = self.prepare_rqlst()
        cls.no_relation = no_relation
        f = cls(req, rset=rset, select=rqlst.children[0],
                filtered_variable=filtered_variable)
        f.__regid__ = 'in_group'
        f.rtype = 'in_group'
        f.role = 'subject'
        f.target_attr = 'name'
        guests, managers = [eid for eid, in self.execute('CWGroup G ORDERBY GN '
                                                         'WHERE G name GN, G name IN ("guests", "managers")')]
        groups = [eid for eid, in self.execute('CWGroup G ORDERBY GN '
                                               'WHERE G name GN, G name IN ("guests", "managers")')]
        return f, groups

    def test_relation_simple(self):
        f, (guests, managers) = self._in_group_facet()
        self.assertEqual(f.vocabulary(),
                      [(u'guests', guests), (u'managers', managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(f.select.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(),
                          [str(guests), str(managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(f.select.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        f._cw.form[f.__regid__] = str(guests)
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.select.as_string(),
                         'DISTINCT Any  WHERE X is CWUser, X in_group D, D eid %s' % guests)

    def test_relation_optional_rel(self):
        req = self.request()
        rset = self.execute('Any X,GROUP_CONCAT(GN) GROUPBY X '
                            'WHERE X in_group G?, G name GN, NOT G name "users"')
        rqlst = rset.syntax_tree().copy()
        select = rqlst.children[0]
        filtered_variable, baserql = facet.init_facets(rset, select)

        f = facet.RelationFacet(req, rset=rset,
                                select=select,
                                filtered_variable=filtered_variable)
        f.rtype = 'in_group'
        f.role = 'subject'
        f.target_attr = 'name'
        guests, managers = [eid for eid, in self.execute('CWGroup G ORDERBY GN '
                                                         'WHERE G name GN, G name IN ("guests", "managers")')]
        self.assertEqual(f.vocabulary(),
                          [(u'guests', guests), (u'managers', managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X in_group G?, G name GN, NOT G name "users"')
        #rqlst = rset.syntax_tree()
        self.assertEqual(sorted(f.possible_values()),
                          [str(guests), str(managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X in_group G?, G name GN, NOT G name "users"')
        req.form[f.__regid__] = str(guests)
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.select.as_string(),
                          'DISTINCT Any  WHERE X in_group G?, G name GN, NOT G name "users", X in_group D, D eid %s' % guests)

    def test_relation_no_relation_1(self):
        f, (guests, managers) = self._in_group_facet(no_relation=True)
        self.assertEqual(f.vocabulary(),
                          [(u'guests', guests), (u'managers', managers)])
        self.assertEqual(f.possible_values(),
                          [str(guests), str(managers)])
        f._cw.create_entity('CWUser', login=u'hop', upassword='toto')
        self.assertEqual(f.vocabulary(),
                          [(u'<no relation>', ''), (u'guests', guests), (u'managers', managers)])
        self.assertEqual(f.possible_values(),
                          [str(guests), str(managers), ''])
        f._cw.form[f.__regid__] = ''
        f.add_rql_restrictions()
        self.assertEqual(f.select.as_string(),
                          'DISTINCT Any  WHERE X is CWUser, NOT X in_group G')

    def test_relation_no_relation_2(self):
        f, (guests, managers) = self._in_group_facet(no_relation=True)
        f._cw.form[f.__regid__] = ['', guests]
        f.select.save_state()
        f.add_rql_restrictions()
        self.assertEqual(f.select.as_string(),
                          'DISTINCT Any  WHERE X is CWUser, (NOT X in_group B) OR (X in_group A, A eid %s)' % guests)
        f.select.recover()
        self.assertEqual(f.select.as_string(),
                          'DISTINCT Any  WHERE X is CWUser')



    def test_relationattribute(self):
        f, (guests, managers) = self._in_group_facet(cls=facet.RelationAttributeFacet)
        self.assertEqual(f.vocabulary(),
                          [(u'guests', u'guests'), (u'managers', u'managers')])
        # ensure rqlst is left unmodified
        self.assertEqual(f.select.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(),
                          ['guests', 'managers'])
        # ensure rqlst is left unmodified
        self.assertEqual(f.select.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        f._cw.form[f.__regid__] = 'guests'
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.select.as_string(),
                          "DISTINCT Any  WHERE X is CWUser, X in_group E, E name 'guests'")

    def test_daterange(self):
        req, rset, rqlst, filtered_variable = self.prepare_rqlst()
        f = facet.DateRangeFacet(req, rset=rset,
                                 select=rqlst.children[0],
                                 filtered_variable=filtered_variable)
        f.rtype = 'creation_date'
        dates = self.execute('Any CD ORDERBY CD WHERE X is CWUser, X creation_date CD')
        self.assertEqual(f.vocabulary(),
                          [(str(dates[0][0]), dates[0][0]),
                           (str(dates[1][0]), dates[1][0])])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(),
                          [str(dates[0][0]), str(dates[1][0])])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        req.form['%s_inf' % f.__regid__] = str(datetime2ticks(dates[0][0]))
        req.form['%s_sup' % f.__regid__] = str(datetime2ticks(dates[0][0]))
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.select.as_string(),
                          'DISTINCT Any  WHERE X is CWUser, X creation_date >= "%s", '
                         'X creation_date <= "%s"'
                         % (dates[0][0].strftime('%Y/%m/%d'),
                            dates[0][0].strftime('%Y/%m/%d')))

    def test_attribute(self):
        req, rset, rqlst, filtered_variable = self.prepare_rqlst()
        f = facet.AttributeFacet(req, rset=rset,
                                 select=rqlst.children[0],
                                 filtered_variable=filtered_variable)
        f.rtype = 'login'
        self.assertEqual(f.vocabulary(),
                          [(u'admin', u'admin'), (u'anon', u'anon')])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(),
                          ['admin', 'anon'])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        req.form[f.__regid__] = 'admin'
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.select.as_string(),
                          "DISTINCT Any  WHERE X is CWUser, X login 'admin'")

    def test_rql_path_eid(self):
        req, rset, rqlst, filtered_variable = self.prepare_rqlst()
        facet.RQLPathFacet.path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
        f = facet.RQLPathFacet(req, rset=rset,
                               select=rqlst.children[0],
                               filtered_variable=filtered_variable)
        f.filter_variable = 'O'
        f.label_variable = 'OL'

        self.assertEqual(f.vocabulary(), [(u'admin', self.user().eid),])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(),
                          [str(self.user().eid),])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        req.form[f.__regid__] = '1'
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.select.as_string(),
                         "DISTINCT Any  WHERE X is CWUser, X created_by F, F owned_by G, G eid 1")

    def test_rql_path_attr(self):
        req, rset, rqlst, filtered_variable = self.prepare_rqlst()
        facet.RQLPathFacet.path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
        f = facet.RQLPathFacet(req, rset=rset,
                               select=rqlst.children[0],
                               filtered_variable=filtered_variable)
        f.filter_variable = 'OL'

        self.assertEqual(f.vocabulary(), [(u'admin', 'admin'),])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(), ['admin',])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        req.form[f.__regid__] = 'admin'
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.select.as_string(),
                         "DISTINCT Any  WHERE X is CWUser, X created_by G, G owned_by H, H login 'admin'")

    def prepareg_aggregat_rqlst(self):
        return self.prepare_rqlst(
            'Any 1, COUNT(X) WHERE X is CWUser, X creation_date XD, '
            'X modification_date XM, Y creation_date YD, Y is CWGroup '
            'HAVING DAY(XD)>=DAY(YD) AND DAY(XM)<=DAY(YD)', mainvar='X',
            baserql='DISTINCT Any  WHERE X is CWUser, X creation_date XD, '
            'X modification_date XM, Y creation_date YD, Y is CWGroup '
            'HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)',
            preparedrql='DISTINCT Any  WHERE X is CWUser, X creation_date XD, '
            'X modification_date XM, Y creation_date YD, Y is CWGroup '
            'HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)')


    def test_aggregat_query_cleanup_select(self):
        req, rset, rqlst, filtered_variable = self.prepareg_aggregat_rqlst()
        select = rqlst.children[0]
        facet.cleanup_select(select, filtered_variable=filtered_variable)
        self.assertEqual(select.as_string(),
                         'DISTINCT Any  WHERE X is CWUser, X creation_date XD, '
                         'X modification_date XM, Y creation_date YD, Y is CWGroup '
                         'HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)')

    def test_aggregat_query_rql_path(self):
        req, rset, rqlst, filtered_variable = self.prepareg_aggregat_rqlst()
        facet.RQLPathFacet.path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
        f = facet.RQLPathFacet(req, rset=rset,
                               select=rqlst.children[0],
                               filtered_variable=filtered_variable)
        f.filter_variable = 'OL'
        self.assertEqual(f.vocabulary(), [(u'admin', u'admin')])
        self.assertEqual(f.possible_values(), ['admin'])
        req.form[f.__regid__] = 'admin'
        f.add_rql_restrictions()
        self.assertEqual(f.select.as_string(),
                         "DISTINCT Any  WHERE X is CWUser, X creation_date XD, "
                         "X modification_date XM, Y creation_date YD, Y is CWGroup, "
                         "X created_by G, G owned_by H, H login 'admin' "
                         "HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)")

    def test_aggregat_query_attribute(self):
        req, rset, rqlst, filtered_variable = self.prepareg_aggregat_rqlst()
        f = facet.AttributeFacet(req, rset=rset,
                                 select=rqlst.children[0],
                                 filtered_variable=filtered_variable)
        f.rtype = 'login'
        self.assertEqual(f.vocabulary(),
                          [(u'admin', u'admin'), (u'anon', u'anon')])
        self.assertEqual(f.possible_values(),
                          ['admin', 'anon'])
        req.form[f.__regid__] = 'admin'
        f.add_rql_restrictions()
        self.assertEqual(f.select.as_string(),
                          "DISTINCT Any  WHERE X is CWUser, X creation_date XD, "
                          "X modification_date XM, Y creation_date YD, Y is CWGroup, X login 'admin' "
                          "HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)")

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
