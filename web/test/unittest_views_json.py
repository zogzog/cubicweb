from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.utils import json

class JsonViewsTC(CubicWebTC):

    def test_json_rsetexport(self):
        req = self.request()
        rset = req.execute('Any GN,COUNT(X) GROUPBY GN ORDERBY GN WHERE X in_group G, G name GN')
        data = self.view('jsonexport', rset)
        self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/json'])
        self.assertEqual(data, '[["guests", 1], ["managers", 1]]')

    def test_json_rsetexport_with_jsonp(self):
        req = self.request()
        req.form.update({'callback': 'foo',
                         'rql': 'Any GN,COUNT(X) GROUPBY GN ORDERBY GN WHERE X in_group G, G name GN',
                         })
        data = self.ctrl_publish(req, ctrl='jsonp')
        self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/javascript'])
        # because jsonp anonymizes data, only 'guests' group should be found
        self.assertEqual(data, 'foo([["guests", 1]])')

    def test_json_rsetexport_with_jsonp_and_bad_vid(self):
        req = self.request()
        req.form.update({'callback': 'foo',
                         'vid': 'table', # <-- this parameter should be ignored by jsonp controller
                         'rql': 'Any GN,COUNT(X) GROUPBY GN ORDERBY GN WHERE X in_group G, G name GN',
                         })
        data = self.ctrl_publish(req, ctrl='jsonp')
        self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/javascript'])
        # result should be plain json, not the table view
        self.assertEqual(data, 'foo([["guests", 1]])')

    def test_json_ersetexport(self):
        req = self.request()
        rset = req.execute('Any G ORDERBY GN WHERE G is CWGroup, G name GN')
        data = json.loads(self.view('ejsonexport', rset))
        self.assertEqual(req.headers_out.getRawHeaders('content-type'), ['application/json'])
        self.assertEqual(data[0]['name'], 'guests')
        self.assertEqual(data[1]['name'], 'managers')


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
