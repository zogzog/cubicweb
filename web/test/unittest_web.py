"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.web import ajax_replace_url as  arurl
class AjaxReplaceUrlTC(TestCase):

    def test_ajax_replace_url(self):
        # NOTE: for the simplest use cases, we could use doctest
        self.assertEquals(arurl('foo', 'Person P'),
                          "javascript: replacePageChunk('foo', 'Person%20P');")
        self.assertEquals(arurl('foo', 'Person P', 'oneline'),
                          "javascript: replacePageChunk('foo', 'Person%20P', 'oneline');")
        self.assertEquals(arurl('foo', 'Person P', 'oneline', name='bar', age=12),
                          'javascript: replacePageChunk(\'foo\', \'Person%20P\', \'oneline\', {"age": 12, "name": "bar"});')
        self.assertEquals(arurl('foo', 'Person P', name='bar', age=12),
                          'javascript: replacePageChunk(\'foo\', \'Person%20P\', \'null\', {"age": 12, "name": "bar"});')


if __name__ == '__main__':
    unittest_main()
