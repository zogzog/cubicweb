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
import unittest

from six import PY2

from mock import patch

from cubicweb.cwctl import ListCommand
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.migractions import ServerMigrationHelper

import unittest_cwconfig


class CubicWebCtlTC(unittest.TestCase):

    setUpClass = unittest_cwconfig.CubicWebConfigurationTC.setUpClass
    tearDownClass = unittest_cwconfig.CubicWebConfigurationTC.tearDownClass

    def setUp(self):
        self.stream = BytesIO() if PY2 else StringIO()
        sys.stdout = self.stream

    def tearDown(self):
        sys.stdout = sys.__stdout__

    @patch('pkg_resources.iter_entry_points', side_effect=unittest_cwconfig.iter_entry_points)
    def test_list(self, mock_iter_entry_points):
        ListCommand(None).run([])
        self.assertNotIn('cubicweb_', self.stream.getvalue())
        mock_iter_entry_points.assert_called_once_with(
            group='cubicweb.cubes', name=None)

    def test_list_configurations(self):
        ListCommand(None).run(['configurations'])
        configs = [l[2:].strip() for l in self.stream.getvalue().splitlines()
                   if l.startswith('* ')]
        self.assertIn('all-in-one', configs)
        self.assertIn('pyramid', configs)


class CubicWebShellTC(CubicWebTC):

    def test_process_script_args_context(self):
        repo = self.repo
        with self.admin_access.repo_cnx() as cnx:
            mih = ServerMigrationHelper(None, repo=repo, cnx=cnx,
                                        interactive=False,
                                        # hack so it don't try to load fs schema
                                        schema=1)
            scripts = {
                'script1.py': list(),
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
    unittest.main()
