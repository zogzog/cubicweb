# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import os.path as osp
import sys
import tempfile
import shutil
from subprocess import Popen, PIPE, STDOUT
from unittest import TestCase


class CubicWebCtlTC(TestCase):
    """test case for devtools commands"""

    def test_newcube(self):
        cwctl = osp.abspath(osp.join(osp.dirname(__file__), '../../bin/cubicweb-ctl'))

        tmpdir = tempfile.mkdtemp(prefix="temp-cwctl-newcube")
        try:
            cmd = [sys.executable, cwctl, 'newcube',
                   '--directory', tmpdir, 'foo']
            proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
            stdout, _ = proc.communicate(b'short_desc\n')
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        self.assertEqual(proc.returncode, 0, msg=stdout)


if __name__ == '__main__':
    from unittest import main
    main()
