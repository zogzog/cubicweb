# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from logilab.common import tempattr, attrdict

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web.views.autoform import InlinedFormField

class InlinedFormTC(CubicWebTC):

    def test_linked_to(self):
        with self.admin_access.web_request() as req:
            formview = req.vreg['views'].select(
                'inline-creation', req,
                etype='File', rtype='described_by_test', role='subject',
                peid=123,
                petype='Salesterm')
            self.assertEqual({('described_by_test', 'object'): [123]},
                             formview.form.linked_to)

    def test_linked_to_parent_being_created(self):
        with self.admin_access.web_request() as req:
            formview = req.vreg['views'].select(
                'inline-creation', req,
                etype='File', rtype='described_by_test', role='subject',
                peid='A',
                petype='Salesterm')
            self.assertEqual(formview.form.linked_to, {})

    def test_remove_js_depending_on_cardinality(self):
        with self.admin_access.web_request() as req:
            formview = req.vreg['views'].select(
                'inline-creation', req,
                etype='File', rtype='described_by_test', role='subject',
                peid='A',
                petype='Salesterm')
            # cardinality is 1, can't remove
            self.assertIsNone(formview._get_removejs())
            rdef = self.schema['Salesterm'].rdef('described_by_test')
            with tempattr(rdef, 'cardinality', '?*'):
                self.assertTrue(formview._get_removejs())
            with tempattr(rdef, 'cardinality', '+*'):
                # formview has no parent info (pform). This is what happens
                # when an inline form is requested through AJAX.
                self.assertTrue(formview._get_removejs())
                fakeview = attrdict(dict(rtype='described_by_test', role='subject'))
                # formview is first, can't be removed
                formview.pform = attrdict(fields=[InlinedFormField(view=formview),
                                                  InlinedFormField(view=fakeview)])
                self.assertIsNone(formview._get_removejs())
                # formview isn't first, can be removed
                formview.pform = attrdict(fields=[InlinedFormField(view=fakeview),
                                                  InlinedFormField(view=formview)])
                self.assertTrue(formview._get_removejs())


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
