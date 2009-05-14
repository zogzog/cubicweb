import os

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools._apptest import FakeRequest
from cubicweb.devtools import ApptestConfiguration

class WebconfigTC(TestCase):
    def setUp(self):
        self.config = ApptestConfiguration('data')
        self.config._cubes = ['file']
        self.config.load_configuration()

    def test_nonregr_print_css_as_list(self):
        """make sure PRINT_CSS *must* is a list"""
        config = self.config
        req = FakeRequest()
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


