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
"""unit tests for selectors mechanism"""

from operator import eq, lt, le, gt
from logilab.common.testlib import TestCase, unittest_main

from cubicweb import Binary
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.appobject import Selector, AndSelector, OrSelector
from cubicweb.selectors import (is_instance, adaptable, match_user_groups,
                                multi_lines_rset)
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
        self.assertEqual(selector(None), 2)
        selector = _1_() & _0_()
        self.assertEqual(selector(None), 0)
        selector = _0_() & _1_()
        self.assertEqual(selector(None), 0)

    def test_basic_or(self):
        selector = _1_() | _1_()
        self.assertEqual(selector(None), 1)
        selector = _1_() | _0_()
        self.assertEqual(selector(None), 1)
        selector = _0_() | _1_()
        self.assertEqual(selector(None), 1)
        selector = _0_() | _0_()
        self.assertEqual(selector(None), 0)

    def test_selector_and_function(self):
        selector = _1_() & _2_
        self.assertEqual(selector(None), 3)
        selector = _2_ & _1_()
        self.assertEqual(selector(None), 3)

    def test_three_and(self):
        selector = _1_() & _1_() & _1_()
        self.assertEqual(selector(None), 3)
        selector = _1_() & _0_() & _1_()
        self.assertEqual(selector(None), 0)
        selector = _0_() & _1_() & _1_()
        self.assertEqual(selector(None), 0)

    def test_three_or(self):
        selector = _1_() | _1_() | _1_()
        self.assertEqual(selector(None), 1)
        selector = _1_() | _0_() | _1_()
        self.assertEqual(selector(None), 1)
        selector = _0_() | _1_() | _1_()
        self.assertEqual(selector(None), 1)
        selector = _0_() | _0_() | _0_()
        self.assertEqual(selector(None), 0)

    def test_composition(self):
        selector = (_1_() & _1_()) & (_1_() & _1_())
        self.failUnless(isinstance(selector, AndSelector))
        self.assertEqual(len(selector.selectors), 4)
        self.assertEqual(selector(None), 4)
        selector = (_1_() & _0_()) | (_1_() & _1_())
        self.failUnless(isinstance(selector, OrSelector))
        self.assertEqual(len(selector.selectors), 2)
        self.assertEqual(selector(None), 2)

    def test_search_selectors(self):
        sel = is_instance('something')
        self.assertIs(sel.search_selector(is_instance), sel)
        csel = AndSelector(sel, Selector())
        self.assertIs(csel.search_selector(is_instance), sel)
        csel = AndSelector(Selector(), sel)
        self.assertIs(csel.search_selector(is_instance), sel)

    def test_inplace_and(self):
        selector = _1_()
        selector &= _1_()
        selector &= _1_()
        self.assertEqual(selector(None), 3)
        selector = _1_()
        selector &= _0_()
        selector &= _1_()
        self.assertEqual(selector(None), 0)
        selector = _0_()
        selector &= _1_()
        selector &= _1_()
        self.assertEqual(selector(None), 0)
        selector = _0_()
        selector &= _0_()
        selector &= _0_()
        self.assertEqual(selector(None), 0)

    def test_inplace_or(self):
        selector = _1_()
        selector |= _1_()
        selector |= _1_()
        self.assertEqual(selector(None), 1)
        selector = _1_()
        selector |= _0_()
        selector |= _1_()
        self.assertEqual(selector(None), 1)
        selector = _0_()
        selector |= _1_()
        selector |= _1_()
        self.assertEqual(selector(None), 1)
        selector = _0_()
        selector |= _0_()
        selector |= _0_()
        self.assertEqual(selector(None), 0)


class ImplementsSelectorTC(CubicWebTC):
    def test_etype_priority(self):
        req = self.request()
        f = req.create_entity('File', data_name=u'hop.txt', data=Binary('hop'))
        rset = f.as_rset()
        anyscore = is_instance('Any')(f.__class__, req, rset=rset)
        idownscore = adaptable('IDownloadable')(f.__class__, req, rset=rset)
        self.failUnless(idownscore > anyscore, (idownscore, anyscore))
        filescore = is_instance('File')(f.__class__, req, rset=rset)
        self.failUnless(filescore > idownscore, (filescore, idownscore))

    def test_etype_inheritance_no_yams_inheritance(self):
        cls = self.vreg['etypes'].etype_class('Personne')
        self.failIf(is_instance('Societe').score_class(cls, self.request()))

    def test_yams_inheritance(self):
        cls = self.vreg['etypes'].etype_class('Transition')
        self.assertEqual(is_instance('BaseTransition').score_class(cls, self.request()),
                          3)


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


class MultiLinesRsetSelectorTC(CubicWebTC):
    def setUp(self):
        super(MultiLinesRsetSelectorTC, self).setUp()
        self.req = self.request()
        self.req.execute('INSERT CWGroup G: G name "group1"')
        self.req.execute('INSERT CWGroup G: G name "group2"')
        self.commit()
        self.rset = self.req.execute('Any G WHERE G is CWGroup')

    def test_default_op_in_selector(self):
        expected = len(self.rset)
        selector = multi_lines_rset(expected)
        self.assertEqual(selector(None, self.req, self.rset), 1)
        self.assertEqual(selector(None, self.req, None), 0)
        selector = multi_lines_rset(expected + 1)
        self.assertEqual(selector(None, self.req, self.rset), 0)
        self.assertEqual(selector(None, self.req, None), 0)
        selector = multi_lines_rset(expected - 1)
        self.assertEqual(selector(None, self.req, self.rset), 0)
        self.assertEqual(selector(None, self.req, None), 0)

    def test_without_rset(self):
        expected = len(self.rset)
        selector = multi_lines_rset(expected)
        self.assertEqual(selector(None, self.req, None), 0)
        selector = multi_lines_rset(expected + 1)
        self.assertEqual(selector(None, self.req, None), 0)
        selector = multi_lines_rset(expected - 1)
        self.assertEqual(selector(None, self.req, None), 0)

    def test_with_operators(self):
        expected = len(self.rset)

        # Format     'expected', 'operator', 'assert'
        testdata = (( expected,         eq,        1),
                    ( expected+1,       eq,        0),
                    ( expected-1,       eq,        0),
                    ( expected,         le,        1),
                    ( expected+1,       le,        1),
                    ( expected-1,       le,        0),
                    ( expected-1,       gt,        1),
                    ( expected,         gt,        0),
                    ( expected+1,       gt,        0),
                    ( expected+1,       lt,        1),
                    ( expected,         lt,        0),
                    ( expected-1,       lt,        0))

        for (expected, operator, assertion) in testdata:
            selector = multi_lines_rset(expected, operator)
            yield self.assertEqual, selector(None, self.req, self.rset), assertion


if __name__ == '__main__':
    unittest_main()

