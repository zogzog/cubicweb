"""some utilities to ease repository testing

This module contains functions to initialize a new repository.

:organization: Logilab
:copyright: 2003-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from pprint import pprint

from logilab.common.decorators import clear_cache

def tuplify(list):
    for i in range(len(list)):
        if type(list[i]) is not type(()):
            list[i] = tuple(list[i])
    return list

def snippet_cmp(a, b):
    a = (a[0], [e.expression for e in a[1]])
    b = (b[0], [e.expression for e in b[1]])
    return cmp(a, b)

def test_plan(self, rql, expected, kwargs=None):
    plan = self._prepare_plan(rql, kwargs)
    self.planner.build_plan(plan)
    try:
        self.assertEquals(len(plan.steps), len(expected),
                          'expected %s steps, got %s' % (len(expected), len(plan.steps)))
        # step order is important
        for i, step in enumerate(plan.steps):
            compare_steps(self, step.test_repr(), expected[i])
    except AssertionError:
        pprint([step.test_repr() for step in plan.steps])
        raise

def compare_steps(self, step, expected):
    try:
        self.assertEquals(step[0], expected[0], 'expected step type %s, got %s' % (expected[0], step[0]))
        if len(step) > 2 and isinstance(step[1], list) and isinstance(expected[1], list):
            queries, equeries = step[1], expected[1]
            self.assertEquals(len(queries), len(equeries),
                              'expected %s queries, got %s' % (len(equeries), len(queries)))
            for i, (rql, sol) in enumerate(queries):
                self.assertEquals(rql, equeries[i][0])
                self.assertEquals(sorted(sol), sorted(equeries[i][1]))
            idx = 2
        else:
            idx = 1
        self.assertEquals(step[idx:-1], expected[idx:-1],
                          'expected step characteristic \n%s\n, got\n%s' % (expected[1:-1], step[1:-1]))
        self.assertEquals(len(step[-1]), len(expected[-1]),
                          'got %s child steps, expected %s' % (len(step[-1]), len(expected[-1])))
    except AssertionError:
        print 'error on step ',
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

class DumbOrderedDict2(object):
    def __init__(self, origdict, sortkey):
        self.origdict = origdict
        self.sortkey = sortkey
    def __getattr__(self, attr):
        return getattr(self.origdict, attr)
    def __iter__(self):
        return iter(sorted(self.origdict, key=self.sortkey))

def schema_eids_idx(schema):
    """return a dictionary mapping schema types to their eids so we can reread
    it from the fs instead of the db (too costly) between tests
    """
    schema_eids = {}
    for x in schema.entities():
        schema_eids[x] = x.eid
    for x in schema.relations():
        schema_eids[x] = x.eid
        for rdef in x.rdefs.itervalues():
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
        for rdef in x.rdefs.itervalues():
            rdef.eid = schema_eids[(rdef.subject, rdef.rtype, rdef.object)]
            schema._eid_index[rdef.eid] = rdef


from logilab.common.testlib import TestCase
from rql import RQLHelper
from cubicweb.devtools.fake import FakeRepo, FakeSession
from cubicweb.server import set_debug
from cubicweb.server.querier import QuerierHelper
from cubicweb.server.session import Session
from cubicweb.server.sources.rql2sql import remove_unused_solutions

class RQLGeneratorTC(TestCase):
    schema = None # set this in concret test

    def setUp(self):
        self.repo = FakeRepo(self.schema)
        self.rqlhelper = RQLHelper(self.schema, special_relations={'eid': 'uid',
                                                                   'has_text': 'fti'})
        self.qhelper = QuerierHelper(self.repo, self.schema)
        ExecutionPlan._check_permissions = _dummy_check_permissions
        rqlannotation._select_principal = _select_principal

    def tearDown(self):
        ExecutionPlan._check_permissions = _orig_check_permissions
        rqlannotation._select_principal = _orig_select_principal

    def set_debug(self, debug):
        set_debug(debug)

    def _prepare(self, rql):
        #print '******************** prepare', rql
        union = self.rqlhelper.parse(rql)
        #print '********* parsed', union.as_string()
        self.rqlhelper.compute_solutions(union)
        #print '********* solutions', solutions
        self.rqlhelper.simplify(union)
        #print '********* simplified', union.as_string()
        plan = self.qhelper.plan_factory(union, {}, FakeSession(self.repo))
        plan.preprocess(union)
        for select in union.children:
            select.solutions.sort()
        #print '********* ppsolutions', solutions
        return union


class BaseQuerierTC(TestCase):
    repo = None # set this in concret test

    def setUp(self):
        self.o = self.repo.querier
        self.session = self.repo._sessions.values()[0]
        self.ueid = self.session.user.eid
        assert self.ueid != -1
        self.repo._type_source_cache = {} # clear cache
        self.pool = self.session.set_pool()
        self.maxeid = self.get_max_eid()
        do_monkey_patch()

    def get_max_eid(self):
        return self.session.unsafe_execute('Any MAX(X)')[0][0]
    def cleanup(self):
        self.session.unsafe_execute('DELETE Any X WHERE X eid > %s' % self.maxeid)

    def tearDown(self):
        undo_monkey_patch()
        self.session.rollback()
        self.cleanup()
        self.commit()
        self.repo._free_pool(self.pool)
        assert self.session.user.eid != -1

    def set_debug(self, debug):
        set_debug(debug)

    def _rqlhelper(self):
        rqlhelper = self.repo.vreg.rqlhelper
        # reset uid_func so it don't try to get type from eids
        rqlhelper._analyser.uid_func = None
        rqlhelper._analyser.uid_func_mapping = {}
        return rqlhelper

    def _prepare_plan(self, rql, kwargs=None, simplify=True):
        rqlhelper = self._rqlhelper()
        rqlst = rqlhelper.parse(rql)
        rqlhelper.compute_solutions(rqlst, kwargs=kwargs)
        if simplify:
            rqlhelper.simplify(rqlst)
        for select in rqlst.children:
            select.solutions.sort()
        return self.o.plan_factory(rqlst, kwargs, self.session)

    def _prepare(self, rql, kwargs=None):
        plan = self._prepare_plan(rql, kwargs, simplify=False)
        plan.preprocess(plan.rqlst)
        rqlst = plan.rqlst.children[0]
        rqlst.solutions = remove_unused_solutions(rqlst, rqlst.solutions, {}, self.repo.schema)[0]
        return rqlst

    def user_groups_session(self, *groups):
        """lightweight session using the current user with hi-jacked groups"""
        # use self.session.user.eid to get correct owned_by relation, unless explicit eid
        u = self.repo._build_user(self.session, self.session.user.eid)
        u._groups = set(groups)
        s = Session(u, self.repo)
        s._threaddata.pool = self.pool
        return s

    def execute(self, rql, args=None, eid_key=None, build_descr=True):
        return self.o.execute(self.session, rql, args, eid_key, build_descr)

    def commit(self):
        self.session.commit()
        self.session.set_pool()


class BasePlannerTC(BaseQuerierTC):
    newsources = 0
    def setup(self):
        clear_cache(self.repo, 'rel_type_sources')
        clear_cache(self.repo, 'rel_type_sources')
        clear_cache(self.repo, 'can_cross_relation')
        clear_cache(self.repo, 'is_multi_sources_relation')
        # XXX source_defs
        self.o = self.repo.querier
        self.session = self.repo._sessions.values()[0]
        self.pool = self.session.set_pool()
        self.schema = self.o.schema
        self.sources = self.o._repo.sources
        self.system = self.sources[-1]
        do_monkey_patch()

    def add_source(self, sourcecls, uri):
        self.sources.append(sourcecls(self.repo, self.o.schema,
                                      {'uri': uri}))
        self.repo.sources_by_uri[uri] = self.sources[-1]
        setattr(self, uri, self.sources[-1])
        self.newsources += 1

    def tearDown(self):
        while self.newsources:
            source = self.sources.pop(-1)
            del self.repo.sources_by_uri[source.uri]
            self.newsources -= 1
        undo_monkey_patch()

    def _prepare_plan(self, rql, kwargs=None):
        rqlst = self.o.parse(rql, annotate=True)
        self.o.solutions(self.session, rqlst, kwargs)
        if rqlst.TYPE == 'select':
            self.repo.vreg.rqlhelper.annotate(rqlst)
            for select in rqlst.children:
                select.solutions.sort()
        else:
            rqlst.solutions.sort()
        return self.o.plan_factory(rqlst, kwargs, self.session)


# monkey patch some methods to get predicatable results #######################

from cubicweb.rqlrewrite import RQLRewriter
_orig_insert_snippets = RQLRewriter.insert_snippets
_orig_build_variantes = RQLRewriter.build_variantes

def _insert_snippets(self, snippets, varexistsmap=None):
    _orig_insert_snippets(self, sorted(snippets, snippet_cmp), varexistsmap)

def _build_variantes(self, newsolutions):
    variantes = _orig_build_variantes(self, newsolutions)
    sortedvariantes = []
    for variante in variantes:
        orderedkeys = sorted((k[1], k[2], v) for k, v in variante.iteritems())
        variante = DumbOrderedDict(sorted(variante.iteritems(),
                                          lambda a, b: cmp((a[0][1],a[0][2],a[1]),
                                                           (b[0][1],b[0][2],b[1]))))
        sortedvariantes.append( (orderedkeys, variante) )
    return [v for ok, v in sorted(sortedvariantes)]

from cubicweb.server.querier import ExecutionPlan
_orig_check_permissions = ExecutionPlan._check_permissions
_orig_init_temp_table = ExecutionPlan.init_temp_table

def _check_permissions(*args, **kwargs):
    res, restricted = _orig_check_permissions(*args, **kwargs)
    res = DumbOrderedDict(sorted(res.iteritems(), lambda a, b: cmp(a[1], b[1])))
    return res, restricted

def _dummy_check_permissions(self, rqlst):
    return {(): rqlst.solutions}, set()

def _init_temp_table(self, table, selection, solution):
    if self.tablesinorder is None:
        tablesinorder = self.tablesinorder = {}
    else:
        tablesinorder = self.tablesinorder
    if not table in tablesinorder:
        tablesinorder[table] = 'table%s' % len(tablesinorder)
    return _orig_init_temp_table(self, table, selection, solution)

from cubicweb.server import rqlannotation
_orig_select_principal = rqlannotation._select_principal

def _select_principal(scope, relations):
    return _orig_select_principal(scope, relations,
                                  _sort=lambda rels: sorted(rels, key=lambda x: x.r_type))

try:
    from cubicweb.server.msplanner import PartPlanInformation
except ImportError:
    class PartPlanInformation(object):
        def merge_input_maps(self, *args):
            pass
        def _choose_term(self, sourceterms):
            pass
_orig_merge_input_maps = PartPlanInformation.merge_input_maps
_orig_choose_term = PartPlanInformation._choose_term

def _merge_input_maps(*args):
    return sorted(_orig_merge_input_maps(*args))

def _choose_term(self, sourceterms):
    # predictable order for test purpose
    def get_key(x):
        try:
            # variable
            return x.name
        except AttributeError:
            try:
                # relation
                return x.r_type
            except AttributeError:
                # const
                return x.value
    return _orig_choose_term(self, DumbOrderedDict2(sourceterms, get_key))


def do_monkey_patch():
    RQLRewriter.insert_snippets = _insert_snippets
    RQLRewriter.build_variantes = _build_variantes
    ExecutionPlan._check_permissions = _check_permissions
    ExecutionPlan.tablesinorder = None
    ExecutionPlan.init_temp_table = _init_temp_table
    PartPlanInformation.merge_input_maps = _merge_input_maps
    PartPlanInformation._choose_term = _choose_term

def undo_monkey_patch():
    RQLRewriter.insert_snippets = _orig_insert_snippets
    RQLRewriter.build_variantes = _orig_build_variantes
    ExecutionPlan._check_permissions = _orig_check_permissions
    ExecutionPlan.init_temp_table = _orig_init_temp_table
    PartPlanInformation.merge_input_maps = _orig_merge_input_maps
    PartPlanInformation._choose_term = _orig_choose_term
