# coding: utf-8
# copyright 2011-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb import ValidationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.sources import datafeed
from cubicweb.dataimport.stores import NoHookRQLObjectStore, MetaGenerator


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
                metagenerator = MetaGenerator(self._cw, source=self.source)
                store = NoHookRQLObjectStore(self._cw, metagenerator)
                store.prepare_insert_entity('Card',
                                            cwuri=u'http://www.cubicweb.org/',
                                            title=u'cubicweb.org',
                                            content=u'the cw web site')
                store.flush()
                store.commit()

        with self.temporary_appobjects(AParser):
            try:
                source = self.repo.source_by_uri(u'ô myfeed')
            except ValueError:
                yield
            else:
                yield source._get_parser(session)
        # vreg.unregister just pops appobjects from their regid entry,
        # completely remove the entry to ensure we have no side effect with
        # this empty entry.
        del self.vreg['parsers'][AParser.__regid__]

    def test(self):
        dfsource = self.repo.source_by_uri(u'ô myfeed')
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
                stats = dfsource.pull_data(cnx, force=True, raise_on_error=True)
                cnx.commit()
                # test import stats
                self.assertEqual(sorted(stats), ['checked', 'created', 'updated'])
                entity = cnx.execute('Card X').get_entity(0, 0)
                # test imported entities
                self.assertEqual(entity.title, 'cubicweb.org')
                self.assertEqual(entity.content, 'the cw web site')
                self.assertEqual(entity.cwuri, 'http://www.cubicweb.org/')
                self.assertEqual(entity.cw_source[0].name, u'ô myfeed')
                # test repo cache keys
                self.assertEqual(self.repo._type_cache[entity.eid], 'Card')

                self.assertTrue(dfsource.latest_retrieval)
                self.assertTrue(dfsource.fresh())

        # test_rename_source
        with self.admin_access.repo_cnx() as cnx:
            cnx.entity_from_eid(dfsource.eid).cw_set(name=u"myrenamedfeed")
            cnx.commit()
            entity = cnx.execute('Card X').get_entity(0, 0)
            self.assertEqual(entity.cwuri, 'http://www.cubicweb.org/')
            self.assertEqual(entity.cw_source[0].name, 'myrenamedfeed')
            self.assertEqual(self.repo._type_cache[entity.eid], 'Card')

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
        dfsource = self.repo.source_by_uri(u'ô myfeed')
        with self.admin_access.repo_cnx() as cnx:
            cnx.entity_from_eid(dfsource.eid).cw_set(url=u"http://pouet.com\nhttp://pouet.org")
            cnx.commit()
        self.assertEqual(dfsource.urls, [u'ignored'])
        dfsource = self.repo.source_by_uri(u'ô myfeed')
        self.assertEqual(dfsource.urls, [u"http://pouet.com", u"http://pouet.org"])

    def test_parser_not_found(self):
        dfsource = self.repo.source_by_uri(u'ô myfeed')
        with self.assertLogs('cubicweb.sources.o myfeed', level='ERROR') as cm:
            with self.repo.internal_cnx() as cnx:
                stats = dfsource.pull_data(cnx, force=True)
                importlog = cnx.find('CWDataImport').one().log
        self.assertIn('failed to load parser for', cm.output[0])
        self.assertEqual(stats, {})
        self.assertIn(u'failed to load parser for source &quot;ô myfeed&quot;',
                      importlog)

    def test_bad_config(self):
        with self.admin_access.repo_cnx() as cnx:
            with self.base_parser(cnx):
                with self.assertRaises(ValidationError) as cm:
                    cnx.create_entity(
                        'CWSource', name=u'error', type=u'datafeed', parser=u'testparser',
                        url=u'ignored',
                        config=u'synchronization-interval=1s')
                self.assertIn('synchronization-interval must be greater than 1 minute',
                              str(cm.exception))
                cnx.rollback()

                with self.assertRaises(ValidationError) as cm:
                    cnx.create_entity(
                        'CWSource', name=u'error', type=u'datafeed', parser=u'testparser',
                        url=None,
                        config=u'synchronization-interval=1min')
                self.assertIn('specifying an URL is mandatory',
                              str(cm.exception))
                cnx.rollback()

                with self.assertRaises(ValidationError) as cm:
                    cnx.create_entity(
                        'CWSource', name=u'error', type=u'datafeed', parser=u'testparser',
                        url=u'ignored',
                        config=u'synch-interval=1min')
                self.assertIn('unknown options synch-interval',
                              str(cm.exception))
                cnx.rollback()


class DataFeedConfigTC(CubicWebTC):

    def test_use_cwuri_as_url_override(self):
        with self.admin_access.client_cnx() as cnx:
            cnx.create_entity('CWSource', name=u'myfeed', type=u'datafeed',
                              parser=u'testparser', url=u'ignored',
                              config=u'use-cwuri-as-url=no')
            cnx.commit()
        dfsource = self.repo.source_by_uri('myfeed')
        self.assertEqual(dfsource.use_cwuri_as_url, False)
        self.assertEqual({'type': u'datafeed', 'uri': u'myfeed', 'use-cwuri-as-url': False},
                         dfsource.public_config)


if __name__ == '__main__':
    import unittest
    unittest.main()
