from logilab.common.date import datetime2ticks
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import facet

class BaseFacetTC(CubicWebTC):

    def prepare_rqlst(self, req, rql='CWUser X', mainvar='X',
                      expected_baserql='Any X WHERE X is CWUser',
                      expected_preparedrql='DISTINCT Any  WHERE X is CWUser'):
        rset = req.cnx.execute(rql)
        rqlst = rset.syntax_tree().copy()
        filtered_variable, baserql = facet.init_facets(rset, rqlst.children[0],
                                                       mainvar=mainvar)
        self.assertEqual(filtered_variable.name, mainvar)
        self.assertEqual(baserql, expected_baserql)
        self.assertEqual(rqlst.as_string(), expected_preparedrql)
        return rset, rqlst, filtered_variable

    def _in_group_facet(self, req, cls=facet.RelationFacet, no_relation=False):
        rset, rqlst, filtered_variable = self.prepare_rqlst(req)
        cls.no_relation = no_relation
        f = cls(req, rset=rset, select=rqlst.children[0],
                filtered_variable=filtered_variable)
        f.__regid__ = 'in_group'
        f.rtype = 'in_group'
        f.role = 'subject'
        f.target_attr = 'name'
        guests, managers = [eid for eid, in req.cnx.execute('CWGroup G ORDERBY GN '
                                                            'WHERE G name GN, G name IN ("guests", "managers")')]
        groups = [eid for eid, in req.cnx.execute('CWGroup G ORDERBY GN '
                                                  'WHERE G name GN, G name IN ("guests", "managers")')]
        return f, groups

    def test_relation_simple(self):
        with self.admin_access.web_request() as req:
            f, (guests, managers) = self._in_group_facet(req)
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

    def test_relation_multiple_and(self):
        with self.admin_access.web_request() as req:
            f, (guests, managers) = self._in_group_facet(req)
            f._cw.form[f.__regid__] = [str(guests), str(managers)]
            f._cw.form[f.__regid__ + '_andor'] = 'AND'
            f.add_rql_restrictions()
            self.assertEqual(f.select.as_string(),
                             'DISTINCT Any  WHERE X is CWUser, X in_group A, B eid %s, X in_group B, A eid %s' % (guests, managers))

    def test_relation_multiple_or(self):
        with self.admin_access.web_request() as req:
            f, (guests, managers) = self._in_group_facet(req)
            f._cw.form[f.__regid__] = [str(guests), str(managers)]
            f._cw.form[f.__regid__ + '_andor'] = 'OR'
            f.add_rql_restrictions()
            self.assertEqual(f.select.as_string(),
                             'DISTINCT Any  WHERE X is CWUser, X in_group A, A eid IN(%s, %s)' % (guests, managers))

    def test_relation_optional_rel(self):
        with self.admin_access.web_request() as req:
            rset = req.cnx.execute('Any X,GROUP_CONCAT(GN) GROUPBY X '
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
            guests, managers = [eid for eid, in req.cnx.execute('CWGroup G ORDERBY GN '
                                                                'WHERE G name GN, G name IN ("guests", "managers")')]
            self.assertEqual(f.vocabulary(),
                             [(u'guests', guests), (u'managers', managers)])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), "DISTINCT Any  WHERE X in_group G?, G name GN, NOT G name 'users'")
            #rqlst = rset.syntax_tree()
            self.assertEqual(sorted(f.possible_values()),
                             [str(guests), str(managers)])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), "DISTINCT Any  WHERE X in_group G?, G name GN, NOT G name 'users'")
            req.form[f.__regid__] = str(guests)
            f.add_rql_restrictions()
            # selection is cluttered because rqlst has been prepared for facet (it
            # is not in real life)
            self.assertEqual(f.select.as_string(),
                             "DISTINCT Any  WHERE X in_group G?, G name GN, NOT G name 'users', X in_group D, D eid %s" % guests)

    def test_relation_no_relation_1(self):
        with self.admin_access.web_request() as req:
            f, (guests, managers) = self._in_group_facet(req, no_relation=True)
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
        with self.admin_access.web_request() as req:
            f, (guests, managers) = self._in_group_facet(req, no_relation=True)
            f._cw.form[f.__regid__] = ['', guests]
            f.select.save_state()
            f.add_rql_restrictions()
            self.assertEqual(f.select.as_string(),
                              'DISTINCT Any  WHERE X is CWUser, (NOT X in_group B) OR (X in_group A, A eid %s)' % guests)
            f.select.recover()
            self.assertEqual(f.select.as_string(),
                              'DISTINCT Any  WHERE X is CWUser')



    def test_relationattribute(self):
        with self.admin_access.web_request() as req:
            f, (guests, managers) = self._in_group_facet(req, cls=facet.RelationAttributeFacet)
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
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req)
            f = facet.DateRangeFacet(req, rset=rset,
                                     select=rqlst.children[0],
                                     filtered_variable=filtered_variable)
            f.rtype = 'creation_date'
            mind, maxd = req.cnx.execute('Any MIN(CD), MAX(CD) WHERE X is CWUser, X creation_date CD')[0]
            self.assertEqual(f.vocabulary(),
                              [(str(mind), mind),
                               (str(maxd), maxd)])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            #rqlst = rset.syntax_tree()
            self.assertEqual(f.possible_values(),
                             [str(mind), str(maxd)])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            req.form['%s_inf' % f.__regid__] = str(datetime2ticks(mind))
            req.form['%s_sup' % f.__regid__] = str(datetime2ticks(mind))
            f.add_rql_restrictions()
            # selection is cluttered because rqlst has been prepared for facet (it
            # is not in real life)
            self.assertEqual(f.select.as_string(),
                              'DISTINCT Any  WHERE X is CWUser, X creation_date >= "%s", '
                             'X creation_date <= "%s"'
                             % (mind.strftime('%Y/%m/%d'),
                                mind.strftime('%Y/%m/%d')))

    def test_attribute(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req)
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

    def test_bitfield(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req,
                'CWAttribute X WHERE X ordernum XO',
                expected_baserql='Any X WHERE X ordernum XO, X is CWAttribute',
                expected_preparedrql='DISTINCT Any  WHERE X ordernum XO, X is CWAttribute')
            f = facet.BitFieldFacet(req, rset=rset,
                                    select=rqlst.children[0],
                                    filtered_variable=filtered_variable)
            f.choices = [('un', 1,), ('deux', 2,)]
            f.rtype = 'ordernum'
            self.assertEqual(f.vocabulary(),
                              [(u'deux', 2), (u'un', 1)])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X ordernum XO, X is CWAttribute')
            #rqlst = rset.syntax_tree()
            self.assertEqual(f.possible_values(),
                              ['2', '1'])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X ordernum XO, X is CWAttribute')
            req.form[f.__regid__] = '3'
            f.add_rql_restrictions()
            # selection is cluttered because rqlst has been prepared for facet (it
            # is not in real life)
            self.assertEqual(f.select.as_string(),
                              "DISTINCT Any  WHERE X ordernum XO, X is CWAttribute, X ordernum C HAVING 3 = (C & 3)")

    def test_bitfield_0_value(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req,
                'CWAttribute X WHERE X ordernum XO',
                expected_baserql='Any X WHERE X ordernum XO, X is CWAttribute',
                expected_preparedrql='DISTINCT Any  WHERE X ordernum XO, X is CWAttribute')
            f = facet.BitFieldFacet(req, rset=rset,
                                    select=rqlst.children[0],
                                    filtered_variable=filtered_variable)
            f.choices = [('zero', 0,), ('un', 1,), ('deux', 2,)]
            f.rtype = 'ordernum'
            self.assertEqual(f.vocabulary(),
                              [(u'deux', 2), (u'un', 1), (u'zero', 0)])
            self.assertEqual(f.possible_values(),
                              ['2', '1', '0'])
            req.form[f.__regid__] = '0'
            f.add_rql_restrictions()
            self.assertEqual(f.select.as_string(),
                              "DISTINCT Any  WHERE X ordernum XO, X is CWAttribute, X ordernum C HAVING 0 = C")

    def test_rql_path_eid(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req)
            class RPF(facet.RQLPathFacet):
                path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
                filter_variable = 'O'
                label_variable = 'OL'
            f = RPF(req, rset=rset, select=rqlst.children[0],
                    filtered_variable=filtered_variable)
            self.assertEqual(f.vocabulary(), [(u'admin', req.user.eid),])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            #rqlst = rset.syntax_tree()
            self.assertEqual(f.possible_values(),
                             [str(req.user.eid),])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            req.form[f.__regid__] = '1'
            f.add_rql_restrictions()
            # selection is cluttered because rqlst has been prepared for facet (it
            # is not in real life)
            self.assertEqual(f.select.as_string(),
                             "DISTINCT Any  WHERE X is CWUser, X created_by F, F owned_by G, G eid 1")

    def test_rql_path_eid_no_label(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req)
            class RPF(facet.RQLPathFacet):
                path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
                filter_variable = 'O'
            f = RPF(req, rset=rset, select=rqlst.children[0],
                    filtered_variable=filtered_variable)
            self.assertEqual(f.vocabulary(), [(str(req.user.eid), req.user.eid),])

    def test_rql_path_attr(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req)
            class RPF(facet.RQLPathFacet):
                path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
                filter_variable = 'OL'
            f = RPF(req, rset=rset, select=rqlst.children[0],
                    filtered_variable=filtered_variable)

            self.assertEqual(f.vocabulary(), [(u'admin', 'admin'),])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            self.assertEqual(f.possible_values(), ['admin',])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            req.form[f.__regid__] = 'admin'
            f.add_rql_restrictions()
            # selection is cluttered because rqlst has been prepared for facet (it
            # is not in real life)
            self.assertEqual(f.select.as_string(),
                             "DISTINCT Any  WHERE X is CWUser, X created_by G, G owned_by H, H login 'admin'")

    def test_rql_path_check_filter_label_variable(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepareg_aggregat_rqlst(req)
            class RPF(facet.RQLPathFacet):
                path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
                filter_variable = 'OL'
                label_variable = 'OL'
            self.assertRaises(AssertionError, RPF, req, rset=rset,
                              select=rqlst.children[0],
                              filtered_variable=filtered_variable)


    def test_rqlpath_range(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepare_rqlst(req)
            class RRF(facet.DateRangeRQLPathFacet):
                path = [('X created_by U'), ('U owned_by O'), ('O creation_date OL')]
                filter_variable = 'OL'
            f = RRF(req, rset=rset, select=rqlst.children[0],
                    filtered_variable=filtered_variable)
            mind, maxd = req.cnx.execute('Any MIN(CD), MAX(CD) WHERE X is CWUser, X created_by U, U owned_by O, O creation_date CD')[0]
            self.assertEqual(f.vocabulary(), [(str(mind), mind),
                                              (str(maxd), maxd)])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            self.assertEqual(f.possible_values(),
                             [str(mind), str(maxd)])
            # ensure rqlst is left unmodified
            self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
            req.form['%s_inf' % f.__regid__] = str(datetime2ticks(mind))
            req.form['%s_sup' % f.__regid__] = str(datetime2ticks(mind))
            f.add_rql_restrictions()
            # selection is cluttered because rqlst has been prepared for facet (it
            # is not in real life)
            self.assertEqual(f.select.as_string(),
                             'DISTINCT Any  WHERE X is CWUser, X created_by G, G owned_by H, H creation_date >= "%s", '
                             'H creation_date <= "%s"'
                             % (mind.strftime('%Y/%m/%d'),
                                mind.strftime('%Y/%m/%d')))

    def prepareg_aggregat_rqlst(self, req):
        return self.prepare_rqlst(req,
            'Any 1, COUNT(X) WHERE X is CWUser, X creation_date XD, '
            'X modification_date XM, Y creation_date YD, Y is CWGroup '
            'HAVING DAY(XD)>=DAY(YD) AND DAY(XM)<=DAY(YD)', 'X',
            expected_baserql='Any 1,COUNT(X) WHERE X is CWUser, X creation_date XD, '
            'X modification_date XM, Y creation_date YD, Y is CWGroup '
            'HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)',
            expected_preparedrql='DISTINCT Any  WHERE X is CWUser, X creation_date XD, '
            'X modification_date XM, Y creation_date YD, Y is CWGroup '
            'HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)')


    def test_aggregat_query_cleanup_select(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepareg_aggregat_rqlst(req)
            select = rqlst.children[0]
            facet.cleanup_select(select, filtered_variable=filtered_variable)
            self.assertEqual(select.as_string(),
                             'DISTINCT Any  WHERE X is CWUser, X creation_date XD, '
                             'X modification_date XM, Y creation_date YD, Y is CWGroup '
                             'HAVING DAY(XD) >= DAY(YD), DAY(XM) <= DAY(YD)')

    def test_aggregat_query_rql_path(self):
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepareg_aggregat_rqlst(req)
            class RPF(facet.RQLPathFacet):
                path = [('X created_by U'), ('U owned_by O'), ('O login OL')]
                filter_variable = 'OL'
            f = RPF(req, rset=rset, select=rqlst.children[0],
                    filtered_variable=filtered_variable)
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
        with self.admin_access.web_request() as req:
            rset, rqlst, filtered_variable = self.prepareg_aggregat_rqlst(req)
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
