"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from simplejson import loads

from logilab.common.testlib import unittest_main
from logilab.mtconverter import html_unescape

from cubicweb.devtools.apptest import EnvBasedTC

from cubicweb.web.htmlwidgets import TableWidget
from cubicweb.web.views import vid_from_rset

def loadjson(value):
    return loads(html_unescape(value))

class VidFromRsetTC(EnvBasedTC):

    def test_no_rset(self):
        req = self.request()
        self.assertEquals(vid_from_rset(req, None, self.schema), 'index')

    def test_no_entity(self):
        req = self.request()
        rset = self.execute('Any X WHERE X login "blabla"')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'noresult')

    def test_one_entity(self):
        req = self.request()
        rset = self.execute('Any X WHERE X login "admin"')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'primary')
        rset = self.execute('Any X, L WHERE X login "admin", X login L')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'primary')
        req.search_state = ('pasnormal',)
        rset = self.execute('Any X WHERE X login "admin"')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'outofcontext-search')

    def test_one_entity_eid(self):
        req = self.request()
        rset = self.execute('Any X WHERE X eid 1')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'primary')

    def test_more_than_one_entity_same_type(self):
        req = self.request()
        rset = self.execute('Any X WHERE X is CWUser')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'adaptedlist')
        rset = self.execute('Any X, L WHERE X login L')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'adaptedlist')

    def test_more_than_one_entity_diff_type(self):
        req = self.request()
        rset = self.execute('Any X WHERE X is IN (CWUser, CWGroup)')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'list')

    def test_more_than_one_entity_by_row(self):
        req = self.request()
        rset = self.execute('Any X, G WHERE X in_group G')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'table')

    def test_more_than_one_entity_by_row_2(self):
        req = self.request()
        rset = self.execute('Any X, GN WHERE X in_group G, G name GN')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'table')

    def test_aggregat(self):
        req = self.request()
        rset = self.execute('Any X, COUNT(T) GROUPBY X WHERE X is T')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'table')
        rset = self.execute('Any MAX(X) WHERE X is CWUser')
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'table')

    def test_subquery(self):
        rset = self.execute(
'DISTINCT Any X,N ORDERBY N '
'WITH X,N BEING ('
'     (DISTINCT Any P,N WHERE P is CWUser, P login N)'
'       UNION'
'     (DISTINCT Any W,N WHERE W is CWGroup, W name N))')
        req = self.request()
        self.assertEquals(vid_from_rset(req, rset, self.schema), 'table')


class TableViewTC(EnvBasedTC):

    def _prepare_entity(self):
        e = self.add_entity("State", name=u'<toto>', description=u'loo"ong blabla')
        rset = self.execute('Any X, D, CD, NOW - CD WHERE X is State, X description D, X creation_date CD, X eid %(x)s',
                            {'x': e.eid}, 'x')
        req = self.request()
        view = self.vreg['views'].select('table', req, rset=rset)
        return e, rset, view

    def test_headers(self):
        self.skip('implement me')

    def test_sortvalue(self):
        e, _, view = self._prepare_entity()
        expected = ['<toto>', 'loo"ong blabla'[:10], e.creation_date.strftime('%Y/%m/%d %H:%M:%S')]
        got = [loadjson(view.sortvalue(0, i)) for i in xrange(3)]
        self.assertListEqual(got, expected)
        # XXX sqlite does not handle Interval correctly
        # value = loadjson(view.sortvalue(0, 3))
        # self.assertAlmostEquals(value, rset.rows[0][3].seconds)

    def test_sortvalue_with_display_col(self):
        e, rset, view = self._prepare_entity()
        labels = view.columns_labels()
        table = TableWidget(view)
        table.columns = view.get_columns(labels, [1, 2], None, None, None, None, 0)
        expected = ['loo"ong blabla'[:10], e.creation_date.strftime('%Y/%m/%d %H:%M:%S')]
        got = [loadjson(value) for _, value in table.itercols(0)]
        self.assertListEqual(got, expected)


if __name__ == '__main__':
    unittest_main()
