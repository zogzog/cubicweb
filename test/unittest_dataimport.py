from StringIO import StringIO
from logilab.common.testlib import TestCase, unittest_main
from cubicweb import dataimport
class UcsvreaderTC(TestCase):

    def test_empty_lines_skipped(self):
        stream = StringIO('''a,b,c,d,
1,2,3,4,
,,,,
,,,,
''')
        self.assertEqual([[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u''],
                          ],
                         list(dataimport.ucsvreader(stream)))
        stream.seek(0)
        self.assertEqual([[u'a', u'b', u'c', u'd', u''],
                          [u'1', u'2', u'3', u'4', u''],
                          [u'', u'', u'', u'', u''],
                          [u'', u'', u'', u'', u'']
                          ],
                         list(dataimport.ucsvreader(stream, skip_empty=False)))


if __name__ == '__main__':
    unittest_main()
