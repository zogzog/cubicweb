# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import os, os.path as osp, glob

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.etwist.server import (host_prefixed_baseurl, ConcatFiles,
                                    ConcatFileNotFoundError)


class HostPrefixedBaseURLTC(CubicWebTC):

    def _check(self, baseurl, host, waited):
        self.assertEqual(host_prefixed_baseurl(baseurl, host), waited,
                         'baseurl %s called through host %s should be considered as %s'
                         % (baseurl, host, waited))

    def test1(self):
        self._check('http://www.cubicweb.org/hg/', 'code.cubicweb.org',
                    'http://code.cubicweb.org/hg/')

    def test2(self):
        self._check('http://www.cubicweb.org/hg/', 'cubicweb.org',
                    'http://www.cubicweb.org/hg/')

    def test3(self):
        self._check('http://cubicweb.org/hg/', 'code.cubicweb.org',
                    'http://code.cubicweb.org/hg/')

    def test4(self):
        self._check('http://www.cubicweb.org/hg/', 'localhost',
                    'http://www.cubicweb.org/hg/')

    def test5(self):
        self._check('http://www.cubicweb.org/cubes/', 'hg.code.cubicweb.org',
                    'http://hg.code.cubicweb.org/cubes/')

    def test6(self):
        self._check('http://localhost:8080/hg/', 'code.cubicweb.org',
                    'http://localhost:8080/hg/')


class ConcatFilesTC(CubicWebTC):

    def tearDown(self):
        super(ConcatFilesTC, self).tearDown()
        self._cleanup_concat_cache()
        self.config.debugmode = False

    def _cleanup_concat_cache(self):
        uicachedir = osp.join(self.config.apphome, 'uicache')
        for fname in glob.glob(osp.join(uicachedir, 'cache_concat_*')):
            os.unlink(osp.join(uicachedir, fname))

    def test_cache(self):
        concat = ConcatFiles(self.config, ('cubicweb.ajax.js', 'jquery.js'))
        self.failUnless(osp.isfile(concat.path))

    def test_404(self):
        # when not in debug mode, should not crash
        ConcatFiles(self.config, ('cubicweb.ajax.js', 'dummy.js'))
        # in debug mode, raise error
        self.config.debugmode = True
        try:
            self.assertRaises(ConcatFileNotFoundError, ConcatFiles, self.config,
                              ('cubicweb.ajax.js', 'dummy.js'))
        finally:
            self.config.debugmode = False
