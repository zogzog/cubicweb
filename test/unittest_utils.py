"""unit tests for module cubicweb.common.utils

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.utils import make_uid, UStringIO, SizeConstrainedList


class MakeUidTC(TestCase):
    def test_1(self):
        self.assertNotEquals(make_uid('xyz'), make_uid('abcd'))
        self.assertNotEquals(make_uid('xyz'), make_uid('xyz'))

    def test_2(self):
        d = {}
        while len(d)<10000:
            uid = make_uid('xyz')
            if d.has_key(uid):
                self.fail(len(d))
            d[uid] = 1


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


if __name__ == '__main__':
    unittest_main()
