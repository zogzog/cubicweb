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
"""automatic tests"""
from cubicweb.devtools.testlib import AutoPopulateTest, AutomaticWebTest
from cubicweb.view import AnyRsetView

class AutomaticWebTest(AutomaticWebTest):
    application_rql = [
        'Any L,F WHERE E is CWUser, E login L, E firstname F',
        'Any L,F,E WHERE E is CWUser, E login L, E firstname F',
        'Any COUNT(X) WHERE X is CWUser',
        ]

    def to_test_etypes(self):
        # We do not really want to test cube views here. So we can drop testing
        # some EntityType. The two Blog types below require the sioc cube that
        # we do not want to add as a dependency.
        etypes = super(AutomaticWebTest, self).to_test_etypes()
        etypes -= set(('Blog', 'BlogEntry', 'CWSession'))
        return etypes


class SomeView(AnyRsetView):
    __regid__ = 'someview'

    def call(self):
        self._cw.add_js('spam.js')
        self._cw.add_js('spam.js')


class ManualCubicWebTCs(AutoPopulateTest):

    def test_regr_copy_view(self):
        """regression test: make sure we can ask a copy of a
        composite entity
        """
        with self.admin_access.web_request() as req:
            rset = req.execute(u'CWUser X WHERE X login "admin"')
            self.view('copy', rset, req=req)

    def test_sortable_js_added(self):
        with self.admin_access.web_request() as req:
            # sortable.js should not be included by default
            rset = req.execute('CWUser X')
            self.assertNotIn(b'jquery.tablesorter.js', self.view('oneline', rset, req=req).source)

        with self.admin_access.web_request() as req:
            # but should be included by the tableview
            rset = req.execute('Any P,F,S LIMIT 1 WHERE P is CWUser, P firstname F, P surname S')
            self.assertIn(b'jquery.tablesorter.js', self.view('table', rset, req=req).source)

    def test_js_added_only_once(self):
        with self.admin_access.web_request() as req:
            self.vreg._loadedmods[__name__] = {}
            self.vreg.register(SomeView)
            rset = req.execute('CWUser X')
            source = self.view('someview', rset, req=req).source
            self.assertEqual(source.count(b'spam.js'), 1)

    def test_unrelateddivs(self):
        with self.admin_access.client_cnx() as cnx:
            group = cnx.create_entity('CWGroup', name=u'R&D')
            cnx.commit()
        with self.admin_access.web_request(relation='in_group_subject') as req:
            rset = req.execute(u'Any X WHERE X is CWUser, X login "admin"')
            self.view('unrelateddivs', rset, req=req)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
