# copyright 2013-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unittest for cubicweb.repoapi"""


from cubicweb.devtools.testlib import CubicWebTC

from cubicweb import ProgrammingError
from cubicweb.repoapi import Connection, connect, anonymous_cnx


class REPOAPITC(CubicWebTC):

    def test_cnx_basic_usage(self):
        """Test that a client connection can be used to access the database"""
        with self.admin_access.client_cnx() as cltcnx:
            # (1) some RQL request
            rset = cltcnx.execute('Any X WHERE X is CWUser')
            self.assertTrue(rset)
            # (2) ORM usage
            random_user = rset.get_entity(0, 0)
            # (3) Write operation
            random_user.cw_set(surname=u'babar')
            # (4) commit
            cltcnx.commit()
            rset = cltcnx.execute('''Any X WHERE X is CWUser,
                                                 X surname "babar"
                                  ''')
            self.assertTrue(rset)
            # prepare test for implicit rollback
            random_user = rset.get_entity(0, 0)
            random_user.cw_set(surname=u'celestine')
        # implicit rollback on exit
        with self.admin_access.client_cnx() as cltcnx:
            rset = cltcnx.execute('''Any X WHERE X is CWUser,
                                                 X surname "babar"
                                  ''')
            self.assertTrue(rset)

    def test_cnx_life_cycle(self):
        """Check that ClientConnection requires explicit open and close
        """
        access = self.admin_access
        cltcnx = Connection(access._session)
        # connection not open yet
        with self.assertRaises(ProgrammingError):
            cltcnx.execute('Any X WHERE X is CWUser')
        # connection open and working
        with cltcnx:
            cltcnx.execute('Any X WHERE X is CWUser')
        # connection closed
        with self.assertRaises(ProgrammingError):
            cltcnx.execute('Any X WHERE X is CWUser')

    def test_connect(self):
        """check that repoapi.connect works and returns a usable connection"""
        cnx = connect(self.repo, login='admin', password='gingkow')
        self.assertEqual('admin', cnx.user.login)
        with cnx:
            rset = cnx.execute('Any X WHERE X is CWUser')
            self.assertTrue(rset)

    def test_anonymous_connect(self):
        """check that you can get anonymous connection when the data exist"""
        cnx = anonymous_cnx(self.repo)
        self.assertEqual('anon', cnx.user.login)
        with cnx:
            rset = cnx.execute('Any X WHERE X is CWUser')
            self.assertTrue(rset)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
