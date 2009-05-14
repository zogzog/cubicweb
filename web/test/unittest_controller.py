"""cubicweb.web.controller unit tests

"""

from datetime import datetime, date, time

from logilab.common.testlib import unittest_main

from cubicweb.devtools import apptest

class BaseControllerTC(apptest.ControllerTC):

    def test_parse_datetime_ok(self):
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24 12:18'),
                              datetime)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24'),
                              date)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24 12:18', 'Datetime'),
                              datetime)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24', 'Datetime'),
                              datetime)
        self.assertIsInstance(self.ctrl.parse_datetime('2006/06/24', 'Date'),
                              date)
        self.assertIsInstance(self.ctrl.parse_datetime('12:18', 'Time'),
                              time)

    def test_parse_datetime_ko(self):
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
