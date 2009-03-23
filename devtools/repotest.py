"""some utilities to ease repository testing

This module contains functions to initialize a new repository.

:organization: Logilab
:copyright: 2003-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from pprint import pprint

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
                self.assertEquals(sol, equeries[i][1])
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
        for key_, value in self.iteritems():
            if key == key_:
                return value
        raise KeyError(key)
    def iterkeys(self):
        return (x for x, y in list.__iter__(self))
    def iteritems(self):
        return (x for x in list.__iter__(self))


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
        self.rqlhelper = RQLHelper(self.schema, special_relations={'eid': 'uid',
                                                                   'has_text': 'fti'})
        self.qhelper = QuerierHelper(FakeRepo(self.schema), self.schema)
        ExecutionPlan._check_permissions = _dummy_check_permissions
        rqlannotation._select_principal = _select_principal

    def tearDown(self):
        ExecutionPlan._check_permissions = _orig_check_permissions
        rqlannotation._select_principal = _orig_select_principal
        
    def _prepare(self, rql):
        #print '******************** prepare', rql
        union = self.rqlhelper.parse(rql)
        #print '********* parsed', union.as_string()
        self.rqlhelper.compute_solutions(union)
        #print '********* solutions', solutions
        self.rqlhelper.simplify(union)
        #print '********* simplified', union.as_string()
        plan = self.qhelper.plan_factory(union, {}, FakeSession())
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
        rqlhelper = self.o._rqlhelper
        # reset uid_func so it don't try to get type from eids
        rqlhelper._analyser.uid_func = None
        rqlhelper._analyser.uid_func_mapping = {}
        return rqlhelper

    def _prepare_plan(self, rql, kwargs=None):
        rqlhelper = self._rqlhelper()
        rqlst = rqlhelper.parse(rql)
        rqlhelper.compute_solutions(rqlst, kwargs=kwargs)
        rqlhelper.simplify(rqlst)
        for select in rqlst.children:
            select.solutions.sort()
        return self.o.plan_factory(rqlst, kwargs, self.session)
        
    def _prepare(self, rql, kwargs=None):    
        plan = self._prepare_plan(rql, kwargs)
        plan.preprocess(plan.rqlst)
        rqlst = plan.rqlst.children[0]
        rqlst.solutions = remove_unused_solutions(rqlst, rqlst.solutions, {}, self.repo.schema)[0]
        return rqlst

    def _user_session(self, groups=('guests',), ueid=None):
        # use self.session.user.eid to get correct owned_by relation, unless explicit eid
        if ueid is None:
            ueid = self.session.user.eid
        u = self.repo._build_user(self.session, ueid)
        u._groups = set(groups)
        s = Session(u, self.repo)
        s._threaddata.pool = self.pool
        return u, s

    def execute(self, rql, args=None, eid_key=None, build_descr=True):
        return self.o.execute(self.session, rql, args, eid_key, build_descr)
    
    def commit(self):
        self.session.commit()
        self.session.set_pool()        


class BasePlannerTC(BaseQuerierTC):

    def _prepare_plan(self, rql, kwargs=None):
        rqlst = self.o.parse(rql, annotate=True)
        self.o.solutions(self.session, rqlst, kwargs)
        if rqlst.TYPE == 'select':
            self.o._rqlhelper.annotate(rqlst)
            for select in rqlst.children:
                select.solutions.sort()
        else:
            rqlst.solutions.sort()
        return self.o.plan_factory(rqlst, kwargs, self.session)


# monkey patch some methods to get predicatable results #######################

from cubicweb.server.rqlrewrite import RQLRewriter
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
        def merge_input_maps(*args):
            pass
        def _choose_var(self, sourcevars):
            pass    
_orig_merge_input_maps = PartPlanInformation.merge_input_maps
_orig_choose_var = PartPlanInformation._choose_var

def _merge_input_maps(*args):
    return sorted(_orig_merge_input_maps(*args))

def _choose_var(self, sourcevars):
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
    varsinorder = sorted(sourcevars, key=get_key)
    if len(self._sourcesvars) > 1:
        for var in varsinorder:
            if not var.scope is self.rqlst:
                return var, sourcevars.pop(var)
    else:
        for var in varsinorder:
            if var.scope is self.rqlst:
                return var, sourcevars.pop(var)
    var = varsinorder[0]
    return var, sourcevars.pop(var)


def do_monkey_patch():
    RQLRewriter.insert_snippets = _insert_snippets
    RQLRewriter.build_variantes = _build_variantes
    ExecutionPlan._check_permissions = _check_permissions
    ExecutionPlan.tablesinorder = None
    ExecutionPlan.init_temp_table = _init_temp_table
    PartPlanInformation.merge_input_maps = _merge_input_maps
    PartPlanInformation._choose_var = _choose_var

def undo_monkey_patch():
    RQLRewriter.insert_snippets = _orig_insert_snippets
    RQLRewriter.build_variantes = _orig_build_variantes
    ExecutionPlan._check_permissions = _orig_check_permissions
    ExecutionPlan.init_temp_table = _orig_init_temp_table
    PartPlanInformation.merge_input_maps = _orig_merge_input_maps
    PartPlanInformation._choose_var = _orig_choose_var

