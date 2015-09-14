# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unittest for cubicweb.dataimport.csv"""

from io import BytesIO

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.dataimport import csv


class UcsvreaderTC(TestCase):

    def test_empty_lines_skipped(self):
        stream = BytesIO(b'''a,b,c,d,
1,2,3,4,
,,,,
,,,,
''')
        self.assertEqual([[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u''],
                          ],
                         list(csv.ucsvreader(stream)))
        stream.seek(0)
        self.assertEqual([[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u''],
                          [u'', u'', u'', u'', u''],
                          [u'', u'', u'', u'', u'']
                          ],
                         list(csv.ucsvreader(stream, skip_empty=False)))

    def test_skip_first(self):
        stream = BytesIO(b'a,b,c,d,\n1,2,3,4,\n')
        reader = csv.ucsvreader(stream, skipfirst=True, ignore_errors=True)
        self.assertEqual(list(reader),
                         [[u'1', u'2', u'3', u'4', u'']])

        stream.seek(0)
        reader = csv.ucsvreader(stream, skipfirst=True, ignore_errors=False)
        self.assertEqual(list(reader),
                         [[u'1', u'2', u'3', u'4', u'']])

        stream.seek(0)
        reader = csv.ucsvreader(stream, skipfirst=False, ignore_errors=True)
        self.assertEqual(list(reader),
                         [[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u'']])

        stream.seek(0)
        reader = csv.ucsvreader(stream, skipfirst=False, ignore_errors=False)
        self.assertEqual(list(reader),
                         [[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u'']])


if __name__ == '__main__':
    unittest_main()
