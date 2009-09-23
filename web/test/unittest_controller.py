"""cubicweb.web.controller unit tests

:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from datetime import datetime, date, time

from logilab.common.testlib import unittest_main

from cubicweb.devtools import testlib

class BaseControllerTC(testlib.CubicWebTC):

    def test_parse_datetime_ok(self):
        ctrl = self.vreg['controllers'].select('view', self.request())
        pd = ctrl._cw.parse_datetime
        self.assertIsInstance(pd('2006/06/24 12:18'), datetime)
        self.assertIsInstance(pd('2006/06/24'), date)
        self.assertIsInstance(pd('2006/06/24 12:18', 'Datetime'), datetime)
        self.assertIsInstance(pd('2006/06/24', 'Datetime'), datetime)
        self.assertIsInstance(pd('2006/06/24', 'Date'), date)
        self.assertIsInstance(pd('12:18', 'Time'), time)

    def test_parse_datetime_ko(self):
        ctrl = self.vreg['controllers'].select('view', self.request())
        pd = ctrl._cw.parse_datetime
        self.assertRaises(ValueError,
                          pd, '2006/06/24 12:188', 'Datetime')
        self.assertRaises(ValueError,
                          pd, '2006/06/240', 'Datetime')
        self.assertRaises(ValueError,
                          pd, '2006/06/24 12:18', 'Date')
        self.assertRaises(ValueError,
                          pd, '2006/24/06', 'Date')
        self.assertRaises(ValueError,
                          pd, '2006/06/240', 'Date')
        self.assertRaises(ValueError,
                          pd, '12:188', 'Time')

if __name__ == '__main__':
    unittest_main()
