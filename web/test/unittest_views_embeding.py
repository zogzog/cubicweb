"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.web.views.embedding import prefix_links

class UILIBTC(TestCase):


    def test_prefix_links(self):
        """suppose we are embedding http://embedded.com/page1.html"""
        orig = ['<a href="http://www.perdu.com">perdu ?</a>',
        '<a href="http://embedded.com/page1.html">perdu ?</a>',
        '<a href="/page2.html">perdu ?</a>',
        '<a href="page3.html">perdu ?</a>',
        '<img src="http://www.perdu.com/img.png"/>',
        '<img src="/img.png"/>',
        '<img src="img.png"/>',
        ]
        expected = ['<a href="PREFIXhttp%3A%2F%2Fwww.perdu.com">perdu ?</a>',
        '<a href="PREFIXhttp%3A%2F%2Fembedded.com%2Fpage1.html">perdu ?</a>',
        '<a href="PREFIXhttp%3A%2F%2Fembedded.com%2Fpage2.html">perdu ?</a>',
        '<a href="PREFIXhttp%3A%2F%2Fembedded.com%2Fpage3.html">perdu ?</a>',
        '<img src="http://www.perdu.com/img.png"/>',
        '<img src="http://embedded.com/img.png"/>',
        '<img src="http://embedded.com/img.png"/>',
        ]
        for orig_a, expected_a in zip(orig, expected):
            got = prefix_links(orig_a, 'PREFIX', 'http://embedded.com/page1.html')
            self.assertEquals(got, expected_a)

if __name__ == '__main__':
    unittest_main()

