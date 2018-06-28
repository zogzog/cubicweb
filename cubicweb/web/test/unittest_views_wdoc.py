from cubicweb.devtools import testlib


class WdocViewsTC(testlib.CubicWebTC):

    def test(self):
        with self.admin_access.web_request(fid='main') as req:
            page = req.view('wdoc')
        self.assertIn(u'Site documentation', page)


if __name__ == '__main__':
    import unittest
    unittest.main()
