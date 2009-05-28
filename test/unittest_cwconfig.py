"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import sys
import os
from os.path import dirname, join, abspath
from tempfile import mktemp

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.changelog import Version

from cubicweb.devtools import ApptestConfiguration

def unabsolutize(path):
    parts = path.split(os.sep)
    for i, part in reversed(tuple(enumerate(parts))):
        if part.startswith('cubicweb') or part == 'cubes':
            return '/'.join(parts[i+1:])
    raise Exception('duh? %s' % path)

class CubicWebConfigurationTC(TestCase):
    def setUp(self):
        self.config = ApptestConfiguration('data')
        self.config._cubes = ('email', 'file')

    def tearDown(self):
        os.environ.pop('CW_CUBES_PATH', None)

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
                           'email/entities.py', 'email/views', 'email/hooks.py',
                           'test/data/entities.py'])

    def test_cubes_path(self):
        # make sure we don't import the email cube, but the stdlib email package
        import email
        self.assertNotEquals(dirname(email.__file__), self.config.CUBES_DIR)
        os.environ['CW_CUBES_PATH'] = join(dirname(__file__), 'data', 'cubes')
        self.assertEquals(self.config.cubes_search_path(),
                          [abspath(join(dirname(__file__), 'data', 'cubes')),
                           self.config.CUBES_DIR])
        os.environ['CW_CUBES_PATH'] = '%s%s%s%s%s' % (join(dirname(__file__), 'data', 'cubes'),
                                                      os.pathsep, self.config.CUBES_DIR,
                                                      os.pathsep, 'unexistant')
        # filter out unexistant and duplicates
        self.assertEquals(self.config.cubes_search_path(),
                          [abspath(join(dirname(__file__), 'data', 'cubes')),
                           self.config.CUBES_DIR])
        self.failUnless('mycube' in self.config.available_cubes())
        # test cubes python path
        self.config.adjust_sys_path()
        import cubes
        self.assertEquals(cubes.__path__, self.config.cubes_search_path())
        # this import should succeed once path is adjusted
        from cubes import mycube
        self.assertEquals(mycube.__path__, [abspath(join(dirname(__file__), 'data', 'cubes', 'mycube'))])
        # file cube should be overriden by the one found in data/cubes
        sys.modules.pop('cubes.file', None)
        del cubes.file
        from cubes import file
        self.assertEquals(file.__path__, [abspath(join(dirname(__file__), 'data', 'cubes', 'file'))])


if __name__ == '__main__':
    unittest_main()
