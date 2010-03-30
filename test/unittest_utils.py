"""unit tests for module cubicweb.utils

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import re
import decimal
import datetime

from logilab.common.testlib import TestCase, unittest_main
from cubicweb.utils import make_uid, UStringIO, SizeConstrainedList, RepeatList

try:
    import simplejson
    from cubicweb.utils import CubicWebJsonEncoder
except ImportError:
    simplejson = None

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
            if re.match('\d', uid):
                self.fail('make_uid must not return something begining with '
                          'some numeric character, got %s' % uid)
            d.add(uid)


class UStringIOTC(TestCase):
    def test_boolean_value(self):
        self.assert_(UStringIO())


class RepeatListTC(TestCase):

    def test_base(self):
        l = RepeatList(3, (1, 3))
        self.assertEquals(l[0], (1, 3))
        self.assertEquals(l[2], (1, 3))
        self.assertEquals(l[-1], (1, 3))
        self.assertEquals(len(l), 3)
        # XXX
        self.assertEquals(l[4], (1, 3))

        self.failIf(RepeatList(0, None))

    def test_slice(self):
        l = RepeatList(3, (1, 3))
        self.assertEquals(l[0:1], [(1, 3)])
        self.assertEquals(l[0:4], [(1, 3)]*3)
        self.assertEquals(l[:], [(1, 3)]*3)

    def test_iter(self):
        self.assertEquals(list(RepeatList(3, (1, 3))),
                          [(1, 3)]*3)

    def test_add(self):
        l = RepeatList(3, (1, 3))
        self.assertEquals(l + [(1, 4)], [(1, 3)]*3  + [(1, 4)])
        self.assertEquals([(1, 4)] + l, [(1, 4)] + [(1, 3)]*3)
        self.assertEquals(l + RepeatList(2, (2, 3)), [(1, 3)]*3 + [(2, 3)]*2)

        x = l + RepeatList(2, (1, 3))
        self.assertIsInstance(x, RepeatList)
        self.assertEquals(len(x), 5)
        self.assertEquals(x[0], (1, 3))

        x = l + [(1, 3)] * 2
        self.assertEquals(x, [(1, 3)] * 5)

    def test_eq(self):
        self.assertEquals(RepeatList(3, (1, 3)),
                          [(1, 3)]*3)

    def test_pop(self):
        l = RepeatList(3, (1, 3))
        l.pop(2)
        self.assertEquals(l, [(1, 3)]*2)

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

class JSONEncoderTC(TestCase):
    def setUp(self):
        if simplejson is None:
            self.skip('simplejson not available')

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
