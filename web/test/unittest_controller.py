"""cubicweb.web.controller unit tests

"""

from mx.DateTime import DateTimeType, DateTimeDeltaType

from logilab.common.testlib import unittest_main

from cubicweb.devtools import apptest

class BaseControllerTC(apptest.ControllerTC):
    def test_parse_datetime(self):
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24 12:18'), DateTimeType)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24'), DateTimeType)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24 12:18', 'Datetime'), DateTimeType)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24', 'Datetime'), DateTimeType)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24', 'Date'), DateTimeType)
        self.assertIsInstance(self.ctrl.parse_datetime('12:18', 'Time'), DateTimeDeltaType)
        self.assertRaises(ValueError,
                          self.ctrl.parse_datetime, '2006/06/24 12:188', 'Datetime')
        self.assertRaises(ValueError,
                          self.ctrl.parse_datetime, '2006/06/240', 'Datetime')
        self.assertRaises(ValueError,
                          self.ctrl.parse_datetime, '2006/06/24 12:18', 'Date')
        self.assertRaises(ValueError,
                          self.ctrl.parse_datetime, '2006/24/06', 'Date')
        self.assertRaises(ValueError,
                          self.ctrl.parse_datetime, '2006/06/240', 'Date')
        self.assertRaises(ValueError,
                          self.ctrl.parse_datetime, '12:188', 'Time')
        
if __name__ == '__main__':
    unittest_main()
