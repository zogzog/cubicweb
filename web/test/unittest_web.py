"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools.fake import FakeRequest
class AjaxReplaceUrlTC(TestCase):

    def test_ajax_replace_url(self):
        req = FakeRequest()
        arurl = req.build_ajax_replace_url
        # NOTE: for the simplest use cases, we could use doctest
        self.assertEquals(arurl('foo', 'Person P', 'list'),
                          "javascript: loadxhtml('foo', 'http://testing.fr/cubicweb/view?rql=Person%20P&amp;__notemplate=1&amp;vid=list', 'replace')")
        self.assertEquals(arurl('foo', 'Person P', 'oneline', name='bar', age=12),
                          '''javascript: loadxhtml('foo', 'http://testing.fr/cubicweb/view?age=12&amp;rql=Person%20P&amp;__notemplate=1&amp;vid=oneline&amp;name=bar', 'replace')''')


if __name__ == '__main__':
    unittest_main()
