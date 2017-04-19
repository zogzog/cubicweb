# -*- coding: utf-8 -*-
# copyright 2013-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
"""Massive store test case"""

import psycopg2

from cubicweb.devtools import testlib, PostgresApptestConfiguration
from cubicweb.devtools import startpgcluster, stoppgcluster
from cubicweb.dataimport import ucsvreader, stores
from cubicweb.server.schema2sql import build_index_name
from cubicweb.dataimport.massive_store import MassiveObjectStore, PGHelper

import test_stores


def setUpModule():
    startpgcluster(__file__)


def tearDownModule(*args):
    stoppgcluster(__file__)


def all_indexes(cnx):
    crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
    return set(r[0] for r in crs.fetchall())


class MassiveObjectStoreWithCustomMDGenStoreTC(
        test_stores.NoHookRQLObjectStoreWithCustomMDGenStoreTC):
    configcls = PostgresApptestConfiguration

    def store_impl(self, cnx):
        source = cnx.create_entity('CWSource', type=u'datafeed', name=u'test', url=u'test')
        cnx.commit()
        metagen = stores.MetadataGenerator(cnx, source=cnx.repo.source_by_eid(source.eid))
        return MassiveObjectStore(cnx, metagen=metagen)


class MassImportSimpleTC(testlib.CubicWebTC):
    configcls = PostgresApptestConfiguration
    appid = 'data-massimport'

    def cast(self, _type, value):
        try:
            return _type(value)
        except ValueError:
            return None

    def push_geonames_data(self, dumpname, store):
        # Push timezones
        cnx = store._cnx
        for code, gmt, dst, raw_offset in ucsvreader(open(self.datapath('timeZones.txt'), 'rb'),
                                                     delimiter='\t'):
            cnx.create_entity('TimeZone', code=code, gmt=float(gmt),
                              dst=float(dst), raw_offset=float(raw_offset))
        timezone_code = dict(cnx.execute('Any C, X WHERE X is TimeZone, X code C'))
        # Push data
        for ind, infos in enumerate(ucsvreader(open(dumpname, 'rb'),
                                               delimiter='\t',
                                               ignore_errors=True)):
            latitude = self.cast(float, infos[4])
            longitude = self.cast(float, infos[5])
            population = self.cast(int, infos[14])
            elevation = self.cast(int, infos[15])
            gtopo = self.cast(int, infos[16])
            feature_class = infos[6]
            if len(infos[6]) != 1:
                feature_class = None
            entity = {'name': infos[1],
                      'asciiname': infos[2],
                      'alternatenames': infos[3],
                      'latitude': latitude, 'longitude': longitude,
                      'feature_class': feature_class,
                      'alternate_country_code': infos[9],
                      'admin_code_3': infos[12],
                      'admin_code_4': infos[13],
                      'population': population, 'elevation': elevation,
                      'gtopo30': gtopo, 'timezone': timezone_code.get(infos[17]),
                      'cwuri': u'http://sws.geonames.org/%s/' % int(infos[0]),
                      'geonameid': int(infos[0]),
                      }
            store.prepare_insert_entity('Location', **entity)

    def test_autoflush_metadata(self):
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
                                 {'t': 'Location'})
            self.assertEqual(len(crs.fetchall()), 0)
            store = MassiveObjectStore(cnx)
            store.prepare_insert_entity('Location', name=u'toto')
            store.flush()
            store.commit()
            store.finish()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
                                 {'t': 'Location'})
            self.assertEqual(len(crs.fetchall()), 1)

    def test_massimport_etype_metadata(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            timezone_eid = store.prepare_insert_entity('TimeZone', code=u'12')
            store.prepare_insert_entity('Location', timezone=timezone_eid)
            store.flush()
            store.commit()
            store.finish()
            eid, etname = cnx.execute('Any X, TN WHERE X timezone TZ, X is T, '
                                      'T name TN')[0]
            self.assertEqual(cnx.entity_from_eid(eid).cw_etype, etname)

    def test_index_not_dropped_by_init(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)  # noqa
            cnx.commit()
            indexes = all_indexes(cnx)
            self.assertIn('entities_pkey', indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from', 'eid_to'], 'key_'),
                          indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from'], 'idx_'),
                          indexes)

    def test_drop_index_recreation(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)

            store._drop_metadata_constraints()
            indexes = all_indexes(cnx)
            self.assertIn('entities_pkey', indexes)
            self.assertNotIn(build_index_name('owned_by_relation', ['eid_from', 'eid_to'], 'key_'),
                             indexes)
            self.assertNotIn(build_index_name('owned_by_relation', ['eid_from'], 'idx_'),
                             indexes)

            store.finish()
            indexes = all_indexes(cnx)
            self.assertIn('entities_pkey', indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from', 'eid_to'], 'key_'),
                          indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from'], 'idx_'),
                          indexes)

    def test_consider_metagen(self):
        """Ensure index on owned_by is not deleted if we don't consider this metadata."""
        with self.admin_access.repo_cnx() as cnx:
            metagen = stores.MetadataGenerator(cnx, meta_skipped=('owned_by',))
            store = MassiveObjectStore(cnx, metagen=metagen)
            store._drop_metadata_constraints()

            indexes = all_indexes(cnx)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from', 'eid_to'], 'key_'),
                          indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from'], 'idx_'),
                          indexes)

    def test_eids_seq_range(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, eids_seq_range=1000)
            store.restart_eid_sequence(50000)
            store.prepare_insert_entity('Location', name=u'toto')
            store.flush()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql("SELECT * FROM entities_id_seq")
            self.assertGreater(crs.fetchone()[0], 50000)

    def test_eid_entity(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, eids_seq_range=1000)
            store.restart_eid_sequence(50000)
            eid = store.prepare_insert_entity('Location', name=u'toto')
            store.flush()
            self.assertGreater(eid, 50000)

    def test_eid_entity_2(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.restart_eid_sequence(50000)
            eid = store.prepare_insert_entity('Location', name=u'toto', eid=10000)
            store.flush()
        self.assertEqual(eid, 10000)

    @staticmethod
    def get_db_descr(cnx):
        pgh = PGHelper(cnx)
        all_tables = cnx.system_sql('''
SELECT table_name
FROM information_schema.tables
where table_schema = %(s)s''', {'s': pgh.pg_schema}).fetchall()
        all_tables_descr = {}
        for tablename, in all_tables:
            all_tables_descr[tablename] = set(pgh.table_indexes(tablename)).union(
                set(pgh.table_constraints(tablename)))
        return all_tables_descr

    def test_identical_schema(self):
        with self.admin_access.repo_cnx() as cnx:
            init_descr = self.get_db_descr(cnx)
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.prepare_insert_entity('Location', name=u'toto')
            store.finish()
        with self.admin_access.repo_cnx() as cnx:
            final_descr = self.get_db_descr(cnx)
        self.assertEqual(init_descr, final_descr)

    def test_simple_insert(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            self.push_geonames_data(self.datapath('geonames.csv'), store)
            store.flush()
            store.commit()
            store.finish()
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('Any X WHERE X is Location')
            self.assertEqual(len(rset), 4000)
            rset = cnx.execute('Any X WHERE X is Location, X timezone T')
            self.assertEqual(len(rset), 4000)

    def test_index_building(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            self.push_geonames_data(self.datapath('geonames.csv'), store)
            store.flush()

            # Check index
            indexes = all_indexes(cnx)
            self.assertIn('entities_pkey', indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from', 'eid_to'], 'key_'),
                          indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from'], 'idx_'),
                          indexes)

            # Cleanup -> index
            store.finish()

            # Check index again
            indexes = all_indexes(cnx)
            self.assertIn('entities_pkey', indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from', 'eid_to'], 'key_'),
                          indexes)
            self.assertIn(build_index_name('owned_by_relation', ['eid_from'], 'idx_'),
                          indexes)

    def test_multiple_insert(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.prepare_insert_entity('Location', name=u'toto')
            store.finish()
            store = MassiveObjectStore(cnx)
            store.prepare_insert_entity('Location', name=u'toto')
            store.finish()

    def test_delete_metatable_on_integrity_error(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.prepare_insert_entity('TimeZone')
            store.flush()
            store.commit()
            with self.assertRaises(psycopg2.IntegrityError):
                store.finish()
            self.assertNotIn('cwmassive_initialized', set(self.get_db_descr(cnx)))


if __name__ == '__main__':
    import unittest
    unittest.main()
