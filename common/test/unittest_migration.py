"""cubicweb.common.migration unit tests

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from os.path import abspath
from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools import TestServerConfiguration
from cubicweb.devtools.apptest import TestEnvironment

from cubicweb.cwconfig import CubicWebConfiguration
from cubicweb.common.migration import migration_files, filter_scripts


class Schema(dict):
    def has_entity(self, e_type):
        return self.has_key(e_type)

SMIGRDIR = abspath('data/server_migration') + '/'
TMIGRDIR = abspath('data/migration') + '/'

class MigrTestConfig(TestServerConfiguration):
    verbosity = 0
    def migration_scripts_dir(cls):
        return SMIGRDIR

    def cube_migration_scripts_dir(cls, cube):
        return TMIGRDIR

class MigrationToolsTC(TestCase):
    def setUp(self):
        self.config = MigrTestConfig('data')
        from yams.schema import Schema
        self.config.load_schema = lambda expand_cubes=False: Schema('test')
        self.config.__class__.cubicweb_vobject_path = frozenset()
        self.config.__class__.cube_vobject_path = frozenset()

    def test_migration_files_base(self):
        self.assertListEquals(migration_files(self.config, [('cubicweb', (2,3,0), (2,4,0)),
                                                            ('TEMPLATE', (0,0,2), (0,0,3))]),
                              [SMIGRDIR+'bootstrapmigration_repository.py',
                               TMIGRDIR+'0.0.3_Any.py'])
        self.assertListEquals(migration_files(self.config, [('cubicweb', (2,4,0), (2,5,0)),
                                                            ('TEMPLATE', (0,0,2), (0,0,3))]),
                              [SMIGRDIR+'bootstrapmigration_repository.py',
                               SMIGRDIR+'2.5.0_Any.sql',
                               TMIGRDIR+'0.0.3_Any.py'])
        self.assertListEquals(migration_files(self.config, [('cubicweb', (2,5,0), (2,6,0)),
                                                            ('TEMPLATE', (0,0,3), (0,0,4))]),
                              [SMIGRDIR+'bootstrapmigration_repository.py',
                               SMIGRDIR+'2.6.0_Any.sql',
                               TMIGRDIR+'0.0.4_Any.py'])

##     def test_migration_files_overlap(self):
##         self.assertListEquals(migration_files(self.config, (2,4,0), (2,10,2),
##                                               (0,0,2), (0,1,2)),
##                               [SMIGRDIR+'bootstrapmigration_repository.py',
##                                TMIGRDIR+'0.0.3_Any.py',
##                                TMIGRDIR+'0.0.4_Any.py',
##                                SMIGRDIR+'2.4.0_2.5.0_Any.sql',
##                                SMIGRDIR+'2.5.1_2.6.0_Any.sql',
##                                TMIGRDIR+'0.1.0_Any.py',
##                                TMIGRDIR+'0.1.0_common.py',
##                                TMIGRDIR+'0.1.0_repository.py',
##                                TMIGRDIR+'0.1.2_Any.py',
##                                SMIGRDIR+'2.10.1_2.10.2_Any.sql'])

    def test_migration_files_for_mode(self):
        from cubicweb.server.migractions import ServerMigrationHelper
        self.assertIsInstance(self.config.migration_handler(), ServerMigrationHelper)
        from cubicweb.common.migration import MigrationHelper
        config = CubicWebConfiguration('data')
        config.verbosity = 0
        self.assert_(not isinstance(config.migration_handler(), ServerMigrationHelper))
        self.assertIsInstance(config.migration_handler(), MigrationHelper)
        config = self.config
        config.__class__.name = 'twisted'
        self.assertListEquals(migration_files(config, [('TEMPLATE', (0,0,4), (0,1,0))]),
                              [TMIGRDIR+'0.1.0_common.py',
                               TMIGRDIR+'0.1.0_web.py'])
        config.__class__.name = 'repository'
        self.assertListEquals(migration_files(config, [('TEMPLATE', (0,0,4), (0,1,0))]),
                              [SMIGRDIR+'bootstrapmigration_repository.py',
                               TMIGRDIR+'0.1.0_Any.py',
                               TMIGRDIR+'0.1.0_common.py',
                               TMIGRDIR+'0.1.0_repository.py'])
        config.__class__.name = 'all-in-one'
        self.assertListEquals(migration_files(config, [('TEMPLATE', (0,0,4), (0,1,0))]),
                              [SMIGRDIR+'bootstrapmigration_repository.py',
                               TMIGRDIR+'0.1.0_Any.py',
                               TMIGRDIR+'0.1.0_common.py',
                               TMIGRDIR+'0.1.0_repository.py',
                               TMIGRDIR+'0.1.0_web.py'])
        config.__class__.name = 'repository'

    def test_filter_scripts(self):
        self.assertListEquals(filter_scripts(self.config, SMIGRDIR, (2,4,0), (2,5,0)),
                              [((2, 5, 0), SMIGRDIR+'2.5.0_Any.sql')])
        self.assertListEquals(filter_scripts(self.config, SMIGRDIR, (2,4,0), (2,6,0)),
                              [((2, 5, 0), SMIGRDIR+'2.5.0_Any.sql'),
                               ((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql')])
        self.assertListEquals(filter_scripts(self.config, SMIGRDIR, (2,5,0), (2,5,1)),
                              [])
        self.assertListEquals(filter_scripts(self.config, SMIGRDIR, (2,5,0), (2,6,0)),
                              [((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql')])
        self.assertListEquals(filter_scripts(self.config, SMIGRDIR, (2,5,0), (2,10,2)),
                              [((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql'),
                               ((2, 10, 2), SMIGRDIR+'2.10.2_Any.sql')])
        self.assertListEquals(filter_scripts(self.config, SMIGRDIR, (2,5,1), (2,6,0)),
                              [((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql')])
        self.assertListEquals(filter_scripts(self.config, SMIGRDIR, (2,5,1), (2,10,2)),
                              [((2, 6, 0), SMIGRDIR+'2.6.0_Any.sql'),
                               ((2, 10, 2), SMIGRDIR+'2.10.2_Any.sql')])


from cubicweb.devtools import ApptestConfiguration, init_test_database, cleanup_sqlite

class BaseCreationTC(TestCase):

    def test_db_creation(self):
        """make sure database can be created"""
        config = ApptestConfiguration('data')
        source = config.sources()['system']
        self.assertEquals(source['db-driver'], 'sqlite')
        cleanup_sqlite(source['db-name'], removecube=True)
        init_test_database(driver=source['db-driver'], config=config)


if __name__ == '__main__':
    unittest_main()
