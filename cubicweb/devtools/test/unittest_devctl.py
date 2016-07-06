# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for cubicweb-ctl commands from devtools"""

import os
import os.path as osp
import sys
import tempfile
import shutil
from subprocess import Popen, PIPE, STDOUT, check_output
from unittest import TestCase


def newcube(directory, name):
    cmd = ['cubicweb-ctl', 'newcube', '--directory', directory, name]
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout, _ = proc.communicate(b'short_desc\n')
    return proc.returncode, stdout


def to_unicode(msg):
    return msg.decode(sys.getdefaultencoding(), errors='replace')


class DevCtlTC(TestCase):
    """Test case for devtools commands"""

    if not hasattr(TestCase, 'assertItemsEqual'):
        assertItemsEqual = TestCase.assertCountEqual

    def test_newcube(self):
        expected_project_content = ['setup.py', 'test', 'MANIFEST.in',
                                    'cubicweb_foo',
                                    'cubicweb-foo.spec', 'debian', 'README',
                                    'tox.ini']
        expected_package_content = ['i18n', 'hooks.py', 'views.py',
                                    'migration', 'entities.py', 'schema.py',
                                    '__init__.py', 'data', '__pkginfo__.py']
        tmpdir = tempfile.mkdtemp(prefix="temp-cwctl-newcube")
        try:
            retcode, stdout = newcube(tmpdir, 'foo')
            self.assertEqual(retcode, 0, msg=to_unicode(stdout))
            project_dir = osp.join(tmpdir, 'cubicweb-foo')
            project_content = os.listdir(project_dir)
            package_dir = osp.join(project_dir, 'cubicweb_foo')
            package_content = os.listdir(package_dir)
            self.assertItemsEqual(project_content, expected_project_content)
            self.assertItemsEqual(package_content, expected_package_content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_flake8(self):
        """Ensure newcube built from skeleton is flake8-compliant"""
        tmpdir = tempfile.mkdtemp(prefix="temp-cwctl-newcube-flake8")
        try:
            newcube(tmpdir, 'foo')
            cmd = [sys.executable, '-m', 'flake8',
                   osp.join(tmpdir, 'cubicweb-foo', 'cubicweb_foo')]
            proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
            retcode = proc.wait()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertEqual(retcode, 0,
                         msg=to_unicode(proc.stdout.read()))

    def test_newcube_sdist(self):
        """Ensure sdist can be built from a new cube"""
        tmpdir = tempfile.mkdtemp(prefix="temp-cwctl-newcube-sdist")
        try:
            newcube(tmpdir, 'foo')
            projectdir = osp.join(tmpdir, 'cubicweb-foo')
            cmd = [sys.executable, 'setup.py', 'sdist']
            proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, cwd=projectdir)
            retcode = proc.wait()
            stdout = to_unicode(proc.stdout.read())
            self.assertEqual(retcode, 0, stdout)
            distfpath = osp.join(projectdir, 'dist', 'cubicweb-foo-0.1.0.tar.gz')
            self.assertTrue(osp.isfile(distfpath))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_newcube_install(self):
        """Ensure a new cube can be installed"""
        tmpdir = tempfile.mkdtemp(prefix="temp-cwctl-newcube-install")
        try:
            newcube(tmpdir, 'foo')
            projectdir = osp.join(tmpdir, 'cubicweb-foo')
            env = os.environ.copy()
            env['HOME'] = tmpdir
            cmd = [sys.executable, 'setup.py', 'install', '--user']
            proc = Popen(cmd, stdout=PIPE, stderr=STDOUT,
                         cwd=projectdir, env=env)
            retcode = proc.wait()
            stdout = to_unicode(proc.stdout.read())
            self.assertEqual(retcode, 0, stdout)
            targetdir = check_output([sys.executable, '-m', 'site', '--user-site'],
                                     env=env, cwd=projectdir).strip()
            target_egg = 'cubicweb_foo-0.1.0-py{0}.egg'.format(sys.version[:3]).encode()
            self.assertTrue(osp.isdir(osp.join(targetdir, target_egg)),
                            'target directory content: %s' % os.listdir(targetdir))
            pkgdir = osp.join(targetdir, target_egg, b'cubicweb_foo')
            self.assertTrue(osp.isdir(pkgdir),
                            os.listdir(osp.join(targetdir, target_egg)))
            pkgcontent = [f for f in os.listdir(pkgdir) if f.endswith(b'.py')]
            self.assertItemsEqual(pkgcontent,
                                  [b'schema.py', b'entities.py', b'hooks.py', b'__init__.py',
                                   b'__pkginfo__.py', b'views.py'])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    from unittest import main
    main()
