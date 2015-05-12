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
from logilab.mtconverter import html_unescape

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.utils import json
from cubicweb.view import StartupView, TRANSITIONAL_DOCTYPE
from cubicweb.web.views import vid_from_rset

def loadjson(value):
    return json.loads(html_unescape(value))

class VidFromRsetTC(CubicWebTC):

    def test_no_rset(self):
        with self.admin_access.web_request() as req:
            self.assertEqual(vid_from_rset(req, None, self.schema), 'index')

    def test_no_entity(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X WHERE X login "blabla"')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'noresult')

    def test_one_entity(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X WHERE X login "admin"')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'primary')
            rset = req.execute('Any X, L WHERE X login "admin", X login L')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'primary')
            req.search_state = ('pasnormal',)
            rset = req.execute('Any X WHERE X login "admin"')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'outofcontext-search')

    def test_one_entity_eid(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X WHERE X eid 1')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'primary')

    def test_more_than_one_entity_same_type(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X WHERE X is CWUser')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'sameetypelist')
            rset = req.execute('Any X, L WHERE X login L')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'sameetypelist')

    def test_more_than_one_entity_diff_type(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X WHERE X is IN (CWUser, CWGroup)')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'list')

    def test_more_than_one_entity_by_row(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X, G WHERE X in_group G')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'table')

    def test_more_than_one_entity_by_row_2(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X, GN WHERE X in_group G, G name GN')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'table')

    def test_aggregat(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X, COUNT(T) GROUPBY X WHERE X is T')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'table')
            rset = req.execute('Any MAX(X) WHERE X is CWUser')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'table')

    def test_subquery(self):
        with self.admin_access.web_request() as req:
            rset = req.execute(
'DISTINCT Any X,N ORDERBY N '
'WITH X,N BEING ('
'     (DISTINCT Any P,N WHERE P is CWUser, P login N)'
'       UNION'
'     (DISTINCT Any W,N WHERE W is CWGroup, W name N))')
            self.assertEqual(vid_from_rset(req, rset, self.schema), 'table')


class TableViewTC(CubicWebTC):

    def _prepare_entity(self, req):
        e = req.create_entity("State", name=u'<toto>', description=u'loo"ong blabla')
        rset = req.execute('Any X, D, CD, NOW - CD WHERE X is State, '
                           'X description D, X creation_date CD, X eid %(x)s',
                           {'x': e.eid})
        view = self.vreg['views'].select('table', req, rset=rset)
        return e, rset, view

    def test_sortvalue(self):
        with self.admin_access.web_request() as req:
            e, _, view = self._prepare_entity(req)
            colrenderers = view.build_column_renderers()[:3]
            self.assertListEqual([renderer.sortvalue(0) for renderer in colrenderers],
                                 [u'<toto>', u'loo"ong blabla', e.creation_date])


class HTMLStreamTests(CubicWebTC):

    def test_set_doctype_reset_xmldecl(self):
        """
        tests `cubicweb.web.request.CubicWebRequestBase.set_doctype`
        with xmldecl reset
        """
        class MyView(StartupView):
            __regid__ = 'my-view'
            def call(self):
                self._cw.set_doctype('<!DOCTYPE html>')

        with self.admin_access.web_request() as req:
            with self.temporary_appobjects(MyView):
                html_source = self.view('my-view', req=req).source
                source_lines = [line.strip()
                                for line in html_source.splitlines(False)
                                if line.strip()]
                self.assertListEqual([b'<!DOCTYPE html>',
                                      b'<html xmlns:cubicweb="http://www.cubicweb.org" lang="en">'],
                                     source_lines[:2])

    def test_set_doctype_no_reset_xmldecl(self):
        """
        tests `cubicweb.web.request.CubicWebRequestBase.set_doctype`
        with no xmldecl reset
        """
        html_doctype = TRANSITIONAL_DOCTYPE.strip()
        class MyView(StartupView):
            __regid__ = 'my-view'
            def call(self):
                self._cw.set_doctype(html_doctype)
                self._cw.main_stream.set_htmlattrs([('lang', 'cz')])

        with self.admin_access.web_request() as req:
            with self.temporary_appobjects(MyView):
                html_source = self.view('my-view', req=req).source
                source_lines = [line.strip()
                                for line in html_source.splitlines(False)
                                if line.strip()]
                self.assertListEqual([html_doctype.encode('ascii'),
                                      b'<html xmlns:cubicweb="http://www.cubicweb.org" lang="cz">',
                                      b'<head>'],
                                     source_lines[:3])

class BaseViewsTC(CubicWebTC):

    def test_null(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any X WHERE X login "admin"')
            result = req.view('null', rset)
            self.assertEqual(result, u'')

    def test_final(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any "<script></script>"')
            result = req.view('final', rset)
            self.assertEqual(result, u'&lt;script&gt;&lt;/script&gt;')

    def test_incontext(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            result = entity.view('incontext')
            expected = (u'<a href="http://testing.fr/cubicweb/%d" title="">'
                        u'&lt;script&gt;&lt;/script&gt;</a>' % entity.eid)
            self.assertEqual(result, expected)

    def test_outofcontext(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            result = entity.view('outofcontext')
            expect = (u'<a href="http://testing.fr/cubicweb/%d" title="">'
                      u'&lt;script&gt;&lt;/script&gt;</a>' % entity.eid)
            self.assertEqual(result, expect)

    def test_outofcontext(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            result = entity.view('oneline')
            expect = (u'<a href="http://testing.fr/cubicweb/%d" title="">'
                      u'&lt;script&gt;&lt;/script&gt;</a>' % entity.eid)
            self.assertEqual(result, expect)

    def test_text(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            result = entity.view('text')
            self.assertEqual(result, u'<script></script>')

    def test_textincontext(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            result = entity.view('textincontext')
            self.assertEqual(result, u'<script></script>')

    def test_textoutofcontext(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            result = entity.view('textoutofcontext')
            self.assertEqual(result, u'<script></script>')

    def test_list(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            rset = req.execute('Any X WHERE X is CWUser')
            result = req.view('list', rset)
            expected = u'''<ul class="section">
<li><a href="http://testing.fr/cubicweb/%d" title="">&lt;script&gt;&lt;/script&gt;</a></li>
<li><a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin</a></li>
<li><a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a></li>
</ul>
''' % entity.eid
            self.assertEqual(result, expected)

    def test_simplelist(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            rset = req.execute('Any X WHERE X is CWUser')
            result = req.view('simplelist', rset)
            expected = (
                u'<div class="section">'
                u'<a href="http://testing.fr/cubicweb/%d" title="">'
                u'&lt;script&gt;&lt;/script&gt;</a></div>'
                u'<div class="section">'
                u'<a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin</a></div>'
                u'<div class="section">'
                u'<a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a></div>'
                % entity.eid
            )
            self.assertEqual(result, expected)

    def test_sameetypelist(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            rset = req.execute('Any X WHERE X is CWUser')
            result = req.view('sameetypelist', rset)
            expected = (
                u'<h1>CWUser_plural</h1>'
                u'<div class="section">'
                u'<a href="http://testing.fr/cubicweb/%d" title="">'
                u'&lt;script&gt;&lt;/script&gt;</a></div>'
                u'<div class="section">'
                u'<a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin</a></div>'
                u'<div class="section">'
                u'<a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a></div>'
                % entity.eid
            )
            self.assertEqual(expected, result)

    def test_sameetypelist(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            rset = req.execute('Any X WHERE X is CWUser')
            result = req.view('csv', rset)
            expected = (
                u'<a href="http://testing.fr/cubicweb/%d" title="">&lt;script&gt;&lt;/script&gt;</a>, '
                u'<a href="http://testing.fr/cubicweb/cwuser/admin" title="">admin</a>, '
                u'<a href="http://testing.fr/cubicweb/cwuser/anon" title="">anon</a>'
                % entity.eid
            )
            self.assertEqual(result, expected)

    def test_metadata(self):
        with self.admin_access.web_request() as req:
            entity = req.create_entity('CWUser', login=u'<script></script>', upassword=u'toto')
            entity.cw_set(creation_date=u'2000-01-01 00:00:00')
            entity.cw_set(modification_date=u'2015-01-01 00:00:00')
            result = entity.view('metadata')
            expected = (
                u'<div>CWUser #%d - <span>latest update on</span>'
                u' <span class="value">2015/01/01</span>,'
                u' <span>created on</span>'
                u' <span class="value">2000/01/01</span></div>'
                % entity.eid
            )
            self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest_main()
