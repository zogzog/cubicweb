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
"""

"""
import sys
from StringIO import StringIO
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools import init_test_database


from cubicweb.server.checkintegrity import check

class CheckIntegrityTC(TestCase):
    def test(self):
        repo, cnx = init_test_database()
        sys.stderr = sys.stdout = StringIO()
        try:
            check(repo, cnx, ('entities', 'relations', 'text_index', 'metadata'),
                  reindex=True, fix=True, withpb=False)
        finally:
            sys.stderr = sys.__stderr__
            sys.stdout = sys.__stdout__
        repo.shutdown()

if __name__ == '__main__':
    unittest_main()
