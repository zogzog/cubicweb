# -*- coding: utf-8 -*-
# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb.web.webconfig unit tests"""

import os

from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools import ApptestConfiguration, fake

class WebconfigTC(TestCase):
    def setUp(self):
        # need explicit None if dirname(__file__) is empty, see
        # ApptestConfiguration.__init__
        self.config = ApptestConfiguration('data', apphome=os.path.dirname(__file__) or None)
        self.config._cubes = ['file']
        self.config.load_configuration()

    def test_nonregr_print_css_as_list(self):
        """make sure PRINT_CSS *must* is a list"""
        config = self.config
        print_css = config.uiprops['STYLESHEETS_PRINT']
        self.assertTrue(isinstance(print_css, list))
        ie_css = config.uiprops['STYLESHEETS_IE']
        self.assertTrue(isinstance(ie_css, list))

    def test_locate_resource(self):
        self.assertIn('FILE_ICON', self.config.uiprops)
        rname = self.config.uiprops['FILE_ICON'].replace(self.config.datadir_url, '')
        self.assertIn('file', self.config.locate_resource(rname)[0].split(os.sep))
        cubicwebcsspath = self.config.locate_resource('cubicweb.css')[0].split(os.sep)

        # 'shared' if tests under apycot
        self.assertTrue('web' in cubicwebcsspath or 'shared' in cubicwebcsspath,
                        'neither "web" nor "shared" found in cubicwebcsspath (%s)'
                        % cubicwebcsspath)

    def test_sign_text(self):
        signature = self.config.sign_text(u'hôp')
        self.assertTrue(self.config.check_text_sign(u'hôp', signature))

if __name__ == '__main__':
    unittest_main()


