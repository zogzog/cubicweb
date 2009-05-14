"""unit tests for module cubicweb.server.sqlutils
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
        self.assertEquals(o.encoding, 'UTF-8')

    def test_init_encoding(self):
        config = BASE_CONFIG.copy()
        config['db-encoding'] = 'ISO-8859-1'
        o = SQLAdapterMixIn(config)
        self.assertEquals(o.encoding, 'ISO-8859-1')

if __name__ == '__main__':
    unittest_main()
