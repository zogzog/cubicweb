# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

class PyViewsTC(CubicWebTC):

    def test_pyvaltable(self):
        with self.admin_access.web_request() as req:
            view = self.vreg['views'].select('pyvaltable', req,
                                             pyvalue=[[1, 'a'], [2, 'b']])
            content = view.render(pyvalue=[[1, 'a'], [2, 'b']],
                                  headers=['num', 'char'])
            self.assertEqual(content.strip(), '''<table class="listing"><tbody>\
<tr class="even" onmouseout="$(this).removeClass(&quot;highlighted&quot;)" onmouseover="$(this).addClass(&quot;highlighted&quot;);"><td >1</td><td >a</td></tr>
<tr class="odd" onmouseout="$(this).removeClass(&quot;highlighted&quot;)" onmouseover="$(this).addClass(&quot;highlighted&quot;);"><td >2</td><td >b</td></tr>
</tbody></table>''')

    def test_pyvallist(self):
        with self.admin_access.web_request() as req:
            view = self.vreg['views'].select('pyvallist', req,
                                             pyvalue=[1, 'a'])
            content = view.render(pyvalue=[1, 'a'])
            self.assertEqual(content.strip(), '''<ul>
<li>1</li>
<li>a</li>
</ul>''')

if __name__ == '__main__':
    unittest_main()
