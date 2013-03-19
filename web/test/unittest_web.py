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

    def test_ajax_replace_url_1(self):
        self._test_arurl("fname=view&rql=Person%20P&vid=list",
                         rql='Person P', vid='list')

    def test_ajax_replace_url_2(self):
        self._test_arurl("age=12&fname=view&name=bar&rql=Person%20P&vid=oneline",
                         rql='Person P', vid='oneline', name='bar', age=12)

    def _test_arurl(self, qs, **kwargs):
        req = FakeRequest()
        arurl = req.ajax_replace_url
        # NOTE: for the simplest use cases, we could use doctest
        url = arurl('foo', **kwargs)
        self.assertTrue(url.startswith('javascript:'))
        self.assertTrue(url.endswith('()'))
        cbname = url.split()[1][:-2]
        self.assertMultiLineEqual(
            'function %s() { $("#foo").loadxhtml("http://testing.fr/cubicweb/ajax?%s",'
            '{"pageid": "%s"},"get","replace"); }' %
            (cbname, qs, req.pageid),
            req.html_headers.post_inlined_scripts[0])

if __name__ == '__main__':
    unittest_main()
