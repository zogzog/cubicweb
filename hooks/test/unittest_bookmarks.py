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
from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

class BookmarkHooksTC(CubicWebTC):


    def test_auto_delete_bookmarks(self):
        with self.admin_access.repo_cnx() as cnx:
            beid = cnx.execute('INSERT Bookmark X: X title "hop", X path "view", X bookmarked_by U '
                               'WHERE U login "admin"')[0][0]
            cnx.execute('SET X bookmarked_by U WHERE U login "anon"')
            cnx.commit()
            cnx.execute('DELETE X bookmarked_by U WHERE U login "admin"')
            cnx.commit()
            self.assertTrue(cnx.execute('Any X WHERE X eid %(x)s', {'x': beid}))
            cnx.execute('DELETE X bookmarked_by U WHERE U login "anon"')
            cnx.commit()
            self.assertFalse(cnx.execute('Any X WHERE X eid %(x)s', {'x': beid}))

if __name__ == '__main__':
    unittest_main()
