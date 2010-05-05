import os
from os.path import join, dirname
from shutil import rmtree

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.web.propertysheet import *

DATADIR = join(dirname(__file__), 'data')
CACHEDIR = join(DATADIR, 'uicache')

class PropertySheetTC(TestCase):

    def tearDown(self):
        rmtree(CACHEDIR)

    def test(self):
        ps = PropertySheet(CACHEDIR, datadir_url='http://cwtest.com')
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
        self.assertEquals(ps.process_resource(DATADIR, 'pouet.css'),
                          CACHEDIR)
        self.failUnless('pouet.css' in ps._cache)
        self.failIf(ps.need_reload())
        os.utime(join(DATADIR, 'sheet1.py'), None)
        self.failUnless('pouet.css' in ps._cache)
        self.failUnless(ps.need_reload())
        self.failUnless('pouet.css' in ps._cache)
        ps.reload()
        self.failIf('pouet.css' in ps._cache)
        self.failIf(ps.need_reload())
        ps.process_resource(DATADIR, 'pouet.css') # put in cache
        os.utime(join(DATADIR, 'pouet.css'), None)
        self.failIf(ps.need_reload())
        self.failIf('pouet.css' in ps._cache)

if __name__ == '__main__':
    unittest_main()
