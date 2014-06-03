import os
from os.path import join, dirname
from shutil import rmtree

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.web.propertysheet import PropertySheet, lazystr

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
        self.assertEqual(ps['logo'], 'http://cwtest.com/logo.png')
        # defined by sheet1, overriden by sheet2
        self.assertEqual(ps['bgcolor'], '#FFFFFF')
        # defined by sheet2
        self.assertEqual(ps['fontcolor'], 'black')
        # defined by sheet1, extended by sheet2
        self.assertEqual(ps['stylesheets'], ['http://cwtest.com/cubicweb.css',
                                              'http://cwtest.com/mycube.css'])
        # lazy string defined by sheet1
        self.assertIsInstance(ps['lazy'], lazystr)
        self.assertEqual(str(ps['lazy']), '#FFFFFF')
        # test compilation
        self.assertEqual(ps.compile('a {bgcolor: %(bgcolor)s; size: 1%;}'),
                          'a {bgcolor: #FFFFFF; size: 1%;}')
        self.assertEqual(ps.process_resource(DATADIR, 'pouet.css'),
                          CACHEDIR)
        self.assertIn('pouet.css', ps._cache)
        self.assertFalse(ps.need_reload())
        os.utime(join(DATADIR, 'sheet1.py'), None)
        self.assertIn('pouet.css', ps._cache)
        self.assertTrue(ps.need_reload())
        self.assertIn('pouet.css', ps._cache)
        ps.reload()
        self.assertNotIn('pouet.css', ps._cache)
        self.assertFalse(ps.need_reload())
        ps.process_resource(DATADIR, 'pouet.css') # put in cache
        os.utime(join(DATADIR, 'pouet.css'), None)
        self.assertFalse(ps.need_reload())
        self.assertNotIn('pouet.css', ps._cache)

if __name__ == '__main__':
    unittest_main()
