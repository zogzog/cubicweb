# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.ext.rest import rest_publish

class RestTC(CubicWebTC):
    def context(self):
        return self.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)

    def test_eid_role(self):
        context = self.context()
        self.assertEqual(rest_publish(context, ':eid:`%s`' % context.eid),
                          '<p><a class="reference" href="http://testing.fr/cubicweb/cwuser/admin">#%s</a></p>\n' % context.eid)
        self.assertEqual(rest_publish(context, ':eid:`%s:some text`' %  context.eid),
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


    def test_rql_role_with_vid(self):
        context = self.context()
        out = rest_publish(context, ':rql:`Any X WHERE X is CWUser:table`')
        self.assertTrue(out.endswith('<a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a>'
                                     '</td></tr>\n</tbody></table></div></p>\n'))

    def test_rql_role_with_vid_empty_rset(self):
        context = self.context()
        out = rest_publish(context, ':rql:`Any X WHERE X is CWUser, X login "nono":table`')
        self.assertTrue(out.endswith('<p><div class="searchMessage"><strong>No result matching query</strong></div>\n</p>\n'))

    def test_rql_role_with_unknown_vid(self):
        context = self.context()
        out = rest_publish(context, ':rql:`Any X WHERE X is CWUser:toto`')
        self.assertTrue(out.startswith("<p>an error occured while interpreting this rql directive: ObjectNotFound(u'toto',)</p>"))

    def test_rql_role_without_vid(self):
        context = self.context()
        out = rest_publish(context, ':rql:`Any X WHERE X is CWUser`')
        self.assertEqual(out, u'<p><h1>CWUser_plural</h1><div class="section"><a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin</a></div><div class="section"><a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a></div></p>\n')

    def test_bookmark_role(self):
        context = self.context()
        rset = self.execute('INSERT Bookmark X: X title "hello", X path "/view?rql=Any X WHERE X is CWUser"')
        eid = rset[0][0]
        out = rest_publish(context, ':bookmark:`%s`' % eid)
        self.assertEqual(out, u'<p><h1>CWUser_plural</h1><div class="section"><a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin</a></div><div class="section"><a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a></div></p>\n')

if __name__ == '__main__':
    unittest_main()
