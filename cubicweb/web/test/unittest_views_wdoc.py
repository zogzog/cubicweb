from cubicweb.devtools import testlib


class WdocViewsTC(testlib.CubicWebTC):

    def test(self):
        with self.admin_access.web_request(fid='main') as req:
            page = req.view('wdoc')
        self.assertIn(u'Site documentation', page)
        # This part is renderend through rst extension (..winclude directive).
        self.assertIn(u'This web application is based on the CubicWeb knowledge management system',
                      page)


if __name__ == '__main__':
    import unittest
    unittest.main()
