# -*- coding: utf-8 -*-
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


class CSVExportViewsTC(CubicWebTC):

    def test_csvexport(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any GN,COUNT(X) GROUPBY GN ORDERBY GN '
                               'WHERE X in_group G, G name GN')
            data = self.view('csvexport', rset, req=req)
            self.assertEqual(req.headers_out.getRawHeaders('content-type'),
                             ['text/comma-separated-values;charset=UTF-8'])
            expected_data = "String;COUNT(CWUser)\nguests;1\nmanagers;1"
            self.assertMultiLineEqual(expected_data, data)

    def test_csvexport_on_empty_rset(self):
        """Should return the CSV header.
        """
        with self.admin_access.web_request() as req:
            rset = req.execute('Any GN,COUNT(X) GROUPBY GN ORDERBY GN '
                               'WHERE X in_group G, G name GN, X login "Miles"')
            data = self.view('csvexport', rset, req=req)
            self.assertEqual(req.headers_out.getRawHeaders('content-type'),
                             ['text/comma-separated-values;charset=UTF-8'])
            expected_data = "String;COUNT(CWUser)"
            self.assertMultiLineEqual(expected_data, data)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
