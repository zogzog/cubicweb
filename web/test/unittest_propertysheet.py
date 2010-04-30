from os.path import join, dirname
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.web.propertysheet import *

DATADIR = join(dirname(__file__), 'data')
class PropertySheetTC(TestCase):

    def test(self):
        ps = PropertySheet(None, datadir_url='http://cwtest.com')
        ps.load(join(DATADIR, 'sheet1.py'))
        ps.load(join(DATADIR, 'sheet2.py'))
        # defined by sheet1
        self.assertEquals(ps['logo'], 'http://cwtest.com/logo.png')
        # defined by sheet1, overriden by sheet2
        self.assertEquals(ps['bgcolor'], '#FFFFFF')
        # defined by sheet2
        self.assertEquals(ps['fontcolor'], 'black')
        # defined by sheet1, extended by sheet2
        self.assertEquals(ps['stylesheets'], ['http://cwtest.com/cubicweb.css',
                                              'http://cwtest.com/mycube.css'])
        self.assertEquals(ps.compile('a {bgcolor: %(bgcolor)s; size: 1%;}'),
                          'a {bgcolor: #FFFFFF; size: 1%;}')

if __name__ == '__main__':
    unittest_main()
