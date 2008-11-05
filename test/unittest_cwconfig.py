import os
from tempfile import mktemp

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.changelog import Version

from cubicweb.devtools import ApptestConfiguration

def unabsolutize(path):
    parts = path.split(os.sep)
    for i, part in enumerate(parts):
        if part in ('cubicweb', 'cubes', 'cubes'):
            return '/'.join(parts[i+1:])
    raise Exception('duh? %s' % path)
    
class CubicWebConfigurationTC(TestCase):
    def setUp(self):
        self.config = ApptestConfiguration('data')
        self.config._cubes = ('eemail', 'efile')

    def test_reorder_cubes(self):
        # jpl depends on eemail and efile and ecomment
        # eemail depends on efile
        self.assertEquals(self.config.reorder_cubes(['efile', 'eemail', 'jpl']),
                          ('jpl', 'eemail', 'efile'))
        self.assertEquals(self.config.reorder_cubes(['eemail', 'efile', 'jpl']),
                          ('jpl', 'eemail', 'efile'))
        self.assertEquals(self.config.reorder_cubes(['eemail', 'jpl', 'efile']),
                          ('jpl', 'eemail', 'efile'))
        self.assertEquals(self.config.reorder_cubes(['efile', 'jpl', 'eemail']),
                          ('jpl', 'eemail', 'efile'))
        self.assertEquals(self.config.reorder_cubes(['jpl', 'efile', 'eemail']),
                          ('jpl', 'eemail', 'efile'))
        self.assertEquals(self.config.reorder_cubes(('jpl', 'eemail', 'efile')),
                          ('jpl', 'eemail', 'efile'))
        
    def test_reorder_cubes_recommends(self):
        from ecomment import __pkginfo__ as ecomment_pkginfo
        ecomment_pkginfo.__recommend__ = ('efile',)
        try:
            # eemail recommends ecomment
            # ecomment recommends efile
            self.assertEquals(self.config.reorder_cubes(('jpl', 'eemail', 'efile', 'ecomment')),
                              ('jpl', 'eemail', 'ecomment', 'efile'))
            self.assertEquals(self.config.reorder_cubes(('jpl', 'eemail', 'ecomment', 'efile')),
                              ('jpl', 'eemail', 'ecomment', 'efile'))
            self.assertEquals(self.config.reorder_cubes(('jpl', 'ecomment', 'eemail', 'efile')),
                              ('jpl', 'eemail', 'ecomment', 'efile'))
            self.assertEquals(self.config.reorder_cubes(('ecomment', 'jpl', 'eemail', 'efile')),
                              ('jpl', 'eemail', 'ecomment', 'efile'))
        finally:
            ecomment_pkginfo.__use__ = ()
            
        
#     def test_vc_config(self):
#         vcconf = self.config.vc_config()
#         self.assertIsInstance(vcconf['EEMAIL'], Version)
#         self.assertEquals(vcconf['EEMAIL'], (0, 3, 1))
#         self.assertEquals(vcconf['CW'], (2, 31, 2))
#         self.assertRaises(KeyError, vcconf.__getitem__, 'CW_VERSION')
#         self.assertRaises(KeyError, vcconf.__getitem__, 'CRM')
        
    def test_expand_cubes(self):
        self.assertEquals(self.config.expand_cubes(('eemail', 'eblog')),
                          ['eemail', 'eblog', 'efile'])

    def test_vregistry_path(self):
        self.assertEquals([unabsolutize(p) for p in self.config.vregistry_path()],
                          ['entities', 'web/views', 'sobjects',
                           'efile/entities.py', 'efile/views', 'efile/hooks.py',
                           'eemail/entities.py', 'eemail/views', 'eemail/hooks.py'])
            
if __name__ == '__main__':
    unittest_main()
