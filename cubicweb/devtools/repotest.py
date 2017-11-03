# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""some utilities to ease repository testing

This module contains functions to initialize a new repository.
"""
from __future__ import print_function

from contextlib import contextmanager
from pprint import pprint


from cubicweb.entities.authobjs import user_session_cache_key
from cubicweb.server import set_debug, debugged
from cubicweb.server.sources.rql2sql import remove_unused_solutions

from .testlib import RepoAccess, BaseTestCase
from .fake import FakeRequest


def tuplify(mylist):
    return [tuple(item) for item in mylist]


def snippet_key(a):
    # a[0] may be a dict or a key/value tuple
    return (sorted(dict(a[0]).items()), [e.expression for e in a[1]])


def check_plan(self, rql, expected, kwargs=None):
    with self.admin_access.cnx() as cnx:
        plan = self._prepare_plan(cnx, rql, kwargs)
        self.planner.build_plan(plan)
        try:
            self.assertEqual(len(plan.steps), len(expected),
                             'expected %s steps, got %s' % (len(expected), len(plan.steps)))
            # step order is important
            for i, step in enumerate(plan.steps):
                compare_steps(self, step.test_repr(), expected[i])
        except AssertionError:
            pprint([step.test_repr() for step in plan.steps])
            raise


def compare_steps(self, step, expected):
    try:
        self.assertEqual(step[0], expected[0], 'expected step type %s, got %s' % (expected[0], step[0]))
        if len(step) > 2 and isinstance(step[1], list) and isinstance(expected[1], list):
            queries, equeries = step[1], expected[1]
            self.assertEqual(len(queries), len(equeries),
                              'expected %s queries, got %s' % (len(equeries), len(queries)))
            for i, (rql, sol) in enumerate(queries):
                self.assertEqual(rql, equeries[i][0])
                self.assertEqual(sorted(sorted(x.items()) for x in sol), sorted(sorted(x.items()) for x in equeries[i][1]))
            idx = 2
        else:
            idx = 1
        self.assertEqual(step[idx:-1], expected[idx:-1],
                          'expected step characteristic \n%s\n, got\n%s' % (expected[1:-1], step[1:-1]))
        self.assertEqual(len(step[-1]), len(expected[-1]),
                          'got %s child steps, expected %s' % (len(step[-1]), len(expected[-1])))
    except AssertionError:
        print('error on step ', end=' ')
        pprint(step[:-1])
        raise
    children = step[-1]
    if step[0] in ('UnionFetchStep', 'UnionStep'):
        # sort children
        children = sorted(children)
        expectedchildren = sorted(expected[-1])
    else:
        expectedchildren = expected[-1]
    for i, substep in enumerate(children):
        compare_steps(self, substep, expectedchildren[i])


class DumbOrderedDict(list):
    def __iter__(self):
        return self.iterkeys()
    def __contains__(self, key):
        return key in self.iterkeys()
    def __getitem__(self, key):
        for key_, value in list.__iter__(self):
            if key == key_:
                return value
        raise KeyError(key)
    def iterkeys(self):
        return (x for x, y in list.__iter__(self))
    def iteritems(self):
        return (x for x in list.__iter__(self))
    def items(self):
        return [x for x in list.__iter__(self)]


def schema_eids_idx(schema):
    """return a dictionary mapping schema types to their eids so we can reread
    it from the fs instead of the db (too costly) between tests
    """
    schema_eids = {}
    for x in schema.entities():
        schema_eids[x] = x.eid
    for x in schema.relations():
        schema_eids[x] = x.eid
        for rdef in x.rdefs.values():
            schema_eids[(rdef.subject, rdef.rtype, rdef.object)] = rdef.eid
    return schema_eids

def restore_schema_eids_idx(schema, schema_eids):
    """rebuild schema eid index"""
    for x in schema.entities():
        x.eid = schema_eids[x]
        schema._eid_index[x.eid] = x
    for x in schema.relations():
        x.eid = schema_eids[x]
        schema._eid_index[x.eid] = x
        for rdef in x.rdefs.values():
            rdef.eid = schema_eids[(rdef.subject, rdef.rtype, rdef.object)]
            schema._eid_index[rdef.eid] = rdef


class BaseQuerierTC(BaseTestCase):
    repo = None # set this in concrete class

    def setUp(self):
        self.o = self.repo.querier
        self.admin_access = RepoAccess(self.repo, 'admin', FakeRequest)
        self.ueid = self.admin_access._user.eid
        assert self.ueid != -1
        self.repo._type_cache = {} # clear cache
        do_monkey_patch()
        self._dumb_sessions = []

    def tearDown(self):
        undo_monkey_patch()
        assert self.admin_access._user.eid != -1

    def set_debug(self, debug):
        set_debug(debug)
    def debugged(self, debug):
        return debugged(debug)

    def _rqlhelper(self):
        rqlhelper = self.repo.vreg.rqlhelper
        # reset uid_func so it don't try to get type from eids
        rqlhelper._analyser.uid_func = None
        rqlhelper._analyser.uid_func_mapping = {}
        return rqlhelper

    def _prepare_plan(self, cnx, rql, kwargs=None, simplify=True):
        rqlhelper = self._rqlhelper()
        rqlst = rqlhelper.parse(rql)
        rqlhelper.compute_solutions(rqlst, kwargs=kwargs)
        if simplify:
            rqlhelper.simplify(rqlst)
        for select in rqlst.children:
            select.solutions.sort(key=lambda x: list(x.items()))
        return self.o.plan_factory(rqlst, kwargs, cnx)

    def _prepare(self, cnx, rql, kwargs=None):
        plan = self._prepare_plan(cnx, rql, kwargs, simplify=False)
        plan.preprocess(plan.rqlst)
        rqlst = plan.rqlst.children[0]
        rqlst.solutions = remove_unused_solutions(rqlst, rqlst.solutions, self.repo.schema)[0]
        return rqlst

    @contextmanager
    def user_groups_session(self, *groups):
        """lightweight session using the current user with hi-jacked groups"""
        # use cnx.user.eid to get correct owned_by relation, unless explicit eid
        with self.admin_access.cnx() as cnx:
            user_eid = cnx.user.eid
            cnx.user._cw.transaction_data[user_session_cache_key(user_eid, 'groups')] = set(groups)
            yield cnx

    def qexecute(self, rql, args=None, build_descr=True):
        with self.admin_access.cnx() as cnx:
            try:
                return self.o.execute(cnx, rql, args, build_descr)
            finally:
                if rql.startswith(('INSERT', 'DELETE', 'SET')):
                    cnx.commit()


class BasePlannerTC(BaseQuerierTC):

    def setup(self):
        # XXX source_defs
        self.o = self.repo.querier
        self.schema = self.o.schema
        self.system = self.repo.system_source
        do_monkey_patch()
        self.repo.vreg.rqlhelper.backend = 'postgres' # so FTIRANK is considered

    def tearDown(self):
        undo_monkey_patch()

    def _prepare_plan(self, cnx, rql, kwargs=None):
        rqlst = self.repo.vreg.rqlhelper.parse(rql, annotate=True)
        self.repo.vreg.solutions(cnx, rqlst, kwargs)
        if rqlst.TYPE == 'select':
            self.repo.vreg.rqlhelper.annotate(rqlst)
            for select in rqlst.children:
                select.solutions.sort(key=lambda x: list(x.items()))
        else:
            rqlst.solutions.sort(key=lambda x: list(x.items()))
        return self.o.plan_factory(rqlst, kwargs, cnx)


# monkey patch some methods to get predictable results #######################

from cubicweb import rqlrewrite
_orig_iter_relations = rqlrewrite.iter_relations
_orig_insert_snippets = rqlrewrite.RQLRewriter.insert_snippets
_orig_build_variantes = rqlrewrite.RQLRewriter.build_variantes

def _insert_snippets(self, snippets, varexistsmap=None):
    _orig_insert_snippets(self, sorted(snippets, key=snippet_key), varexistsmap)

def _build_variantes(self, newsolutions):
    variantes = _orig_build_variantes(self, newsolutions)
    sortedvariantes = []
    for variante in variantes:
        orderedkeys = sorted((k[1], k[2], v) for k, v in variante.items())
        variante = DumbOrderedDict(sorted(variante.items(),
                                          key=lambda a: (a[0][1], a[0][2], a[1])))
        sortedvariantes.append( (orderedkeys, variante) )
    return [v for ok, v in sorted(sortedvariantes)]

from cubicweb.server.querier import ExecutionPlan
_orig_check_permissions = ExecutionPlan._check_permissions

def _check_permissions(*args, **kwargs):
    res, restricted = _orig_check_permissions(*args, **kwargs)
    res = DumbOrderedDict(sorted(res.items(), key=lambda x: [list(y.items()) for y in x[1]]))
    return res, restricted


from cubicweb.server import rqlannotation
_orig_select_principal = rqlannotation._select_principal

def _select_principal(scope, relations):
    def sort_key(something):
        try:
            return something.r_type
        except AttributeError:
            return (something[0].r_type, something[1])
    return _orig_select_principal(scope, relations,
                                  _sort=lambda rels: sorted(rels, key=sort_key))


def _ordered_iter_relations(stinfo):
    return sorted(_orig_iter_relations(stinfo), key=lambda x:x.r_type)

def do_monkey_patch():
    rqlrewrite.iter_relations = _ordered_iter_relations
    rqlrewrite.RQLRewriter.insert_snippets = _insert_snippets
    rqlrewrite.RQLRewriter.build_variantes = _build_variantes
    ExecutionPlan._check_permissions = _check_permissions
    ExecutionPlan.tablesinorder = None

def undo_monkey_patch():
    rqlrewrite.iter_relations = _orig_iter_relations
    rqlrewrite.RQLRewriter.insert_snippets = _orig_insert_snippets
    rqlrewrite.RQLRewriter.build_variantes = _orig_build_variantes
    ExecutionPlan._check_permissions = _orig_check_permissions
