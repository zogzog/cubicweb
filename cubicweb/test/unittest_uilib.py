# -*- coding: utf-8 -*-
# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unittests for cubicweb.uilib"""




import doctest
import pkg_resources
from unittest import skipIf

from logilab.common.testlib import TestCase, unittest_main

from cubicweb import uilib, utils as cwutils

lxml_version = pkg_resources.get_distribution('lxml').version.split('.')

class UILIBTC(TestCase):

    def test_remove_tags(self):
        """make sure remove_tags remove all tags"""
        data = [
            ('<h1>Hello</h1>', 'Hello'),
            ('<h1>Hello <a href="foo/bar"><b>s</b>pam</a></h1>', 'Hello spam'),
            ('<br>Hello<img src="doh.png"/>', 'Hello'),
            ('<p></p>', ''),
            ]
        for text, expected in data:
            got = uilib.remove_html_tags(text)
            self.assertEqual(got, expected)

    def test_fallback_safe_cut(self):
        self.assertEqual(uilib.fallback_safe_cut(u'ab <a href="hello">cd</a>', 4), u'ab c...')
        self.assertEqual(uilib.fallback_safe_cut(u'ab <a href="hello">cd</a>', 5), u'ab <a href="hello">cd</a>')
        self.assertEqual(uilib.fallback_safe_cut(u'ab <a href="hello">&amp;d</a>', 4), u'ab &amp;...')
        self.assertEqual(uilib.fallback_safe_cut(u'ab <a href="hello">&amp;d</a> ef', 5), u'ab &amp;d...')
        self.assertEqual(uilib.fallback_safe_cut(u'ab <a href="hello">&igrave;d</a>', 4), u'ab ì...')
        self.assertEqual(uilib.fallback_safe_cut(u'&amp; <a href="hello">&amp;d</a> ef', 4), u'&amp; &amp;d...')

    def test_lxml_safe_cut(self):
        self.assertEqual(uilib.safe_cut(u'aaa<div>aaad</div> ef', 4), u'<p>aaa</p><div>a...</div>')
        self.assertEqual(uilib.safe_cut(u'aaa<div>aaad</div> ef', 7), u'<p>aaa</p><div>aaad</div>...')
        self.assertEqual(uilib.safe_cut(u'aaa<div>aaad</div>', 7), u'<p>aaa</p><div>aaad</div>')
        # Missing ellipsis due to space management but we don't care
        self.assertEqual(uilib.safe_cut(u'ab <a href="hello">&amp;d</a>', 4), u'<p>ab <a href="hello">&amp;...</a></p>')

    def test_cut(self):
        """tests uilib.cut() behaviour"""
        data = [
            ('hello', 'hello'),
            ('hello world', 'hello wo...'),
            ("hell<b>O'</b> world", "hell<b>O..."),
            ]
        for text, expected in data:
            got = uilib.cut(text, 8)
            self.assertEqual(got, expected)

    def test_text_cut(self):
        """tests uilib.text_cut() behaviour with no text"""
        data = [('',''),
                ("""Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur.""",
                 "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod \
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, \
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo \
consequat."),
                ("""Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia deserunt mollit anim id est laborum
""",
                 "Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod \
tempor incididunt ut labore et dolore magna aliqua Ut enim ad minim veniam, \
quis nostrud exercitation ullamco laboris nisi"),
                ]
        for text, expected in data:
            got = uilib.text_cut(text, 30)
            self.assertEqual(got, expected)

    def test_soup2xhtml_0(self):
        self.assertEqual(uilib.soup2xhtml('hop\r\nhop', 'ascii'),
                          'hop\nhop')

    def test_soup2xhtml_1_1(self):
        self.assertEqual(uilib.soup2xhtml('hop', 'ascii'),
                          'hop')
        self.assertEqual(uilib.soup2xhtml('hop<div>', 'ascii'),
                          'hop<div/>')
        self.assertEqual(uilib.soup2xhtml('hop <div>', 'ascii'),
                          'hop <div/>')
        self.assertEqual(uilib.soup2xhtml('<div> hop', 'ascii'),
                          '<div> hop</div>')
        self.assertEqual(uilib.soup2xhtml('hop <div> hop', 'ascii'),
                          'hop <div> hop</div>')

    def test_soup2xhtml_1_2(self):
        self.assertEqual(uilib.soup2xhtml('hop </div>', 'ascii'),
                          'hop ')
        self.assertEqual(uilib.soup2xhtml('</div> hop', 'ascii'),
                          '<div/> hop')
        self.assertEqual(uilib.soup2xhtml('hop </div> hop', 'ascii'),
                          '<div>hop </div> hop')

    def test_soup2xhtml_2_1(self):
        self.assertEqual(uilib.soup2xhtml('hop <body>', 'ascii'),
                          'hop ')
        self.assertEqual(uilib.soup2xhtml('<body> hop', 'ascii'),
                          ' hop')
        self.assertEqual(uilib.soup2xhtml('hop <body> hop', 'ascii'),
                          'hop  hop')

    def test_soup2xhtml_2_2a(self):
        self.assertEqual(uilib.soup2xhtml('hop </body>', 'ascii'),
                          'hop ')
        self.assertEqual(uilib.soup2xhtml('</body> hop', 'ascii'),
                          ' hop')

    @skipIf(lxml_version < ['2', '2'], 'expected behaviour on recent version of lxml only')
    def test_soup2xhtml_2_2b(self):
        self.assertEqual(uilib.soup2xhtml('hop </body> hop', 'ascii'),
                          'hop  hop')

    def test_soup2xhtml_3_1(self):
        self.assertEqual(uilib.soup2xhtml('hop <html>', 'ascii'),
                          'hop ')
        self.assertEqual(uilib.soup2xhtml('<html> hop', 'ascii'),
                          ' hop')
        self.assertEqual(uilib.soup2xhtml('hop <html> hop', 'ascii'),
                          'hop  hop')

    def test_soup2xhtml_3_2(self):
        self.assertEqual(uilib.soup2xhtml('hop </html>', 'ascii'),
                          'hop ')
        self.assertEqual(uilib.soup2xhtml('</html> hop', 'ascii'),
                          ' hop')
        self.assertEqual(uilib.soup2xhtml('hop </html> hop', 'ascii'),
                          'hop  hop')

    def test_soup2xhtml_3_3(self):
        self.assertEqual(uilib.soup2xhtml('<script>test</script> hop ', 'ascii'),
                          ' hop ')

    def test_js(self):
        self.assertEqual(str(uilib.js.pouet(1, "2")),
                          'pouet(1,"2")')
        self.assertEqual(str(uilib.js.cw.pouet(1, "2")),
                          'cw.pouet(1,"2")')
        self.assertEqual(str(uilib.js.cw.pouet(1, "2").pouet(None)),
                          'cw.pouet(1,"2").pouet(null)')
        self.assertEqual(str(uilib.js.cw.pouet(1, cwutils.JSString("$")).pouet(None)),
                         'cw.pouet(1,$).pouet(null)')
        self.assertEqual(
            str(uilib.js.cw.pouet(
                1, {'call back': cwutils.JSString("cw.cb")}).pouet(None)),
            'cw.pouet(1,{"call back": cw.cb}).pouet(null)')


    def test_embedded_css(self):
        incoming = u"""voir le ticket <style type="text/css">@font-face { font-family: "Cambria"; }p.MsoNormal, li.MsoNormal, div.MsoNormal { margin: 0cm 0cm 10pt; font-size: 12pt; font-family: "Times New Roman"; }a:link, span.MsoHyperlink { color: blue; text-decoration: underline; }a:visited, span.MsoHyperlinkFollowed { color: purple; text-decoration: underline; }div.Section1 { page: Section1; }</style></p><p class="MsoNormal">text</p>"""
        expected = 'voir le ticket <p class="MsoNormal">text</p>'
        self.assertMultiLineEqual(uilib.soup2xhtml(incoming, 'ascii'), expected)

    def test_unknown_namespace(self):
        incoming = '''<table cellspacing="0" cellpadding="0" width="81" border="0" x:str="" style="width: 61pt; border-collapse: collapse">\
<colgroup><col width="81" style="width: 61pt; mso-width-source: userset; mso-width-alt: 2962"/></colgroup>\
<tbody><tr height="17" style="height: 12.75pt"><td width="81" height="17" style="border-right: #e0dfe3; border-top: #e0dfe3; border-left: #e0dfe3; width: 61pt; border-bottom: #e0dfe3; height: 12.75pt; background-color: transparent"><font size="2">XXXXXXX</font></td></tr></tbody>\
</table>'''
        expected = '''<table cellspacing="0" cellpadding="0" width="81" border="0">\
<colgroup><col width="81"/></colgroup>\
<tbody><tr height="17"><td width="81" height="17">XXXXXXX</td></tr></tbody>\
</table>'''
        self.assertMultiLineEqual(uilib.soup2xhtml(incoming, 'ascii'), expected)


def load_tests(loader, tests, ignore):
    import cubicweb.utils
    tests.addTests(doctest.DocTestSuite(uilib))
    return tests


if __name__ == '__main__':
    unittest_main()
