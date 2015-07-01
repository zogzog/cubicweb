# coding: utf-8
# copyright 2011-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from datetime import timedelta
from contextlib import contextmanager

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.sources import datafeed


class DataFeedTC(CubicWebTC):
    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            with self.base_parser(cnx):
                cnx.create_entity('CWSource', name=u'ô myfeed', type=u'datafeed',
                                  parser=u'testparser', url=u'ignored',
                                  config=u'synchronization-interval=1min')
                cnx.commit()

    @contextmanager
    def base_parser(self, session):
        class AParser(datafeed.DataFeedParser):
            __regid__ = 'testparser'
            def process(self, url, raise_on_error=False):
                entity = self.extid2entity('http://www.cubicweb.org/', 'Card',
                                           item={'title': u'cubicweb.org',
                                                 'content': u'the cw web site'},
                                           raise_on_error=raise_on_error)
                if not self.created_during_pull(entity):
                    self.notify_updated(entity)
            def before_entity_copy(self, entity, sourceparams):
                entity.cw_edited.update(sourceparams['item'])

        with self.temporary_appobjects(AParser):
            if u'ô myfeed' in self.repo.sources_by_uri:
                yield self.repo.sources_by_uri[u'ô myfeed']._get_parser(session)
            else:
                yield

    def test(self):
        self.assertIn(u'ô myfeed', self.repo.sources_by_uri)
        dfsource = self.repo.sources_by_uri[u'ô myfeed']
        self.assertNotIn('use_cwuri_as_url', dfsource.__dict__)
        self.assertEqual({'type': u'datafeed', 'uri': u'ô myfeed', 'use-cwuri-as-url': True},
                         dfsource.public_config)
        self.assertEqual(dfsource.use_cwuri_as_url, True)
        self.assertEqual(dfsource.latest_retrieval, None)
        self.assertEqual(dfsource.synchro_interval, timedelta(seconds=60))
        self.assertFalse(dfsource.fresh())
        # ensure source's logger name has been unormalized
        self.assertEqual(dfsource.info.__self__.name, 'cubicweb.sources.o myfeed')

        with self.repo.internal_cnx() as cnx:
            with self.base_parser(cnx):
                stats = dfsource.pull_data(cnx, force=True)
                cnx.commit()
                # test import stats
                self.assertEqual(sorted(stats), ['checked', 'created', 'updated'])
                self.assertEqual(len(stats['created']), 1)
                entity = cnx.execute('Card X').get_entity(0, 0)
                self.assertIn(entity.eid, stats['created'])
                self.assertEqual(stats['updated'], set())
                # test imported entities
                self.assertEqual(entity.title, 'cubicweb.org')
                self.assertEqual(entity.content, 'the cw web site')
                self.assertEqual(entity.cwuri, 'http://www.cubicweb.org/')
                self.assertEqual(entity.cw_source[0].name, u'ô myfeed')
                self.assertEqual(entity.cw_metainformation(),
                                 {'type': 'Card',
                                  'source': {'uri': u'ô myfeed', 'type': 'datafeed', 'use-cwuri-as-url': True},
                                  'extid': b'http://www.cubicweb.org/'}
                                 )
                self.assertEqual(entity.absolute_url(), 'http://www.cubicweb.org/')
                # test repo cache keys
                self.assertEqual(self.repo._type_source_cache[entity.eid],
                                 ('Card', b'http://www.cubicweb.org/', u'ô myfeed'))
                self.assertEqual(self.repo._extid_cache[b'http://www.cubicweb.org/'],
                                 entity.eid)
                # test repull
                stats = dfsource.pull_data(cnx, force=True)
                self.assertEqual(stats['created'], set())
                self.assertEqual(stats['updated'], set((entity.eid,)))
                # test repull with caches reseted
                self.repo._type_source_cache.clear()
                self.repo._extid_cache.clear()
                stats = dfsource.pull_data(cnx, force=True)
                self.assertEqual(stats['created'], set())
                self.assertEqual(stats['updated'], set((entity.eid,)))
                self.assertEqual(self.repo._type_source_cache[entity.eid],
                                 ('Card', b'http://www.cubicweb.org/', u'ô myfeed'))
                self.assertEqual(self.repo._extid_cache[b'http://www.cubicweb.org/'],
                                 entity.eid)

                self.assertEqual(dfsource.source_uris(cnx),
                                 {b'http://www.cubicweb.org/': (entity.eid, 'Card')})
                self.assertTrue(dfsource.latest_retrieval)
                self.assertTrue(dfsource.fresh())

        # test_rename_source
        with self.admin_access.repo_cnx() as cnx:
            cnx.entity_from_eid(dfsource.eid).cw_set(name=u"myrenamedfeed")
            cnx.commit()
            entity = cnx.execute('Card X').get_entity(0, 0)
            self.assertEqual(entity.cwuri, 'http://www.cubicweb.org/')
            self.assertEqual(entity.cw_source[0].name, 'myrenamedfeed')
            self.assertEqual(entity.cw_metainformation(),
                             {'type': 'Card',
                              'source': {'uri': 'myrenamedfeed', 'type': 'datafeed', 'use-cwuri-as-url': True},
                              'extid': b'http://www.cubicweb.org/'}
                             )
            self.assertEqual(self.repo._type_source_cache[entity.eid],
                             ('Card', b'http://www.cubicweb.org/', 'myrenamedfeed'))
            self.assertEqual(self.repo._extid_cache[b'http://www.cubicweb.org/'],
                             entity.eid)

            # test_delete_source
            cnx.execute('DELETE CWSource S WHERE S name "myrenamedfeed"')
            cnx.commit()
            self.assertFalse(cnx.execute('Card X WHERE X title "cubicweb.org"'))
            self.assertFalse(cnx.execute('Any X WHERE X has_text "cubicweb.org"'))

    def test_parser_retrieve_url_local(self):
        with self.admin_access.repo_cnx() as cnx:
            with self.base_parser(cnx) as parser:
                value = parser.retrieve_url('a string')
                self.assertEqual(200, value.getcode())
                self.assertEqual('a string', value.geturl())

    def test_update_url(self):
        dfsource = self.repo.sources_by_uri[u'ô myfeed']
        with self.admin_access.repo_cnx() as cnx:
            cnx.entity_from_eid(dfsource.eid).cw_set(url=u"http://pouet.com\nhttp://pouet.org")
            self.assertEqual(dfsource.urls, [u'ignored'])
            cnx.commit()
        self.assertEqual(dfsource.urls, [u"http://pouet.com", u"http://pouet.org"])


class DataFeedConfigTC(CubicWebTC):

    def test_use_cwuri_as_url_override(self):
        with self.admin_access.client_cnx() as cnx:
            cnx.create_entity('CWSource', name=u'myfeed', type=u'datafeed',
                              parser=u'testparser', url=u'ignored',
                              config=u'use-cwuri-as-url=no')
            cnx.commit()
        dfsource = self.repo.sources_by_uri['myfeed']
        self.assertEqual(dfsource.use_cwuri_as_url, False)
        self.assertEqual({'type': u'datafeed', 'uri': u'myfeed', 'use-cwuri-as-url': False},
                         dfsource.public_config)

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
