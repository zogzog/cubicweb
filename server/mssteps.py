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
"""Defines the diferent querier steps usable in plans.

FIXME : this code needs refactoring. Some problems :
* get data from the parent plan, the latest step, temporary table...
* each step has is own members (this is not necessarily bad, but a bit messy
  for now)
"""
__docformat__ = "restructuredtext en"

from rql.nodes import VariableRef, Variable, Function

from cubicweb.server.ssplanner import (LimitOffsetMixIn, Step, OneFetchStep,
                                    varmap_test_repr, offset_result)

AGGR_TRANSFORMS = {'COUNT':'SUM', 'MIN':'MIN', 'MAX':'MAX', 'SUM': 'SUM'}

class remove_and_restore_clauses(object):
    def __init__(self, union, keepgroup):
        self.union = union
        self.keepgroup = keepgroup
        self.clauses = None

    def __enter__(self):
        self.clauses = clauses = []
        for select in self.union.children:
            if self.keepgroup:
                having, orderby = select.having, select.orderby
                select.having, select.orderby = (), ()
                clauses.append( (having, orderby) )
            else:
                groupby, having, orderby = select.groupby, select.having, select.orderby
                select.groupby, select.having, select.orderby = (), (), ()
                clauses.append( (groupby, having, orderby) )

    def __exit__(self, exctype, exc, traceback):
        for i, select in enumerate(self.union.children):
            if self.keepgroup:
                select.having, select.orderby = self.clauses[i]
            else:
                select.groupby, select.having, select.orderby = self.clauses[i]


class FetchStep(OneFetchStep):
    """step consisting in fetching data from sources, and storing result in
    a temporary table
    """
    def __init__(self, plan, union, sources, table, keepgroup, inputmap=None):
        OneFetchStep.__init__(self, plan, union, sources)
        # temporary table to store step result
        self.table = table
        # should groupby clause be kept or not
        self.keepgroup = keepgroup
        # variables mapping to use as input
        self.inputmap = inputmap
        # output variable mapping
        srqlst = union.children[0] # sample select node
        # add additional information to the output mapping
        self.outputmap = plan.init_temp_table(table, srqlst.selection,
                                              srqlst.solutions[0])
        for vref in srqlst.selection:
            if not isinstance(vref, VariableRef):
                continue
            var = vref.variable
            if var.stinfo.get('attrvars'):
                for lhsvar, rtype in var.stinfo['attrvars']:
                    if lhsvar.name in srqlst.defined_vars:
                        key = '%s.%s' % (lhsvar.name, rtype)
                        self.outputmap[key] = self.outputmap[var.name]
            else:
                rschema = self.plan.schema.rschema
                for rel in var.stinfo['rhsrelations']:
                    if rschema(rel.r_type).inlined:
                        lhsvar = rel.children[0]
                        if lhsvar.name in srqlst.defined_vars:
                            key = '%s.%s' % (lhsvar.name, rel.r_type)
                            self.outputmap[key] = self.outputmap[var.name]

    def execute(self):
        """execute this step"""
        self.execute_children()
        plan = self.plan
        plan.create_temp_table(self.table)
        union = self.union
        with remove_and_restore_clauses(union, self.keepgroup):
            for source in self.sources:
                source.flying_insert(self.table, plan.session, union, plan.args,
                                     self.inputmap)

    def mytest_repr(self):
        """return a representation of this step suitable for test"""
        with remove_and_restore_clauses(self.union, self.keepgroup):
            try:
                inputmap = varmap_test_repr(self.inputmap, self.plan.tablesinorder)
                outputmap = varmap_test_repr(self.outputmap, self.plan.tablesinorder)
            except AttributeError:
                inputmap = self.inputmap
                outputmap = self.outputmap
            return (self.__class__.__name__,
                    sorted((r.as_string(kwargs=self.plan.args), r.solutions)
                           for r in self.union.children),
                    sorted(self.sources), inputmap, outputmap)


