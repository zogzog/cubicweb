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
"""unit tests for module cubicweb.utils"""

import re
import decimal
import datetime

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.utils import make_uid, UStringIO, SizeConstrainedList, RepeatList
from cubicweb.entity import Entity

try:
    from cubicweb.utils import CubicWebJsonEncoder, json
except ImportError:
    json = None

class MakeUidTC(TestCase):
    def test_1(self):
        self.assertNotEqual(make_uid('xyz'), make_uid('abcd'))
        self.assertNotEqual(make_uid('xyz'), make_uid('xyz'))

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
        self.assertEqual(l[0], (1, 3))
        self.assertEqual(l[2], (1, 3))
        self.assertEqual(l[-1], (1, 3))
        self.assertEqual(len(l), 3)
        # XXX
        self.assertEqual(l[4], (1, 3))

        self.failIf(RepeatList(0, None))

    def test_slice(self):
        l = RepeatList(3, (1, 3))
        self.assertEqual(l[0:1], [(1, 3)])
        self.assertEqual(l[0:4], [(1, 3)]*3)
        self.assertEqual(l[:], [(1, 3)]*3)

    def test_iter(self):
        self.assertEqual(list(RepeatList(3, (1, 3))),
                          [(1, 3)]*3)

    def test_add(self):
        l = RepeatList(3, (1, 3))
        self.assertEqual(l + [(1, 4)], [(1, 3)]*3  + [(1, 4)])
        self.assertEqual([(1, 4)] + l, [(1, 4)] + [(1, 3)]*3)
        self.assertEqual(l + RepeatList(2, (2, 3)), [(1, 3)]*3 + [(2, 3)]*2)

        x = l + RepeatList(2, (1, 3))
        self.assertIsInstance(x, RepeatList)
        self.assertEqual(len(x), 5)
        self.assertEqual(x[0], (1, 3))

        x = l + [(1, 3)] * 2
        self.assertEqual(x, [(1, 3)] * 5)

    def test_eq(self):
        self.assertEqual(RepeatList(3, (1, 3)),
                          [(1, 3)]*3)

    def test_pop(self):
        l = RepeatList(3, (1, 3))
        l.pop(2)
        self.assertEqual(l, [(1, 3)]*2)


class SizeConstrainedListTC(TestCase):

    def test_append(self):
        l = SizeConstrainedList(10)
        for i in xrange(12):
            l.append(i)
        self.assertEqual(l, range(2, 12))

    def test_extend(self):
        testdata = [(range(5), range(5)),
                    (range(10), range(10)),
                    (range(12), range(2, 12)),
                    ]
        for extension, expected in testdata:
            l = SizeConstrainedList(10)
            l.extend(extension)
            yield self.assertEqual, l, expected


class JSONEncoderTC(TestCase):
    def setUp(self):
        if json is None:
            self.skipTest('json not available')

    def encode(self, value):
        return json.dumps(value, cls=CubicWebJsonEncoder)

    def test_encoding_dates(self):
        self.assertEqual(self.encode(datetime.datetime(2009, 9, 9, 20, 30)),
                          '"2009/09/09 20:30:00"')
        self.assertEqual(self.encode(datetime.date(2009, 9, 9)),
                          '"2009/09/09"')
        self.assertEqual(self.encode(datetime.time(20, 30)),
                          '"20:30:00"')

    def test_encoding_decimal(self):
        self.assertEqual(self.encode(decimal.Decimal('1.2')), '1.2')

    def test_encoding_bare_entity(self):
        e = Entity(None)
        e.cw_attr_cache['pouet'] = 'hop'
        e.eid = 2
        self.assertEqual(json.loads(self.encode(e)),
                          {'pouet': 'hop', 'eid': 2})

    def test_encoding_entity_in_list(self):
        e = Entity(None)
        e.cw_attr_cache['pouet'] = 'hop'
        e.eid = 2
        self.assertEqual(json.loads(self.encode([e])),
                          [{'pouet': 'hop', 'eid': 2}])

    def test_encoding_unknown_stuff(self):
        self.assertEqual(self.encode(TestCase), 'null')


if __name__ == '__main__':
    unittest_main()
