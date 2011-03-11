# copyright 2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from __future__ import with_statement

from datetime import timedelta

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.sources import datafeed


class DataFeedTC(CubicWebTC):
    def setup_database(self):
        self.request().create_entity('CWSource', name=u'myfeed', type=u'datafeed',
                                    parser=u'testparser', url=u'ignored',
                                    config=u'synchronization-interval=1min')

    def test(self):
        self.assertIn('myfeed', self.repo.sources_by_uri)
        dfsource = self.repo.sources_by_uri['myfeed']
        self.assertNotIn(dfsource, self.repo.sources)
        self.assertEqual(dfsource.latest_retrieval, None)
        self.assertEqual(dfsource.synchro_interval, timedelta(seconds=60))
        self.assertFalse(dfsource.fresh())

        class AParser(datafeed.DataFeedParser):
            __regid__ = 'testparser'
            def process(self, url):
                entity = self.extid2entity('http://www.cubicweb.org/', 'Card',
                                  item={'title': u'cubicweb.org',
                                        'content': u'the cw web site'})
                if not self.created_during_pull(entity):
                    self.notify_updated(entity)
            def before_entity_copy(self, entity, sourceparams):
                entity.cw_edited.update(sourceparams['item'])

        with self.temporary_appobjects(AParser):
            stats = dfsource.pull_data(self.session, force=True)
            self.commit()
            # test import stats
            self.assertEqual(sorted(stats.keys()), ['created', 'updated'])
            self.assertEqual(len(stats['created']), 1)
            entity = self.execute('Card X').get_entity(0, 0)
            self.assertIn(entity.eid, stats['created'])
            self.assertEqual(stats['updated'], set())
            # test imported entities
            self.assertEqual(entity.title, 'cubicweb.org')
            self.assertEqual(entity.content, 'the cw web site')
            self.assertEqual(entity.cwuri, 'http://www.cubicweb.org/')
            self.assertEqual(entity.cw_source[0].name, 'myfeed')
            self.assertEqual(entity.cw_metainformation(),
                             {'type': 'Card',
                              'source': {'uri': 'system', 'type': 'native'},
                              'extid': 'http://www.cubicweb.org/'}
                             )
            # test repo cache keys
            self.assertEqual(self.repo._type_source_cache[entity.eid],
                             ('Card', 'system', 'http://www.cubicweb.org/'))
            self.assertEqual(self.repo._extid_cache[('http://www.cubicweb.org/', 'system')],
                             entity.eid)
            # test repull
            stats = dfsource.pull_data(self.session, force=True)
            self.assertEqual(stats['created'], set())
            self.assertEqual(stats['updated'], set((entity.eid,)))
            # test repull with caches reseted
            self.repo._type_source_cache.clear()
            self.repo._extid_cache.clear()
            stats = dfsource.pull_data(self.session, force=True)
            self.assertEqual(stats['created'], set())
            self.assertEqual(stats['updated'], set((entity.eid,)))
            self.assertEqual(self.repo._type_source_cache[entity.eid],
                             ('Card', 'system', 'http://www.cubicweb.org/'))
            self.assertEqual(self.repo._extid_cache[('http://www.cubicweb.org/', 'system')],
                             entity.eid)

        self.assertEqual(dfsource.source_cwuris(self.session),
                         {'http://www.cubicweb.org/': (entity.eid, 'Card')}
                         )
        self.assertTrue(dfsource.latest_retrieval)
        self.assertTrue(dfsource.fresh())

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
