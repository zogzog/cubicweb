# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from cubicweb.devtools import init_test_database


from cubicweb.server.checkintegrity import check, reindex_entities

class CheckIntegrityTC(TestCase):
    def setUp(self):
        self.repo, self.cnx = init_test_database(apphome=self.datadir)
        self.execute = self.cnx.cursor().execute
        self.session = self.repo._sessions[self.cnx.sessionid]
        sys.stderr = sys.stdout = StringIO()

    def tearDown(self):
        sys.stderr = sys.__stderr__
        sys.stdout = sys.__stdout__
        self.cnx.close()
        self.repo.shutdown()

    def test_checks(self):
        check(self.repo, self.cnx, ('entities', 'relations', 'text_index', 'metadata'),
              reindex=False, fix=True, withpb=False)

    def test_reindex_all(self):
        self.execute('INSERT Personne X: X nom "toto", X prenom "tutu"')
        self.session.commit(False)
        self.failUnless(self.execute('Any X WHERE X has_text "tutu"'))
        reindex_entities(self.repo.schema, self.session, withpb=False)
        self.failUnless(self.execute('Any X WHERE X has_text "tutu"'))

    def test_reindex_etype(self):
        self.execute('INSERT Personne X: X nom "toto", X prenom "tutu"')
        self.execute('INSERT Affaire X: X ref "toto"')
        self.session.commit(False)
        reindex_entities(self.repo.schema, self.session, withpb=False,
                         etypes=('Personne',))
        self.failUnless(self.execute('Any X WHERE X has_text "tutu"'))
        self.failUnless(self.execute('Any X WHERE X has_text "toto"'))

if __name__ == '__main__':
    unittest_main()
