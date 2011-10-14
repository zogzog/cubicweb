# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from __future__ import with_statement

from operator import eq, lt, le, gt
from logilab.common.testlib import TestCase, unittest_main

from cubicweb import Binary
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.appobject import Selector, AndSelector, OrSelector
from cubicweb.selectors import (is_instance, adaptable, match_kwargs, match_user_groups,
                                multi_lines_rset, score_entity, is_in_state,
                                on_transition, rql_condition, relation_possible)
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
        self.assertTrue(isinstance(selector, AndSelector))
        self.assertEqual(len(selector.selectors), 4)
        self.assertEqual(selector(None), 4)
        selector = (_1_() & _0_()) | (_1_() & _1_())
        self.assertTrue(isinstance(selector, OrSelector))
        self.assertEqual(len(selector.selectors), 2)
        self.assertEqual(selector(None), 2)

    def test_search_selectors(self):
        sel = is_instance('something')
        self.assertIs(sel.search_selector(is_instance), sel)
        csel = AndSelector(sel, Selector())
        self.assertIs(csel.search_selector(is_instance), sel)
        csel = AndSelector(Selector(), sel)
        self.assertIs(csel.search_selector(is_instance), sel)
        self.assertIs(csel.search_selector((AndSelector, OrSelector)), csel)
        self.assertIs(csel.search_selector((OrSelector, AndSelector)), csel)
        self.assertIs(csel.search_selector((is_instance, score_entity)),  sel)
        self.assertIs(csel.search_selector((score_entity, is_instance)), sel)

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
        self.assertTrue(idownscore > anyscore, (idownscore, anyscore))
        filescore = is_instance('File')(f.__class__, req, rset=rset)
        self.assertTrue(filescore > idownscore, (filescore, idownscore))

    def test_etype_inheritance_no_yams_inheritance(self):
        cls = self.vreg['etypes'].etype_class('Personne')
        self.assertFalse(is_instance('Societe').score_class(cls, self.request()))

    def test_yams_inheritance(self):
        cls = self.vreg['etypes'].etype_class('Transition')
        self.assertEqual(is_instance('BaseTransition').score_class(cls, self.request()),
                          3)


class WorkflowSelectorTC(CubicWebTC):
    def _commit(self):
        self.commit()
        self.wf_entity.cw_clear_all_caches()

    def setup_database(self):
        wf = self.shell().add_workflow("wf_test", 'StateFull', default=True)
        created   = wf.add_state('created', initial=True)
        validated = wf.add_state('validated')
        abandoned = wf.add_state('abandoned')
        wf.add_transition('validate', created, validated, ('managers',))
        wf.add_transition('forsake', (created, validated,), abandoned, ('managers',))

    def setUp(self):
        super(WorkflowSelectorTC, self).setUp()
        self.req = self.request()
        self.wf_entity = self.req.create_entity('StateFull', name=u'')
        self.rset = self.wf_entity.as_rset()
        self.adapter = self.wf_entity.cw_adapt_to('IWorkflowable')
        self._commit()
        self.assertEqual(self.adapter.state, 'created')
        # enable debug mode to state/transition validation on the fly
        self.vreg.config.debugmode = True

    def tearDown(self):
        self.vreg.config.debugmode = False
        super(WorkflowSelectorTC, self).tearDown()

    def test_is_in_state(self):
        for state in ('created', 'validated', 'abandoned'):
            selector = is_in_state(state)
            self.assertEqual(selector(None, self.req, rset=self.rset),
                             state=="created")

        self.adapter.fire_transition('validate')
        self._commit()
        self.assertEqual(self.adapter.state, 'validated')

        selector = is_in_state('created')
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
        selector = is_in_state('validated')
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)
        selector = is_in_state('validated', 'abandoned')
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)
        selector = is_in_state('abandoned')
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)

        self.adapter.fire_transition('forsake')
        self._commit()
        self.assertEqual(self.adapter.state, 'abandoned')

        selector = is_in_state('created')
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
        selector = is_in_state('validated')
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
        selector = is_in_state('validated', 'abandoned')
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)
        self.assertEqual(self.adapter.state, 'abandoned')
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)

    def test_is_in_state_unvalid_names(self):
        selector = is_in_state("unknown")
        with self.assertRaises(ValueError) as cm:
            selector(None, self.req, rset=self.rset)
        self.assertEqual(str(cm.exception),
                         "wf_test: unknown state(s): unknown")
        selector = is_in_state("weird", "unknown", "created", "weird")
        with self.assertRaises(ValueError) as cm:
            selector(None, self.req, rset=self.rset)
        self.assertEqual(str(cm.exception),
                         "wf_test: unknown state(s): unknown,weird")

    def test_on_transition(self):
        for transition in ('validate', 'forsake'):
            selector = on_transition(transition)
            self.assertEqual(selector(None, self.req, rset=self.rset), 0)

        self.adapter.fire_transition('validate')
        self._commit()
        self.assertEqual(self.adapter.state, 'validated')

        selector = on_transition("validate")
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)
        selector = on_transition("validate", "forsake")
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)
        selector = on_transition("forsake")
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)

        self.adapter.fire_transition('forsake')
        self._commit()
        self.assertEqual(self.adapter.state, 'abandoned')

        selector = on_transition("validate")
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
        selector = on_transition("validate", "forsake")
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)
        selector = on_transition("forsake")
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)

    def test_on_transition_unvalid_names(self):
        selector = on_transition("unknown")
        with self.assertRaises(ValueError) as cm:
            selector(None, self.req, rset=self.rset)
        self.assertEqual(str(cm.exception),
                         "wf_test: unknown transition(s): unknown")
        selector = on_transition("weird", "unknown", "validate", "weird")
        with self.assertRaises(ValueError) as cm:
            selector(None, self.req, rset=self.rset)
        self.assertEqual(str(cm.exception),
                         "wf_test: unknown transition(s): unknown,weird")

    def test_on_transition_with_no_effect(self):
        """selector will not be triggered with `change_state()`"""
        self.adapter.change_state('validated')
        self._commit()
        self.assertEqual(self.adapter.state, 'validated')

        selector = on_transition("validate")
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
        selector = on_transition("validate", "forsake")
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
        selector = on_transition("forsake")
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)


