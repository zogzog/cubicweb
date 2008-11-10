from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.web.views.searchrestriction import insert_attr_select_relation

class ExtractFilterFieldsTC(EnvBasedTC):
    def test_relations_cleanup(self):
        self.skip('test needs to be updated (facet API changed)')
        # removing relation should be done in the table filter form but not
        # from the facets box
        rset = self.execute('Any X, S WHERE X in_state S')
        afielddefs, baserql, groupby, orderby = extract_filter_fields(rset, 0)
        afielddefs = [(getattr(r, 'r_type', r), role, type) for r, role, type, values in afielddefs]
        self.assertEquals(afielddefs, [('has_text', 'subject', 'rstring'),
                                       ('in_state', 'subject', 'eid')])
        self.assertEquals(baserql, 'DISTINCT Any X,S')
        self.assertEquals(groupby, '')
        self.assertEquals(orderby, '')
        # test rql st state
        self.assertEquals(rset.syntax_tree().as_string(), 'Any X,S WHERE X in_state S')
        afielddefs, baserql, groupby, orderby = extract_filter_fields(rset, 0, removerels=False)
        afielddefs = [(getattr(r, 'r_type', r), role, type) for r, role, type, values in afielddefs]
        self.assertEquals(afielddefs, [('has_text', 'subject', 'rstring'),
                                       ('in_state', 'subject', 'eid')])
        self.assertEquals(baserql, 'DISTINCT Any X,S WHERE X in_state S')


class InsertAttrRelationTC(EnvBasedTC):
    def setUp(self):
        self.skip('test needs to be updated (facet API changed)')

    def parse(self, query):
        rqlst = self.vreg.parse(self.session, query)
        select = rqlst.children[0]
        select.remove_groups()
        return select

    def _generate(self, select, rel, var, attr):
        return insert_attr_select_relation(select, select.defined_vars[var], 'subject', rel, attr)
        
    @property
    def select(self):
        return self.parse('Any B,(NOW - CD),S,V,U,GROUP_CONCAT(TN),VN,P,CD,BMD '
                          'GROUPBY B,CD,S,V,U,VN,P,BMD '
                          'WHERE B in_state S, B creation_date CD, '
                          'B modification_date BMD, T? tags B, T name TN, '
                          'V? bookmarked_by B, V title VN, B created_by U?, '
                          'B in_group P, P name "managers"')
    
    def test_1(self):
        self.assertEquals(self._generate(self.select, 'in_state', 'S', 'name'),
                          "DISTINCT Any S,A ORDERBY A WHERE B in_state S, B in_group P, "
                          "P name 'managers', S name A, B is EUser")
        
    def test_2(self):
        self.assertEquals(self._generate(self.select, 'tags', 'T', 'name'),
                          "DISTINCT Any T,TN ORDERBY TN WHERE T tags B, T name TN, "
                          "B in_group P, P name 'managers', B is EUser")
        
    def test_3(self):
        self.assertEquals(self._generate(self.select, 'created_by', 'U', 'login'),
                          "DISTINCT Any U,A ORDERBY A WHERE B created_by U, B in_group P, "
                          "P name 'managers', U login A, B is EUser")
        
    def test_nonregr1(self):
        select = self.parse('Any T,V WHERE T bookmarked_by V?, '
                            'V in_state VS, VS name "published", T created_by U')
        self.assertEquals(self._generate(select, 'created_by', 'U', 'login'),
                          'DISTINCT Any U,A ORDERBY A WHERE T created_by U, U login A, '
                          'T is Bookmark')

    def test_nonregr2(self):
        #'DISTINCT Any X,TMP,N WHERE P name TMP, X version_of P, P is Project, X is Version, not X in_state S,S name "published", X num N ORDERBY TMP,N'
        select = self.parse('DISTINCT Any V,TN,L ORDERBY TN,L WHERE T nom TN, V connait T, T is Personne, V is EUser,'
                            'NOT V in_state VS, VS name "published", V login L')
        rschema = self.schema['connait']
        for s, o in rschema.iter_rdefs():
            rschema.set_rproperty(s, o, 'cardinality', '++')
        try:
            self.assertEquals(self._generate(select, 'in_state', 'VS', 'name'),
                              "DISTINCT Any VS,A ORDERBY A WHERE V is EUser, NOT V in_state VS, VS name 'published', VS name A")
        finally:
            for s, o in rschema.iter_rdefs():
                rschema.set_rproperty(s, o, 'cardinality', '**')

    def test_nonregr3(self):
        #'DISTINCT Any X,TMP,N WHERE P name TMP, X version_of P, P is Project, X is Version, not X in_state S,S name "published", X num N ORDERBY TMP,N'
        select = self.parse('DISTINCT Any X, MAX(Y) GROUPBY X WHERE X is EUser, Y is Bookmark, X in_group A')
        self.assertEquals(self._generate(select, 'in_group', 'A', 'name'),
                          "DISTINCT Any A,B ORDERBY B WHERE X is EUser, X in_group A, A name B")

        
if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
