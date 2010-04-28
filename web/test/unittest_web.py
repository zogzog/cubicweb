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
