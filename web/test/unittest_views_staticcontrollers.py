from logilab.common import tempattr
from logilab.common.testlib import tag, Tags
from cubicweb.devtools.testlib import CubicWebTC

import os
import os.path as osp
import glob

from cubicweb.utils import HTMLHead
from cubicweb.web.views.staticcontrollers import ConcatFilesHandler

class StaticControllerCacheTC(CubicWebTC):

    tags = CubicWebTC.tags | Tags('static_controller', 'cache', 'http')


    def _publish_static_files(self, url, header={}):
        req = self.request(headers=header)
        req._url = url
        return self.app_handle_request(req, url), req

    def test_static_file_are_cached(self):
        _, req = self._publish_static_files('data/cubicweb.css')
        self.assertEqual(200, req.status_out)
        self.assertIn('last-modified', req.headers_out)
        next_headers = {
            'if-modified-since': req.get_response_header('last-modified', raw=True),
        }
        _, req = self._publish_static_files('data/cubicweb.css', next_headers)
        self.assertEqual(304, req.status_out)



class DataControllerTC(CubicWebTC):

    tags = CubicWebTC.tags | Tags('static_controller', 'data', 'http')

    def _publish_static_files(self, url, header={}):
        req = self.request(headers=header)
        req._url = url
        return self.app_handle_request(req, url), req

    def _check_datafile_ok(self, fname):
        _, req = self._publish_static_files(fname)
        self.assertEqual(200, req.status_out)
        self.assertIn('last-modified', req.headers_out)
        next_headers = {
            'if-modified-since': req.get_response_header('last-modified', raw=True),
        }
        _, req = self._publish_static_files(fname, next_headers)
        self.assertEqual(304, req.status_out)

    def _check_no_datafile(self, fname):
        _, req = self._publish_static_files(fname)
        self.assertEqual(404, req.status_out)

    def test_static_data_mode(self):
        hash = self.vreg.config.instance_md5_version()
        self.assertEqual(32, len(hash))

        with tempattr(self.vreg.config, 'mode', 'test'):
            self._check_datafile_ok('data/cubicweb.css')
            self._check_no_datafile('data/does/not/exist')
            self._check_no_datafile('data/%s/cubicweb.css' % ('0'*len(hash)))

        with tempattr(self.vreg.config, 'mode', 'notest'):
            self._check_datafile_ok('data/cubicweb.css')
            self._check_datafile_ok('data/%s/cubicweb.css' % hash)
            self._check_no_datafile('data/does/not/exist')
            self._check_no_datafile('data/%s/cubicweb.css' % ('0'*len(hash)))


class ConcatFilesTC(CubicWebTC):

    tags = CubicWebTC.tags | Tags('static_controller', 'concat')

    def tearDown(self):
        super(ConcatFilesTC, self).tearDown()
        self._cleanup_concat_cache()

    def _cleanup_concat_cache(self):
        uicachedir = osp.join(self.config.apphome, 'uicache')
        for fname in glob.glob(osp.join(uicachedir, 'cache_concat_*')):
            os.unlink(osp.join(uicachedir, fname))

    def _publish_js_files(self, js_files):
        req = self.request()
        head = HTMLHead(req)
        url = head.concat_urls([req.data_url(js_file) for js_file in js_files])[len(req.base_url()):]
        req._url = url
        return self.app_handle_request(req, url), req

    def expected_content(self, js_files):
        content = u''
        for js_file in js_files:
            dirpath, rid = self.config.locate_resource(js_file)
            if dirpath is not None: # ignore resources not found
                with open(osp.join(dirpath, rid)) as f:
                    content += f.read() + '\n'
        return content

    def test_cache(self):
        js_files = ('cubicweb.ajax.js', 'jquery.js')
        result, req = self._publish_js_files(js_files)
        self.assertNotEqual(404, req.status_out)
        # check result content
        self.assertEqual(result, self.expected_content(js_files))
        # make sure we kept a cached version on filesystem
        concat_hander = ConcatFilesHandler(self.config)
        filepath = concat_hander.build_filepath(js_files)
        self.assertTrue(osp.isfile(filepath))


    def test_invalid_file_in_debug_mode(self):
        js_files = ('cubicweb.ajax.js', 'dummy.js')
        # in debug mode, an error is raised
        self.config.debugmode = True
        try:
            result, req = self._publish_js_files(js_files)
            #print result
            self.assertEqual(404, req.status_out)
        finally:
            self.config.debugmode = False

    def test_invalid_file_in_production_mode(self):
        js_files = ('cubicweb.ajax.js', 'dummy.js')
        result, req = self._publish_js_files(js_files)
        self.assertNotEqual(404, req.status_out)
        # check result content
        self.assertEqual(result, self.expected_content(js_files))


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()

