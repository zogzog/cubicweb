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
from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

from cubicweb.ext.rest import rest_publish

class RestTC(CubicWebTC):
    def context(self):
        return self.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)

    def test_eid_role(self):
        context = self.context()
        self.assertEquals(rest_publish(context, ':eid:`%s`' % context.eid),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/cwuser/admin">#%s</a></p>\n' % context.eid)
        self.assertEquals(rest_publish(context, ':eid:`%s:some text`' %  context.eid),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/cwuser/admin">some text</a></p>\n')

    def test_bad_rest_no_crash(self):
        data = rest_publish(self.context(), '''
| card | implication     |
--------------------------
| 1-1  | N1 = N2         |
| 1-?  | N1 <= N2        |
| 1-+  | N1 >= N2        |
| 1-*  | N1>0 => N2>0    |
--------------------------
| ?-?  | N1 # N2         |
| ?-+  | N1 >= N2        |
| ?-*  | N1 #  N2        |
--------------------------
| +-+  | N1>0 => N2>0 et |
|      | N2>0 => N1>0    |
| +-*  | N1>+ => N2>0    |
--------------------------
| *-*  | N1#N2           |
--------------------------

''')

if __name__ == '__main__':
    unittest_main()
