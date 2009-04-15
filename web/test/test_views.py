"""automatic tests"""

from cubicweb.devtools.testlib import WebTest, AutomaticWebTest
from cubicweb.view import AnyRsetView

AutomaticWebTest.application_rql = [
    'Any L,F WHERE E is EUser, E login L, E firstname F',
    'Any L,F,E WHERE E is EUser, E login L, E firstname F',
    'Any COUNT(X) WHERE X is EUser',
    ]

class ComposityCopy(WebTest):

    def test_regr_copy_view(self):
        """regression test: make sure we can ask a copy of a
        composite entity
        """
        rset = self.execute('EUser X WHERE X login "admin"')
        self.view('copy', rset)



class SomeView(AnyRsetView):
    id = 'someview'
    
    def call(self):
        self.req.add_js('spam.js')
        self.req.add_js('spam.js')


class ManualWebTests(WebTest):
    def setup_database(self):
        self.auto_populate(10)

    def test_manual_tests(self):
        rset = self.execute('Any P,F,S WHERE P is EUser, P firstname F, P surname S')
        self.view('table', rset, template=None, displayfilter=True, displaycols=[0,2])        

    def test_sortable_js_added(self):
        rset = self.execute('EUser X')
        # sortable.js should not be included by default
        self.failIf('jquery.tablesorter.js' in self.view('oneline', rset))
        # but should be included by the tableview
        rset = self.execute('Any P,F,S LIMIT 1 WHERE P is EUser, P firstname F, P surname S')
        self.failUnless('jquery.tablesorter.js' in self.view('table', rset))

    def test_js_added_only_once(self):
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register_vobject_class(SomeView)
        rset = self.execute('EUser X')
        source = self.view('someview', rset).source
        self.assertEquals(source.count('spam.js'), 1)



class ExplicitViewsTest(WebTest):
    
    def test_unrelateddivs(self):
        rset = self.execute('Any X WHERE X is EUser, X login "admin"')
        group = self.add_entity('EGroup', name=u'R&D')
        req = self.request(relation='in_group_subject')
        self.view('unrelateddivs', rset, req)
        
        

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
