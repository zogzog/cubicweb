# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
import sys
import os
from os.path import join
from io import StringIO, BytesIO

from six import PY2

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.migractions import ServerMigrationHelper

CubicWebConfiguration.load_cwctl_plugins() # XXX necessary?


class CubicWebCtlTC(TestCase):
    def setUp(self):
        self.stream = BytesIO() if PY2 else StringIO()
        sys.stdout = self.stream
    def tearDown(self):
        sys.stdout = sys.__stdout__

    def test_list(self):
        from cubicweb.cwctl import ListCommand
        ListCommand(None).run([])


class CubicWebShellTC(CubicWebTC):

    def test_process_script_args_context(self):
        repo = self.repo
        with self.admin_access.repo_cnx() as cnx:
            mih = ServerMigrationHelper(None, repo=repo, cnx=cnx,
                                        interactive=False,
                                        # hack so it don't try to load fs schema
                                        schema=1)
            scripts = {'script1.py': list(),
                       'script2.py': ['-v'],
                       'script3.py': ['-vd', '-f', 'FILE.TXT'],
                      }
            mih.cmd_process_script(join(self.datadir, 'scripts', 'script1.py'),
                                   funcname=None)
            for script, args in scripts.items():
                scriptname = os.path.join(self.datadir, 'scripts', script)
                self.assertTrue(os.path.exists(scriptname))
                mih.cmd_process_script(scriptname, None, scriptargs=args)


if __name__ == '__main__':
    unittest_main()