class AggrStep(LimitOffsetMixIn, Step):
    """step consisting in making aggregat from temporary data in the system
    source
    """
    def __init__(self, plan, selection, select, table, outputtable=None):
        Step.__init__(self, plan)
        # original selection
        self.selection = selection
        # original Select RQL tree
        self.select = select
        # table where are located temporary results
        self.table = table
        # optional table where to write results
        self.outputtable = outputtable
        if outputtable is not None:
            plan.init_temp_table(outputtable, selection, select.solutions[0])

        #self.inputmap = inputmap

    def mytest_repr(self):
        """return a representation of this step suitable for test"""
        try:
            # rely on a monkey patch (cf unittest_querier)
            table = self.plan.tablesinorder[self.table]
            outputtable = self.outputtable and self.plan.tablesinorder[self.outputtable]
        except AttributeError:
            # not monkey patched
            table = self.table
            outputtable = self.outputtable
        sql = self.get_sql().replace(self.table, table)
        return (self.__class__.__name__, sql, outputtable)

    def execute(self):
        """execute this step"""
        self.execute_children()
        sql = self.get_sql()
        if self.outputtable:
            self.plan.create_temp_table(self.outputtable)
            sql = 'INSERT INTO %s %s' % (self.outputtable, sql)
            self.plan.syssource.doexec(self.plan.session, sql, self.plan.args)
        else:
            return self.plan.sqlexec(sql, self.plan.args)

    def get_sql(self):
        self.inputmap = inputmap = self.children[-1].outputmap
        dbhelper=self.plan.syssource.dbhelper
        # get the select clause
        clause = []
        for i, term in enumerate(self.selection):
            try:
                var_name = inputmap[term.as_string()]
            except KeyError:
                var_name = 'C%s' % i
            if isinstance(term, Function):
                # we have to translate some aggregat function
                # (for instance COUNT -> SUM)
                orig_name = term.name
                try:
                    term.name = AGGR_TRANSFORMS[term.name]
                    # backup and reduce children
                    orig_children = term.children
                    term.children = [VariableRef(Variable(var_name))]
                    clause.append(term.accept(self))
                    # restaure the tree XXX necessary?
                    term.name = orig_name
                    term.children = orig_children
                except KeyError:
                    clause.append(var_name)
            else:
                clause.append(var_name)
                for vref in term.iget_nodes(VariableRef):
                    inputmap[vref.name] = var_name
        # XXX handle distinct with non selected sort term
        if self.select.distinct:
            sql = ['SELECT DISTINCT %s' % ', '.join(clause)]
        else:
            sql = ['SELECT %s' % ', '.join(clause)]
        sql.append("FROM %s" % self.table)
        # get the group/having clauses
        if self.select.groupby:
            clause = [inputmap[var.name] for var in self.select.groupby]
            grouped = set(var.name for var in self.select.groupby)
            sql.append('GROUP BY %s' % ', '.join(clause))
        else:
            grouped = None
        if self.select.having:
            clause = [term.accept(self) for term in self.select.having]
            sql.append('HAVING %s' % ', '.join(clause))
        # get the orderby clause
        if self.select.orderby:
            clause = []
            for sortterm in self.select.orderby:
                sqlterm = sortterm.term.accept(self)
                if sortterm.asc:
                    clause.append(sqlterm)
                else:
                    clause.append('%s DESC' % sqlterm)
                if grouped is not None:
                    for vref in sortterm.iget_nodes(VariableRef):
                        if not vref.name in grouped:
                            sql[-1] += ', ' + self.inputmap[vref.name]
                            grouped.add(vref.name)
            sql = dbhelper.sql_add_order_by(' '.join(sql),
                                            clause,
                                            None, False,
                                            self.limit or self.offset)
        else:
            sql = ' '.join(sql)
            clause = None

        sql = dbhelper.sql_add_limit_offset(sql, self.limit, self.offset, clause)
        return sql

    def visit_function(self, function):
        """generate SQL name for a function"""
        try:
            return self.children[0].outputmap[str(function)]
        except KeyError:
            return '%s(%s)' % (function.name,
                               ','.join(c.accept(self) for c in function.children))

    def visit_variableref(self, variableref):
        """get the sql name for a variable reference"""
        try:
            return self.inputmap[variableref.name]
        except KeyError: # XXX duh? explain
            return variableref.variable.name

    def visit_constant(self, constant):
        """generate SQL name for a constant"""
        assert constant.type == 'Int'
        return str(constant.value)


class UnionStep(LimitOffsetMixIn, Step):
    """union results of child in-memory steps (e.g. OneFetchStep / AggrStep)"""

    def execute(self):
        """execute this step"""
        result = []
        limit = olimit = self.limit
        offset = self.offset
        assert offset != 0
        if offset is not None:
            limit = limit + offset
        for step in self.children:
            if limit is not None:
                if offset is None:
                    limit = olimit - len(result)
                step.set_limit_offset(limit, None)
            result_ = step.execute()
            if offset is not None:
                offset, result_ = offset_result(offset, result_)
            result += result_
            if limit is not None:
                if len(result) >= olimit:
                    return result[:olimit]
        return result

    def mytest_repr(self):
        """return a representation of this step suitable for test"""
        return (self.__class__.__name__, self.limit, self.offset)


class IntersectStep(UnionStep):
    """return intersection of results of child in-memory steps (e.g. OneFetchStep / AggrStep)"""

    def execute(self):
        """execute this step"""
        result = set()
        for step in self.children:
            result &= frozenset(step.execute())
        result = list(result)
        if self.offset:
            result = result[self.offset:]
        if self.limit:
            result = result[:self.limit]
        return result


class UnionFetchStep(Step):
    """union results of child steps using temporary tables (e.g. FetchStep)"""

    def execute(self):
        """execute this step"""
        self.execute_children()


__all__ = ('FetchStep', 'AggrStep', 'UnionStep', 'UnionFetchStep', 'IntersectStep')
