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
"""

"""
import os

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools import ApptestConfiguration, fake

class WebconfigTC(TestCase):
    def setUp(self):
        self.config = ApptestConfiguration('data')
        self.config._cubes = ['file']
        self.config.load_configuration()

    def test_nonregr_print_css_as_list(self):
        """make sure PRINT_CSS *must* is a list"""
        config = self.config
        req = fake.FakeRequest()
        print_css = req.external_resource('STYLESHEETS_PRINT')
        self.failUnless(isinstance(print_css, list))
        ie_css = req.external_resource('IE_STYLESHEETS')
        self.failUnless(isinstance(ie_css, list))

    def test_locate_resource(self):
        self.failUnless('FILE_ICON' in self.config.ext_resources)
        rname = self.config.ext_resources['FILE_ICON'].replace('DATADIR/', '')
        self.failUnless('file' in self.config.locate_resource(rname).split(os.sep))
        cubicwebcsspath = self.config.locate_resource('cubicweb.css').split(os.sep)
        self.failUnless('web' in cubicwebcsspath or 'shared' in cubicwebcsspath) # 'shared' if tests under apycot

if __name__ == '__main__':
    unittest_main()