class RelationPossibleTC(CubicWebTC):

    def test_rqlst_1(self):
        req = self.request()
        selector = relation_possible('in_group')
        select = self.vreg.parse(req, 'Any X WHERE X is CWUser').children[0]
        score = selector(None, req, rset=1,
                         select=select, filtered_variable=select.defined_vars['X'])
        self.assertEqual(score, 1)

    def test_rqlst_2(self):
        req = self.request()
        selector = relation_possible('in_group')
        select = self.vreg.parse(req, 'Any 1, COUNT(X) WHERE X is CWUser, X creation_date XD, '
                                 'Y creation_date YD, Y is CWGroup '
                                 'HAVING DAY(XD)=DAY(YD)').children[0]
        score = selector(None, req, rset=1,
                         select=select, filtered_variable=select.defined_vars['X'])
        self.assertEqual(score, 1)


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
        self.assertTrue(SomeAction in self.vreg['actions']['yo'], self.vreg['actions'])
        try:
            # login as a simple user
            req = self.request()
            self.create_user(req, 'john')
            self.login('john')
            # it should not be possible to use SomeAction not owned objects
            req = self.request()
            rset = req.execute('Any G WHERE G is CWGroup, G name "managers"')
            self.assertFalse('yo' in dict(self.pactions(req, rset)))
            # insert a new card, and check that we can use SomeAction on our object
            self.execute('INSERT Card C: C title "zoubidou"')
            self.commit()
            req = self.request()
            rset = req.execute('Card C WHERE C title "zoubidou"')
            self.assertTrue('yo' in dict(self.pactions(req, rset)), self.pactions(req, rset))
            # make sure even managers can't use the action
            self.restore_connection()
            req = self.request()
            rset = req.execute('Card C WHERE C title "zoubidou"')
            self.assertFalse('yo' in dict(self.pactions(req, rset)))
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
        self.assertEqual(selector(None, self.req, rset=self.rset), 1)
        self.assertEqual(selector(None, self.req, None), 0)
        selector = multi_lines_rset(expected + 1)
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
        self.assertEqual(selector(None, self.req, None), 0)
        selector = multi_lines_rset(expected - 1)
        self.assertEqual(selector(None, self.req, rset=self.rset), 0)
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
            yield self.assertEqual, selector(None, self.req, rset=self.rset), assertion

    def test_match_kwargs_default(self):
        selector = match_kwargs( set( ('a', 'b') ) )
        self.assertEqual(selector(None, None, a=1, b=2), 2)
        self.assertEqual(selector(None, None, a=1), 0)
        self.assertEqual(selector(None, None, c=1), 0)
        self.assertEqual(selector(None, None, a=1, c=1), 0)

    def test_match_kwargs_any(self):
        selector = match_kwargs( set( ('a', 'b') ), mode='any')
        self.assertEqual(selector(None, None, a=1, b=2), 2)
        self.assertEqual(selector(None, None, a=1), 1)
        self.assertEqual(selector(None, None, c=1), 0)
        self.assertEqual(selector(None, None, a=1, c=1), 1)


class ScoreEntitySelectorTC(CubicWebTC):

    def test_intscore_entity_selector(self):
        req = self.request()
        rset = req.execute('Any E WHERE E eid 1')
        selector = score_entity(lambda x: None)
        self.assertEqual(selector(None, req, rset=rset), 0)
        selector = score_entity(lambda x: "something")
        self.assertEqual(selector(None, req, rset=rset), 1)
        selector = score_entity(lambda x: object)
        self.assertEqual(selector(None, req, rset=rset), 1)
        rset = req.execute('Any G LIMIT 2 WHERE G is CWGroup')
        selector = score_entity(lambda x: 10)
        self.assertEqual(selector(None, req, rset=rset), 20)
        selector = score_entity(lambda x: 10, mode='any')
        self.assertEqual(selector(None, req, rset=rset), 10)

    def test_rql_condition_entity(self):
        req = self.request()
        selector = rql_condition('X identity U')
        rset = req.user.as_rset()
        self.assertEqual(selector(None, req, rset=rset), 1)
        self.assertEqual(selector(None, req, entity=req.user), 1)
        self.assertEqual(selector(None, req), 0)

    def test_rql_condition_user(self):
        req = self.request()
        selector = rql_condition('U login "admin"', user_condition=True)
        self.assertEqual(selector(None, req), 1)
        selector = rql_condition('U login "toto"', user_condition=True)
        self.assertEqual(selector(None, req), 0)

if __name__ == '__main__':
    unittest_main()

