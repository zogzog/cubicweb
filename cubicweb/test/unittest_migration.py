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
"""cubicweb.migration unit tests"""

from os.path import dirname, join
from unittest.mock import patch

from logilab.common.testlib import TestCase, unittest_main

from cubicweb import devtools, utils
from logilab.common.shellutils import ASK
from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.migration import (
    filter_scripts,
    split_constraint,
    version_strictly_lower,
    MigrationHelper,
)


class Schema(dict):
    def has_entity(self, e_type):
        return e_type in self

SMIGRDIR = join(dirname(__file__), 'data', 'server_migration') + '/'
TMIGRDIR = join(dirname(__file__), 'data', 'migration') + '/'


class MigrTestConfig(devtools.TestServerConfiguration):
    verbosity = 0

    def migration_scripts_dir(cls):
        return SMIGRDIR

    def cube_migration_scripts_dir(cls, cube):
        return TMIGRDIR

class MigrationToolsTC(TestCase):
    def setUp(self):
        self.config = MigrTestConfig('data', __file__)
        from yams.schema import Schema
        self.config.load_schema = lambda expand_cubes=False: Schema('test')
        self.config.__class__.cubicweb_appobject_path = frozenset()
        self.config.__class__.cube_appobject_path = frozenset()

    def test_filter_scripts_base(self):
        self.assertListEqual(filter_scripts(self.config, SMIGRDIR, (2,3,0), (2,4,0)),
                              [])
        self.assertListEqual(filter_scripts(self.config, SMIGRDIR, (2,4,0), (2,5,0)),
                              [((2, 5, 0), SMIGRDIR+'2.5.0_Any.sql')])
        self.assertListEqual(filter_scripts(self.config, SMIGRDIR, (2,5,0), (2,6,0)),
                              [((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql')])
        self.assertListEqual(filter_scripts(self.config, SMIGRDIR, (2,4,0), (2,6,0)),
                              [((2, 5, 0), SMIGRDIR+'2.5.0_Any.sql'),
                               ((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql')])
        self.assertListEqual(filter_scripts(self.config, SMIGRDIR, (2,5,0), (2,5,1)),
                              [])
        self.assertListEqual(filter_scripts(self.config, SMIGRDIR, (2,5,0), (2,10,2)),
                              [((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql'),
                               ((2, 10, 2), SMIGRDIR+'2.10.2_Any.sql')])
        self.assertListEqual(filter_scripts(self.config, SMIGRDIR, (2,5,1), (2,6,0)),
                              [((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql')])

        self.assertListEqual(filter_scripts(self.config, TMIGRDIR, (0,0,2), (0,0,3)),
                              [((0, 0, 3), TMIGRDIR+'0.0.3_Any.py')])
        self.assertListEqual(filter_scripts(self.config, TMIGRDIR, (0,0,2), (0,0,4)),
                              [((0, 0, 3), TMIGRDIR+'0.0.3_Any.py'),
                               ((0, 0, 4), TMIGRDIR+'0.0.4_Any.py')])

    def test_filter_scripts_for_mode(self):
        config = CubicWebConfiguration('data', __file__)
        config.verbosity = 0
        config = self.config
        config.__class__.name = 'repository'
        self.assertListEqual(filter_scripts(config, TMIGRDIR, (0,0,4), (0,1,0)),
                              [((0, 1 ,0), TMIGRDIR+'0.1.0_Any.py'),
                               ((0, 1 ,0), TMIGRDIR+'0.1.0_common.py'),
                               ((0, 1 ,0), TMIGRDIR+'0.1.0_repository.py')])
        config.__class__.name = 'all-in-one'
        self.assertListEqual(filter_scripts(config, TMIGRDIR, (0,0,4), (0,1,0)),
                              [((0, 1 ,0), TMIGRDIR+'0.1.0_Any.py'),
                               ((0, 1 ,0), TMIGRDIR+'0.1.0_common.py'),
                               ((0, 1 ,0), TMIGRDIR+'0.1.0_repository.py')])
        config.__class__.name = 'repository'

    def test_version_strictly_lower(self):
        self.assertTrue(version_strictly_lower(None, '1.0.0'))
        self.assertFalse(version_strictly_lower('1.0.0', None))


from cubicweb.devtools import ApptestConfiguration, get_test_db_handler

class BaseCreationTC(TestCase):

    def test_db_creation(self):
        """make sure database can be created"""
        config = ApptestConfiguration('data', __file__)
        source = config.system_source_config
        self.assertEqual(source['db-driver'], 'sqlite')
        handler = get_test_db_handler(config)
        handler.init_test_database()
        handler.build_db_cache()
        repo, cnx = handler.get_repo_and_cnx()
        with cnx:
            self.assertEqual(cnx.execute('Any SN WHERE X is CWUser, X login "admin", X in_state S, S name SN').rows,
                             [['activated']])
        repo.shutdown()

def test_split_constraint():
    assert split_constraint(">=0.1.0") == (">=", "0.1.0")
    assert split_constraint(">= 0.1.0") == (">=", "0.1.0")
    assert split_constraint(">0.1.1") == (">", "0.1.1")
    assert split_constraint("> 0.1.1") == (">", "0.1.1")
    assert split_constraint("<0.2.0") == ("<", "0.2.0")
    assert split_constraint("< 0.2.0") == ("<", "0.2.0")
    assert split_constraint("<=42.1.0") == ("<=", "42.1.0")
    assert split_constraint("<= 42.1.0") == ("<=", "42.1.0")


class WontColideWithOtherExceptionsException(Exception):
    pass


class MigrationHelperTC(TestCase):
    @patch.object(utils, 'get_pdb')
    @patch.object(ASK, 'ask', return_value="pdb")
    def test_confirm_no_traceback(self, ask, get_pdb):
        post_mortem = get_pdb.return_value.post_mortem
        set_trace = get_pdb.return_value.set_trace

        # we need to break after post_mortem is called otherwise we get
        # infinite recursion
        set_trace.side_effect = WontColideWithOtherExceptionsException

        mh = MigrationHelper(config=None)

        with self.assertRaises(WontColideWithOtherExceptionsException):
            mh.confirm("some question")

        get_pdb.assert_called_once()
        set_trace.assert_called_once()
        post_mortem.assert_not_called()

    @patch.object(utils, 'get_pdb')
    @patch.object(ASK, 'ask', return_value="pdb")
    def test_confirm_got_traceback(self, ask, get_pdb):
        post_mortem = get_pdb.return_value.post_mortem
        set_trace = get_pdb.return_value.set_trace

        # we need to break after post_mortem is called otherwise we get
        # infinite recursion
        post_mortem.side_effect = WontColideWithOtherExceptionsException

        mh = MigrationHelper(config=None)

        fake_traceback = object()

        with self.assertRaises(WontColideWithOtherExceptionsException):
            mh.confirm("some question", traceback=fake_traceback)

        get_pdb.assert_called_once()
        set_trace.assert_not_called()
        post_mortem.assert_called_once()

        # we want post_mortem to actually receive the traceback
        self.assertEqual(post_mortem.call_args, ((fake_traceback,),))


if __name__ == '__main__':
    unittest_main()
