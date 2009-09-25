"""automatic tests

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from cubicweb.devtools.testlib import CubicWebTC, AutoPopulateTest, AutomaticWebTest
from cubicweb.view import AnyRsetView

AutomaticWebTest.application_rql = [
    'Any L,F WHERE E is CWUser, E login L, E firstname F',
    'Any L,F,E WHERE E is CWUser, E login L, E firstname F',
    'Any COUNT(X) WHERE X is CWUser',
    ]

class ComposityCopy(CubicWebTC):

    def test_regr_copy_view(self):
        """regression test: make sure we can ask a copy of a
        composite entity
        """
        rset = self.execute('CWUser X WHERE X login "admin"')
        self.view('copy', rset)



class SomeView(AnyRsetView):
    __regid__ = 'someview'

    def call(self):
        self._cw.add_js('spam.js')
        self._cw.add_js('spam.js')


class ManualCubicWebTCs(AutoPopulateTest):
    def setup_database(self):
        self.auto_populate(10)

    def test_manual_tests(self):
        rset = self.execute('Any P,F,S WHERE P is CWUser, P firstname F, P surname S')
        self.view('table', rset, template=None, displayfilter=True, displaycols=[0,2])

    def test_sortable_js_added(self):
        rset = self.execute('CWUser X')
        # sortable.js should not be included by default
        self.failIf('jquery.tablesorter.js' in self.view('oneline', rset))
        # but should be included by the tableview
        rset = self.execute('Any P,F,S LIMIT 1 WHERE P is CWUser, P firstname F, P surname S')
        self.failUnless('jquery.tablesorter.js' in self.view('table', rset))

    def test_js_added_only_once(self):
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register_appobject_class(SomeView)
        rset = self.execute('CWUser X')
        source = self.view('someview', rset).source
        self.assertEquals(source.count('spam.js'), 1)



class ExplicitViewsTest(CubicWebTC):

    def test_unrelateddivs(self):
        rset = self.execute('Any X WHERE X is CWUser, X login "admin"')
        group = self.add_entity('CWGroup', name=u'R&D')
        req = self.request(relation='in_group_subject')
        self.view('unrelateddivs', rset, req)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
