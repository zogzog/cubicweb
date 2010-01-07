"""unit tests for module cubicweb.common.utils

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main

import simplejson
import decimal
import datetime

from cubicweb.utils import make_uid, UStringIO, SizeConstrainedList, CubicWebJsonEncoder


class MakeUidTC(TestCase):
    def test_1(self):
        self.assertNotEquals(make_uid('xyz'), make_uid('abcd'))
        self.assertNotEquals(make_uid('xyz'), make_uid('xyz'))

    def test_2(self):
        d = set()
        while len(d)<10000:
            uid = make_uid('xyz')
            if uid in d:
                self.fail(len(d))
            d.add(uid)


class UStringIOTC(TestCase):
    def test_boolean_value(self):
        self.assert_(UStringIO())


class SizeConstrainedListTC(TestCase):

    def test_append(self):
        l = SizeConstrainedList(10)
        for i in xrange(12):
            l.append(i)
        self.assertEquals(l, range(2, 12))

    def test_extend(self):
        testdata = [(range(5), range(5)),
                    (range(10), range(10)),
                    (range(12), range(2, 12)),
                    ]
        for extension, expected in testdata:
            l = SizeConstrainedList(10)
            l.extend(extension)
            yield self.assertEquals, l, expected

class JSONEncoerTests(TestCase):

    def encode(self, value):
        return simplejson.dumps(value, cls=CubicWebJsonEncoder)

    def test_encoding_dates(self):
        self.assertEquals(self.encode(datetime.datetime(2009, 9, 9, 20, 30)),
                          '"2009/09/09 20:30:00"')
        self.assertEquals(self.encode(datetime.date(2009, 9, 9)),
                          '"2009/09/09"')
        self.assertEquals(self.encode(datetime.time(20, 30)),
                          '"20:30:00"')

    def test_encoding_decimal(self):
        self.assertEquals(self.encode(decimal.Decimal('1.2')), '1.2')

    def test_encoding_unknown_stuff(self):
        self.assertEquals(self.encode(TestCase), 'null')

if __name__ == '__main__':
    unittest_main()
