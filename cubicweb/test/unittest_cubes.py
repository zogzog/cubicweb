# copyright 2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
# You should have received a copy of the GNU Lesser General Public License
# along with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for "cubes" importer."""

from contextlib import contextmanager
import os
from os import path
import sys

from six import PY2

from cubicweb import _CubesImporter
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.devtools.testlib import TemporaryDirectory, TestCase


@contextmanager
def temp_cube():
    with TemporaryDirectory() as tempdir:
        try:
            libdir = path.join(tempdir, 'libpython')
            cubedir = path.join(libdir, 'cubicweb_foo')
            os.makedirs(cubedir)
            check_code = ("import logging\n"
                          "logging.getLogger('cubicweb_foo')"
                          ".warn('imported %s', __name__)\n")
            with open(path.join(cubedir, '__init__.py'), 'w') as f:
                f.write("'cubicweb_foo application package'\n" + check_code)
            with open(path.join(cubedir, 'bar.py'), 'w') as f:
                f.write(check_code + 'baz = 1\n')
            sys.path.append(libdir)
            yield cubedir
        finally:
            sys.path.remove(libdir)


class CubesImporterTC(TestCase):

    def setUp(self):
        # During discovery, CubicWebConfiguration.cls_adjust_sys_path may be
        # called (probably because of cubicweb.devtools's __init__.py), so
        # uninstall _CubesImporter.
        for x in sys.meta_path:
            if isinstance(x, _CubesImporter):
                sys.meta_path.remove(x)
        # Keep track of initial sys.path and sys.meta_path.
        self.orig_sys_path = sys.path[:]
        self.orig_sys_meta_path = sys.meta_path[:]

    def tearDown(self):
        # Cleanup any imported "cubes".
        for name in list(sys.modules):
            if name.startswith('cubes') or name.startswith('cubicweb_'):
                del sys.modules[name]
        # Restore sys.{meta_,}path
        sys.path[:] = self.orig_sys_path
        sys.meta_path[:] = self.orig_sys_meta_path

    def test_importer_install(self):
        _CubesImporter.install()
        self.assertIsInstance(sys.meta_path[-1], _CubesImporter)

    def test_config_installs_importer(self):
        CubicWebConfiguration.cls_adjust_sys_path()
        self.assertIsInstance(sys.meta_path[-1], _CubesImporter)

    def test_import_cube_as_package_legacy_name(self):
        """Check for import of an actual package-cube using legacy name"""
        with temp_cube() as cubedir:
            import cubicweb_foo  # noqa
            del sys.modules['cubicweb_foo']
            with self.assertRaises(ImportError):
                import cubes.foo
            CubicWebConfiguration.cls_adjust_sys_path()
            import cubes.foo  # noqa
            self.assertEqual(cubes.foo.__path__, [cubedir])
            self.assertEqual(cubes.foo.__doc__,
                             'cubicweb_foo application package')
            # Import a submodule.
            from cubes.foo import bar
            self.assertEqual(bar.baz, 1)

    def test_reload_cube(self):
        """reloading cubes twice should return the same module"""
        CubicWebConfiguration.cls_adjust_sys_path()
        import cubes
        if PY2:
            new = reload(cubes)
        else:
            import importlib
            new = importlib.reload(cubes)
        self.assertIs(new, cubes)

    def test_no_double_import(self):
        """Check new and legacy import the same module once"""
        with temp_cube():
            CubicWebConfiguration.cls_adjust_sys_path()
            with self.assertLogs('cubicweb_foo', 'WARNING') as cm:
                from cubes.foo import bar
                from cubicweb_foo import bar as bar2
                self.assertIs(bar, bar2)
                self.assertIs(sys.modules['cubes.foo'],
                              sys.modules['cubicweb_foo'])
            self.assertEqual(cm.output, [
                'WARNING:cubicweb_foo:imported cubicweb_foo',
                # module __name__ for subpackage differ along python version
                # for PY2 it's based on how the module was imported "from
                # cubes.foo import bar" and for PY3 based on __name__ of parent
                # module "cubicweb_foo". Not sure if it's an issue, but PY3
                # behavior looks better.
                'WARNING:cubicweb_foo:imported ' + (
                    'cubes.foo.bar' if PY2 else 'cubicweb_foo.bar')
            ])

    def test_import_legacy_cube(self):
        """Check that importing a legacy cube works when sys.path got adjusted.
        """
        CubicWebConfiguration.cls_adjust_sys_path()
        import cubes.card  # noqa

    def test_import_cube_as_package_after_legacy_cube(self):
        """Check import of a "cube as package" after a legacy cube."""
        CubicWebConfiguration.cls_adjust_sys_path()
        with temp_cube() as cubedir:
            import cubes.card
            import cubes.foo
        self.assertEqual(cubes.foo.__path__, [cubedir])

    def test_cube_inexistant(self):
        """Check for import of an inexistant cube"""
        CubicWebConfiguration.cls_adjust_sys_path()
        with self.assertRaises(ImportError) as cm:
            import cubes.doesnotexists  # noqa
        msg = "No module named " + ("doesnotexists" if PY2 else "'cubes.doesnotexists'")
        self.assertEqual(str(cm.exception), msg)


if __name__ == '__main__':
    import unittest
    unittest.main()
