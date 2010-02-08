"""unit tests for selectors mechanism

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.appobject import Selector, AndSelector, OrSelector
from cubicweb.selectors import implements, match_user_groups
from cubicweb.interfaces import IDownloadable
from cubicweb.web import action

class _1_(Selector):
    def __call__(self, *args, **kwargs):
        return 1

class _0_(Selector):
    def __call__(self, *args, **kwargs):
        return 0

def _2_(*args, **kwargs):
    return 2


class SelectorsTC(TestCase):
    def test_basic_and(self):
        selector = _1_() & _1_()
        self.assertEquals(selector(None), 2)
        selector = _1_() & _0_()
        self.assertEquals(selector(None), 0)
        selector = _0_() & _1_()
        self.assertEquals(selector(None), 0)

    def test_basic_or(self):
        selector = _1_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _1_() | _0_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _0_()
        self.assertEquals(selector(None), 0)

    def test_selector_and_function(self):
        selector = _1_() & _2_
        self.assertEquals(selector(None), 3)
        selector = _2_ & _1_()
        self.assertEquals(selector(None), 3)

    def test_three_and(self):
        selector = _1_() & _1_() & _1_()
        self.assertEquals(selector(None), 3)
        selector = _1_() & _0_() & _1_()
        self.assertEquals(selector(None), 0)
        selector = _0_() & _1_() & _1_()
        self.assertEquals(selector(None), 0)

    def test_three_or(self):
        selector = _1_() | _1_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _1_() | _0_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _1_() | _1_()
        self.assertEquals(selector(None), 1)
        selector = _0_() | _0_() | _0_()
        self.assertEquals(selector(None), 0)

    def test_composition(self):
        selector = (_1_() & _1_()) & (_1_() & _1_())
        self.failUnless(isinstance(selector, AndSelector))
        self.assertEquals(len(selector.selectors), 4)
        self.assertEquals(selector(None), 4)
        selector = (_1_() & _0_()) | (_1_() & _1_())
        self.failUnless(isinstance(selector, OrSelector))
        self.assertEquals(len(selector.selectors), 2)
        self.assertEquals(selector(None), 2)

    def test_search_selectors(self):
        sel = implements('something')
        self.assertIs(sel.search_selector(implements), sel)
        csel = AndSelector(sel, Selector())
        self.assertIs(csel.search_selector(implements), sel)
        csel = AndSelector(Selector(), sel)
        self.assertIs(csel.search_selector(implements), sel)


class ImplementsSelectorTC(CubicWebTC):
    def test_etype_priority(self):
        req = self.request()
        cls = self.vreg['etypes'].etype_class('File')
        anyscore = implements('Any').score_class(cls, req)
        idownscore = implements(IDownloadable).score_class(cls, req)
        self.failUnless(idownscore > anyscore, (idownscore, anyscore))
        filescore = implements('File').score_class(cls, req)
        self.failUnless(filescore > idownscore, (filescore, idownscore))

    def test_etype_inheritance_no_yams_inheritance(self):
        cls = self.vreg['etypes'].etype_class('Personne')
        self.failIf(implements('Societe').score_class(cls, self.request()))


class MatchUserGroupsTC(CubicWebTC):
    def test_owners_group(self):
        """tests usage of 'owners' group with match_user_group"""
        class SomeAction(action.Action):
            __regid__ = 'yo'
            category = 'foo'
            __select__ = match_user_groups('owners')
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register(SomeAction)
        SomeAction.__registered__(self.vreg['actions'])
        self.failUnless(SomeAction in self.vreg['actions']['yo'], self.vreg['actions'])
        try:
            # login as a simple user
            self.create_user('john')
            self.login('john')
            # it should not be possible to use SomeAction not owned objects
            req = self.request()
            rset = req.execute('Any G WHERE G is CWGroup, G name "managers"')
            self.failIf('yo' in dict(self.pactions(req, rset)))
            # insert a new card, and check that we can use SomeAction on our object
            self.execute('INSERT Card C: C title "zoubidou"')
            self.commit()
            req = self.request()
            rset = req.execute('Card C WHERE C title "zoubidou"')
            self.failUnless('yo' in dict(self.pactions(req, rset)), self.pactions(req, rset))
            # make sure even managers can't use the action
            self.restore_connection()
            req = self.request()
            rset = req.execute('Card C WHERE C title "zoubidou"')
            self.failIf('yo' in dict(self.pactions(req, rset)))
        finally:
            del self.vreg[SomeAction.__registry__][SomeAction.__regid__]

if __name__ == '__main__':
    unittest_main()

