from __future__ import with_statement

from cubicweb.devtools.testlib import CubicWebTC

import os
import os.path as osp
import glob

from cubicweb.utils import HTMLHead
from cubicweb.web import StatusResponse
from cubicweb.web.views.staticcontrollers import ConcatFilesHandler

class ConcatFilesTC(CubicWebTC):

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
        return self.app_publish(req, url)

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
        try:
            result = self._publish_js_files(js_files)
        except StatusResponse, exc:
            if exc.status == 404:
                self.fail('unable to serve cubicweb.js+jquery.js')
            # let the exception propagate for any other status (e.g 500)
            raise
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
            result = self._publish_js_files(js_files)
            self.fail('invalid concat js should return a 404 in debug mode')
        except StatusResponse, exc:
            if exc.status != 404:
                self.fail('invalid concat js should return a 404 in debug mode')
        finally:
            self.config.debugmode = False

    def test_invalid_file_in_production_mode(self):
        js_files = ('cubicweb.ajax.js', 'dummy.js')
        try:
            result = self._publish_js_files(js_files)
        except StatusResponse, exc:
            if exc.status == 404:
                self.fail('invalid concat js should NOT return a 404 in debug mode')
            # let the exception propagate for any other status (e.g 500)
            raise
        # check result content
        self.assertEqual(result, self.expected_content(js_files))


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()

