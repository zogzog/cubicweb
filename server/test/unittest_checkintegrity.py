"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import sys
from StringIO import StringIO
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools import init_test_database


from cubicweb.server.checkintegrity import check

repo, cnx = init_test_database()

class CheckIntegrityTC(TestCase):
    def test(self):
        sys.stderr = sys.stdout = StringIO()
        try:
            check(repo, cnx, ('entities', 'relations', 'text_index', 'metadata'),
                  True, True)
        finally:
            sys.stderr = sys.__stderr__
            sys.stdout = sys.__stdout__

if __name__ == '__main__':
    unittest_main()
