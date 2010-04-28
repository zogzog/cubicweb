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
import sys
import os
import tempfile
from os.path import dirname, join, abspath

from logilab.common.modutils import cleanup_sys_modules
from logilab.common.testlib import (TestCase, unittest_main,
                                    with_tempdir)
from logilab.common.changelog import Version

from cubicweb.devtools import ApptestConfiguration
from cubicweb.cwconfig import _find_prefix

def unabsolutize(path):
    parts = path.split(os.sep)
    for i, part in reversed(tuple(enumerate(parts))):
        if part.startswith('cubicweb') or part == 'cubes':
            return '/'.join(parts[i+1:])
    raise Exception('duh? %s' % path)

CUSTOM_CUBES_DIR = abspath(join(dirname(__file__), 'data', 'cubes'))


class CubicWebConfigurationTC(TestCase):
    def setUp(self):
        cleanup_sys_modules([CUSTOM_CUBES_DIR, ApptestConfiguration.CUBES_DIR])
        self.config = ApptestConfiguration('data')
        self.config._cubes = ('email', 'file')

    def tearDown(self):
        ApptestConfiguration.CUBES_PATH = []

    def test_reorder_cubes(self):
        # jpl depends on email and file and comment
        # email depends on file
        self.assertEquals(self.config.reorder_cubes(['file', 'email', 'forge']),
                          ('forge', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['email', 'file', 'forge']),
                          ('forge', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['email', 'forge', 'file']),
                          ('forge', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['file', 'forge', 'email']),
                          ('forge', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(['forge', 'file', 'email']),
                          ('forge', 'email', 'file'))
        self.assertEquals(self.config.reorder_cubes(('forge', 'email', 'file')),
                          ('forge', 'email', 'file'))

    def test_reorder_cubes_recommends(self):
        from cubes.comment import __pkginfo__ as comment_pkginfo
        comment_pkginfo.__recommends_cubes__ = {'file': None}
        try:
            # email recommends comment
            # comment recommends file
            self.assertEquals(self.config.reorder_cubes(('forge', 'email', 'file', 'comment')),
                              ('forge', 'email', 'comment', 'file'))
            self.assertEquals(self.config.reorder_cubes(('forge', 'email', 'comment', 'file')),
                              ('forge', 'email', 'comment', 'file'))
            self.assertEquals(self.config.reorder_cubes(('forge', 'comment', 'email', 'file')),
                              ('forge', 'email', 'comment', 'file'))
            self.assertEquals(self.config.reorder_cubes(('comment', 'forge', 'email', 'file')),
                              ('forge', 'email', 'comment', 'file'))
        finally:
            comment_pkginfo.__recommends_cubes__ = {}


#     def test_vc_config(self):
#         vcconf = self.config.vc_config()
#         self.assertIsInstance(vcconf['EEMAIL'], Version)
#         self.assertEquals(vcconf['EEMAIL'], (0, 3, 1))
#         self.assertEquals(vcconf['CW'], (2, 31, 2))
#         self.assertRaises(KeyError, vcconf.__getitem__, 'CW_VERSION')
#         self.assertRaises(KeyError, vcconf.__getitem__, 'CRM')

    def test_expand_cubes(self):
        self.assertEquals(self.config.expand_cubes(('email', 'blog')),
                          ['email', 'blog', 'file'])

    def test_vregistry_path(self):
        self.assertEquals([unabsolutize(p) for p in self.config.vregistry_path()],
                          ['entities', 'web/views', 'sobjects', 'hooks',
                           'file/entities.py', 'file/views', 'file/hooks.py',
                           'email/entities.py', 'email/views', 'email/hooks.py',
                           'test/data/entities.py', 'test/data/views.py'])

    def test_cubes_path(self):
        # make sure we don't import the email cube, but the stdlib email package
        import email
        self.assertNotEquals(dirname(email.__file__), self.config.CUBES_DIR)
        self.config.__class__.CUBES_PATH = [CUSTOM_CUBES_DIR]
        self.assertEquals(self.config.cubes_search_path(),
                          [CUSTOM_CUBES_DIR, self.config.CUBES_DIR])
        self.config.__class__.CUBES_PATH = [CUSTOM_CUBES_DIR,
                                            self.config.CUBES_DIR, 'unexistant']
        # filter out unexistant and duplicates
        self.assertEquals(self.config.cubes_search_path(),
                          [CUSTOM_CUBES_DIR,
                           self.config.CUBES_DIR])
        self.failUnless('mycube' in self.config.available_cubes())
        # test cubes python path
        self.config.adjust_sys_path()
        import cubes
        self.assertEquals(cubes.__path__, self.config.cubes_search_path())
        # this import should succeed once path is adjusted
        from cubes import mycube
        self.assertEquals(mycube.__path__, [join(CUSTOM_CUBES_DIR, 'mycube')])
        # file cube should be overriden by the one found in data/cubes
        sys.modules.pop('cubes.file', None)
        del cubes.file
        from cubes import file
        self.assertEquals(file.__path__, [join(CUSTOM_CUBES_DIR, 'file')])

class FindPrefixTC(TestCase):
    def make_dirs(self, *args):
        path = join(tempfile.tempdir, *args)
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def make_file(self, *args):
        self.make_dirs(*args[: -1])
        file_path = join(tempfile.tempdir, *args)
        file_obj = open(file_path, 'w')
        file_obj.write('""" None """')
        file_obj.close()
        return file_path

    @with_tempdir
    def test_samedir(self):
        prefix = tempfile.tempdir
        self.make_dirs('share', 'cubicweb')
        self.assertEquals(_find_prefix(prefix), prefix)

    @with_tempdir
    def test_samedir_filepath(self):
        prefix = tempfile.tempdir
        self.make_dirs('share', 'cubicweb')
        file_path = self.make_file('bob.py')
        self.assertEquals(_find_prefix(file_path), prefix)

    @with_tempdir
    def test_dir_inside_prefix(self):
        prefix = tempfile.tempdir
        self.make_dirs('share', 'cubicweb')
        dir_path = self.make_dirs('bob')
        self.assertEquals(_find_prefix(dir_path), prefix)

    @with_tempdir
    def test_file_in_dir_inside_prefix(self):
        prefix = tempfile.tempdir
        self.make_dirs('share', 'cubicweb')
        file_path = self.make_file('bob', 'toto.py')
        self.assertEquals(_find_prefix(file_path), prefix)

    @with_tempdir
    def test_file_in_deeper_dir_inside_prefix(self):
        prefix = tempfile.tempdir
        self.make_dirs('share', 'cubicweb')
        file_path = self.make_file('bob', 'pyves', 'alain', 'adim', 'syt', 'toto.py')
        self.assertEquals(_find_prefix(file_path), prefix)

    @with_tempdir
    def test_multiple_candidate_prefix(self):
        self.make_dirs('share', 'cubicweb')
        prefix = self.make_dirs('bob')
        self.make_dirs('bob', 'share', 'cubicweb')
        file_path = self.make_file('bob', 'pyves', 'alain', 'adim', 'syt', 'toto.py')
        self.assertEquals(_find_prefix(file_path), prefix)

    @with_tempdir
    def test_sister_candidate_prefix(self):
        prefix = tempfile.tempdir
        self.make_dirs('share', 'cubicweb')
        self.make_dirs('bob', 'share', 'cubicweb')
        file_path = self.make_file('bell', 'toto.py')
        self.assertEquals(_find_prefix(file_path), prefix)

    @with_tempdir
    def test_multiple_parent_candidate_prefix(self):
        self.make_dirs('share', 'cubicweb')
        prefix = self.make_dirs('share', 'cubicweb', 'bob')
        self.make_dirs('share', 'cubicweb', 'bob', 'share', 'cubicweb')
        file_path = self.make_file('share', 'cubicweb', 'bob', 'pyves', 'alain', 'adim', 'syt', 'toto.py')
        self.assertEquals(_find_prefix(file_path), prefix)

    @with_tempdir
    def test_upper_candidate_prefix(self):
        prefix = tempfile.tempdir
        self.make_dirs('share', 'cubicweb')
        self.make_dirs('bell','bob',  'share', 'cubicweb')
        file_path = self.make_file('bell', 'toto.py')
        self.assertEquals(_find_prefix(file_path), prefix)

    @with_tempdir
    def test_no_prefix(self):
        prefix = tempfile.tempdir
        self.assertEquals(_find_prefix(prefix), sys.prefix)

if __name__ == '__main__':
    unittest_main()
