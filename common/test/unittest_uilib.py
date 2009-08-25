# -*- coding: utf-8 -*-
"""unittests for cubicweb.common.uilib

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.tree import Node

from cubicweb.common import uilib

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
            self.assertEquals(got, expected)

    def test_fallback_safe_cut(self):
        self.assertEquals(uilib.fallback_safe_cut(u'ab <a href="hello">cd</a>', 4), u'ab c...')
        self.assertEquals(uilib.fallback_safe_cut(u'ab <a href="hello">cd</a>', 5), u'ab <a href="hello">cd</a>')
        self.assertEquals(uilib.fallback_safe_cut(u'ab <a href="hello">&amp;d</a>', 4), u'ab &amp;...')
        self.assertEquals(uilib.fallback_safe_cut(u'ab <a href="hello">&amp;d</a> ef', 5), u'ab &amp;d...')
        self.assertEquals(uilib.fallback_safe_cut(u'ab <a href="hello">&igrave;d</a>', 4), u'ab ì...')
        self.assertEquals(uilib.fallback_safe_cut(u'&amp; <a href="hello">&amp;d</a> ef', 4), u'&amp; &amp;d...')

    def test_lxml_safe_cut(self):
        self.assertEquals(uilib.safe_cut(u'aaa<div>aaad</div> ef', 4), u'<p>aaa</p><div>a...</div>')
        self.assertEquals(uilib.safe_cut(u'aaa<div>aaad</div> ef', 7), u'<p>aaa</p><div>aaad</div>...')
        self.assertEquals(uilib.safe_cut(u'aaa<div>aaad</div>', 7), u'<p>aaa</p><div>aaad</div>')
        # Missing ellipsis due to space management but we don't care
        self.assertEquals(uilib.safe_cut(u'ab <a href="hello">&amp;d</a>', 4), u'<p>ab <a href="hello">&amp;...</a></p>')

    def test_cut(self):
        """tests uilib.cut() behaviour"""
        data = [
            ('hello', 'hello'),
            ('hello world', 'hello wo...'),
            ("hell<b>O'</b> world", "hell<b>O..."),
            ]
        for text, expected in data:
            got = uilib.cut(text, 8)
            self.assertEquals(got, expected)

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
            self.assertEquals(got, expected)

if __name__ == '__main__':
    unittest_main()

