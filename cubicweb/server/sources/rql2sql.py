# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""RQL to SQL generator for native sources.


SQL queries optimization
~~~~~~~~~~~~~~~~~~~~~~~~
1. CWUser X WHERE X in_group G, G name 'users':

   CWUser is the only subject entity type for the in_group relation,
   which allow us to do ::

     SELECT eid_from FROM in_group, CWGroup
     WHERE in_group.eid_to = CWGroup.eid_from
     AND CWGroup.name = 'users'


2. Any X WHERE X nonfinal1 Y, Y nonfinal2 Z

   -> direct join between nonfinal1 and nonfinal2, whatever X,Y, Z (unless
      inlined...)

      NOT IMPLEMENTED (and quite hard to implement)

Potential optimization information is collected by the querier, sql generation
is done according to this information

cross RDMS note : read `Comparison of different SQL implementations`_
by Troels Arvin. Features SQL ISO Standard, PG, mysql, Oracle, MS SQL, DB2
and Informix.

.. _Comparison of different SQL implementations: http://www.troels.arvin.dk/db/rdbms
"""

import threading

from six import PY2, text_type
from six.moves import range

from logilab.database import FunctionDescr, SQL_FUNCTIONS_REGISTRY

from rql import BadRQLQuery, CoercionError
from rql.utils import common_parent
from rql.stmts import Union, Select
from rql.nodes import (VariableRef, Constant, Function, Variable, Or,
                       Not, Comparison, ColumnAlias, Relation, SubQuery)

from cubicweb import QueryError
from cubicweb.rqlrewrite import cleanup_solutions
from cubicweb.server.sqlutils import SQL_PREFIX

get_func_descr = SQL_FUNCTIONS_REGISTRY.get_function

ColumnAlias._q_invariant = False  # avoid to check for ColumnAlias / Variable


def default_update_cb_stack(self, stack):
    stack.append(self.source_execute)
FunctionDescr.update_cb_stack = default_update_cb_stack
FunctionDescr.source_execute = None


def length_source_execute(source, session, value):
    return len(value.getvalue())

LENGTH = get_func_descr('LENGTH')
LENGTH.source_execute = length_source_execute


def _new_var(select, varname):
    newvar = select.get_variable(varname)
    if 'relations' not in newvar.stinfo:
        # not yet initialized
        newvar.prepare_annotation()
        newvar.stinfo['scope'] = select
        newvar._q_invariant = False
        select.selection.append(VariableRef(newvar))
    return newvar


def _fill_to_wrap_rel(var, newselect, towrap, schema):
    for rel in var.stinfo['relations'] - var.stinfo['rhsrelations']:
        rschema = schema.rschema(rel.r_type)
        if rschema.inlined:
            towrap.add((var, rel))
            for vref in rel.children[1].iget_nodes(VariableRef):
                newivar = _new_var(newselect, vref.name)
                _fill_to_wrap_rel(vref.variable, newselect, towrap, schema)
        elif rschema.final:
            towrap.add((var, rel))
            for vref in rel.children[1].iget_nodes(VariableRef):
                newivar = _new_var(newselect, vref.name)
                newivar.stinfo['attrvar'] = (var, rel.r_type)


def rewrite_unstable_outer_join(select, solutions, unstable, schema):
    """if some optional variables are unstable, they should be selected in a
    subquery. This function check this and rewrite the rql syntax tree if
    necessary (in place). Return a boolean telling if the tree has been modified
    """
    modified = False
    for varname in tuple(unstable):
        var = select.defined_vars[varname]
        if not var.stinfo.get('optrelations'):
            continue
        unstable.remove(varname)
        newselect = Select()
        myunion = Union()
        myunion.append(newselect)
        # extract aliases / selection
        newvar = _new_var(newselect, var.name)
        newselect.selection = [VariableRef(newvar)]
        towrap_rels = set()
        _fill_to_wrap_rel(var, newselect, towrap_rels, schema)
        # extract relations
        for var, rel in towrap_rels:
            newrel = rel.copy(newselect)
            newselect.add_restriction(newrel)
            select.remove_node(rel)
            var.stinfo['relations'].remove(rel)
            newvar.stinfo['relations'].add(newrel)
            if rel.optional in ('left', 'both'):
                newvar.add_optional_relation(newrel)
            for vref in newrel.children[1].iget_nodes(VariableRef):
                var = vref.variable
                var.stinfo['relations'].add(newrel)
                var.stinfo['rhsrelations'].add(newrel)
                if rel.optional in ('right', 'both'):
                    var.add_optional_relation(newrel)
        if not select.where and not modified:
            # oops, generated the same thing as the original select....
            # restore original query, else we'll indefinitly loop
            for var, rel in towrap_rels:
                select.add_restriction(rel)
            continue
        modified = True
        # extract subquery solutions
        mysolutions = [sol.copy() for sol in solutions]
        cleanup_solutions(newselect, mysolutions)
        newselect.set_possible_types(mysolutions)
        # full sub-query
        aliases = [VariableRef(select.get_variable(avar.name, i))
                   for i, avar in enumerate(newselect.selection)]
        select.add_subquery(SubQuery(aliases, myunion), check=False)
    return modified


def _new_solutions(rqlst, solutions):
    """first filter out subqueries variables from solutions"""
    newsolutions = []
    for origsol in solutions:
        asol = {}
        for vname in rqlst.defined_vars:
            asol[vname] = origsol[vname]
        if asol not in newsolutions:
            newsolutions.append(asol)
    return newsolutions


def remove_unused_solutions(rqlst, solutions, schema):
    """cleanup solutions: remove solutions where invariant variables are taking
    different types
    """
    newsols = _new_solutions(rqlst, solutions)
    existssols = {}
    unstable = set()
    invariants = {}
    for vname, var in rqlst.defined_vars.items():
        vtype = newsols[0][vname]
        if var._q_invariant:
            # remove invariant variable from solutions to remove duplicates
            # later, then reinserting a type for the variable even later
            for sol in newsols:
                invariants.setdefault(id(sol), {})[vname] = sol.pop(vname)
        elif var.scope is not rqlst:
            # move apart variables which are in a EXISTS scope and are variating
            try:
                thisexistssols, thisexistsvars = existssols[var.scope]
            except KeyError:
                # copy to avoid shared dict in newsols and exists sols
                thisexistssols = [newsols[0].copy()]
                thisexistsvars = set()
                existssols[var.scope] = thisexistssols, thisexistsvars
            for i in range(len(newsols) - 1, 0, -1):
                if vtype != newsols[i][vname]:
                    thisexistssols.append(newsols.pop(i))
                    thisexistsvars.add(vname)
        else:
            # remember unstable variables
            for i in range(1, len(newsols)):
                if vtype != newsols[i][vname]:
                    unstable.add(vname)
    # remove unstable variables from exists solutions: the possible types of these variables are
    # not properly represented in exists solutions, so we have to remove and reinject them later
    # according to the outer solution (see `iter_exists_sols`)
    for sols, _ in existssols.values():
        for vname in unstable:
            for sol in sols:
                sol.pop(vname, None)
    if invariants:
        # filter out duplicates
        newsols_ = []
        for sol in newsols:
            if sol not in newsols_:
                newsols_.append(sol)
        newsols = newsols_
        # reinsert solutions for invariants
        for sol in newsols:
            for invvar, vartype in invariants[id(sol)].items():
                sol[invvar] = vartype
        for sol in existssols:
            try:
                for invvar, vartype in invariants[id(sol)].items():
                    sol[invvar] = vartype
            except KeyError:
                continue
    if len(newsols) > 1:
        if rewrite_unstable_outer_join(rqlst, newsols, unstable, schema):
            # remove variables extracted to subqueries from solutions
            newsols = _new_solutions(rqlst, newsols)
    return newsols, existssols, unstable


def relation_info(relation):
    lhs, rhs = relation.get_variable_parts()
    try:
        lhs = lhs.variable
        lhsconst = lhs.stinfo['constnode']
    except AttributeError:
        lhsconst = lhs
        lhs = None
    except KeyError:
        lhsconst = None  # ColumnAlias
    try:
        rhs = rhs.variable
        rhsconst = rhs.stinfo['constnode']
    except AttributeError:
        rhsconst = rhs
        rhs = None
    except KeyError:
        rhsconst = None  # ColumnAlias
    return lhs, lhsconst, rhs, rhsconst


def sort_term_selection(sorts, rqlst, groups):
    # XXX beurk
    if isinstance(rqlst, list):
        def append(term):
            rqlst.append(term)
        selectionidx = set(str(term) for term in rqlst)
    else:
        def append(term):
            rqlst.selection.append(term.copy(rqlst))
        selectionidx = set(str(term) for term in rqlst.selection)

    for sortterm in sorts:
        term = sortterm.term
        if not isinstance(term, Constant) and not str(term) in selectionidx:
            selectionidx.add(str(term))
            append(term)
            if groups:
                for vref in term.iget_nodes(VariableRef):
                    if not any(vref.is_equivalent(g) for g in groups):
                        groups.append(vref)


def is_in_aggregat(node):
    while node:
        node = node.parent
        if isinstance(node, Function) and node.descr().aggregat:
            return True
    return False


def fix_selection_and_group(rqlst, needwrap, selectsortterms,
                            sorts, groups, having):
    if selectsortterms and sorts:
        sort_term_selection(sorts, rqlst, not needwrap and groups)
    groupvrefs = [vref for term in groups for vref in term.iget_nodes(VariableRef)]
    if sorts and groups:
        # when a query is grouped, ensure sort terms are grouped as well
        for sortterm in sorts:
            term = sortterm.term
            for vref in term.iget_nodes(VariableRef):
                if not (any(vref.is_equivalent(group) for group in groupvrefs)
                        or is_in_aggregat(vref)):
                    groups.append(vref)
                    groupvrefs.append(vref)
    if needwrap and (groups or having):
        selectedidx = set(vref.name for term in rqlst.selection
                          for vref in term.get_nodes(VariableRef))
        if groups:
            for vref in groupvrefs:
                if vref.name not in selectedidx:
                    selectedidx.add(vref.name)
                    rqlst.selection.append(vref)
        if having:
            for term in having:
                for vref in term.iget_nodes(VariableRef):
                    if vref.name not in selectedidx:
                        selectedidx.add(vref.name)
                        rqlst.selection.append(vref)


def iter_mapped_var_sels(stmt, variable):
    # variable is a Variable or ColumnAlias node mapped to a source side
    # callback
    if not (len(variable.stinfo['rhsrelations']) <= 1 and  # < 1 on column alias
            variable.stinfo['selected']):
        raise QueryError("can't use %s as a restriction variable"
                         % variable.name)
    for selectidx in variable.stinfo['selected']:
        vrefs = stmt.selection[selectidx].get_nodes(VariableRef)
        if len(vrefs) != 1:
            raise QueryError()
        yield selectidx, vrefs[0]


def update_source_cb_stack(state, stmt, node, stack):
    while True:
        node = node.parent
        if node is stmt:
            break
        if not isinstance(node, Function):
            raise QueryError()
        funcd = get_func_descr(node.name)
        if funcd.source_execute is None:
            raise QueryError('%s can not be called on mapped attribute'
                             % node.name)
        state.source_cb_funcs.add(node)
        funcd.update_cb_stack(stack)


# IGenerator implementation for RQL->SQL #######################################

class StateInfo(object):
    """this class stores data accumulated during the RQL syntax tree visit
    for later SQL generation.

    Attributes related to OUTER JOIN handling
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    * `outer_chains`, list of list of strings. Each list represent a tables
      that have to be outer joined together.

    * `outer_tables`, dictionary used as index of tables used in outer join ::

        'table alias': (outertype, [conditions], [chain])

      where:

      * `outertype` is one of None, 'LEFT', 'RIGHT', 'FULL'
      * `conditions` is a list of join conditions (string)
      * `chain` is a list of table alias (the *outer chain*) in which the key
        alias appears

    * `outer_pending` is a dictionary containing some conditions that will have
      to be added to the outer join when the table will be turned into an
      outerjoin ::

       'table alias': [conditions]
    """
    def __init__(self, select, existssols, unstablevars):
        self.existssols = existssols
        self.unstablevars = unstablevars
        self.subtables = {}
        self.needs_source_cb = None
        self.subquery_source_cb = None
        self.source_cb_funcs = set()
        self.scopes = {select: 0}
        self.scope_nodes = []

    def reset(self, solution):
        """reset some visit variables"""
        self.solution = solution
        self.count = 0
        self.done = set()
        self.tables = self.subtables.copy()
        self.actual_tables = [[]]
        for _, tsql in self.tables.values():
            self.actual_tables[-1].append(tsql)
        self.outer_chains = []
        self.outer_tables = {}
        self.outer_pending = {}
        self.duplicate_switches = []
        self.aliases = {}
        self.restrictions = []
        self._restr_stack = []
        self._needs_source_cb = {}

    def merge_source_cbs(self, needs_source_cb):
        if self.needs_source_cb is None:
            self.needs_source_cb = needs_source_cb
        elif needs_source_cb != self.needs_source_cb:
            raise QueryError('query fetch some source mapped attribute, some not')

    def finalize_source_cbs(self):
        if self.subquery_source_cb is not None:
            self.needs_source_cb.update(self.subquery_source_cb)

    def add_restriction(self, restr):
        if restr:
            self.restrictions.append(restr)

    def iter_exists_sols(self, exists):
        if exists not in self.existssols:
            yield 1
            return
        thisexistssols, thisexistsvars = self.existssols[exists]
        notdone_outside_vars = set()
        # when iterating other solutions inner to an EXISTS subquery, we should
        # reset variables which have this EXISTS node as scope at each iteration
        for var in exists.stmt.defined_vars.values():
            if var.scope is exists:
                thisexistsvars.add(var.name)
            elif var.name not in self.done:
                notdone_outside_vars.add(var)
        # make a copy of the outer statement's solution for later restore
        origsol = self.solution.copy()
        origtables = self.tables
        done = self.done
        for thisexistssol in thisexistssols:
            for vname in self.unstablevars:
                # check first if variable belong to the EXISTS's scope, else it may be missing from
                # `thisexistssol`
                if vname in thisexistsvars and thisexistssol[vname] != origsol[vname]:
                    break
            else:
                self.tables = origtables.copy()
                # overwrite current outer solution by EXISTS solution (the later will be missing
                # unstable outer variables)
                self.solution.update(thisexistssol)
                yield 1
                # cleanup self.done from stuff specific to EXISTS, so they will be reconsidered in
                # the next round
                for var in thisexistsvars:
                    if var in done:
                        done.remove(var)
                for var in list(notdone_outside_vars):
                    if var.name in done and var._q_sqltable in self.tables:
                        origtables[var._q_sqltable] = self.tables[var._q_sqltable]
                        notdone_outside_vars.remove(var)
                for rel in exists.iget_nodes(Relation):
                    if rel in done:
                        done.remove(rel)
        # restore original solution
        self.solution = origsol
        self.tables = origtables

    def push_scope(self, scope_node):
        self.scope_nodes.append(scope_node)
        self.scopes[scope_node] = len(self.actual_tables)
        self.actual_tables.append([])
        self._restr_stack.append(self.restrictions)
        self.restrictions = []

    def pop_scope(self):
        del self.scopes[self.scope_nodes[-1]]
        self.scope_nodes.pop()
        restrictions = self.restrictions
        self.restrictions = self._restr_stack.pop()
        scope = len(self.actual_tables) - 1
        # check if we have some outer chain for this scope
        matching_chains = []
        for chain in self.outer_chains:
            for tablealias in chain:
                if self.tables[tablealias][0] < scope:
                    # chain belongs to outer scope
                    break
            else:
                # chain match current scope
                matching_chains.append(chain)
        # call to `tables_sql` will pop actual_tables
        tables = self.tables_sql(matching_chains)
        # cleanup outer join related structure for tables in matching chains
        for chain in matching_chains:
            self.outer_chains.remove(chain)
            for alias in chain:
                del self.outer_tables[alias]
        return restrictions, tables

    # tables handling #########################################################

    def add_table(self, table, key=None, scope=-1):
        if key is None:
            key = table
        if key in self.tables:
            return
        if scope < 0:
            scope = len(self.actual_tables) + scope
        self.tables[key] = (scope, table)
        self.actual_tables[scope].append(table)

    def alias_and_add_table(self, tablename, scope=-1):
        alias = '%s%s' % (tablename, self.count)
        self.count += 1
        self.add_table('%s AS %s' % (tablename, alias), alias, scope)
        return alias

    def relation_table(self, relation):
        """return the table alias used by the given relation"""
        if relation in self.done:
            return relation._q_sqltable
        rid = 'rel_%s%s' % (relation.r_type, self.count)
        # relation's table is belonging to the root scope if it is the principal
        # table of one of its variable and that variable belong's to parent
        # scope
        for varref in relation.iget_nodes(VariableRef):
            var = varref.variable
            # XXX may have a principal without being invariant for this generation,
            #     not sure this is a pb or not
            if var.stinfo.get('principal') is relation and var.scope is var.stmt:
                scope = 0
                break
        else:
            scope = -1
        self.count += 1
        self.add_table('%s_relation AS %s' % (relation.r_type, rid), rid, scope=scope)
        relation._q_sqltable = rid
        self.done.add(relation)
        return rid

    def fti_table(self, relation, fti_table):
        """return the table alias used by the given has_text relation,
        `fti_table` being the table name for the plain text index
        """
        if relation in self.done:
            try:
                return relation._q_sqltable
            except AttributeError:
                pass
        self.done.add(relation)
        scope = self.scopes[relation.scope]
        alias = self.alias_and_add_table(fti_table, scope=scope)
        relation._q_sqltable = alias
        return alias

    # outer join handling ######################################################

    def mark_as_used_in_outer_join(self, tablealias, addpending=True):
        """Mark table of given alias as used in outer join. This must be called
        after `outer_tables[tablealias]` has been initialized.
        """
        # remove a table from actual_table because it's used in an outer join
        # chain
        scope, tabledef = self.tables[tablealias]
        self.actual_tables[scope].remove(tabledef)
        # check if there are some pending outer join condition for this table
        if addpending:
            try:
                pending_conditions = self.outer_pending.pop(tablealias)
            except KeyError:
                pass
            else:
                self.outer_tables[tablealias][1].extend(pending_conditions)
        else:
            assert tablealias not in self.outer_pending

    def add_outer_join_condition(self, tablealias, condition):
        try:
            outer, conditions, chain = self.outer_tables[tablealias]
            conditions.append(condition)
        except KeyError:
            self.outer_pending.setdefault(tablealias, []).append(condition)

    def replace_tables_by_outer_join(self, leftalias, rightalias,
                                     outertype, condition):
        """tell we need <leftalias> <outertype> JOIN <rightalias> ON <condition>
        """
        assert leftalias != rightalias, leftalias
        outer_tables = self.outer_tables
        louter, lconditions, lchain = outer_tables.get(leftalias,
                                                       (None, None, None))
        router, rconditions, rchain = outer_tables.get(rightalias,
                                                       (None, None, None))
        if lchain is None and rchain is None:
            # create a new outer chaine
            chain = [leftalias, rightalias]
            outer_tables[leftalias] = (None, [], chain)
            outer_tables[rightalias] = (outertype, [condition], chain)
            self.outer_chains.append(chain)
            self.mark_as_used_in_outer_join(leftalias, addpending=False)
            self.mark_as_used_in_outer_join(rightalias)
        elif lchain is None:
            # [A > B > C] + [D > A] -> [D > A > B > C]
            if rightalias == rchain[0]:
                outer_tables[leftalias] = (None, [], rchain)
                conditions = outer_tables[rightalias][1] + [condition]
                outer_tables[rightalias] = (outertype, conditions, rchain)
                rchain.insert(0, leftalias)
            else:
                # [A > B > C] + [D > B] -> [A > B > C < D]
                if outertype == 'LEFT':
                    outertype = 'RIGHT'
                outer_tables[leftalias] = (outertype, [condition], rchain)
                rchain.append(leftalias)
            self.mark_as_used_in_outer_join(leftalias)
        elif rchain is None:
            # [A > B > C] + [B > D] -> [A > B > C > D]
            outer_tables[rightalias] = (outertype, [condition], lchain)
            lchain.append(rightalias)
            self.mark_as_used_in_outer_join(rightalias)
        elif lchain is rchain:
            # already in the same chain, simply check compatibility and append
            # the condition if it's ok
            lidx = lchain.index(leftalias)
            ridx = lchain.index(rightalias)
            if ((outertype == 'FULL' and router != 'FULL')
                    or (lidx < ridx and router != 'LEFT')
                    or (ridx < lidx and louter != 'RIGHT')):
                raise BadRQLQuery()
            # merge conditions
            if lidx < ridx:
                rconditions.append(condition)
            else:
                lconditions.append(condition)
        elif louter is None:
            # merge chains
            self.outer_chains.remove(lchain)
            rchain += lchain
            self.mark_as_used_in_outer_join(leftalias)
            for alias, (aouter, aconditions, achain) in outer_tables.items():
                if achain is lchain:
                    outer_tables[alias] = (aouter, aconditions, rchain)
        else:
            raise BadRQLQuery()

    # sql generation helpers ###################################################

    def tables_sql(self, outer_chains=None):
        """generate SQL for FROM clause"""
        # sort for test predictability
        tables = sorted(self.actual_tables.pop())
        # process outer joins
        if outer_chains is None:
            assert not self.actual_tables, self.actual_tables
            assert not self.outer_pending
            outer_chains = self.outer_chains
        for chain in sorted(outer_chains):
            tablealias = chain[0]
            outertype, conditions, _ = self.outer_tables[tablealias]
            assert _ is chain, (chain, _)
            assert outertype is None, (chain, self.outer_chains)
            assert not conditions, (chain, self.outer_chains)
            assert len(chain) > 1
            tabledef = self.tables[tablealias][1]
            outerjoin = [tabledef]
            for tablealias in chain[1:]:
                outertype, conditions, _ = self.outer_tables[tablealias]
                assert _ is chain, (chain, self.outer_chains)
                assert outertype in ('LEFT', 'RIGHT', 'FULL'), (
                    tablealias, outertype, conditions)
                assert isinstance(conditions, (list)), (
                    tablealias, outertype, conditions)
                tabledef = self.tables[tablealias][1]
                outerjoin.append('%s OUTER JOIN %s ON (%s)' % (
                    outertype, tabledef, ' AND '.join(conditions)))
            tables.append(' '.join(outerjoin))
        return ', '.join(tables)


def extract_fake_having_terms(having):
    """RQL's HAVING may be used to contains stuff that should go in the WHERE
    clause of the SQL query, due to RQL grammar limitation. Split them...

    Return a list nodes that can be ANDed with query's WHERE clause. Having
    subtrees updated in place.
    """
    fakehaving = []
    for subtree in having:
        ors, tocheck = set(), []
        for compnode in subtree.get_nodes(Comparison):
            for fnode in compnode.get_nodes(Function):
                if fnode.descr().aggregat:
                    p = compnode.parent
                    oor = None
                    while not isinstance(p, Select):
                        if isinstance(p, (Or, Not)):
                            oor = p
                        p = p.parent
                    if oor is not None:
                        ors.add(oor)
                    break
            else:
                tocheck.append(compnode)
        # tocheck hold a set of comparison not implying an aggregat function
        # put them in fakehaving if they don't share an Or node as ancestor
        # with another comparison containing an aggregat function
        for compnode in tocheck:
            p = compnode.parent
            oor = None
            while not isinstance(p, Select):
                if p in ors or p is None:  # p is None for nodes already in fakehaving
                    break
                if isinstance(p, (Or, Not)):
                    oor = p
                p = p.parent
            else:
                node = oor or compnode
                fakehaving.append(node)
                node.parent.remove(node)
    return fakehaving


class SQLGenerator(object):
    """
    generation of SQL from the fully expanded RQL syntax tree
    SQL is designed to be used with a CubicWeb SQL schema

    Groups and sort are not handled here since they should not be handled at
    this level (see cubicweb.server.querier)

    we should not have errors here!

    WARNING: a CubicWebSQLGenerator instance is not thread safe, but generate is
    protected by a lock
    """

    def __init__(self, schema, dbhelper, attrmap=None):
        self.schema = schema
        self.dbhelper = dbhelper
        self.dbencoding = dbhelper.dbencoding
        self.keyword_map = {
            'NOW': self.dbhelper.sql_current_timestamp,
            'TODAY': self.dbhelper.sql_current_date,
        }
        if not self.dbhelper.union_parentheses_support:
            self.union_sql = self.noparen_union_sql
        self._lock = threading.Lock()
        if attrmap is None:
            attrmap = {}
        self.attr_map = attrmap

    def generate(self, union, args=None):
        """return SQL queries and a variable dictionary from a RQL syntax tree

        :partrqls: a list of couple (rqlst, solutions)
        :args: optional dictionary with values of substitutions used in the query

        return an sql string and a dictionary with substitutions values
        """
        if args is None:
            args = {}
        self._lock.acquire()
        self._args = args
        self._query_attrs = {}
        self._state = None
        # self._not_scope_offset = 0
        try:
            # union query for each rqlst / solution
            sql = self.union_sql(union)
            # we are done
            return sql, self._query_attrs, self._state.needs_source_cb
        finally:
            self._lock.release()

    def union_sql(self, union, needalias=False):  # pylint: disable=E0202
        if len(union.children) == 1:
            return self.select_sql(union.children[0], needalias)
        sqls = ('(%s)' % self.select_sql(select, needalias)
                for select in union.children)
        return '\nUNION ALL\n'.join(sqls)

    def noparen_union_sql(self, union, needalias=False):
        # needed for sqlite backend which doesn't like parentheses around union
        # query. This may cause bug in some condition (sort in one of the
        # subquery) but will work in most case
        #
        # see http://www.sqlite.org/cvstrac/tktview?tn=3074
        sqls = (self.select_sql(select, needalias)
                for i, select in enumerate(union.children))
        return '\nUNION ALL\n'.join(sqls)

    def select_sql(self, select, needalias=False):
        """return SQL queries and a variable dictionary from a RQL syntax tree

        :select: a selection statement of the syntax tree (`rql.stmts.Select`)
        :solution: a dictionary containing variables binding.
          A solution's dictionary has variable's names as key and variable's
          types as values
        :needwrap: boolean telling if the query will be wrapped in an outer
          query (to deal with aggregat and/or grouping)
        """
        if select.distinct:
            distinct = True
        elif self.dbhelper.fti_need_distinct:
            distinct = getattr(select.parent, 'has_text_query', False)
        else:
            distinct = False
        sorts = select.orderby
        groups = select.groupby
        having = select.having
        for restr in extract_fake_having_terms(having):
            scope = None
            for vref in restr.get_nodes(VariableRef):
                vscope = vref.variable.scope
                if vscope is select:
                    # ignore select scope, so restriction is added to the innermost possible scope
                    continue
                if scope is None:
                    scope = vscope
                elif vscope is not scope:
                    scope = common_parent(scope, vscope).scope
            if scope is None:
                scope = select
            scope.add_restriction(restr)
        # remember selection, it may be changed and have to be restored
        origselection = select.selection[:]
        # check if the query will have union subquery, if it need sort term
        # selection (union or distinct query) and wrapping (union with groups)
        needwrap = False
        sols = select.solutions
        selectsortterms = distinct
        if len(sols) > 1:
            # remove invariant from solutions
            sols, existssols, unstable = remove_unused_solutions(
                select, sols, self.schema)
            if len(sols) > 1:
                # if there is still more than one solution, a UNION will be
                # generated and so sort terms have to be selected
                selectsortterms = True
                # and if select is using group by or aggregat, a wrapping
                # query will be necessary
                if groups or select.has_aggregat:
                    select.select_only_variables()
                    needwrap = True
        else:
            existssols, unstable = {}, ()
        state = StateInfo(select, existssols, unstable)
        if self._state is not None:
            # state from a previous unioned select
            state.merge_source_cbs(self._state.needs_source_cb)
        # treat subqueries
        self._subqueries_sql(select, state)
        # generate sql for this select node
        if needwrap:
            outerselection = origselection[:]
            if sorts and selectsortterms:
                if distinct:
                    sort_term_selection(sorts, outerselection, groups)
        fix_selection_and_group(select, needwrap, selectsortterms,
                                sorts, groups, having)
        if needwrap:
            fneedwrap = len(outerselection) != len(origselection)
        else:
            fneedwrap = len(select.selection) != len(origselection)
        if fneedwrap:
            needalias = True
        self._in_wrapping_query = False
        self._state = state
        try:
            sql = self._solutions_sql(select, sols, distinct,
                                      needalias or needwrap)
            # generate groups / having before wrapping query selection to get
            # correct column aliases
            self._in_wrapping_query = needwrap
            if groups:
                # no constant should be inserted in GROUP BY else the backend
                # will interpret it as a positional index in the selection
                groups = ','.join(vref.accept(self) for vref in groups
                                  if not isinstance(vref, Constant))
            if having:
                # filter out constants as for GROUP BY
                having = ' AND '.join(term.accept(self) for term in having
                                      if not isinstance(term, Constant))
            if needwrap:
                sql = '%s FROM (%s) AS T1' % (
                    self._selection_sql(outerselection, distinct, needalias),
                    sql)
            if groups:
                sql += '\nGROUP BY %s' % groups
            if having:
                sql += '\nHAVING %s' % having
            # sort
            if sorts:
                sqlsortterms = []
                if needwrap:
                    selectidx = [str(term) for term in outerselection]
                else:
                    selectidx = [str(term) for term in select.selection]
                for sortterm in sorts:
                    _term = self._sortterm_sql(sortterm, selectidx)
                    if _term is not None:
                        sqlsortterms.append(_term)
                if sqlsortterms:
                    sql = self.dbhelper.sql_add_order_by(
                        sql, sqlsortterms, origselection, fneedwrap,
                        select.limit or select.offset)
            else:
                sqlsortterms = None
            state.finalize_source_cbs()
        finally:
            select.selection = origselection
        # limit / offset
        sql = self.dbhelper.sql_add_limit_offset(sql,
                                                 select.limit,
                                                 select.offset,
                                                 sqlsortterms)
        return sql

    def _subqueries_sql(self, select, state):
        for i, subquery in enumerate(select.with_):
            sql = self.union_sql(subquery.query, needalias=True)
            tablealias = '_T%s' % i  # XXX nested subqueries
            sql = '(%s) AS %s' % (sql, tablealias)
            state.subtables[tablealias] = (0, sql)
            latest_state = self._state
            for vref in subquery.aliases:
                alias = vref.variable
                alias._q_sqltable = tablealias
                alias._q_sql = '%s.C%s' % (tablealias, alias.colnum)
                try:
                    stack = latest_state.needs_source_cb[alias.colnum]
                    if state.subquery_source_cb is None:
                        state.subquery_source_cb = {}
                    for selectidx, vref in iter_mapped_var_sels(select, alias):
                        stack = stack[:]
                        update_source_cb_stack(state, select, vref, stack)
                        state.subquery_source_cb[selectidx] = stack
                except KeyError:
                    continue

    def _solutions_sql(self, select, solutions, distinct, needalias):
        sqls = []
        for solution in solutions:
            self._state.reset(solution)
            # visit restriction subtree
            if select.where is not None:
                self._state.add_restriction(select.where.accept(self))
            sql = [self._selection_sql(select.selection, distinct, needalias)]
            if self._state.restrictions:
                sql.append('WHERE %s' % ' AND '.join(self._state.restrictions))
            self._state.merge_source_cbs(self._state._needs_source_cb)
            # add required tables
            assert len(self._state.actual_tables) == 1, self._state.actual_tables
            tables = self._state.tables_sql()
            if tables:
                sql.insert(1, 'FROM %s' % tables)
            elif self._state.restrictions and self.dbhelper.needs_from_clause:
                sql.insert(1, 'FROM (SELECT 1) AS _T')
            sqls.append('\n'.join(sql))
        if distinct:
            return '\nUNION\n'.join(sqls)
        else:
            return '\nUNION ALL\n'.join(sqls)

    def _selection_sql(self, selected, distinct, needaliasing=False):
        clause = []
        for term in selected:
            sql = term.accept(self)
            if needaliasing:
                colalias = 'C%s' % len(clause)
                clause.append('%s AS %s' % (sql, colalias))
                if isinstance(term, VariableRef):
                    self._state.aliases[term.name] = colalias
            else:
                clause.append(sql)
        if distinct:
            return 'SELECT DISTINCT %s' % ', '.join(clause)
        return 'SELECT %s' % ', '.join(clause)

    def _sortterm_sql(self, sortterm, selectidx):
        term = sortterm.term
        try:
            sqlterm = selectidx.index(str(term)) + 1
        except ValueError:
            # Constant node or non selected term
            sqlterm = term.accept(self)
            if sqlterm is None:
                return None
        if sortterm.asc:
            return str(sqlterm)
        else:
            return '%s DESC' % sqlterm

    def visit_and(self, et):
        """generate SQL for a AND subtree"""
        res = []
        for c in et.children:
            part = c.accept(self)
            if part:
                res.append(part)
        return ' AND '.join(res)

    def visit_or(self, ou):
        """generate SQL for a OR subtree"""
        res = []
        for c in ou.children:
            part = c.accept(self)
            if part:
                res.append('(%s)' % part)
        if res:
            if len(res) > 1:
                return '(%s)' % ' OR '.join(res)
            return res[0]
        return ''

    def visit_not(self, node):
        csql = node.children[0].accept(self)
        if node in self._state.done or not csql:
            # already processed or no sql generated by children
            return csql
        return 'NOT (%s)' % csql

    def visit_exists(self, exists):
        """generate SQL name for a exists subquery"""
        sqls = []
        for dummy in self._state.iter_exists_sols(exists):
            sql = self._visit_exists(exists)
            if sql:
                sqls.append(sql)
        if not sqls:
            return ''
        return 'EXISTS(%s)' % ' UNION '.join(sqls)

    def _visit_exists(self, exists):
        self._state.push_scope(exists)
        restriction = exists.children[0].accept(self)
        restrictions, tables = self._state.pop_scope()
        if restriction:
            restrictions.append(restriction)
        restriction = ' AND '.join(restrictions)
        if not restriction:
            if tables:
                return 'SELECT 1 FROM %s' % tables
            return ''
        if not tables:
            # XXX could leave surrounding EXISTS() in this case no?
            sql = 'SELECT 1 WHERE %s' % restriction
        else:
            sql = 'SELECT 1 FROM %s WHERE %s' % (tables, restriction)
        return sql

    def visit_relation(self, relation):
        """generate SQL for a relation"""
        rtype = relation.r_type
        # don't care of type constraint statement (i.e. relation_type = 'is')
        if relation.is_types_restriction():
            return ''
        lhs, rhs = relation.get_parts()
        rschema = self.schema.rschema(rtype)
        if rschema.final:
            if (rtype == 'eid' and lhs.variable._q_invariant
                    and lhs.variable.stinfo['constnode']):
                # special case where this restriction is already generated by
                # some other relation
                return ''
            # attribute relation
            if rtype == 'has_text':
                sql = self._visit_has_text_relation(relation)
            else:
                rhs_vars = rhs.get_nodes(VariableRef)
                if rhs_vars:
                    # if variable(s) in the RHS
                    sql = self._visit_var_attr_relation(relation, rhs_vars)
                else:
                    # no variables in the RHS
                    sql = self._visit_attribute_relation(relation)
        elif (rtype == 'is' and isinstance(rhs.children[0], Constant)
              and rhs.children[0].eval(self._args) is None):
            lhssql = lhs.accept(self)
            return '%s%s' % (lhssql, rhs.accept(self))
        elif relation.optional:
            # OPTIONAL relation, generate a left|right outer join
            if rtype == 'identity' or rschema.inlined:
                sql = self._visit_outer_join_inlined_relation(relation, rschema)
            else:
                sql = self._visit_outer_join_relation(relation, rschema)
        elif rschema.inlined:
            sql = self._visit_inlined_relation(relation)
        else:
            # regular (non final) relation
            sql = self._visit_relation(relation, rschema)
        return sql

    def _visit_inlined_relation(self, relation):
        lhsvar, _, rhsvar, rhsconst = relation_info(relation)
        # we are sure lhsvar is not None
        lhssql = self._inlined_var_sql(lhsvar, relation.r_type)
        if rhsvar is None:
            moresql = None
        else:
            moresql = self._extra_join_sql(relation, lhssql, rhsvar)
        if isinstance(relation.parent, Not):
            self._state.done.add(relation.parent)
            if rhsvar is not None and rhsvar._q_invariant:
                sql = '%s IS NULL' % lhssql
            else:
                # column != 1234 may not get back rows where column is NULL...
                sql = '(%s IS NULL OR %s!=%s)' % (
                    lhssql, lhssql, (rhsvar or rhsconst).accept(self))
        elif rhsconst is not None:
            sql = '%s=%s' % (lhssql, rhsconst.accept(self))
        elif isinstance(rhsvar, Variable) and rhsvar._q_invariant:
            # if the rhs variable is only linked to this relation, this mean we
            # only want the relation to exists, eg NOT NULL in case of inlined
            # relation
            if moresql is not None:
                return moresql
            return '%s IS NOT NULL' % lhssql
        else:
            sql = '%s=%s' % (lhssql, rhsvar.accept(self))
        if moresql is None:
            return sql
        return '%s AND %s' % (sql, moresql)

    def _process_relation_term(self, relation, rid, termvar, termconst, relfield):
        if termconst or not termvar._q_invariant:
            termsql = termconst and termconst.accept(self) or termvar.accept(self)
            yield '%s.%s=%s' % (rid, relfield, termsql)
        elif termvar._q_invariant:
            extrajoin = self._extra_join_sql(relation, '%s.%s' % (rid, relfield), termvar)
            if extrajoin is not None:
                yield extrajoin

    def _visit_relation(self, relation, rschema):
        """generate SQL for a relation

        implements optimization 1.
        """
        if relation.r_type == 'identity':
            # special case "X identity Y"
            lhs, rhs = relation.get_parts()
            return '%s%s' % (lhs.accept(self), rhs.accept(self))
        lhsvar, lhsconst, rhsvar, rhsconst = relation_info(relation)
        rid = self._state.relation_table(relation)
        sqls = []
        sqls += self._process_relation_term(relation, rid, lhsvar, lhsconst, 'eid_from')
        sqls += self._process_relation_term(relation, rid, rhsvar, rhsconst, 'eid_to')
        sql = ' AND '.join(sqls)
        return sql

    def _visit_outer_join_relation(self, relation, rschema):
        """
        left outer join syntax (optional=='right'):
          X relation Y?

        right outer join syntax (optional=='left'):
          X? relation Y

        full outer join syntaxes (optional=='both'):
          X? relation Y?

        if relation is inlined:
           if it's a left outer join:
           -> X LEFT OUTER JOIN Y ON (X.relation=Y.eid)
           elif it's a right outer join:
           -> Y LEFT OUTER JOIN X ON (X.relation=Y.eid)
           elif it's a full outer join:
           -> X FULL OUTER JOIN Y ON (X.relation=Y.eid)
        else:
           if it's a left outer join:
           -> X LEFT OUTER JOIN relation ON (relation.eid_from=X.eid)
              LEFT OUTER JOIN Y ON (relation.eid_to=Y.eid)
           elif it's a right outer join:
           -> Y LEFT OUTER JOIN relation ON (relation.eid_to=Y.eid)
              LEFT OUTER JOIN X ON (relation.eid_from=X.eid)
           elif it's a full outer join:
           -> X FULL OUTER JOIN Y ON (X.relation=Y.eid)
        """
        leftvar, leftconst, rightvar, rightconst = relation_info(relation)
        assert not (leftconst and rightconst), "doesn't make sense"
        if relation.optional == 'left':
            leftvar, rightvar = rightvar, leftvar
            leftconst, rightconst = rightconst, leftconst
            joinattr, restrattr = 'eid_to', 'eid_from'
        else:
            joinattr, restrattr = 'eid_from', 'eid_to'
        # search table for this variable, to use as left table of the outer join
        leftalias = None
        if leftvar:
            # take care, may return None for invariant variable
            leftalias = self._var_table(leftvar)
        if leftalias is None:
            if leftvar.stinfo['principal'] is not relation:
                # use variable's principal relation
                leftalias = leftvar.stinfo['principal']._q_sqltable
            else:
                # search for relation on which we should join
                rschema = self.schema.rschema
                for orelation in leftvar.stinfo['relations']:
                    if orelation is not relation and not rschema(orelation.r_type).final:
                        break
                else:
                    for orelation in rightvar.stinfo['relations']:
                        if (orelation is not relation
                                and not rschema(orelation.r_type).final
                                and orelation.optional):
                            break
                    else:
                        # unexpected
                        assert False, leftvar
                leftalias = self._state.relation_table(orelation)
        # right table of the outer join
        rightalias = self._state.relation_table(relation)
        # compute join condition
        if not leftconst or (leftvar and not leftvar._q_invariant):
            leftsql = leftvar.accept(self)
        else:
            leftsql = leftconst.accept(self)
        condition = '%s.%s=%s' % (rightalias, joinattr, leftsql)
        if rightconst:
            condition += ' AND %s.%s=%s' % (rightalias, restrattr, rightconst.accept(self))
        # record outer join
        outertype = 'FULL' if relation.optional == 'both' else 'LEFT'
        self._state.replace_tables_by_outer_join(leftalias, rightalias,
                                                 outertype, condition)
        # need another join?
        if rightconst is None:
            # we need another outer join for the other side of the relation (e.g.
            # for "X relation Y?" in RQL, we treated earlier the (cw_X.eid /
            # relation.eid_from) join, now we've to do (relation.eid_to /
            # cw_Y.eid)
            leftalias = rightalias
            rightvar.accept(self)  # accept before using var_table
            rightalias = self._var_table(rightvar)
            if rightalias is None:
                if rightvar.stinfo['principal'] is not relation:
                    self._state.replace_tables_by_outer_join(
                        leftalias, rightvar.stinfo['principal']._q_sqltable,
                        outertype, '%s.%s=%s' % (leftalias, restrattr, rightvar.accept(self)))
            else:
                self._state.replace_tables_by_outer_join(
                    leftalias, rightalias, outertype,
                    '%s.%s=%s' % (leftalias, restrattr, rightvar.accept(self)))
        # this relation will hence be expressed in FROM clause, return nothing
        # here
        return ''

    def _visit_outer_join_inlined_relation(self, relation, rschema):
        lhsvar, lhsconst, rhsvar, rhsconst = relation_info(relation)
        assert not (lhsconst and rhsconst), "doesn't make sense"
        attr = 'eid' if relation.r_type == 'identity' else relation.r_type
        lhsalias = self._var_table(lhsvar)
        rhsalias = rhsvar and self._var_table(rhsvar)
        if lhsalias is None:
            lhssql = lhsconst.accept(self)
        elif attr == 'eid':
            lhssql = lhsvar.accept(self)
        else:
            lhssql = '%s.%s%s' % (lhsalias, SQL_PREFIX, attr)
        condition = '%s=%s' % (lhssql, (rhsconst or rhsvar).accept(self))
        # this is not a typo, rhs optional variable means lhs outer join and vice-versa
        if relation.optional == 'left':
            lhsvar, rhsvar = rhsvar, lhsvar
            lhsconst, rhsconst = rhsconst, lhsconst
            lhsalias, rhsalias = rhsalias, lhsalias
            outertype = 'LEFT'
        elif relation.optional == 'both':
            outertype = 'FULL'
        else:
            outertype = 'LEFT'
        if rhsalias is None:
            if rhsconst is not None:
                # inlined relation with invariant as rhs
                if relation.r_type != 'identity':
                    condition = '(%s OR %s IS NULL)' % (condition, lhssql)
                if not lhsvar.stinfo.get('optrelations'):
                    return condition
                self._state.add_outer_join_condition(lhsalias, condition)
            return
        if lhsalias is None:
            if lhsconst is not None and not rhsvar.stinfo.get('optrelations'):
                return condition
            lhsalias = lhsvar._q_sql.split('.', 1)[0]
        if lhsalias == rhsalias:
            self._state.add_outer_join_condition(lhsalias, condition)
        else:
            self._state.replace_tables_by_outer_join(
                lhsalias, rhsalias, outertype, condition)
        return ''

    def _visit_var_attr_relation(self, relation, rhs_vars):
        """visit an attribute relation with variable(s) in the RHS

        attribute variables are used either in the selection or for unification
        (eg X attr1 A, Y attr2 A). In case of selection, nothing to do here.
        """
        ored = relation.ored()
        for vref in rhs_vars:
            var = vref.variable
            if isinstance(var, ColumnAlias):
                # force sql generation whatever the computed principal
                principal = 1
            else:
                principal = var.stinfo.get('principal')
            # we've to return some sql if:
            # 1. visited relation is ored
            # 2. variable's principal is not this relation and not 1.
            if ored or (principal is not None and principal is not relation
                        and not getattr(principal, 'ored', lambda: 0)()):
                # we have to generate unification expression
                if principal is relation:
                    # take care if ored case and principal is the relation to
                    # use the right relation in the unification term
                    _rel = [rel for rel in var.stinfo['rhsrelations']
                            if rel is not principal][0]
                else:
                    _rel = relation
                lhssql = self._inlined_var_sql(_rel.children[0].variable,
                                               _rel.r_type)
                sql = lhssql + relation.children[1].accept(self)
                if relation.optional == 'right':
                    leftalias = self._var_table(principal.children[0].variable)
                    rightalias = self._var_table(relation.children[0].variable)
                    self._state.replace_tables_by_outer_join(
                        leftalias, rightalias, 'LEFT', sql)
                    return ''
                return sql
        return ''

    def _visit_attribute_relation(self, rel):
        """generate SQL for an attribute relation"""
        lhs, rhs = rel.get_parts()
        rhssql = rhs.accept(self)
        if isinstance(lhs.variable, ColumnAlias):
            if rel.r_type != 'eid':
                raise BadRQLQuery('Attribute %s of %s must be selected from subqueries'
                                  % (rel.r_type, lhs.variable))
            # nb: case where subquery variable isn't an eid will raise a TypeResolverException, no
            # need for defense here
            lhssql = lhs.accept(self)
        else:
            table = self._var_table(lhs.variable)
            if table is None:
                # table is None if variable has been annotated as invariant, hence we don't expect
                # accessing another attribute than eid
                assert rel.r_type == 'eid'
                lhssql = lhs.accept(self)
            else:
                mapkey = '%s.%s' % (self._state.solution[lhs.name], rel.r_type)
                if mapkey in self.attr_map:
                    cb, sourcecb = self.attr_map[mapkey]
                    if sourcecb:
                        # callback is a source callback, we can't use this
                        # attribute in restriction
                        raise QueryError("can't use %s (%s) in restriction"
                                         % (mapkey, rel.as_string()))
                    lhssql = cb(self, lhs.variable, rel)
                elif rel.r_type == 'eid':
                    lhssql = lhs.variable._q_sql
                else:
                    lhssql = '%s.%s%s' % (table, SQL_PREFIX, rel.r_type)
        try:
            if rel._q_needcast == 'TODAY':
                sql = 'DATE(%s)%s' % (lhssql, rhssql)
            # XXX which cast function should be used
            # elif rel._q_needcast == 'NOW':
            #    sql = 'TIMESTAMP(%s)%s' % (lhssql, rhssql)
            else:
                sql = '%s%s' % (lhssql, rhssql)
        except AttributeError:
            sql = '%s%s' % (lhssql, rhssql)
        if lhs.variable.stinfo.get('optrelations'):
            self._state.add_outer_join_condition(table, sql)
        else:
            return sql

    def _visit_has_text_relation(self, rel):
        """generate SQL for a has_text relation"""
        lhs, rhs = rel.get_parts()
        const = rhs.children[0]
        alias = self._state.fti_table(rel, self.dbhelper.fti_table)
        jointo = lhs.accept(self)
        restriction = ''
        lhsvar = lhs.variable
        me_is_principal = lhsvar.stinfo.get('principal') is rel
        if me_is_principal:
            jointo = None
            if lhsvar.stinfo['typerel'] is not None:
                if not lhsvar._q_invariant or len(lhsvar.stinfo['possibletypes']) == 1:
                    ealias = lhsvar._q_sqltable = '_' + lhsvar.name
                    jointo = lhsvar._q_sql = '%s.cw_eid' % ealias
                    self._state.add_table('cw_%s AS %s' % (self._state.solution[lhs.name], ealias),
                                          ealias)
                else:
                    subquery = ' UNION '.join('SELECT cw_eid FROM cw_%s' % etype
                                              for etype in sorted(lhsvar.stinfo['possibletypes']))
                    restriction = ' AND %s IN (%s)' % (lhsvar._q_sql, subquery)
        if isinstance(rel.parent, Not):
            self._state.done.add(rel.parent)
            not_ = True
        else:
            not_ = False
        query = const.eval(self._args)
        return self.dbhelper.fti_restriction_sql(alias, query,
                                                 jointo, not_) + restriction

    def visit_comparison(self, cmp):
        """generate SQL for a comparison"""
        optional = cmp.optional
        if len(cmp.children) == 2:
            # simplified expression from HAVING clause
            lhs, rhs = cmp.children
        else:
            lhs = None
            rhs = cmp.children[0]
            assert not optional
        sql = None
        operator = cmp.operator
        if operator in ('LIKE', 'ILIKE'):
            if operator == 'ILIKE' and not self.dbhelper.ilike_support:
                operator = ' LIKE '
            else:
                operator = ' %s ' % operator
        elif operator == 'REGEXP':
            sql = ' %s' % self.dbhelper.sql_regexp_match_expression(rhs.accept(self))
        elif (operator == '=' and isinstance(rhs, Constant)
              and rhs.eval(self._args) is None):
            if lhs is None:
                sql = ' IS NULL'
            else:
                sql = '%s IS NULL' % lhs.accept(self)
        elif isinstance(rhs, Function) and rhs.name == 'IN':
            assert operator == '='
            operator = ' '
        if sql is None:
            if lhs is None:
                sql = '%s%s' % (operator, rhs.accept(self))
            else:
                sql = '%s%s%s' % (lhs.accept(self), operator, rhs.accept(self))
        if optional is None:
            return sql
        leftvars = cmp.children[0].get_nodes(VariableRef)
        assert len(leftvars) == 1
        if leftvars[0].variable.stinfo['attrvar'] is None:
            assert isinstance(leftvars[0].variable, ColumnAlias)
            leftalias = leftvars[0].variable._q_sqltable
        else:
            leftalias = self._var_table(leftvars[0].variable.stinfo['attrvar'])
        rightvars = cmp.children[1].get_nodes(VariableRef)
        assert len(rightvars) == 1
        if rightvars[0].variable.stinfo['attrvar'] is None:
            assert isinstance(rightvars[0].variable, ColumnAlias)
            rightalias = rightvars[0].variable._q_sqltable
        else:
            rightalias = self._var_table(rightvars[0].variable.stinfo['attrvar'])
        if optional == 'right':
            self._state.replace_tables_by_outer_join(
                leftalias, rightalias, 'LEFT', sql)
        elif optional == 'left':
            self._state.replace_tables_by_outer_join(
                rightalias, leftalias, 'LEFT', sql)
        else:
            self._state.replace_tables_by_outer_join(
                leftalias, rightalias, 'FULL', sql)
        return ''

    def visit_mathexpression(self, mexpr):
        """generate SQL for a mathematic expression"""
        lhs, rhs = mexpr.get_parts()
        # check for string concatenation
        operator = mexpr.operator
        if operator == '%':
            operator = '%%'
        try:
            if (mexpr.operator == '+'
                    and mexpr.get_type(self._state.solution, self._args) == 'String'):
                return '(%s)' % self.dbhelper.sql_concat_string(lhs.accept(self),
                                                                rhs.accept(self))
        except CoercionError:
            pass
        return '(%s %s %s)' % (lhs.accept(self), operator, rhs.accept(self))

    def visit_unaryexpression(self, uexpr):
        """generate SQL for a unary expression"""
        return '%s%s' % (uexpr.operator, uexpr.children[0].accept(self))

    def visit_function(self, func):
        """generate SQL name for a function"""
        if func.name == 'FTIRANK':
            try:
                rel = next(iter(func.children[0].variable.stinfo['ftirels']))
            except KeyError:
                raise BadRQLQuery("can't use FTIRANK on variable not used in an"
                                  " 'has_text' relation (eg full-text search)")
            const = rel.get_parts()[1].children[0]
            return self.dbhelper.fti_rank_order(
                self._state.fti_table(rel, self.dbhelper.fti_table),
                const.eval(self._args))
        args = [c.accept(self) for c in func.children]
        if func in self._state.source_cb_funcs:
            # function executed as a callback on the source
            assert len(args) == 1
            return args[0]
        # func_as_sql will check function is supported by the backend
        return self.dbhelper.func_as_sql(func.name, args)

    def visit_constant(self, constant):
        """generate SQL name for a constant"""
        if constant.type is None:
            return 'NULL'
        value = constant.value
        if constant.type == 'etype':
            return value
        # don't substitute int, causes pb when used as sorting column number
        if constant.type == 'Int':
            return str(value)
        if constant.type in ('Date', 'Datetime'):
            rel = constant.relation()
            if rel is not None:
                rel._q_needcast = value
            return self.keyword_map[value]()
        if constant.type == 'Substitute':
            _id = value
            if PY2 and isinstance(_id, text_type):
                _id = _id.encode()
        else:
            _id = str(id(constant)).replace('-', '', 1)
            self._query_attrs[_id] = value
        return '%%(%s)s' % _id

    def visit_variableref(self, variableref):
        """get the sql name for a variable reference"""
        # use accept, .variable may be a variable or a columnalias
        return variableref.variable.accept(self)

    def visit_columnalias(self, colalias):
        """get the sql name for a subquery column alias"""
        return colalias._q_sql

    def visit_variable(self, variable):
        """get the table name and sql string for a variable"""
        if variable.name in self._state.done:
            if self._in_wrapping_query:
                return 'T1.%s' % self._state.aliases[variable.name]
            return variable._q_sql
        self._state.done.add(variable.name)
        vtablename = None
        if variable.stinfo['attrvar']:
            # attribute variable (systematically used in rhs of final
            # relation(s)), get table name and sql from any rhs relation
            sql = self._linked_var_sql(variable)
        elif variable._q_invariant:
            # since variable is invariant, we know we won't found final relation
            principal = variable.stinfo['principal']
            if principal is None:
                assert variable.stinfo['typerel'] is None
                vtablename = '_' + variable.name
                self._state.add_table('entities AS %s' % vtablename, vtablename)
                sql = '%s.eid' % vtablename
            elif principal.r_type == 'has_text':
                sql = '%s.%s' % (self._state.fti_table(principal,
                                                       self.dbhelper.fti_table),
                                 self.dbhelper.fti_uid_attr)
            elif principal in variable.stinfo['rhsrelations']:
                if self.schema.rschema(principal.r_type).inlined:
                    sql = self._linked_var_sql(variable)
                else:
                    sql = '%s.eid_to' % self._state.relation_table(principal)
            else:
                sql = '%s.eid_from' % self._state.relation_table(principal)
        else:
            # standard variable: get table name according to etype and use .eid
            # attribute
            sql, vtablename = self._var_info(variable)
        variable._q_sqltable = vtablename
        variable._q_sql = sql
        return sql

    # various utilities #######################################################

    def _extra_join_sql(self, relation, sql, var):
        # if rhs var is invariant, and this relation is not its principal,
        # generate extra join
        try:
            if not var.stinfo['principal'] is relation:
                op = relation.operator()
                if op == '=':
                    # need a predicable result for tests
                    args = sorted((sql, var.accept(self)))
                    args.insert(1, op)
                else:
                    args = (sql, op, var.accept(self))
                return '%s%s%s' % tuple(args)
        except KeyError:
            # no principal defined, relation is necessarily the principal and
            # so nothing to return here
            pass
        return None

    def _var_info(self, var):
        scope = self._state.scopes[var.scope]
        etype = self._state.solution[var.name]
        # XXX this check should be moved in rql.stcheck
        if self.schema.eschema(etype).final:
            raise BadRQLQuery(var.stmt.root)
        tablealias = '_' + var.name
        sql = '%s.%seid' % (tablealias, SQL_PREFIX)
        self._state.add_table('%s%s AS %s' % (SQL_PREFIX, etype, tablealias),
                              tablealias, scope=scope)
        return sql, tablealias

    def _inlined_var_sql(self, var, rtype):
        # rtype may be an attribute relation when called from
        # _visit_var_attr_relation.  take care about 'eid' rtype, since in
        # some case we may use the `entities` table, so in that case we've
        # to properly use variable'sql
        if rtype == 'eid':
            sql = var.accept(self)
        else:
            sql = '%s.%s%s' % (self._var_table(var), SQL_PREFIX, rtype)
        return sql

    def _linked_var_sql(self, variable):
        rel = (variable.stinfo.get('principal') or
               next(iter(variable.stinfo['rhsrelations'])))
        linkedvar = rel.children[0].variable
        if rel.r_type == 'eid':
            return linkedvar.accept(self)
        if isinstance(linkedvar, ColumnAlias):
            raise BadRQLQuery('variable %s should be selected by the subquery'
                              % variable.name)
        mapkey = '%s.%s' % (self._state.solution[linkedvar.name], rel.r_type)
        if mapkey in self.attr_map:
            cb, sourcecb = self.attr_map[mapkey]
            if not sourcecb:
                return cb(self, linkedvar, rel)
            # attribute mapped at the source level (bfss for instance)
            stmt = rel.stmt
            for selectidx, vref in iter_mapped_var_sels(stmt, variable):
                stack = [cb]
                update_source_cb_stack(self._state, stmt, vref, stack)
                self._state._needs_source_cb[selectidx] = stack
        linkedvar.accept(self)
        return '%s.%s%s' % (linkedvar._q_sqltable, SQL_PREFIX, rel.r_type)

    # tables handling #########################################################

    def _var_table(self, var):
        var.accept(self)
        return var._q_sqltable
