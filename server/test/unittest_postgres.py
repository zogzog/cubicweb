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

from datetime import datetime
from threading import Thread

from logilab.common.testlib import SkipTest

from cubicweb.devtools import PostgresApptestConfiguration
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.predicates import is_instance
from cubicweb.entities.adapters import IFTIndexableAdapter

from unittest_querier import FixedOffset

class PostgresTimeoutConfiguration(PostgresApptestConfiguration):
    default_sources = PostgresApptestConfiguration.default_sources.copy()
    default_sources['system'] = PostgresApptestConfiguration.default_sources['system'].copy()
    default_sources['system']['db-statement-timeout'] = 200


class PostgresFTITC(CubicWebTC):
    configcls = PostgresTimeoutConfiguration

    def test_eid_range(self):
        # concurrent allocation of eid ranges
        source = self.session.repo.sources_by_uri['system']
        range1 = []
        range2 = []
        def allocate_eid_ranges(session, target):
            for x in xrange(1, 10):
                eid = source.create_eid(session, count=x)
                target.extend(range(eid-x, eid))

        t1 = Thread(target=lambda: allocate_eid_ranges(self.session, range1))
        t2 = Thread(target=lambda: allocate_eid_ranges(self.session, range2))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(range1, sorted(range1))
        self.assertEqual(range2, sorted(range2))
        self.assertEqual(set(), set(range1) & set(range2))

    def test_occurence_count(self):
        with self.admin_access.repo_cnx() as cnx:
            c1 = cnx.create_entity('Card', title=u'c1',
                                   content=u'cubicweb cubicweb cubicweb')
            c2 = cnx.create_entity('Card', title=u'c3',
                                   content=u'cubicweb')
            c3 = cnx.create_entity('Card', title=u'c2',
                                   content=u'cubicweb cubicweb')
            cnx.commit()
            self.assertEqual(cnx.execute('Card X ORDERBY FTIRANK(X) DESC '
                                         'WHERE X has_text "cubicweb"').rows,
                             [[c1.eid,], [c3.eid,], [c2.eid,]])


    def test_attr_weight(self):
        class CardIFTIndexableAdapter(IFTIndexableAdapter):
            __select__ = is_instance('Card')
            attr_weight = {'title': 'A'}
        with self.temporary_appobjects(CardIFTIndexableAdapter):
            with self.admin_access.repo_cnx() as cnx:
                c1 = cnx.create_entity('Card', title=u'c1',
                                       content=u'cubicweb cubicweb cubicweb')
                c2 = cnx.create_entity('Card', title=u'c2',
                                       content=u'cubicweb cubicweb')
                c3 = cnx.create_entity('Card', title=u'cubicweb',
                                       content=u'autre chose')
                cnx.commit()
                self.assertEqual(cnx.execute('Card X ORDERBY FTIRANK(X) DESC '
                                             'WHERE X has_text "cubicweb"').rows,
                                 [[c3.eid,], [c1.eid,], [c2.eid,]])

    def test_entity_weight(self):
        class PersonneIFTIndexableAdapter(IFTIndexableAdapter):
            __select__ = is_instance('Personne')
            entity_weight = 2.0
        with self.temporary_appobjects(PersonneIFTIndexableAdapter):
            with self.admin_access.repo_cnx() as cnx:
                c1 = cnx.create_entity('Personne', nom=u'c1', prenom=u'cubicweb')
                c2 = cnx.create_entity('Comment', content=u'cubicweb cubicweb',
                                       comments=c1)
                c3 = cnx.create_entity('Comment', content=u'cubicweb cubicweb cubicweb',
                                       comments=c1)
                cnx.commit()
                self.assertEqual(cnx.execute('Any X ORDERBY FTIRANK(X) DESC '
                                             'WHERE X has_text "cubicweb"').rows,
                                  [[c1.eid,], [c3.eid,], [c2.eid,]])


    def test_tz_datetime(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute("INSERT Personne X: X nom 'bob', X tzdatenaiss %(date)s",
                        {'date': datetime(1977, 6, 7, 2, 0, tzinfo=FixedOffset(1))})
            datenaiss = cnx.execute("Any XD WHERE X nom 'bob', X tzdatenaiss XD")[0][0]
            self.assertEqual(datenaiss.tzinfo, None)
            self.assertEqual(datenaiss.utctimetuple()[:5], (1977, 6, 7, 1, 0))
            cnx.commit()
            cnx.execute("INSERT Personne X: X nom 'boby', X tzdatenaiss %(date)s",
                        {'date': datetime(1977, 6, 7, 2, 0)})
            datenaiss = cnx.execute("Any XD WHERE X nom 'boby', X tzdatenaiss XD")[0][0]
            self.assertEqual(datenaiss.tzinfo, None)
            self.assertEqual(datenaiss.utctimetuple()[:5], (1977, 6, 7, 2, 0))

class PostgresLimitSizeTC(CubicWebTC):
    configcls = PostgresApptestConfiguration

    def test(self):
        with self.admin_access.repo_cnx() as cnx:
            def sql(string):
                return cnx.system_sql(string).fetchone()[0]
            yield self.assertEqual, sql("SELECT limit_size('<p>hello</p>', 'text/html', 20)"), \
                '<p>hello</p>'
            yield self.assertEqual, sql("SELECT limit_size('<p>hello</p>', 'text/html', 2)"), \
                'he...'
            yield self.assertEqual, sql("SELECT limit_size('<br/>hello', 'text/html', 2)"), \
                'he...'
            yield self.assertEqual, sql("SELECT limit_size('<span class=\"1\">he</span>llo', 'text/html', 2)"), \
                'he...'
            yield self.assertEqual, sql("SELECT limit_size('<span>a>b</span>', 'text/html', 2)"), \
                'a>...'

    def test_statement_timeout(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.system_sql('select pg_sleep(0.1)')
            with self.assertRaises(Exception):
                cnx.system_sql('select pg_sleep(0.3)')


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
