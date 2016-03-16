# -*- coding: utf-8 -*-
# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from contextlib import contextmanager

from logilab.common import tempattr
from logilab.common.testlib import Tags
from cubicweb.devtools.testlib import CubicWebTC

import os
import os.path as osp
import glob

from cubicweb.utils import HTMLHead
from cubicweb.web.views.staticcontrollers import ConcatFilesHandler

class staticfilespublishermixin(object):

    @contextmanager
    def _publish_static_files(self, url, header={}):
        with self.admin_access.web_request(headers=header) as req:
            req._url = url
            self.app_handle_request(req, url)
            yield req

class StaticControllerCacheTC(staticfilespublishermixin, CubicWebTC):
    tags = CubicWebTC.tags | Tags('static_controller', 'cache', 'http')

    def test_static_file_are_cached(self):
        with self._publish_static_files('data/cubicweb.css') as req:
            self.assertEqual(200, req.status_out)
            self.assertIn('last-modified', req.headers_out)
        next_headers = {
            'if-modified-since': req.get_response_header('last-modified', raw=True),
        }
        with self._publish_static_files('data/cubicweb.css', next_headers) as req:
            self.assertEqual(304, req.status_out)

class StaticDirectoryControllerTC(staticfilespublishermixin, CubicWebTC):

    def test_check_static_dir_access(self):
        """write a file in the static directory and test the access"""
        staticdir = osp.join(self.vreg.config.static_directory)
        if not os.path.exists(staticdir):
            os.makedirs(staticdir)
        filename = osp.join(staticdir, 'test')
        with open(filename, 'a') as f:
            with self._publish_static_files('static/test') as req:
                self.assertEqual(200, req.status_out)

class DataControllerTC(staticfilespublishermixin, CubicWebTC):
    tags = CubicWebTC.tags | Tags('static_controller', 'data', 'http')

    def _check_datafile_ok(self, fname):
        with self._publish_static_files(fname) as req:
            self.assertEqual(200, req.status_out)
            self.assertIn('last-modified', req.headers_out)
            self.assertIn('expires', req.headers_out)
            self.assertEqual(req.get_response_header('cache-control'),
                             {'max-age': 604800})
        next_headers = {
            'if-modified-since': req.get_response_header('last-modified', raw=True),
        }
        with self._publish_static_files(fname, next_headers) as req:
            self.assertEqual(304, req.status_out)

    def _check_datafile_redirect(self, fname, expected):
        with self._publish_static_files(fname) as req:
            self.assertEqual(302, req.status_out)
            self.assertEqual(req.get_response_header('location'),
                             req.base_url() + expected)

    def _check_no_datafile(self, fname):
        with self._publish_static_files(fname) as req:
            self.assertEqual(404, req.status_out)

    def test_static_data_mode(self):
        hash = self.vreg.config.instance_md5_version()
        self.assertEqual(32, len(hash))

        with tempattr(self.vreg.config, 'mode', 'test'):
            self._check_datafile_ok('data/cubicweb.css')
            self._check_no_datafile('data/does/not/exist')
            self._check_no_datafile('data/%s/cubicweb.css' % ('0'*len(hash)))

        with tempattr(self.vreg.config, 'mode', 'notest'):
            self.config._init_base_url()  # reset config.datadir_url
            self._check_datafile_redirect('data/cubicweb.css', 'data/%s/cubicweb.css' % hash)
            self._check_datafile_ok('data/%s/cubicweb.css' % hash)
            self._check_no_datafile('data/%s/does/not/exist' % hash)
            self._check_datafile_redirect('data/%s/does/not/exist' % ('0'*len(hash)),
                                          'data/%s/%s/does/not/exist' % (hash, '0'*len(hash)))


class ConcatFilesTC(CubicWebTC):

    tags = CubicWebTC.tags | Tags('static_controller', 'concat')

    def tearDown(self):
        super(ConcatFilesTC, self).tearDown()
        self._cleanup_concat_cache()

    def _cleanup_concat_cache(self):
        uicachedir = osp.join(self.config.apphome, 'uicache')
        for fname in glob.glob(osp.join(uicachedir, 'cache_concat_*')):
            os.unlink(osp.join(uicachedir, fname))

    @contextmanager
    def _publish_js_files(self, js_files):
        with self.admin_access.web_request() as req:
            head = HTMLHead(req)
            url = head.concat_urls([req.data_url(js_file)
                                    for js_file in js_files])[len(req.base_url()):]
            req._url = url
            res = self.app_handle_request(req, url)
            yield res, req

    def expected_content(self, js_files):
        content = b''
        for js_file in js_files:
            dirpath, rid = self.config.locate_resource(js_file)
            if dirpath is not None: # ignore resources not found
                with open(osp.join(dirpath, rid), 'rb') as f:
                    content += f.read() + b'\n'
        return content

    def test_cache(self):
        js_files = ('cubicweb.ajax.js', 'jquery.js')
        with self._publish_js_files(js_files) as (result, req):
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
            with self._publish_js_files(js_files) as (result, req):
                #print result
                self.assertEqual(404, req.status_out)
        finally:
            self.config.debugmode = False

    def test_invalid_file_in_production_mode(self):
        js_files = ('cubicweb.ajax.js', 'dummy.js')
        with self._publish_js_files(js_files) as (result, req):
            self.assertNotEqual(404, req.status_out)
            # check result content
            self.assertEqual(result, self.expected_content(js_files))


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
