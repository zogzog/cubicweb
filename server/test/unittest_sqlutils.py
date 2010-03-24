"""unit tests for module cubicweb.server.sqlutils
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import sys

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.server.sqlutils import *

BASE_CONFIG = {
    'db-driver' : 'Postgres',
    'db-host'   : 'crater',
    'db-name'   : 'cubicweb2_test',
    'db-user'   : 'toto',
    'db-upassword' : 'toto',
    }

class SQLAdapterMixInTC(TestCase):

    def test_init(self):
        o = SQLAdapterMixIn(BASE_CONFIG)
        self.assertEquals(o.dbhelper.dbencoding, 'UTF-8')

    def test_init_encoding(self):
        config = BASE_CONFIG.copy()
        config['db-encoding'] = 'ISO-8859-1'
        o = SQLAdapterMixIn(config)
        self.assertEquals(o.dbhelper.dbencoding, 'ISO-8859-1')

if __name__ == '__main__':
    unittest_main()
