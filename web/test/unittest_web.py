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

from logilab.common.testlib import TestCase, unittest_main
from cubicweb.devtools.fake import FakeRequest

class AjaxReplaceUrlTC(TestCase):

    def test_ajax_replace_url(self):
        req = FakeRequest()
        arurl = req.ajax_replace_url
        # NOTE: for the simplest use cases, we could use doctest
        self.assertEquals(arurl('foo', rql='Person P', vid='list'),
                          """javascript: $('#foo').loadxhtml("http://testing.fr/cubicweb/json?rql=Person%20P&fname=view&vid=list",null,"get","replace"); noop()""")
        self.assertEquals(arurl('foo', rql='Person P', vid='oneline', name='bar', age=12),
                          """javascript: $('#foo').loadxhtml("http://testing.fr/cubicweb/json?name=bar&age=12&rql=Person%20P&fname=view&vid=oneline",null,"get","replace"); noop()""")


if __name__ == '__main__':
    unittest_main()
