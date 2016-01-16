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
"""SQL object store test case"""

import itertools

from cubicweb.dataimport import ucsvreader
from cubicweb.devtools import testlib, PostgresApptestConfiguration
from cubicweb.devtools import startpgcluster, stoppgcluster
from cubicweb.dataimport.pgstore import SQLGenObjectStore


def setUpModule():
    startpgcluster(__file__)


def tearDownModule(*args):
    stoppgcluster(__file__)


class SQLGenImportSimpleTC(testlib.CubicWebTC):
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
        cnx.commit()
        # Push data
        for ind, infos in enumerate(ucsvreader(open(dumpname, 'rb'),
                                               delimiter='\t',
                                               ignore_errors=True)):
            if ind > 99:
                break
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
            store = SQLGenObjectStore(cnx)
            store.prepare_insert_entity('Location', name=u'toto')
            store.flush()
            store.commit()
            cnx.commit()
        with self.admin_access.repo_cnx() as cnx:
            crs = cnx.system_sql('SELECT * FROM entities WHERE type=%(t)s',
                                 {'t': 'Location'})
            self.assertEqual(len(crs.fetchall()), 1)

    def test_sqlgenstore_etype_metadata(self):
        with self.admin_access.repo_cnx() as cnx:
            store = SQLGenObjectStore(cnx)
            timezone_eid = store.prepare_insert_entity('TimeZone')
            store.prepare_insert_entity('Location', timezone=timezone_eid)
            store.flush()
            store.commit()
            eid, etname = cnx.execute('Any X, TN WHERE X timezone TZ, X is T, '
                                      'T name TN')[0]
            self.assertEqual(cnx.entity_from_eid(eid).cw_etype, etname)

    def test_simple_insert(self):
        with self.admin_access.repo_cnx() as cnx:
            store = SQLGenObjectStore(cnx)
            self.push_geonames_data(self.datapath('geonames.csv'), store)
            store.flush()
            store.commit()
        with self.admin_access.repo_cnx() as cnx:
            rset = cnx.execute('Any X WHERE X is Location')
            self.assertEqual(len(rset), 100)
            rset = cnx.execute('Any X WHERE X is Location, X timezone T')
            self.assertEqual(len(rset), 100)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
