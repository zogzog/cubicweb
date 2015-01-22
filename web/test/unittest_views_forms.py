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

from cubicweb.devtools.testlib import CubicWebTC

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


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()

