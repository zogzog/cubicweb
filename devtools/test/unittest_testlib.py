"""unittests for gct.apptest module

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from cStringIO import StringIO
from unittest import TestSuite


from logilab.common.testlib import (TestCase, unittest_main, 
                                    SkipAwareTextTestRunner)

from cubicweb.devtools import htmlparser
from cubicweb.devtools.testlib import CubicWebTC

class WebTestTC(TestCase):

    def setUp(self):
        output = StringIO()
        self.runner = SkipAwareTextTestRunner(stream=output)

    def test_error_raised(self):
        class MyWebTest(CubicWebTC):

            def test_error_view(self):
                self.request().create_entity('Bug', title=u"bt")
                self.view('raising', self.execute('Bug B'), template=None)

            def test_correct_view(self):
                self.view('primary', self.execute('CWUser U'), template=None)

        tests = [MyWebTest('test_error_view'), MyWebTest('test_correct_view')]
        result = self.runner.run(TestSuite(tests))
        self.assertEquals(result.testsRun, 2)
        self.assertEquals(len(result.errors), 0)
        self.assertEquals(len(result.failures), 1)



HTML_PAGE = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
  <head><title>need a title</title></head>
  <body>
    <h1>Hello World !</h1>
  </body>
</html>
"""

HTML_PAGE2 = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
 <head><title>need a title</title></head>
 <body>
   <h1>Test</h1>
   <h1>Hello <a href="http://www.google.com">world</a> !</h1>
   <h2>h2 title</h2>
   <h3>h3 title</h3>
   <h2>antoher h2 title</h2>
   <h4>h4 title</h4>
   <p><a href="http://www.logilab.org">Logilab</a> introduces CW !</p>
 </body>
</html>
"""

HTML_PAGE_ERROR = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
 <head><title>need a title</title></head>
 <body>
   Logilab</a> introduces CW !
 </body>
</html>
"""

HTML_NON_STRICT = u"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html>
  <head><title>need a title</title></head>
  <body>
    <h1><a href="something.com">title</h1>
  </body>
</html>
"""


class HTMLPageInfoTC(TestCase):
    """test cases for PageInfo"""
    def setUp(self):
        parser = htmlparser.DTDValidator()
        self.page_info = parser.parse_string(HTML_PAGE2)

    def test_source1(self):
        """make sure source is stored correctly"""
        self.assertEquals(self.page_info.source, HTML_PAGE2)

    def test_source2(self):
        """make sure source is stored correctly - raise exception"""
        parser = htmlparser.DTDValidator()
        self.assertRaises(AssertionError, parser.parse_string, HTML_PAGE_ERROR)


    def test_has_title_no_level(self):
        """tests h? tags information"""
        self.assertEquals(self.page_info.has_title('Test'), True)
        self.assertEquals(self.page_info.has_title('Test '), False)
        self.assertEquals(self.page_info.has_title('Tes'), False)
        self.assertEquals(self.page_info.has_title('Hello world !'), True)

    def test_has_title_level(self):
        """tests h? tags information"""
        self.assertEquals(self.page_info.has_title('Test', level = 1), True)
        self.assertEquals(self.page_info.has_title('Test', level = 2), False)
        self.assertEquals(self.page_info.has_title('Test', level = 3), False)
        self.assertEquals(self.page_info.has_title('Test', level = 4), False)
        self.assertRaises(IndexError, self.page_info.has_title, 'Test', level = 5)

    def test_has_title_regexp_no_level(self):
        """tests has_title_regexp() with no particular level specified"""
        self.assertEquals(self.page_info.has_title_regexp('h[23] title'), True)

    def test_has_title_regexp_level(self):
        """tests has_title_regexp() with a particular level specified"""
        self.assertEquals(self.page_info.has_title_regexp('h[23] title', 2), True)
        self.assertEquals(self.page_info.has_title_regexp('h[23] title', 3), True)
        self.assertEquals(self.page_info.has_title_regexp('h[23] title', 4), False)

    def test_appears(self):
        """tests PageInfo.appears()"""
        self.assertEquals(self.page_info.appears('CW'), True)
        self.assertEquals(self.page_info.appears('Logilab'), True)
        self.assertEquals(self.page_info.appears('Logilab introduces'), True)
        self.assertEquals(self.page_info.appears('H2 title'), False)

    def test_has_link(self):
        """tests has_link()"""
        self.assertEquals(self.page_info.has_link('Logilab'), True)
        self.assertEquals(self.page_info.has_link('logilab'), False)
        self.assertEquals(self.page_info.has_link('Logilab', 'http://www.logilab.org'), True)
        self.assertEquals(self.page_info.has_link('Logilab', 'http://www.google.com'), False)

    def test_has_link_regexp(self):
        """test has_link_regexp()"""
        self.assertEquals(self.page_info.has_link_regexp('L[oi]gilab'), True)
        self.assertEquals(self.page_info.has_link_regexp('L[ai]gilab'), False)


if __name__ == '__main__':
    unittest_main()
