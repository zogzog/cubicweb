# -*- coding: utf-8 -*-
"""unittests for cubicweb.common.uilib"""

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

tree = ('root', (
    ('child_1_1', (
    ('child_2_1', ()), ('child_2_2', (
    ('child_3_1', ()),
    ('child_3_2', ()),
    ('child_3_3', ()),
    )))),
    ('child_1_2', (('child_2_3', ()),))))

generated_html = """\
<table class="tree">
<tr><td class="tree_cell" rowspan="2"><div class="tree_cell">root</div></td><td class="tree_cell_1_1">&nbsp;</td><td class="tree_cell_1_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div class="tree_cell">child_1_1</div></td><td class="tree_cell_1_1">&nbsp;</td><td class="tree_cell_1_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div class="tree_cell">child_2_1</div></td><td class="tree_cell_0_1">&nbsp;</td><td class="tree_cell_0_2">&nbsp;</td><td rowspan="2">&nbsp;</td></tr>
<tr><td class="tree_cell_1_3">&nbsp;</td><td class="tree_cell_1_4">&nbsp;</td><td class="tree_cell_1_3">&nbsp;</td><td class="tree_cell_1_4">&nbsp;</td><td class="tree_cell_0_3">&nbsp;</td><td class="tree_cell_0_4">&nbsp;</td></tr>
<tr><td rowspan="2">&nbsp;</td><td class="tree_cell_2_1">&nbsp;</td><td class="tree_cell_2_2">&nbsp;</td><td rowspan="2">&nbsp;</td><td class="tree_cell_4_1">&nbsp;</td><td class="tree_cell_4_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div id="selected" class="tree_cell">child_2_2</div></td><td class="tree_cell_1_1">&nbsp;</td><td class="tree_cell_1_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div class="tree_cell">child_3_1</div></td></tr>
<tr><td class="tree_cell_2_3">&nbsp;</td><td class="tree_cell_2_4">&nbsp;</td><td class="tree_cell_4_3">&nbsp;</td><td class="tree_cell_4_4">&nbsp;</td><td class="tree_cell_1_3">&nbsp;</td><td class="tree_cell_1_4">&nbsp;</td></tr>
<tr><td rowspan="2">&nbsp;</td><td class="tree_cell_2_1">&nbsp;</td><td class="tree_cell_2_2">&nbsp;</td><td rowspan="2">&nbsp;</td><td class="tree_cell_0_1">&nbsp;</td><td class="tree_cell_0_2">&nbsp;</td><td rowspan="2">&nbsp;</td><td class="tree_cell_3_1">&nbsp;</td><td class="tree_cell_3_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div class="tree_cell">child_3_2</div></td></tr>
<tr><td class="tree_cell_2_3">&nbsp;</td><td class="tree_cell_2_4">&nbsp;</td><td class="tree_cell_0_3">&nbsp;</td><td class="tree_cell_0_4">&nbsp;</td><td class="tree_cell_3_3">&nbsp;</td><td class="tree_cell_3_4">&nbsp;</td></tr>
<tr><td rowspan="2">&nbsp;</td><td class="tree_cell_2_1">&nbsp;</td><td class="tree_cell_2_2">&nbsp;</td><td rowspan="2">&nbsp;</td><td class="tree_cell_0_1">&nbsp;</td><td class="tree_cell_0_2">&nbsp;</td><td rowspan="2">&nbsp;</td><td class="tree_cell_4_1">&nbsp;</td><td class="tree_cell_4_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div class="tree_cell">child_3_3</div></td></tr>
<tr><td class="tree_cell_2_3">&nbsp;</td><td class="tree_cell_2_4">&nbsp;</td><td class="tree_cell_0_3">&nbsp;</td><td class="tree_cell_0_4">&nbsp;</td><td class="tree_cell_4_3">&nbsp;</td><td class="tree_cell_4_4">&nbsp;</td></tr>
<tr><td rowspan="2">&nbsp;</td><td class="tree_cell_4_1">&nbsp;</td><td class="tree_cell_4_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div class="tree_cell">child_1_2</div></td><td class="tree_cell_5_1">&nbsp;</td><td class="tree_cell_5_2">&nbsp;</td><td class="tree_cell" rowspan="2"><div class="tree_cell">child_2_3</div></td><td class="tree_cell_0_1">&nbsp;</td><td class="tree_cell_0_2">&nbsp;</td><td rowspan="2">&nbsp;</td></tr>
<tr><td class="tree_cell_4_3">&nbsp;</td><td class="tree_cell_4_4">&nbsp;</td><td class="tree_cell_5_3">&nbsp;</td><td class="tree_cell_5_4">&nbsp;</td><td class="tree_cell_0_3">&nbsp;</td><td class="tree_cell_0_4">&nbsp;</td></tr>
</table>\
"""

def make_tree(tuple):
    n = Node(tuple[0])
    for child in tuple[1]:
        n.append(make_tree(child))
    return n

class UIlibHTMLGenerationTC(TestCase):
    """ a basic tree node, caracterised by an id"""
    def setUp(self):
        """ called before each test from this class """
        self.o = make_tree(tree)

    def test_generated_html(self):
        s = uilib.render_HTML_tree(self.o, selected_node="child_2_2")
        self.assertTextEqual(s, generated_html)


if __name__ == '__main__':
    unittest_main()

