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

from cubicweb.ext.rest import rest_publish


class RestTC(CubicWebTC):

    def context(self, req):
        return req.execute('CWUser X WHERE X login "admin"').get_entity(0, 0)

    def test_eid_role(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            self.assertEqual(rest_publish(context, ':eid:`%s`' % context.eid),
                             '<p><a class="reference"'
                             ' href="http://testing.fr/cubicweb/cwuser/admin">'
                             '#%s</a></p>\n' % context.eid)
            self.assertEqual(rest_publish(context, ':eid:`%s:some text`' % context.eid),
                             '<p><a class="reference"'
                             ' href="http://testing.fr/cubicweb/cwuser/admin">'
                             'some text</a></p>\n')

    def test_bad_rest_no_crash(self):
        with self.admin_access.web_request() as req:
            rest_publish(self.context(req), '''
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

    def test_disable_field_name_colspan(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            value = rest_publish(context, '''my field list:

:a long dumb param name: value
''')
            self.assertNotIn('colspan', value)

    def test_rql_role_with_vid(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            out = rest_publish(context,
                               ':rql:`Any X ORDERBY XL WHERE X is CWUser, X login XL:table`')
            self.assertTrue(out.endswith('<a href="http://testing.fr/cubicweb/cwuser/anon" '
                                         'title="">anon</a></td></tr>\n</tbody></table>'
                                         '</div></p>\n'))

    def test_rql_role_with_vid_empty_rset(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            out = rest_publish(context, ':rql:`Any X WHERE X is CWUser, X login "nono":table`')
            self.assertTrue(out.endswith('<p><div class="searchMessage"><strong>'
                                         'No result matching query</strong></div>\n</p>\n'))

    def test_rql_role_with_unknown_vid(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            out = rest_publish(context, ':rql:`Any X WHERE X is CWUser:toto`')
            self.assertTrue(out.startswith("<p>an error occurred while interpreting this "
                                           "rql directive: ObjectNotFound('toto'"),
                            out)

    def test_rql_role_without_vid(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            out = rest_publish(context, ':rql:`Any X,XL ORDERBY XL WHERE X is CWUser, X login XL`')
            self.assertEqual(out, u'<p><h1>CWUser_plural</h1><div class="section">'
                             '<a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin</a>'
                             '</div><div class="section">'
                             '<a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a>'
                             '</div></p>\n')

    def test_bookmark_role(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            rset = req.execute('INSERT Bookmark X: X title "hello", X path '
                               '"/view?rql=Any X,XL ORDERBY XL WHERE X is CWUser, X login XL"')
            eid = rset[0][0]
            out = rest_publish(context, ':bookmark:`%s`' % eid)
            self.assertEqual(out, u'<p><h1>CWUser_plural</h1><div class="section">'
                             '<a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin'
                             '</a></div><div class="section">'
                             '<a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon'
                             '</a></div></p>\n')

    def test_rqltable_nocontent(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            out = rest_publish(context, """.. rql-table::""")
            self.assertIn("System Message: ERROR", out)
            self.assertIn("Content block expected for the &quot;rql-table&quot; "
                          "directive; none found", out)

    def test_rqltable_norset(self):
        with self.admin_access.web_request() as req:
            context = self.context(req)
            rql = "Any X WHERE X is CWUser, X firstname 'franky'"
            out = rest_publish(
                context, """\
.. rql-table::

                %(rql)s""" % {'rql': rql})
            self.assertIn("System Message: WARNING", out)
            self.assertIn("empty result set", out)

    def test_rqltable_nooptions(self):
        with self.admin_access.web_request() as req:
            rql = "Any S,F,L WHERE X is CWUser, X surname S, X firstname F, X login L"
            out = rest_publish(
                self.context(req), """\
.. rql-table::

   %(rql)s
                """ % {'rql': rql})
            view = self.vreg['views'].select('table', req, rset=req.execute(rql))
            self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_vid(self):
        with self.admin_access.web_request() as req:
            rql = "Any S,F,L WHERE X is CWUser, X surname S, X firstname F, X login L"
            vid = 'mytable'
            out = rest_publish(
                self.context(req), """\
.. rql-table::
   :vid: %(vid)s

   %(rql)s
                """ % {'rql': rql, 'vid': vid})
            view = self.vreg['views'].select(vid, req, rset=req.execute(rql))
            self.assertEqual(view.render(w=None)[49:], out[49:])
            self.assertIn(vid, out[:49])

    def test_rqltable_badvid(self):
        with self.admin_access.web_request() as req:
            rql = "Any S,F,L WHERE X is CWUser, X surname S, X firstname F, X login L"
            vid = 'mytabel'
            out = rest_publish(
                self.context(req), """\
.. rql-table::
   :vid: %(vid)s

   %(rql)s
                """ % {'rql': rql, 'vid': vid})
            self.assertIn("fail to select '%s' view" % vid, out)

    def test_rqltable_headers(self):
        with self.admin_access.web_request() as req:
            rql = "Any S,F,L WHERE X is CWUser, X surname S, X firstname F, X login L"
            headers = ["nom", "prenom", "identifiant"]
            out = rest_publish(
                self.context(req), """\
.. rql-table::
   :headers: %(headers)s

   %(rql)s
                """ % {'rql': rql, 'headers': ', '.join(headers)})
            view = self.vreg['views'].select('table', req, rset=req.execute(rql))
            view.headers = headers
            self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_headers_missing(self):
        with self.admin_access.web_request() as req:
            rql = "Any S,F,L WHERE X is CWUser, X surname S, X firstname F, X login L"
            headers = ["nom", "", "identifiant"]
            out = rest_publish(
                self.context(req), """\
.. rql-table::
   :headers: %(headers)s

   %(rql)s
                """ % {'rql': rql, 'headers': ', '.join(headers)})
            view = self.vreg['views'].select('table', req, rset=req.execute(rql))
            view.headers = [headers[0], None, headers[2]]
            self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_headers_missing_edges(self):
        with self.admin_access.web_request() as req:
            rql = "Any S,F,L WHERE X is CWUser, X surname S, X firstname F, X login L"
            headers = [" ", "prenom", ""]
            out = rest_publish(
                self.context(req), """\
.. rql-table::
   :headers: %(headers)s

   %(rql)s
                """ % {'rql': rql, 'headers': ', '.join(headers)})
            view = self.vreg['views'].select('table', req, rset=req.execute(rql))
            view.headers = [None, headers[1], None]
            self.assertEqual(view.render(w=None)[49:], out[49:])

    def test_rqltable_colvids(self):
        with self.admin_access.web_request() as req:
            rql = "Any X,S,F,L WHERE X is CWUser, X surname S, X firstname F, X login L"
            colvids = {0: "oneline"}
            out = rest_publish(
                self.context(req), """\
.. rql-table::
   :colvids: %(colvids)s

   %(rql)s
                """
                % {'rql': rql,
                   'colvids': ', '.join(["%d=%s" % (k, v)
                                         for k, v in colvids.items()])}
            )
            view = self.vreg['views'].select('table', req, rset=req.execute(rql))
            view.cellvids = colvids
            self.assertEqual(view.render(w=None)[49:], out[49:])


if __name__ == '__main__':
    unittest_main()
