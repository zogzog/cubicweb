# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""

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

