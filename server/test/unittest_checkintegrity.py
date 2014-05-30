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

import sys
from StringIO import StringIO
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools import get_test_db_handler, TestServerConfiguration


from cubicweb.server.checkintegrity import check, reindex_entities

class CheckIntegrityTC(TestCase):

    def setUp(self):
        handler = get_test_db_handler(TestServerConfiguration(apphome=self.datadir))
        handler.build_db_cache()
        self.repo, _cnx = handler.get_repo_and_cnx()
        sys.stderr = sys.stdout = StringIO()

    def tearDown(self):
        sys.stderr = sys.__stderr__
        sys.stdout = sys.__stdout__
        self.repo.shutdown()

    def test_checks(self):
        with self.repo.internal_cnx() as cnx:
            check(self.repo, cnx, ('entities', 'relations', 'text_index', 'metadata'),
                  reindex=False, fix=True, withpb=False)

    def test_reindex_all(self):
        with self.repo.internal_cnx() as cnx:
            cnx.execute('INSERT Personne X: X nom "toto", X prenom "tutu"')
            cnx.commit()
            self.assertTrue(cnx.execute('Any X WHERE X has_text "tutu"'))
            reindex_entities(self.repo.schema, cnx, withpb=False)
            self.assertTrue(cnx.execute('Any X WHERE X has_text "tutu"'))

    def test_reindex_etype(self):
        with self.repo.internal_cnx() as cnx:
            cnx.execute('INSERT Personne X: X nom "toto", X prenom "tutu"')
            cnx.execute('INSERT Affaire X: X ref "toto"')
            cnx.commit()
            reindex_entities(self.repo.schema, cnx, withpb=False,
                             etypes=('Personne',))
            self.assertTrue(cnx.execute('Any X WHERE X has_text "tutu"'))
            self.assertTrue(cnx.execute('Any X WHERE X has_text "toto"'))

if __name__ == '__main__':
    unittest_main()
