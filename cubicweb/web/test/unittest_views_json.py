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


class JsonViewsTC(CubicWebTC):
    anonymize = True
    res_jsonp_data = b'[["guests", 1]]'

    def setUp(self):
        super(JsonViewsTC, self).setUp()
        self.config.global_set_option('anonymize-jsonp-queries', self.anonymize)

    def test_json_rsetexport(self):
        with self.admin_access.web_request() as req:
            rset = req.execute(
                'Any GN,COUNT(X) GROUPBY GN ORDERBY GN WHERE X in_group G, G name GN')
            data = self.view('jsonexport', rset, req=req)
            self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/json'])
            self.assertListEqual(data, [["guests", 1], ["managers", 1]])

    def test_json_rsetexport_empty_rset(self):
        with self.admin_access.web_request() as req:
            rset = req.execute(u'Any X WHERE X is CWUser, X login "foobarbaz"')
            data = self.view('jsonexport', rset, req=req)
            self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/json'])
            self.assertListEqual(data, [])

    def test_json_rsetexport_with_jsonp(self):
        with self.admin_access.web_request() as req:
            req.form.update({'callback': u'foo',
                             'rql': u'Any GN,COUNT(X) GROUPBY GN ORDERBY GN '
                             'WHERE X in_group G, G name GN'})
            data = self.ctrl_publish(req, ctrl='jsonp')
            self.assertIsInstance(data, bytes)
            self.assertEqual(req.headers_out.getRawHeaders('content-type'),
                             ['application/javascript'])
            # because jsonp anonymizes data, only 'guests' group should be found
            self.assertEqual(data, b'foo(' + self.res_jsonp_data + b')')

    def test_json_rsetexport_with_jsonp_and_bad_vid(self):
        with self.admin_access.web_request() as req:
            req.form.update({'callback': 'foo',
                             # "vid" parameter should be ignored by jsonp controller
                             'vid': 'table',
                             'rql': 'Any GN,COUNT(X) GROUPBY GN ORDERBY GN '
                             'WHERE X in_group G, G name GN'})
            data = self.ctrl_publish(req, ctrl='jsonp')
            self.assertEqual(req.headers_out.getRawHeaders('content-type'),
                             ['application/javascript'])
            # result should be plain json, not the table view
            self.assertEqual(data, b'foo(' + self.res_jsonp_data + b')')

    def test_json_ersetexport(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any G ORDERBY GN WHERE G is CWGroup, G name GN')
            data = self.view('ejsonexport', rset, req=req)
            self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/json'])
            self.assertEqual(data[0]['name'], 'guests')
            self.assertEqual(data[1]['name'], 'managers')

            rset = req.execute(u'Any G WHERE G is CWGroup, G name "foo"')
            data = self.view('ejsonexport', rset, req=req)
            self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/json'])
            self.assertEqual(data, [])


class NotAnonymousJsonViewsTC(JsonViewsTC):
    anonymize = False
    res_jsonp_data = b'[["guests", 1], ["managers", 1]]'


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
