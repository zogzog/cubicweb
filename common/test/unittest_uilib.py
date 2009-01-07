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
       
    def test_safe_cut(self):
        """ tests uilib.safe_cut() behaviour with very long text"""
        
        data = [
            ('opkolk', '<div><p>opkolk</p></div>'),
            ("""<p>Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
 tempor incididunt <strong>ut</strong> labore et dolore magna aliqua. Ut enim ad minim veniam,
 quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
 consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
 cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
 proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
 Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
 tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
 quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
 consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
 cillum dolore eu fugiat nulla pariatur.</p> ""","""<div><p>Lorem ipsum dolor sit amet, consectetur</p></div>"""),
            ("""<p>empor incididunt utlabore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia d</p>""","""<div><p>empor incididunt utlabore et dolore magna aliqua.</p></div>"""),
            ("""empor <strong>incididunt</strong> utlabore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia""","""<div><p>empor <strong>incididunt</strong> utlabore et dolore magna aliqua.</p></div>"""),
            ("""<p>Lorem <strong>ipsum</strong> dolor <it>sit</it> amet, <strong>consectetur</strong> adipisicing elit, sed do eiusmod
 tempor incididunt <strong>ut</strong> labore et dolore magna aliqua. Ut enim ad minim veniam,
 quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
 consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
 cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
 proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
 Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
 tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
 quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
 consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
 cillum dolore eu fugiat nulla pariatur.</p>""","""<div><p>Lorem <strong>ipsum</strong> dolor <it>sit</it> amet, <strong>consectetur</strong></p></div>"""),
            ("""&iexcl;""",u"""<div><p>\xa1</p></div>"""),
            ("""<strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong>""",
             u"""<div><strong>\xa1 \xa1 \xa1 \xa1</strong></div>"""),
            ("""<strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong><strong>&iexcl; &iexcl; &iexcl; &iexcl;</strong>""",
             u"""<div><strong>\xa1 \xa1 \xa1 \xa1</strong><strong>\xa1 \xa1 \xa1 \xa1</strong><strong>\xa1 \xa1 \xa1 \xa1</strong><strong>\xa1 \xa1 \xa1 \xa1</strong><strong>\xa1 \xa1 \xa1 \xa1</strong><strong>\xa1 \xa1 \xa1 \xa1</strong><strong>\xa1 \xa1 \xa1 \xa1</strong><strong>\xa1 \xa1 \xa1 \xa1</strong></div>"""),
                      
                       
            ]
        for text, expected in data:
            got = uilib.safe_cut(text, 30)
            self.assertEquals(got, expected)

    def test_cut(self):
        """tests uilib.cut() behaviour"""
        data = [
            ('hello', 'hello'),
            ('hello world', 'hello...'),
            ("hell<b>O'</b> world", "hell<..."),
            ]
        for text, expected in data:
            got = uilib.cut(text, 8)
            self.assertEquals(got, expected)

    def test_text_cut_no_text(self):
        """tests uilib.text_cut() behaviour with no text"""
        data = [('','')]
        for text, expected in data:
            got = uilib.text_cut(text, 8)
            self.assertEquals(got, expected)

    def test_text_cut_long_text(self):
        """tests uilib.text_cut() behaviour with long text"""
        data = [("""Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
""","""Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat.""")]
        for text, expected in data:
            got = uilib.text_cut(text, 30)
            self.assertEquals(got, expected)

    def  test_text_cut_no_point(self):
        """tests uilib.text_cut() behaviour with no point"""
        data = [("""Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia deserunt mollit anim id est laborum
Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo
consequat Duis aute irure dolor in reprehenderit in voluptate velit esse
cillum dolore eu fugiat nulla pariatur Excepteur sint occaecat cupidatat non
proident, sunt in culpa qui officia deserunt mollit anim id est laborum
""","""Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi""")]
        for text, expected in data:
            got = uilib.text_cut(text, 30)
            self.assertEquals(got, expected)

    def test_ajax_replace_url(self):
        # NOTE: for the simplest use cases, we could use doctest
        arurl = uilib.ajax_replace_url
        self.assertEquals(arurl('foo', 'Person P'),
                          "javascript: replacePageChunk('foo', 'Person%20P');")
        self.assertEquals(arurl('foo', 'Person P', 'oneline'),
                          "javascript: replacePageChunk('foo', 'Person%20P', 'oneline');")
        self.assertEquals(arurl('foo', 'Person P', 'oneline', name='bar', age=12),
                          'javascript: replacePageChunk(\'foo\', \'Person%20P\', \'oneline\', {"age": 12, "name": "bar"});')
        self.assertEquals(arurl('foo', 'Person P', name='bar', age=12),
                          'javascript: replacePageChunk(\'foo\', \'Person%20P\', \'null\', {"age": 12, "name": "bar"});')

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

