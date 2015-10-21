# -*- coding: utf-8 -*-
# copyright 2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import os.path as osp
import itertools

from cubicweb.dataimport import ucsvreader
from cubicweb.devtools import testlib, PostgresApptestConfiguration
from cubicweb.devtools import startpgcluster, stoppgcluster
from cubicweb.dataimport.massive_store import MassiveObjectStore


HERE = osp.abspath(osp.dirname(__file__))


def setUpModule():
    startpgcluster(__file__)


def tearDownModule(*args):
    stoppgcluster(__file__)


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
        for code, gmt, dst, raw_offset in ucsvreader(open(osp.join(HERE, 'data/timeZones.txt')),
                                                     delimiter='\t'):
            cnx.create_entity('TimeZone', code=code, gmt=float(gmt),
                                    dst=float(dst), raw_offset=float(raw_offset))
        timezone_code = dict(cnx.execute('Any C, X WHERE X is TimeZone, X code C'))
        # Push data
        for ind, infos in enumerate(ucsvreader(open(dumpname),
                                               separator='\t',
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
                      'alternate_country_code':infos[9],
                      'admin_code_3': infos[12],
                      'admin_code_4': infos[13],
                      'population': population, 'elevation': elevation,
                      'gtopo30': gtopo, 'timezone': timezone_code.get(infos[17]),
                      'cwuri':  u'http://sws.geonames.org/%s/' % int(infos[0]),
                      'geonameid': int(infos[0]),
                      }
            store.create_entity('Location', **entity)

    def test_autoflush_metadata(self):
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
                                 {'t': 'Location'})
            self.assertEqual(len(crs.fetchall()), 0)
            store = MassiveObjectStore(cnx, autoflush_metadata=True)
            store.create_entity('Location', name=u'toto')
            store.flush()
            store.commit()
            store.cleanup()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
                                 {'t': 'Location'})
            self.assertEqual(len(crs.fetchall()), 1)

