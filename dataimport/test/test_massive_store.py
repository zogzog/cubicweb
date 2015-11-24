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
        for code, gmt, dst, raw_offset in ucsvreader(open(osp.join(HERE, 'data/timeZones.txt'), 'rb'),
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
                      'alternate_country_code':infos[9],
                      'admin_code_3': infos[12],
                      'admin_code_4': infos[13],
                      'population': population, 'elevation': elevation,
                      'gtopo30': gtopo, 'timezone': timezone_code.get(infos[17]),
                      'cwuri':  u'http://sws.geonames.org/%s/' % int(infos[0]),
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
            timezone_eid = store.prepare_insert_entity('TimeZone')
            store.prepare_insert_entity('Location', timezone=timezone_eid)
            store.flush()
            store.commit()
            eid, etname = cnx.execute('Any X, TN WHERE X timezone TZ, X is T, '
                                      'T name TN')[0]
            self.assertEqual(cnx.entity_from_eid(eid).cw_etype, etname)

    def test_drop_index(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
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
            store = MassiveObjectStore(cnx)
            store.finish()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
        self.assertIn('entities_pkey', indexes)
        self.assertIn('unique_entities_extid_idx', indexes)
        self.assertIn('owned_by_relation_p_key', indexes)
        self.assertIn('owned_by_relation_to_idx', indexes)

    def test_eids_seq_range(self):
        class MyMassiveObjectStore(MassiveObjectStore):
            eids_seq_range = 1000
            eids_seq_start = 50000

        with self.admin_access.repo_cnx() as cnx:
            store = MyMassiveObjectStore(cnx)
            store.prepare_insert_entity('Location', name=u'toto')
            store.flush()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql("SELECT * FROM entities_id_seq")
            self.assertGreater(crs.fetchone()[0], 50000)

    def test_eid_entity(self):
        class MyMassiveObjectStore(MassiveObjectStore):
            eids_seq_range = 1000
            eids_seq_start = 50000

        with self.admin_access.repo_cnx() as cnx:
            store = MyMassiveObjectStore(cnx)
            eid = store.prepare_insert_entity('Location', name=u'toto')
            store.flush()
            self.assertGreater(eid, 50000)

    def test_eid_entity_2(self):
        class MyMassiveObjectStore(MassiveObjectStore):
            eids_seq_range = 1000
            eids_seq_start = 50000

        with self.admin_access.repo_cnx() as cnx:
            store = MyMassiveObjectStore(cnx)
            eid = store.prepare_insert_entity('Location', name=u'toto', eid=10000)
            store.flush()
        self.assertEqual(eid, 10000)

    def test_on_commit_callback(self):
        counter = itertools.count()
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, on_commit_callback=lambda:next(counter))
            store.prepare_insert_entity('Location', name=u'toto')
            store.flush()
            store.commit()
        self.assertGreaterEqual(next(counter), 1)

    def test_on_rollback_callback(self):
        counter = itertools.count()
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx, on_rollback_callback=lambda *_: next(counter))
            store.prepare_insert_entity('Location', nm='toto')
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
            self.assertRaises(RuntimeError, slave_store.finish)

    def test_simple_insert(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            self.push_geonames_data(osp.join(HERE, 'data/geonames.csv'), store)
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
            store.finish()

            # Check index again
            crs = cnx.system_sql('SELECT indexname FROM pg_indexes')
            indexes = [r[0] for r in crs.fetchall()]
            self.assertIn('entities_pkey', indexes)
            self.assertIn('unique_entities_extid_idx', indexes)
            self.assertIn('owned_by_relation_p_key', indexes)
            self.assertIn('owned_by_relation_to_idx', indexes)

    def test_multiple_insert(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.init_etype_table('TestLocation')
            store.finish()
            store = MassiveObjectStore(cnx)
            store.init_etype_table('TestLocation')
            store.finish()

    def test_multiple_insert_relation(self):
        with self.admin_access.repo_cnx() as cnx:
            store = MassiveObjectStore(cnx)
            store.init_relation_table('used_language')
            store.finish()
            store = MassiveObjectStore(cnx)
            store.init_relation_table('used_language')
            store.finish()


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
