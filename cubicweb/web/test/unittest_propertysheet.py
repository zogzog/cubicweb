import os
from os.path import join, dirname
from shutil import rmtree
import errno
import tempfile
from unittest import TestCase, main

from cubicweb.web.propertysheet import PropertySheet, lazystr


DATADIR = join(dirname(__file__), 'data')


class PropertySheetTC(TestCase):

    def setUp(self):
        uicache = join(DATADIR, 'uicache')
        try:
            os.makedirs(uicache)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        self.cachedir = tempfile.mkdtemp(dir=uicache)

    def tearDown(self):
        rmtree(self.cachedir)

    def data(self, filename):
        return join(DATADIR, filename)

    def test(self):
        ps = PropertySheet(self.cachedir, datadir_url='http://cwtest.com')
        ps.load(self.data('sheet1.py'))
        ps.load(self.data('sheet2.py'))
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
                         self.cachedir)
        self.assertFalse(ps.need_reload())
        os.utime(self.data('sheet1.py'), None)
        self.assertTrue(ps.need_reload())
        ps.reload()
        self.assertFalse(ps.need_reload())
        ps.process_resource(DATADIR, 'pouet.css')  # put in cache
        os.utime(self.data('pouet.css'), None)
        self.assertFalse(ps.need_reload())

    def test_chmod(self):
        ps = PropertySheet(self.cachedir, datadir_url='http://cwtest.com')
        ps.load(self.data('sheet1.py'))
        rdir = ps.process_resource(DATADIR, 'pouet.css')
        mode = os.stat(join(rdir, 'pouet.css')).st_mode
        self.assertEqual(('%o' % mode)[-4:], '0644')


if __name__ == '__main__':
    main()
