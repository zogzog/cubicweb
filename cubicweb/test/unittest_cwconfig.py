# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb.cwconfig unit tests"""

import sys
import os
from os.path import dirname, join, abspath
from pkg_resources import EntryPoint, Distribution
import unittest

from mock import patch
from six import PY3

from logilab.common.modutils import cleanup_sys_modules
from logilab.common.changelog import Version

from cubicweb.devtools import ApptestConfiguration
from cubicweb.devtools.testlib import BaseTestCase, TemporaryDirectory
from cubicweb.cwconfig import _find_prefix


def unabsolutize(path):
    parts = path.split(os.sep)
    for i, part in reversed(tuple(enumerate(parts))):
        if part.startswith('cubicweb_'):
            return os.sep.join([part[len('cubicweb_'):]] + parts[i+1:])
        if part.startswith('cubicweb') or part == 'legacy_cubes':
            return os.sep.join(parts[i+1:])
    raise Exception('duh? %s' % path)


class CubicWebConfigurationTC(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        sys.path.append(cls.datapath('libpython'))

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(cls.datapath('libpython'))

    def setUp(self):
        self.config = ApptestConfiguration('data', __file__)
        self.config._cubes = ('email', 'file')

    def tearDown(self):
        ApptestConfiguration.CUBES_PATH = []

    def iter_entry_points(group, name):
        """Mock pkg_resources.iter_entry_points to yield EntryPoint from
        packages found in test/data/libpython even though these are not
        installed.
        """
        libpython = CubicWebConfigurationTC.datapath('libpython')
        prefix = 'cubicweb_'
        for pkgname in os.listdir(libpython):
            if not pkgname.startswith(prefix):
                continue
            location = join(libpython, pkgname)
            yield EntryPoint(pkgname[len(prefix):], pkgname,
                             dist=Distribution(location))

    @patch('pkg_resources.iter_entry_points', side_effect=iter_entry_points)
    def test_available_cubes(self, mock_iter_entry_points):
        expected_cubes = [
            'card', 'comment', 'cubicweb_comment', 'cubicweb_email', 'file',
            'cubicweb_file', 'cubicweb_forge', 'localperms',
            'cubicweb_mycube', 'tag',
        ]
        self._test_available_cubes(expected_cubes)
        mock_iter_entry_points.assert_called_once_with(
            group='cubicweb.cubes', name=None)

    def _test_available_cubes(self, expected_cubes):
        self.assertEqual(self.config.available_cubes(), expected_cubes)

    def test_reorder_cubes(self):
        # forge depends on email and file and comment
        # email depends on file
        self.assertEqual(self.config.reorder_cubes(['file', 'email', 'forge']),
                          ('forge', 'email', 'file'))
        self.assertEqual(self.config.reorder_cubes(['email', 'file', 'forge']),
                          ('forge', 'email', 'file'))
        self.assertEqual(self.config.reorder_cubes(['email', 'forge', 'file']),
                          ('forge', 'email', 'file'))
        self.assertEqual(self.config.reorder_cubes(['file', 'forge', 'email']),
                          ('forge', 'email', 'file'))
        self.assertEqual(self.config.reorder_cubes(['forge', 'file', 'email']),
                          ('forge', 'email', 'file'))
        self.assertEqual(self.config.reorder_cubes(('forge', 'email', 'file')),
                          ('forge', 'email', 'file'))

    def test_reorder_cubes_recommends(self):
        from cubicweb_comment import __pkginfo__ as comment_pkginfo
        self._test_reorder_cubes_recommends(comment_pkginfo)

    def _test_reorder_cubes_recommends(self, comment_pkginfo):
        comment_pkginfo.__recommends_cubes__ = {'file': None}
        try:
            # email recommends comment
            # comment recommends file
            self.assertEqual(self.config.reorder_cubes(('forge', 'email', 'file', 'comment')),
                              ('forge', 'email', 'comment', 'file'))
            self.assertEqual(self.config.reorder_cubes(('forge', 'email', 'comment', 'file')),
                              ('forge', 'email', 'comment', 'file'))
            self.assertEqual(self.config.reorder_cubes(('forge', 'comment', 'email', 'file')),
                              ('forge', 'email', 'comment', 'file'))
            self.assertEqual(self.config.reorder_cubes(('comment', 'forge', 'email', 'file')),
                              ('forge', 'email', 'comment', 'file'))
        finally:
            comment_pkginfo.__recommends_cubes__ = {}

    def test_expand_cubes(self):
        self.assertEqual(self.config.expand_cubes(('email', 'comment')),
                          ['email', 'comment', 'file'])

    def test_appobjects_path(self):
        path = [unabsolutize(p) for p in self.config.appobjects_path()]
        self.assertEqual(path[0], 'entities')
        self.assertCountEqual(path[1:4], ['web/views', 'sobjects', 'hooks'])
        self.assertEqual(path[4], 'file/entities')
        self.assertCountEqual(path[5:7],
                              ['file/views.py', 'file/hooks'])
        self.assertEqual(path[7], 'email/entities.py')
        self.assertCountEqual(path[8:10],
                              ['email/views', 'email/hooks.py'])
        self.assertEqual(path[10:], ['test/data/entities.py', 'test/data/views.py'])

    def test_init_cubes_ignore_pyramid_cube(self):
        warning_msg = 'cubicweb-pyramid got integrated into CubicWeb'
        with self.assertLogs('cubicweb.configuration', level='WARNING') as cm:
            self.config.init_cubes(['pyramid', 'card'])
        self.assertIn(warning_msg, cm.output[0])
        self.assertNotIn('pyramid', self.config._cubes)

class CubicWebConfigurationWithLegacyCubesTC(CubicWebConfigurationTC):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.custom_cubes_dir = self.datapath('legacy_cubes')
        cleanup_sys_modules([self.custom_cubes_dir, ApptestConfiguration.CUBES_DIR])
        super(CubicWebConfigurationWithLegacyCubesTC, self).setUp()
        self.config.__class__.CUBES_PATH = [self.custom_cubes_dir]
        self.config.adjust_sys_path()

    def tearDown(self):
        ApptestConfiguration.CUBES_PATH = []

    def test_available_cubes(self):
        expected_cubes = sorted(set([
            # local cubes
            'comment', 'email', 'file', 'forge', 'mycube',
            # test dependencies
            'card', 'file', 'localperms', 'tag',
        ]))
        self._test_available_cubes(expected_cubes)

    def test_reorder_cubes_recommends(self):
        from cubes.comment import __pkginfo__ as comment_pkginfo
        self._test_reorder_cubes_recommends(comment_pkginfo)

    def test_cubes_path(self):
        # make sure we don't import the email cube, but the stdlib email package
        import email
        self.assertNotEqual(dirname(email.__file__), self.config.CUBES_DIR)
        self.config.__class__.CUBES_PATH = [self.custom_cubes_dir]
        self.assertEqual(self.config.cubes_search_path(),
                          [self.custom_cubes_dir, self.config.CUBES_DIR])
        self.config.__class__.CUBES_PATH = [self.custom_cubes_dir,
                                            self.config.CUBES_DIR, 'unexistant']
        # filter out unexistant and duplicates
        self.assertEqual(self.config.cubes_search_path(),
                          [self.custom_cubes_dir,
                           self.config.CUBES_DIR])
        self.assertIn('mycube', self.config.available_cubes())
        # test cubes python path
        self.config.adjust_sys_path()
        import cubes
        self.assertEqual(cubes.__path__, self.config.cubes_search_path())
        # this import should succeed once path is adjusted
        from cubes import mycube
        self.assertEqual(mycube.__path__, [join(self.custom_cubes_dir, 'mycube')])
        # file cube should be overriden by the one found in data/cubes
        if sys.modules.pop('cubes.file', None) and PY3:
            del cubes.file
        from cubes import file
        self.assertEqual(file.__path__, [join(self.custom_cubes_dir, 'file')])

    def test_config_value_from_environment_str(self):
        self.assertIsNone(self.config['base-url'])
        os.environ['CW_BASE_URL'] = 'https://www.cubicweb.org'
        try:
            self.assertEqual(self.config['base-url'],
                             'https://www.cubicweb.org')
        finally:
            del os.environ['CW_BASE_URL']

    def test_config_value_from_environment_int(self):
        self.assertEqual(self.config['connections-pool-size'], 4)
        os.environ['CW_CONNECTIONS_POOL_SIZE'] = '6'
        try:
            self.assertEqual(self.config['connections-pool-size'], 6)
        finally:
            del os.environ['CW_CONNECTIONS_POOL_SIZE']

    def test_config_value_from_environment_yn(self):
        self.assertEqual(self.config['allow-email-login'], False)
        try:
            for val, result in (('yes', True), ('no', False),
                                ('y', True), ('n', False),):
                os.environ['CW_ALLOW_EMAIL_LOGIN'] = val
            self.assertEqual(self.config['allow-email-login'], result)
        finally:
            del os.environ['CW_ALLOW_EMAIL_LOGIN']
            

class FindPrefixTC(unittest.TestCase):

    def make_dirs(self, basedir, *args):
        path = join(basedir, *args)
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def make_file(self, basedir, *args):
        self.make_dirs(basedir, *args[:-1])
        file_path = join(basedir, *args)
        with open(file_path, 'w') as f:
            f.write('""" None """')
        return file_path

    def test_samedir(self):
        with TemporaryDirectory() as prefix:
            self.make_dirs(prefix, 'share', 'cubicweb')
            self.assertEqual(_find_prefix(prefix), prefix)

    def test_samedir_filepath(self):
        with TemporaryDirectory() as prefix:
            self.make_dirs(prefix, 'share', 'cubicweb')
            file_path = self.make_file(prefix, 'bob.py')
            self.assertEqual(_find_prefix(file_path), prefix)

    def test_dir_inside_prefix(self):
        with TemporaryDirectory() as prefix:
            self.make_dirs(prefix, 'share', 'cubicweb')
            dir_path = self.make_dirs(prefix, 'bob')
            self.assertEqual(_find_prefix(dir_path), prefix)

    def test_file_in_dir_inside_prefix(self):
        with TemporaryDirectory() as prefix:
            self.make_dirs(prefix, 'share', 'cubicweb')
            file_path = self.make_file(prefix, 'bob', 'toto.py')
            self.assertEqual(_find_prefix(file_path), prefix)

    def test_file_in_deeper_dir_inside_prefix(self):
        with TemporaryDirectory() as prefix:
            self.make_dirs(prefix, 'share', 'cubicweb')
            file_path = self.make_file(prefix, 'bob', 'pyves', 'alain',
                                       'adim', 'syt', 'toto.py')
            self.assertEqual(_find_prefix(file_path), prefix)

    def test_multiple_candidate_prefix(self):
        with TemporaryDirectory() as tempdir:
            self.make_dirs(tempdir, 'share', 'cubicweb')
            prefix = self.make_dirs(tempdir, 'bob')
            self.make_dirs(prefix, 'share', 'cubicweb')
            file_path = self.make_file(prefix, 'pyves', 'alain',
                                       'adim', 'syt', 'toto.py')
            self.assertEqual(_find_prefix(file_path), prefix)

    def test_sister_candidate_prefix(self):
        with TemporaryDirectory() as prefix:
            self.make_dirs(prefix, 'share', 'cubicweb')
            self.make_dirs(prefix, 'bob', 'share', 'cubicweb')
            file_path = self.make_file(prefix, 'bell', 'toto.py')
            self.assertEqual(_find_prefix(file_path), prefix)

    def test_multiple_parent_candidate_prefix(self):
        with TemporaryDirectory() as tempdir:
            self.make_dirs(tempdir, 'share', 'cubicweb')
            prefix = self.make_dirs(tempdir, 'share', 'cubicweb', 'bob')
            self.make_dirs(tempdir, 'share', 'cubicweb', 'bob', 'share',
                           'cubicweb')
            file_path = self.make_file(tempdir, 'share', 'cubicweb', 'bob',
                                       'pyves', 'alain', 'adim', 'syt',
                                       'toto.py')
            self.assertEqual(_find_prefix(file_path), prefix)

    def test_upper_candidate_prefix(self):
        with TemporaryDirectory() as prefix:
            self.make_dirs(prefix, 'share', 'cubicweb')
            self.make_dirs(prefix, 'bell', 'bob',  'share', 'cubicweb')
            file_path = self.make_file(prefix, 'bell', 'toto.py')
            self.assertEqual(_find_prefix(file_path), prefix)

    def test_no_prefix(self):
        with TemporaryDirectory() as prefix:
            self.assertEqual(_find_prefix(prefix), sys.prefix)

    def test_virtualenv(self):
        venv = os.environ.get('VIRTUAL_ENV')
        try:
            with TemporaryDirectory() as prefix:
                os.environ['VIRTUAL_ENV'] = prefix
                self.make_dirs(prefix, 'share', 'cubicweb')
                self.assertEqual(_find_prefix(), prefix)
        finally:
            if venv:
                os.environ['VIRTUAL_ENV'] = venv


if __name__ == '__main__':
    unittest.main()
