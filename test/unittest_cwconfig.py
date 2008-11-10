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
        self.config._cubes = ('email', 'file')

    def test_reorder_cubes(self):
        # jpl depends on email and file and comment
        # email depends on file
        self.assertEquals(self.config.reorder_cubes(['file', 'email', 'jpl']),
                          ('jpl', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['email', 'file', 'jpl']),
                          ('jpl', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['email', 'jpl', 'file']),
                          ('jpl', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['file', 'jpl', 'email']),
                          ('jpl', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['jpl', 'file', 'email']),
                          ('jpl', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(('jpl', 'email', 'file')),
                          ('jpl', 'email', 'file'))
        
    def test_reorder_cubes_recommends(self):
        from cubes.comment import __pkginfo__ as comment_pkginfo
        comment_pkginfo.__recommend__ = ('file',)
        try:
            # email recommends comment
            # comment recommends file
            self.assertEquals(self.config.reorder_cubes(('jpl', 'email', 'file', 'comment')),
                              ('jpl', 'email', 'comment', 'file'))
            self.assertEquals(self.config.reorder_cubes(('jpl', 'email', 'comment', 'file')),
                              ('jpl', 'email', 'comment', 'file'))
            self.assertEquals(self.config.reorder_cubes(('jpl', 'comment', 'email', 'file')),
                              ('jpl', 'email', 'comment', 'file'))
            self.assertEquals(self.config.reorder_cubes(('comment', 'jpl', 'email', 'file')),
                              ('jpl', 'email', 'comment', 'file'))
        finally:
            comment_pkginfo.__use__ = ()
            
        
#     def test_vc_config(self):
#         vcconf = self.config.vc_config()
#         self.assertIsInstance(vcconf['EEMAIL'], Version)
#         self.assertEquals(vcconf['EEMAIL'], (0, 3, 1))
#         self.assertEquals(vcconf['CW'], (2, 31, 2))
#         self.assertRaises(KeyError, vcconf.__getitem__, 'CW_VERSION')
#         self.assertRaises(KeyError, vcconf.__getitem__, 'CRM')
        
    def test_expand_cubes(self):
        self.assertEquals(self.config.expand_cubes(('email', 'eblog')),
                          ['email', 'eblog', 'file'])

    def test_vregistry_path(self):
        self.assertEquals([unabsolutize(p) for p in self.config.vregistry_path()],
                          ['entities', 'web/views', 'sobjects',
                           'file/entities.py', 'file/views', 'file/hooks.py',
                           'email/entities.py', 'email/views', 'email/hooks.py'])
            
if __name__ == '__main__':
    unittest_main()
