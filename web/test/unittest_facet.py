from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import facet

class BaseFacetTC(CubicWebTC):

    def prepare_rqlst(self):
        req = self.request()
        rset = self.execute('CWUser X')
        rqlst = rset.syntax_tree().copy()
        req.vreg.rqlhelper.annotate(rqlst)
        mainvar, baserql = facet.prepare_facets_rqlst(rqlst, rset.args)
        self.assertEqual(mainvar.name, 'X')
        self.assertEqual(baserql, 'Any X WHERE X is CWUser')
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        return req, rset, rqlst, mainvar

    def test_relation_simple(self):
        req, rset, rqlst, mainvar = self.prepare_rqlst()
        f = facet.RelationFacet(req, rset=rset,
                                rqlst=rqlst.children[0],
                                filtered_variable=mainvar)
        f.rtype = 'in_group'
        f.role = 'subject'
        f.target_attr = 'name'
        guests, managers = [eid for eid, in self.execute('CWGroup G ORDERBY GN '
                                                         'WHERE G name GN, G name IN ("guests", "managers")')]
        self.assertEqual(f.vocabulary(),
                          [(u'guests', guests), (u'managers', managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(),
                          [str(guests), str(managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        req.form[f.__regid__] = str(guests)
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.rqlst.as_string(),
                          'DISTINCT Any  WHERE X is CWUser, X in_group D, D eid %s' % guests)

    def test_relation_optional_rel(self):
        req = self.request()
        rset = self.execute('Any X,GROUP_CONCAT(GN) GROUPBY X '
                            'WHERE X in_group G?, G name GN, NOT G name "users"')
        rqlst = rset.syntax_tree().copy()
        req.vreg.rqlhelper.annotate(rqlst)
        mainvar, baserql = facet.prepare_facets_rqlst(rqlst, rset.args)

        f = facet.RelationFacet(req, rset=rset,
                                rqlst=rqlst.children[0],
                                filtered_variable=mainvar)
        f.rtype = 'in_group'
        f.role = 'subject'
        f.target_attr = 'name'
        guests, managers = [eid for eid, in self.execute('CWGroup G ORDERBY GN '
                                                         'WHERE G name GN, G name IN ("guests", "managers")')]
        self.assertEqual(f.vocabulary(),
                          [(u'guests', guests), (u'managers', managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  GROUPBY X WHERE X in_group G?, G name GN, NOT G name "users"')
        #rqlst = rset.syntax_tree()
        self.assertEqual(sorted(f.possible_values()),
                          [str(guests), str(managers)])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  GROUPBY X WHERE X in_group G?, G name GN, NOT G name "users"')
        req.form[f.__regid__] = str(guests)
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.rqlst.as_string(),
                          'DISTINCT Any  GROUPBY X WHERE X in_group G?, G name GN, NOT G name "users", X in_group D, D eid %s' % guests)


    def test_relationattribute(self):
        req, rset, rqlst, mainvar = self.prepare_rqlst()
        f = facet.RelationAttributeFacet(req, rset=rset,
                                         rqlst=rqlst.children[0],
                                         filtered_variable=mainvar)
        f.rtype = 'in_group'
        f.role = 'subject'
        f.target_attr = 'name'
        self.assertEqual(f.vocabulary(),
                          [(u'guests', u'guests'), (u'managers', u'managers')])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        #rqlst = rset.syntax_tree()
        self.assertEqual(f.possible_values(),
                          ['guests', 'managers'])
        # ensure rqlst is left unmodified
        self.assertEqual(rqlst.as_string(), 'DISTINCT Any  WHERE X is CWUser')
        req.form[f.__regid__] = 'guests'
        f.add_rql_restrictions()
        # selection is cluttered because rqlst has been prepared for facet (it
        # is not in real life)
        self.assertEqual(f.rqlst.as_string(),
                          "DISTINCT Any  WHERE X is CWUser, X in_group E, E name 'guests'")


    def test_attribute(self):
        req, rset, rqlst, mainvar = self.prepare_rqlst()
        f = facet.AttributeFacet(req, rset=rset,
                                 rqlst=rqlst.children[0],
                                 filtered_variable=mainvar)
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
        self.assertEqual(f.rqlst.as_string(),
                          "DISTINCT Any  WHERE X is CWUser, X login 'admin'")


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
