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
"""unit tests for selectors mechanism"""

from operator import eq, lt, le, gt
from contextlib import contextmanager

from six.moves import range

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.decorators import clear_cache

from cubicweb import Binary
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.predicates import (is_instance, adaptable, match_kwargs, match_user_groups,
                                 multi_lines_rset, score_entity, is_in_state,
                                 rql_condition, relation_possible, match_form_params,
                                 paginated_rset)
from cubicweb.selectors import on_transition # XXX on_transition is deprecated
from cubicweb.view import EntityAdapter
from cubicweb.web import action



class ImplementsTC(CubicWebTC):
    def test_etype_priority(self):
        with self.admin_access.web_request() as req:
            f = req.create_entity('FakeFile', data_name=u'hop.txt', data=Binary(b'hop'),
                                  data_format=u'text/plain')
            rset = f.as_rset()
            anyscore = is_instance('Any')(f.__class__, req, rset=rset)
            idownscore = adaptable('IDownloadable')(f.__class__, req, rset=rset)
            self.assertTrue(idownscore > anyscore, (idownscore, anyscore))
            filescore = is_instance('FakeFile')(f.__class__, req, rset=rset)
            self.assertTrue(filescore > idownscore, (filescore, idownscore))

    def test_etype_inheritance_no_yams_inheritance(self):
        cls = self.vreg['etypes'].etype_class('Personne')
        with self.admin_access.web_request() as req:
            self.assertFalse(is_instance('Societe').score_class(cls, req))

    def test_yams_inheritance(self):
        cls = self.vreg['etypes'].etype_class('Transition')
        with self.admin_access.web_request() as req:
            self.assertEqual(is_instance('BaseTransition').score_class(cls, req),
                             3)

    def test_outer_join(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any U,B WHERE B? bookmarked_by U, U login "anon"')
            self.assertEqual(is_instance('Bookmark')(None, req, rset=rset, row=0, col=1),
                             0)


class WorkflowSelectorTC(CubicWebTC):

    def setUp(self):
        super(WorkflowSelectorTC, self).setUp()
        # enable debug mode to state/transition validation on the fly
        self.vreg.config.debugmode = True

    def tearDown(self):
        self.vreg.config.debugmode = False
        super(WorkflowSelectorTC, self).tearDown()

    def setup_database(self):
        with self.admin_access.shell() as shell:
            wf = shell.add_workflow("wf_test", 'StateFull', default=True)
            created   = wf.add_state('created', initial=True)
            validated = wf.add_state('validated')
            abandoned = wf.add_state('abandoned')
            wf.add_transition('validate', created, validated, ('managers',))
            wf.add_transition('forsake', (created, validated,), abandoned, ('managers',))

    @contextmanager
    def statefull_stuff(self):
        with self.admin_access.web_request() as req:
            wf_entity = req.create_entity('StateFull', name=u'')
            rset = wf_entity.as_rset()
            adapter = wf_entity.cw_adapt_to('IWorkflowable')
            req.cnx.commit()
            self.assertEqual(adapter.state, 'created')
            yield req, wf_entity, rset, adapter

    def test_is_in_state(self):
        with self.statefull_stuff() as (req, wf_entity, rset, adapter):
            for state in ('created', 'validated', 'abandoned'):
                selector = is_in_state(state)
                self.assertEqual(selector(None, req, rset=rset),
                                 state=="created")

            adapter.fire_transition('validate')
            req.cnx.commit(); wf_entity.cw_clear_all_caches()
            self.assertEqual(adapter.state, 'validated')

            clear_cache(rset, 'get_entity')

            selector = is_in_state('created')
            self.assertEqual(selector(None, req, rset=rset), 0)
            selector = is_in_state('validated')
            self.assertEqual(selector(None, req, rset=rset), 1)
            selector = is_in_state('validated', 'abandoned')
            self.assertEqual(selector(None, req, rset=rset), 1)
            selector = is_in_state('abandoned')
            self.assertEqual(selector(None, req, rset=rset), 0)

            adapter.fire_transition('forsake')
            req.cnx.commit(); wf_entity.cw_clear_all_caches()
            self.assertEqual(adapter.state, 'abandoned')

            clear_cache(rset, 'get_entity')

            selector = is_in_state('created')
            self.assertEqual(selector(None, req, rset=rset), 0)
            selector = is_in_state('validated')
            self.assertEqual(selector(None, req, rset=rset), 0)
            selector = is_in_state('validated', 'abandoned')
            self.assertEqual(selector(None, req, rset=rset), 1)
            self.assertEqual(adapter.state, 'abandoned')
            self.assertEqual(selector(None, req, rset=rset), 1)

    def test_is_in_state_unvalid_names(self):
        with self.statefull_stuff() as (req, wf_entity, rset, adapter):
            selector = is_in_state("unknown")
            with self.assertRaises(ValueError) as cm:
                selector(None, req, rset=rset)
            self.assertEqual(str(cm.exception),
                             "wf_test: unknown state(s): unknown")
            selector = is_in_state("weird", "unknown", "created", "weird")
            with self.assertRaises(ValueError) as cm:
                selector(None, req, rset=rset)
            self.assertEqual(str(cm.exception),
                             "wf_test: unknown state(s): unknown,weird")

    def test_on_transition(self):
        with self.statefull_stuff() as (req, wf_entity, rset, adapter):
            for transition in ('validate', 'forsake'):
                selector = on_transition(transition)
                self.assertEqual(selector(None, req, rset=rset), 0)

            adapter.fire_transition('validate')
            req.cnx.commit(); wf_entity.cw_clear_all_caches()
            self.assertEqual(adapter.state, 'validated')

            clear_cache(rset, 'get_entity')

            selector = on_transition("validate")
            self.assertEqual(selector(None, req, rset=rset), 1)
            selector = on_transition("validate", "forsake")
            self.assertEqual(selector(None, req, rset=rset), 1)
            selector = on_transition("forsake")
            self.assertEqual(selector(None, req, rset=rset), 0)

            adapter.fire_transition('forsake')
            req.cnx.commit(); wf_entity.cw_clear_all_caches()
            self.assertEqual(adapter.state, 'abandoned')

            clear_cache(rset, 'get_entity')

            selector = on_transition("validate")
            self.assertEqual(selector(None, req, rset=rset), 0)
            selector = on_transition("validate", "forsake")
            self.assertEqual(selector(None, req, rset=rset), 1)
            selector = on_transition("forsake")
            self.assertEqual(selector(None, req, rset=rset), 1)

    def test_on_transition_unvalid_names(self):
        with self.statefull_stuff() as (req, wf_entity, rset, adapter):
            selector = on_transition("unknown")
            with self.assertRaises(ValueError) as cm:
                selector(None, req, rset=rset)
            self.assertEqual(str(cm.exception),
                             "wf_test: unknown transition(s): unknown")
            selector = on_transition("weird", "unknown", "validate", "weird")
            with self.assertRaises(ValueError) as cm:
                selector(None, req, rset=rset)
            self.assertEqual(str(cm.exception),
                             "wf_test: unknown transition(s): unknown,weird")

    def test_on_transition_with_no_effect(self):
        """selector will not be triggered with `change_state()`"""
        with self.statefull_stuff() as (req, wf_entity, rset, adapter):
            adapter.change_state('validated')
            req.cnx.commit(); wf_entity.cw_clear_all_caches()
            self.assertEqual(adapter.state, 'validated')

            selector = on_transition("validate")
            self.assertEqual(selector(None, req, rset=rset), 0)
            selector = on_transition("validate", "forsake")
            self.assertEqual(selector(None, req, rset=rset), 0)
            selector = on_transition("forsake")
            self.assertEqual(selector(None, req, rset=rset), 0)


class RelationPossibleTC(CubicWebTC):

    def test_rqlst_1(self):
        with self.admin_access.web_request() as req:
            selector = relation_possible('in_group')
            select = self.vreg.parse(req, 'Any X WHERE X is CWUser').children[0]
            score = selector(None, req, rset=1,
                             select=select, filtered_variable=select.defined_vars['X'])
            self.assertEqual(score, 1)

    def test_rqlst_2(self):
        with self.admin_access.web_request() as req:
            selector = relation_possible('in_group')
            select = self.vreg.parse(req, 'Any 1, COUNT(X) WHERE X is CWUser, X creation_date XD, '
                                     'Y creation_date YD, Y is CWGroup '
                                     'HAVING DAY(XD)=DAY(YD)').children[0]
            score = selector(None, req, rset=1,
                             select=select, filtered_variable=select.defined_vars['X'])
            self.assertEqual(score, 1)

    def test_ambiguous(self):
        # Ambiguous relations are :
        # (Service, fabrique_par, Personne) and (Produit, fabrique_par, Usine)
        # There used to be a crash here with a bad rdef choice in the strict
        # checking case.
        selector = relation_possible('fabrique_par', role='object',
                                     target_etype='Personne', strict=True)
        with self.admin_access.web_request() as req:
            usine = req.create_entity('Usine', lieu=u'here')
            score = selector(None, req, rset=usine.as_rset())
            self.assertEqual(0, score)


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
            with self.admin_access.web_request() as req:
                self.create_user(req, 'john')
            # login as a simple user
            john_access = self.new_access('john')
            with john_access.web_request() as req:
                # it should not be possible to use SomeAction not owned objects
                rset = req.execute('Any G WHERE G is CWGroup, G name "managers"')
                self.assertFalse('yo' in dict(self.pactions(req, rset)))
                # insert a new card, and check that we can use SomeAction on our object
                req.execute('INSERT Card C: C title "zoubidou"')
                req.cnx.commit()
            with john_access.web_request() as req:
                rset = req.execute('Card C WHERE C title "zoubidou"')
                self.assertTrue('yo' in dict(self.pactions(req, rset)), self.pactions(req, rset))
            # make sure even managers can't use the action
            with self.admin_access.web_request() as req:
                rset = req.execute('Card C WHERE C title "zoubidou"')
                self.assertFalse('yo' in dict(self.pactions(req, rset)))
        finally:
            del self.vreg[SomeAction.__registry__][SomeAction.__regid__]


class MultiLinesRsetTC(CubicWebTC):
    def setup_database(self):
        with self.admin_access.web_request() as req:
            req.execute('INSERT CWGroup G: G name "group1"')
            req.execute('INSERT CWGroup G: G name "group2"')
            req.cnx.commit()

    def test_default_op_in_selector(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any G WHERE G is CWGroup')
            expected = len(rset)
            selector = multi_lines_rset(expected)
            self.assertEqual(selector(None, req, rset=rset), 1)
            self.assertEqual(selector(None, req, None), 0)
            selector = multi_lines_rset(expected + 1)
            self.assertEqual(selector(None, req, rset=rset), 0)
            self.assertEqual(selector(None, req, None), 0)
            selector = multi_lines_rset(expected - 1)
            self.assertEqual(selector(None, req, rset=rset), 0)
            self.assertEqual(selector(None, req, None), 0)

    def test_without_rset(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any G WHERE G is CWGroup')
            expected = len(rset)
            selector = multi_lines_rset(expected)
            self.assertEqual(selector(None, req, None), 0)
            selector = multi_lines_rset(expected + 1)
            self.assertEqual(selector(None, req, None), 0)
            selector = multi_lines_rset(expected - 1)
            self.assertEqual(selector(None, req, None), 0)

    def test_with_operators(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('Any G WHERE G is CWGroup')
            expected = len(rset)

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
                with self.subTest(expected=expected, operator=operator):
                    self.assertEqual(selector(None, req, rset=rset), assertion)


class MatchKwargsTC(TestCase):

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


class ScoreEntityTC(CubicWebTC):

    def test_intscore_entity_selector(self):
        with self.admin_access.web_request() as req:
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
        with self.admin_access.web_request() as req:
            selector = rql_condition('X identity U')
            rset = req.user.as_rset()
            self.assertEqual(selector(None, req, rset=rset), 1)
            self.assertEqual(selector(None, req, entity=req.user), 1)
            self.assertEqual(selector(None, req), 0)

    def test_rql_condition_user(self):
        with self.admin_access.web_request() as req:
            selector = rql_condition('U login "admin"', user_condition=True)
            self.assertEqual(selector(None, req), 1)
            selector = rql_condition('U login "toto"', user_condition=True)
            self.assertEqual(selector(None, req), 0)


class AdaptablePredicateTC(CubicWebTC):

    def test_multiple_entity_types_rset(self):
        class CWUserIWhatever(EntityAdapter):
            __regid__ = 'IWhatever'
            __select__ = is_instance('CWUser')
        class CWGroupIWhatever(EntityAdapter):
            __regid__ = 'IWhatever'
            __select__ = is_instance('CWGroup')
        with self.temporary_appobjects(CWUserIWhatever, CWGroupIWhatever):
            with self.admin_access.web_request() as req:
                selector = adaptable('IWhatever')
                rset = req.execute('Any X WHERE X is IN(CWGroup, CWUser)')
                self.assertTrue(selector(None, req, rset=rset))


class MatchFormParamsTC(CubicWebTC):
    """tests for match_form_params predicate"""

    def test_keyonly_match(self):
        """test standard usage: ``match_form_params('param1', 'param2')``

        ``param1`` and ``param2`` must be specified in request's form.
        """
        web_request = self.admin_access.web_request
        vid_selector = match_form_params('vid')
        vid_subvid_selector = match_form_params('vid', 'subvid')
        # no parameter => KO,KO
        with web_request() as req:
            self.assertEqual(vid_selector(None, req), 0)
            self.assertEqual(vid_subvid_selector(None, req), 0)
        # one expected parameter found => OK,KO
        with web_request(vid='foo') as req:
            self.assertEqual(vid_selector(None, req), 1)
            self.assertEqual(vid_subvid_selector(None, req), 0)
        # all expected parameters found => OK,OK
        with web_request(vid='foo', subvid='bar') as req:
            self.assertEqual(vid_selector(None, req), 1)
            self.assertEqual(vid_subvid_selector(None, req), 2)

    def test_keyvalue_match_one_parameter(self):
        """test dict usage: ``match_form_params(param1=value1)``

        ``param1`` must be specified in the request's form and its value
        must be ``value1``.
        """
        web_request = self.admin_access.web_request
        # test both positional and named parameters
        vid_selector = match_form_params(vid='foo')
        # no parameter => should fail
        with web_request() as req:
            self.assertEqual(vid_selector(None, req), 0)
        # expected parameter found with expected value => OK
        with web_request(vid='foo', subvid='bar') as req:
            self.assertEqual(vid_selector(None, req), 1)
        # expected parameter found but value is incorrect => KO
        with web_request(vid='bar') as req:
            self.assertEqual(vid_selector(None, req), 0)

    def test_keyvalue_match_two_parameters(self):
        """test dict usage: ``match_form_params(param1=value1, param2=value2)``

        ``param1`` and ``param2`` must be specified in the request's form and
        their respective value must be ``value1`` and ``value2``.
        """
        web_request = self.admin_access.web_request
        vid_subvid_selector = match_form_params(vid='list', subvid='tsearch')
        # missing one expected parameter => KO
        with web_request(vid='list') as req:
            self.assertEqual(vid_subvid_selector(None, req), 0)
        # expected parameters found but values are incorrect => KO
        with web_request(vid='list', subvid='foo') as req:
            self.assertEqual(vid_subvid_selector(None, req), 0)
        # expected parameters found and values are correct => OK
        with web_request(vid='list', subvid='tsearch') as req:
            self.assertEqual(vid_subvid_selector(None, req), 2)

    def test_keyvalue_multiple_match(self):
        """test dict usage with multiple values

        i.e. as in ``match_form_params(param1=('value1', 'value2'))``

        ``param1`` must be specified in the request's form and its value
        must be either ``value1`` or ``value2``.
        """
        web_request = self.admin_access.web_request
        vid_subvid_selector = match_form_params(vid='list', subvid=('tsearch', 'listitem'))
        # expected parameters found and values correct => OK
        with web_request(vid='list', subvid='tsearch') as req:
            self.assertEqual(vid_subvid_selector(None, req), 2)
        with web_request(vid='list', subvid='listitem') as req:
            self.assertEqual(vid_subvid_selector(None, req), 2)
        # expected parameters found but values are incorrect => OK
        with web_request(vid='list', subvid='foo') as req:
            self.assertEqual(vid_subvid_selector(None, req), 0)

    def test_invalid_calls(self):
        """checks invalid calls raise a ValueError"""
        # mixing named and positional arguments should fail
        with self.assertRaises(ValueError) as cm:
            match_form_params('list', x='1', y='2')
        self.assertEqual(str(cm.exception),
                         "match_form_params() can't be called with both "
                         "positional and named arguments")
        # using a dict as first and unique argument should fail
        with self.assertRaises(ValueError) as cm:
            match_form_params({'x': 1})
        self.assertEqual(str(cm.exception),
                         "match_form_params() positional arguments must be strings")


class PaginatedTC(CubicWebTC):
    """tests for paginated_rset predicate"""

    def setup_database(self):
        with self.admin_access.repo_cnx() as cnx:
            for i in range(30):
                cnx.create_entity('CWGroup', name=u"group%d" % i)
            cnx.commit()

    def test_paginated_rset(self):
        default_nb_pages = 1
        web_request = self.admin_access.web_request
        with web_request() as req:
            rset = req.execute('Any G WHERE G is CWGroup')
        self.assertEqual(len(rset), 34)
        with web_request(vid='list', page_size='10') as req:
            self.assertEqual(paginated_rset()(None, req, rset), default_nb_pages)
        with web_request(vid='list', page_size='20') as req:
            self.assertEqual(paginated_rset()(None, req, rset), default_nb_pages)
        with web_request(vid='list', page_size='50') as req:
            self.assertEqual(paginated_rset()(None, req, rset), 0)
        with web_request(vid='list', page_size='10/') as req:
            self.assertEqual(paginated_rset()(None, req, rset), 0)
        with web_request(vid='list', page_size='.1') as req:
            self.assertEqual(paginated_rset()(None, req, rset), 0)
        with web_request(vid='list', page_size='not_an_int') as req:
            self.assertEqual(paginated_rset()(None, req, rset), 0)


if __name__ == '__main__':
    unittest_main()
