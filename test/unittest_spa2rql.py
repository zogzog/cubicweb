from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools import TestServerConfiguration
from cubicweb.xy import xy
from cubicweb.spa2rql import Sparql2rqlTranslator

xy.add_equivalence('Project', 'doap:Project')
xy.add_equivalence('Project creation_date', 'doap:Project doap:created')
xy.add_equivalence('Project name', 'doap:Project doap:name')


config = TestServerConfiguration('data')
config.bootstrap_cubes()
schema = config.load_schema()


class XYTC(TestCase):
    def setUp(self):
        self.tr = Sparql2rqlTranslator(schema)

    def _test(self, sparql, rql, args={}):
        qi = self.tr.translate(sparql)
        self.assertEquals(qi.finalize(), (rql, args))

    def XXX_test_base_01(self):
        self._test('SELECT * WHERE { }', 'Any X')


    def test_base_is(self):
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT ?project
    WHERE  {
      ?project a doap:Project;
    }''', 'Any PROJECT WHERE PROJECT is Project')


    def test_base_attr_sel(self):
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT ?created
    WHERE  {
      ?project a doap:Project;
              doap:created ?created.
    }''', 'Any CREATED WHERE PROJECT creation_date CREATED, PROJECT is Project')


    def test_base_attr_sel_distinct(self):
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT DISTINCT ?name
    WHERE  {
      ?project a doap:Project;
              doap:name ?name.
    }''', 'DISTINCT Any NAME WHERE PROJECT name NAME, PROJECT is Project')


    def test_base_attr_sel_reduced(self):
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT REDUCED ?name
    WHERE  {
      ?project a doap:Project;
              doap:name ?name.
    }''', 'Any NAME WHERE PROJECT name NAME, PROJECT is Project')


    def test_base_attr_sel_limit_offset(self):
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT ?name
    WHERE  {
      ?project a doap:Project;
              doap:name ?name.
    }
    LIMIT 20''', 'Any NAME LIMIT 20 WHERE PROJECT name NAME, PROJECT is Project')
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT ?name
    WHERE  {
      ?project a doap:Project;
              doap:name ?name.
    }
    LIMIT 20 OFFSET 10''', 'Any NAME LIMIT 20 OFFSET 10 WHERE PROJECT name NAME, PROJECT is Project')


    def test_base_attr_sel_orderby(self):
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT ?name
    WHERE  {
      ?project a doap:Project;
              doap:name ?name;
              doap:created ?created.
    }
    ORDER BY ?name DESC(?created)''', 'Any NAME ORDERBY NAME ASC, CREATED DESC WHERE PROJECT name NAME, PROJECT creation_date CREATED, PROJECT is Project')


    def test_base_any_attr_sel(self):
        self._test('''
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    SELECT ?x ?cd
    WHERE  {
      ?x dc:date ?cd;
    }''', 'Any X, CD WHERE X creation_date CD')


    def test_base_any_attr_sel_amb(self):
        xy.add_equivalence('Version publication_date', 'doap:Version dc:date')
        try:
            self._test('''
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    SELECT ?x ?cd
    WHERE  {
      ?x dc:date ?cd;
    }''', '(Any X, CD WHERE , X creation_date CD) UNION (Any X, CD WHERE , X publication_date CD, X is Version)')
        finally:
            xy.remove_equivalence('Version publication_date', 'doap:Version dc:date')


    def test_base_any_attr_sel_amb_limit_offset(self):
        xy.add_equivalence('Version publication_date', 'doap:Version dc:date')
        try:
            self._test('''
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    SELECT ?x ?cd
    WHERE  {
      ?x dc:date ?cd;
    }
    LIMIT 20 OFFSET 10''', 'Any X, CD LIMIT 20 OFFSET 10 WITH X, CD BEING ((Any X, CD WHERE , X creation_date CD) UNION (Any X, CD WHERE , X publication_date CD, X is Version))')
        finally:
            xy.remove_equivalence('Version publication_date', 'doap:Version dc:date')


    def test_base_any_attr_sel_amb_orderby(self):
        xy.add_equivalence('Version publication_date', 'doap:Version dc:date')
        try:
            self._test('''
    PREFIX dc: <http://purl.org/dc/elements/1.1/>
    SELECT ?x ?cd
    WHERE  {
      ?x dc:date ?cd;
    }
    ORDER BY DESC(?cd)''', 'Any X, CD ORDERBY CD DESC WITH X, CD BEING ((Any X, CD WHERE , X creation_date CD) UNION (Any X, CD WHERE , X publication_date CD, X is Version))')
        finally:
            xy.remove_equivalence('Version publication_date', 'doap:Version dc:date')


    def test_restr_attr(self):
        self._test('''
    PREFIX doap: <http://usefulinc.com/ns/doap#>
    SELECT ?project
    WHERE  {
      ?project a doap:Project;
              doap:name "cubicweb".
    }''', 'Any PROJECT WHERE PROJECT name %(a)s, PROJECT is Project', {'a': 'cubicweb'})

# # Two elements in the group
# PREFIX :  <http://example.org/ns#>
# SELECT *
# { :p :q :r  OPTIONAL { :a :b :c }
#   :p :q :r  OPTIONAL { :a :b :c }
# }

# PREFIX : <http://example.org/ns#>
# SELECT *
# {
#   { ?s ?p ?o } UNION { ?a ?b ?c }
# }

# PREFIX dob: <http://placetime.com/interval/gregorian/1977-01-18T04:00:00Z/P>
# PREFIX time: <http://www.ai.sri.com/daml/ontologies/time/Time.daml#>
# PREFIX dc: <http://purl.org/dc/elements/1.1/>
# SELECT ?desc
# WHERE  {
#   dob:1D a time:ProperInterval;
#          dc:description ?desc.
# }

if __name__ == '__main__':
    unittest_main()
