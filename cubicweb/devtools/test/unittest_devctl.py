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
from subprocess import Popen, PIPE, STDOUT
from unittest import TestCase


def newcube(directory, name):
    cmd = ['cubicweb-ctl', 'newcube', '--directory', directory, name]
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
    stdout, _ = proc.communicate(b'short_desc\n')
    return proc.returncode, stdout


class CubicWebCtlTC(TestCase):
    """test case for devtools commands"""

    if not hasattr(TestCase, 'assertItemsEqual'):
        assertItemsEqual = TestCase.assertCountEqual

    def test_newcube(self):
        expected = ['i18n', 'hooks.py', 'setup.py', 'views.py', 'test',
                    'migration', 'entities.py', 'MANIFEST.in', 'schema.py',
                    'cubicweb-foo.spec', '__init__.py', 'debian', 'data',
                    '__pkginfo__.py', 'README', 'tox.ini']
        tmpdir = tempfile.mkdtemp(prefix="temp-cwctl-newcube")
        try:
            retcode, stdout = newcube(tmpdir, 'foo')
            self.assertItemsEqual(os.listdir(osp.join(tmpdir, 'foo')), expected)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertEqual(retcode, 0, msg=stdout)

    def test_flake8(self):
        """Ensure newcube built from skeleton is flake8-compliant"""
        tmpdir = tempfile.mkdtemp(prefix="temp-cwctl-newcube-flake8")
        try:
            newcube(tmpdir, 'foo')
            cmd = [sys.executable, '-m', 'flake8', osp.join(tmpdir, 'foo')]
            proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
            retcode = proc.wait()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertEqual(retcode, 0, proc.stdout.read())


if __name__ == '__main__':
    from unittest import main
    main()
