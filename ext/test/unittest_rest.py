# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
        self.assertTrue(out.startswith("<p>an error occurred while interpreting this rql directive: ObjectNotFound(u'toto',)</p>"))

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

    def test_rqltable_nocontent(self):
        context = self.context()
        out = rest_publish(context, """.. rql-table::""")
        self.assertIn("System Message: ERROR", out)
        self.assertIn("Content block expected for the &quot;rql-table&quot; "
                      "directive; none found" , out)

    def test_rqltable_norset(self):
        context = self.context()
        rql = "Any X WHERE X is CWUser, X firstname 'franky'"
        out = rest_publish(
            context, """\
.. rql-table::

            %(rql)s""" % {'rql': rql})
        self.assertIn("System Message: WARNING", out)
        self.assertIn("empty result set", out)

    def test_rqltable_nooptions(self):
        rql = """Any S,F,L WHERE X is CWUser, X surname S,
                                 X firstname F, X login L"""
        out = rest_publish(
            self.context(), """\
.. rql-table::

   %(rql)s
            """ % {'rql': rql})
        req = self.request()
        view = self.vreg['views'].select('table', req, rset=req.execute(rql))
        self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_vid(self):
        rql = """Any S,F,L WHERE X is CWUser, X surname S,
                                 X firstname F, X login L"""
        vid = 'mytable'
        out = rest_publish(
            self.context(), """\
.. rql-table::
   :vid: %(vid)s

   %(rql)s
            """ % {'rql': rql, 'vid': vid})
        req = self.request()
        view = self.vreg['views'].select(vid, req, rset=req.execute(rql))
        self.assertEqual(view.render(w=None)[49:], out[49:])
        self.assertIn(vid, out[:49])

    def test_rqltable_badvid(self):
        rql = """Any S,F,L WHERE X is CWUser, X surname S,
                                 X firstname F, X login L"""
        vid = 'mytabel'
        out = rest_publish(
            self.context(), """\
.. rql-table::
   :vid: %(vid)s

   %(rql)s
            """ % {'rql': rql, 'vid': vid})
        self.assertIn("fail to select '%s' view" % vid, out)

    def test_rqltable_headers(self):
        rql = """Any S,F,L WHERE X is CWUser, X surname S,
                                 X firstname F, X login L"""
        headers = ["nom", "prenom", "identifiant"]
        out = rest_publish(
            self.context(), """\
.. rql-table::
   :headers: %(headers)s

   %(rql)s
            """ % {'rql': rql, 'headers': ', '.join(headers)})
        req = self.request()
        view = self.vreg['views'].select('table', req, rset=req.execute(rql))
        view.headers = headers
        self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_headers_missing(self):
        rql = """Any S,F,L WHERE X is CWUser, X surname S,
                                 X firstname F, X login L"""
        headers = ["nom", "", "identifiant"]
        out = rest_publish(
            self.context(), """\
.. rql-table::
   :headers: %(headers)s

   %(rql)s
            """ % {'rql': rql, 'headers': ', '.join(headers)})
        req = self.request()
        view = self.vreg['views'].select('table', req, rset=req.execute(rql))
        view.headers = [headers[0], None, headers[2]]
        self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_headers_missing_edges(self):
        rql = """Any S,F,L WHERE X is CWUser, X surname S,
                                 X firstname F, X login L"""
        headers = [" ", "prenom", ""]
        out = rest_publish(
            self.context(), """\
.. rql-table::
   :headers: %(headers)s

   %(rql)s
            """ % {'rql': rql, 'headers': ', '.join(headers)})
        req = self.request()
        view = self.vreg['views'].select('table', req, rset=req.execute(rql))
        view.headers = [None, headers[1], None]
        self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_colvids(self):
        rql = """Any X,S,F,L WHERE X is CWUser, X surname S,
                                   X firstname F, X login L"""
        colvids = {0: "oneline"}
        out = rest_publish(
            self.context(), """\
.. rql-table::
   :colvids: %(colvids)s

   %(rql)s
            """ % {'rql': rql,
                   'colvids': ', '.join(["%d=%s" % (k, v)
                                         for k, v in colvids.iteritems()])
                  })
        req = self.request()
        view = self.vreg['views'].select('table', req, rset=req.execute(rql))
        view.cellvids = colvids
        self.assertEqual(view.render(w=None)[49:], out[49:])


if __name__ == '__main__':
    unittest_main()
