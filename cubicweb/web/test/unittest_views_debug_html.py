# copyright 2019 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

import inspect

from cubicweb.view import View
from cubicweb.devtools.testlib import CubicWebTC


class DebugHtmlRenderingTC(CubicWebTC):
    def setUp(self):
        super().setUp()
        View.debug_html_rendering = True

    def tearDown(self):
        super().tearDown()
        View.debug_html_rendering = False

    def test_debug_html_rendering_inject_tags(self):
        with self.admin_access.web_request() as req:
            view = self.vreg['views'].select("index", req)
            view_class = view.__class__
            page = view.render()

            self.assertIn('cubicweb-generated-by="%s.%s"' % (view_class.__module__,
                                                             view_class.__name__),
                          page)
            source_file = inspect.getsourcefile(view_class)
            self.assertIn('cubicweb-from-source="%s' % (source_file), page)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
