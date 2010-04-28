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
"""cubicweb.web.controller unit tests

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
