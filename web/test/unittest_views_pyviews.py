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
from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

class PyViewsTC(CubicWebTC):

    def test_pyvaltable(self):
        view = self.vreg['views'].select('pyvaltable', self.request(),
                                         pyvalue=[[1, 'a'], [2, 'b']])
        content = view.render(pyvalue=[[1, 'a'], [2, 'b']],
                              headers=['num', 'char'])
        self.assertEquals(content.strip(), '''<table class="listing">
<thead><tr><th>num</th><th>char</th></tr>
</thead><tbody><tr><td>1</td><td>a</td></tr>
<tr><td>2</td><td>b</td></tr>
</tbody></table>''')

    def test_pyvallist(self):
        view = self.vreg['views'].select('pyvallist', self.request(),
                                         pyvalue=[1, 'a'])
        content = view.render(pyvalue=[1, 'a'])
        self.assertEquals(content.strip(), '''<ul>
<li>1</li>
<li>a</li>
</ul>''')

if __name__ == '__main__':
    unittest_main()
