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
from io import StringIO
import unittest
from unittest.mock import patch, MagicMock

from logilab.common.clcommands import CommandLine

from cubicweb import utils, server
from cubicweb.cwctl import ListCommand, InstanceCommand
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.migractions import ServerMigrationHelper
from cubicweb.cwconfig import CubicWebConfiguration as cwcfg
from cubicweb.__pkginfo__ import version as cw_version

import unittest_cwconfig


class CubicWebCtlTC(unittest.TestCase):
    setUpClass = unittest_cwconfig.CubicWebConfigurationTC.setUpClass
    tearDownClass = unittest_cwconfig.CubicWebConfigurationTC.tearDownClass

    def setUp(self):
        self.stream = StringIO()
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


class _TestCommand(InstanceCommand):
    "I need some doc"
    name = "test"
    actionverb = 'failtested'

    def test_instance(self, appid):
        pass


class _TestFailCommand(InstanceCommand):
    "I need some doc"
    name = "test_fail"
    actionverb = 'tested'

    def test_fail_instance(self, appid):
        raise Exception()


class InstanceCommandTest(unittest.TestCase):
    def setUp(self):
        self.CWCTL = CommandLine('cubicweb-ctl', 'The CubicWeb swiss-knife.',
                                 version=cw_version, check_duplicated_command=False)
        cwcfg.load_cwctl_plugins()
        self.CWCTL.register(_TestCommand)
        self.CWCTL.register(_TestFailCommand)

        self.fake_config = MagicMock()
        self.fake_config.global_set_option = MagicMock()

        # pretend that this instance exists
        config_patcher = patch.object(cwcfg, 'config_for', return_value=self.fake_config)
        config_patcher.start()
        self.addCleanup(config_patcher.stop)

    @patch.object(_TestCommand, 'test_instance', return_value=0)
    def test_getting_called(self, test_instance):
        with self.assertRaises(SystemExit) as cm:
            self.CWCTL.run(["test", "some_instance"])
        self.assertEqual(cm.exception.code, 0)
        test_instance.assert_called_with("some_instance")

    @patch.object(utils, 'get_pdb')
    def test_pdb_not_called(self, get_pdb):
        # CWCTL will finish the program after that
        with self.assertRaises(SystemExit) as cm:
            self.CWCTL.run(["test", "some_instance"])
        self.assertEqual(cm.exception.code, 0)

        get_pdb.assert_not_called()

    @patch.object(utils, 'get_pdb')
    def test_pdb_called(self, get_pdb):
        post_mortem = get_pdb.return_value.post_mortem
        with self.assertRaises(SystemExit) as cm:
            self.CWCTL.run(["test_fail", "some_instance", "--pdb"])
        self.assertEqual(cm.exception.code, 8)

        get_pdb.assert_called_once()
        post_mortem.assert_called_once()

        # we want post_mortem to actually receive the traceback
        self.assertNotEqual(post_mortem.call_args, ((None,),))

    @patch.dict(sys.modules, ipdb=MagicMock())
    def test_ipdb_selected_and_called(self):
        ipdb = sys.modules['ipdb']
        with self.assertRaises(SystemExit) as cm:
            self.CWCTL.run(["test_fail", "some_instance", "--pdb"])
        self.assertEqual(cm.exception.code, 8)

        ipdb.post_mortem.assert_called_once()

    @patch.object(_TestFailCommand, 'test_fail_instance', side_effect=SystemExit(42))
    def test_respect_return_error_code(self, test_fail_instance):
        with self.assertRaises(SystemExit) as cm:
            self.CWCTL.run(["test_fail", "some_instance"])
        self.assertEqual(cm.exception.code, 42)

        test_fail_instance.assert_called_once()

    @patch.object(_TestFailCommand, 'test_fail_instance', side_effect=KeyboardInterrupt)
    def test_error_code_keyboardinterupt_2(self, test_fail_instance):
        with self.assertRaises(SystemExit) as cm:
            self.CWCTL.run(["test_fail", "some_instance"])
        self.assertEqual(cm.exception.code, 2)

        test_fail_instance.assert_called_once()

    def test_set_loglevel(self):
        LOG_LEVELS = ('debug', 'info', 'warning', 'error')

        for log_level in LOG_LEVELS:
            with self.assertRaises(SystemExit) as cm:
                self.CWCTL.run(["test", "some_instance", "--loglevel", log_level])
            self.assertEqual(cm.exception.code, 0)

            self.fake_config.global_set_option.assert_called_with('log-threshold',
                                                                  log_level.upper())

    @patch.object(server, "DEBUG", 0)
    def test_set_dblevel(self):
        DBG_FLAGS = ('RQL', 'SQL', 'REPO', 'HOOKS', 'OPS', 'SEC', 'MORE')

        total_value = 0

        for dbg_flag in DBG_FLAGS:
            with self.assertRaises(SystemExit) as cm:
                self.CWCTL.run(["test", "some_instance", "--dbglevel", dbg_flag])
            self.assertEqual(cm.exception.code, 0)

            total_value += getattr(server, "DBG_%s" % dbg_flag)
            self.assertEqual(total_value, server.DEBUG)


if __name__ == '__main__':
    unittest.main()
