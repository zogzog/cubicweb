from logilab.common import tempattr
from cubicweb.devtools.testlib import CubicWebTC


class SynchronizeSourceTC(CubicWebTC):
    def test_synchronize_view(self):
        with self.admin_access.web_request(vid='cw.source-sync') as req:
            source = req.create_entity('CWSource', name=u'ext', type=u'datafeed',
                                       parser=u'cw.entityxml')
            req.cnx.commit()

            self.threads = 0

            def threaded_task(func):
                self.threads += 1

            with tempattr(req.cnx.repo, 'threaded_task', threaded_task):
                path, args = self.expect_redirect_handle_request(
                    req, path=source.rest_path())
                self.assertEqual(self.threads, 1)
                self.assertTrue(path.startswith('cwdataimport/'))


if __name__ == '__main__':
    import unittest
    unittest.main()