#    def test_no_autoflush_metadata(self):
#        with self.admin_access.repo_cnx() as cnx:
#            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
#                                      {'t': 'Location'})
#            self.assertEqual(len(crs.fetchall()), 0)
#        with self.admin_access.repo_cnx() as cnx:
#            store = MassiveObjectStore(cnx, autoflush_metadata=False)
#            store.create_entity('Location', name=u'toto')
#            store.flush()
#            store.commit()
#            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
#                                 {'t': 'Location'})
#            self.assertEqual(len(crs.fetchall()), 0)
#            store.flush_meta_data()
#            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
#                                 {'t': 'Location'})
#            self.assertEqual(len(crs.fetchall()), 1)
#            store.cleanup()

    def test_massimport_etype_metadata(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            timezone = store.create_entity('TimeZone')
            store.create_entity('Location', timezone=timezone.eid)
            store.flush()
            store.commit()
            eid, etname = cnx.execute('Any X, TN WHERE X timezone TZ, X is T, '
                                      'T name TN')[0]
            self.assertEqual(cnx.entity_from_eid(eid).cw_etype, etname)

    def test_do_not_drop_index(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, drop_index=False)
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
        self.assertIn('entities_pkey', indexes)
        self.assertIn('unique_entities_extid_idx', indexes)
        self.assertIn('owned_by_relation_p_key', indexes)
        self.assertIn('owned_by_relation_to_idx', indexes)

    def test_drop_index(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, drop_index=True)
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
        self.assertNotIn('entities_pkey', indexes)
        self.assertNotIn('unique_entities_extid_idx', indexes)
        self.assertNotIn('owned_by_relation_pkey', indexes)
        self.assertNotIn('owned_by_relation_to_idx', indexes)

    def test_drop_index_recreation(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, drop_index=True)
            store.cleanup()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
        self.assertIn('entities_pkey', indexes)
        self.assertIn('unique_entities_extid_idx', indexes)
        self.assertIn('owned_by_relation_p_key', indexes)
        self.assertIn('owned_by_relation_to_idx', indexes)

    def test_eids_seq_range(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, eids_seq_range=1000, eids_seq_start=50000)
            store.create_entity('Location', name=u'toto')
            store.flush()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql("SELECT * FROM entities_id_seq")
            self.assertTrue(crs.fetchone() > 50000)

    def test_eid_entity(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, eids_seq_range=1000, eids_seq_start=50000)
            entity = store.create_entity('Location', name=u'toto')
            store.flush()
            self.assertTrue(entity.eid > 50000)

    def test_eid_entity_2(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, eids_seq_range=1000, eids_seq_start=50000)
            entity = store.create_entity('Location', name=u'toto', eid=10000)
            store.flush()
        with self.admin_access.repo_cnx() as cnx:
            self.assertTrue(entity.eid==10000)

    def test_on_commit_callback(self):
        counter = itertools.count()
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, on_commit_callback=lambda:next(counter))
            store.create_entity('Location', name=u'toto')
            store.flush()
            store.commit()
        self.assertGreaterEqual(next(counter), 1)

    def test_on_rollback_callback(self):
        counter = itertools.count()
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, on_rollback_callback=lambda *_: next(counter))
            store.create_entity('Location', nm='toto')
            store.flush()
            store.commit()
        self.assertGreaterEqual(next(counter), 1)

    def test_slave_mode_indexes(self):
        with self.admin_access.repo_cnx() as cnx:
            slave_store = MassiveObjectStore(cnx, slave_mode=True)
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
        self.assertIn('entities_pkey', indexes)
        self.assertIn('unique_entities_extid_idx', indexes)
        self.assertIn('owned_by_relation_p_key', indexes)
        self.assertIn('owned_by_relation_to_idx', indexes)

    def test_slave_mode_exception(self):
        with self.admin_access.repo_cnx() as cnx:
            master_store = MassiveObjectStore(cnx, slave_mode=False)
            slave_store = MassiveObjectStore(cnx, slave_mode=True)
            self.assertRaises(RuntimeError, slave_store.flush_meta_data)
            self.assertRaises(RuntimeError, slave_store.cleanup)

    def test_simple_insert(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, autoflush_metadata=True)
            self.push_geonames_data(osp.join(HERE, 'data/geonames.csv'), store)
            store.flush()
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('Any X WHERE X is Location')
            self.assertEqual(len(rset), 4000)
            rset = cnx.execute('Any X WHERE X is Location, X timezone T')
            self.assertEqual(len(rset), 4000)

    def test_index_building(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, autoflush_metadata=True)
            self.push_geonames_data(osp.join(HERE, 'data/geonames.csv'), store)
            store.flush()

            # Check index
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
            self.assertNotIn('entities_pkey', indexes)
            self.assertNotIn('unique_entities_extid_idx', indexes)
            self.assertNotIn('owned_by_relation_p_key', indexes)
            self.assertNotIn('owned_by_relation_to_idx', indexes)

            # Cleanup -> index
            store.cleanup()

            # Check index again
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
            self.assertIn('entities_pkey', indexes)
            self.assertIn('unique_entities_extid_idx', indexes)
            self.assertIn('owned_by_relation_p_key', indexes)
            self.assertIn('owned_by_relation_to_idx', indexes)

    def test_flush_meta_data(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, autoflush_metadata=False)
            self.push_geonames_data(osp.join(HERE, 'data/geonames.csv'), store)
            store.flush()
            curs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
                                  {'t': 'Location'})
            self.assertEqual(len(curs.fetchall()), 0)
            # Flush metadata -> entities table is updated
            store.flush_meta_data()
            curs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
                                  {'t': 'Location'})
            self.assertEqual(len(curs.fetchall()), 4000)

    def test_multiple_insert(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.init_etype_table('TestLocation')
            store.cleanup()
            store = MassiveObjectStore(cnx)
            store.init_etype_table('TestLocation')
            store.cleanup()

    def test_multiple_insert_relation(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.init_relation_table('used_language')
            store.cleanup()
            store = MassiveObjectStore(cnx)
            store.init_relation_table('used_language')
            store.cleanup()

    def test_multiple_insert_drop_index(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, drop_index=False)
            store.init_relation_table('used_language')
            store.init_etype_table('TestLocation')
            store.cleanup()
            store = MassiveObjectStore(cnx)
            store.init_relation_table('used_language')
            store.init_etype_table('TestLocation')
            store.cleanup()

    def test_multiple_insert_drop_index_2(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.init_relation_table('used_language')
            store.init_etype_table('TestLocation')
            store.cleanup()
            store = MassiveObjectStore(cnx, drop_index=False)
            store.init_relation_table('used_language')
            store.init_etype_table('TestLocation')
            store.cleanup()

    def test_multiple_insert_drop_index_3(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, drop_index=False)
            store.init_relation_table('used_language')
            store.init_etype_table('TestLocation')
            store.cleanup()
            store = MassiveObjectStore(cnx, drop_index=False)
            store.init_relation_table('used_language')
            store.init_etype_table('TestLocation')
            store.cleanup()


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()

