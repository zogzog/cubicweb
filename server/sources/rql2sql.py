"""RQL to SQL generator for native sources.


SQL queries optimization
~~~~~~~~~~~~~~~~~~~~~~~~
1. EUser X WHERE X in_group G, G name 'users':

   EUser is the only subject entity type for the in_group relation,
   which allow us to do ::

     SELECT eid_from FROM in_group, EGroup
     WHERE in_group.eid_to = EGroup.eid_from
     AND EGroup.name = 'users'


2. Any X WHERE X nonfinal1 Y, Y nonfinal2 Z

   -> direct join between nonfinal1 and nonfinal2, whatever X,Y, Z (unless
      inlined...)
      
      NOT IMPLEMENTED (and quite hard to implement)

Potential optimization information is collected by the querier, sql generation
is done according to this information


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import threading

from rql import BadRQLQuery, CoercionError
from rql.stmts import Union, Select
from rql.nodes import (SortTerm, VariableRef, Constant, Function, Not,
                       Variable, ColumnAlias, Relation, SubQuery, Exists)

from cubicweb import server
from cubicweb.server.utils import cleanup_solutions

def _new_var(select, varname): 
    newvar = select.get_variable(varname)
    if not 'relations' in newvar.stinfo:
        # not yet initialized
        newvar.prepare_annotation()
        newvar.stinfo['scope'] = select
        newvar._q_invariant = False
    return newvar

def _fill_to_wrap_rel(var, newselect, towrap, schema):
    for rel in var.stinfo['relations'] - var.stinfo['rhsrelations']:
        rschema = schema.rschema(rel.r_type)
        if rschema.inlined:
            towrap.add( (var, rel) )
            for vref in rel.children[1].iget_nodes(VariableRef):
                newivar = _new_var(newselect, vref.name)
                newselect.selection.append(VariableRef(newivar))
                _fill_to_wrap_rel(vref.variable, newselect, towrap, schema)
        elif rschema.is_final():
            towrap.add( (var, rel) )
   
def rewrite_unstable_outer_join(select, solutions, unstable, schema):
    """if some optional variables are unstable, they should be selected in a
    subquery. This function check this and rewrite the rql syntax tree if
    necessary (in place). Return a boolean telling if the tree has been modified
    """
    torewrite = set()
    modified = False
    for varname in tuple(unstable):
        var = select.defined_vars[varname]
        if not var.stinfo['optrelations']:
            continue
        modified = True
        unstable.remove(varname)
        torewrite.add(var)
        newselect = Select()
        newselect.need_distinct = newselect.need_intersect = False
        myunion = Union()
        myunion.append(newselect)
        # extract aliases / selection
        newvar = _new_var(newselect, var.name)
        newselect.selection = [VariableRef(newvar)]
        for avar in select.defined_vars.itervalues():
            if avar.stinfo['attrvar'] is var:
                newavar = _new_var(newselect, avar.name)
                newavar.stinfo['attrvar'] = newvar
                newselect.selection.append(VariableRef(newavar))
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
                newvar.stinfo['optrelations'].add(newrel)
            for vref in newrel.children[1].iget_nodes(VariableRef):
                var = vref.variable
                var.stinfo['relations'].add(newrel)
                var.stinfo['rhsrelations'].add(newrel)
                if rel.optional in ('right', 'both'):
                    var.stinfo['optrelations'].add(newrel)                
        # extract subquery solutions
        solutions = [sol.copy() for sol in solutions]
        cleanup_solutions(newselect, solutions)
        newselect.set_possible_types(solutions)
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
        if not asol in newsolutions:
            newsolutions.append(asol)
    return newsolutions

def remove_unused_solutions(rqlst, solutions, varmap, schema):
    """cleanup solutions: remove solutions where invariant variables are taking
    different types
    """
    newsolutions = _new_solutions(rqlst, solutions)
    existssols = {}
    unstable = set()
    for vname, var in rqlst.defined_vars.iteritems():
        vtype = newsolutions[0][vname]
        if var._q_invariant or vname in varmap:
            for i in xrange(len(newsolutions)-1, 0, -1):
                if vtype != newsolutions[i][vname]:
                    newsolutions.pop(i)
        elif not var.scope is rqlst:
            # move appart variables which are in a EXISTS scope and are variating
            try:
                thisexistssols, thisexistsvars = existssols[var.scope]
            except KeyError:
                thisexistssols = [newsolutions[0]]
                thisexistsvars = set()
                existssols[var.scope] = thisexistssols, thisexistsvars
            for i in xrange(len(newsolutions)-1, 0, -1):
                if vtype != newsolutions[i][vname]:
                    thisexistssols.append(newsolutions.pop(i))
                    thisexistsvars.add(vname)
        else:
            # remember unstable variables
            for i in xrange(1, len(newsolutions)):
                if vtype != newsolutions[i][vname]:
                    unstable.add(vname)
    if len(newsolutions) > 1:
        if rewrite_unstable_outer_join(rqlst, newsolutions, unstable, schema):
            # remove variables extracted to subqueries from solutions
            newsolutions = _new_solutions(rqlst, newsolutions)
    return newsolutions, existssols, unstable

def relation_info(relation):
    lhs, rhs = relation.get_variable_parts()
    try:
        lhs = lhs.variable
        lhsconst = lhs.stinfo['constnode']
    except AttributeError:
        lhsconst = lhs
        lhs = None
    except KeyError:
        lhsconst = None # ColumnAlias
    try:
        rhs = rhs.variable
        rhsconst = rhs.stinfo['constnode']
    except AttributeError:
        rhsconst = rhs
        rhs = None
    except KeyError:
        rhsconst = None # ColumnAlias
    return lhs, lhsconst, rhs, rhsconst

def switch_relation_field(sql, table=''):
    switchedsql = sql.replace(table + '.eid_from', '__eid_from__')
    switchedsql = switchedsql.replace(table + '.eid_to',
                                      table + '.eid_from')
    return switchedsql.replace('__eid_from__', table + '.eid_to')

def sort_term_selection(sorts, selectedidx, rqlst, groups):
    # XXX beurk
    if isinstance(rqlst, list):
        def append(term):
            rqlst.append(term)
    else:
        def append(term):
            rqlst.selection.append(term.copy(rqlst))
    for sortterm in sorts:
        term = sortterm.term
        if not isinstance(term, Constant) and not str(term) in selectedidx:
            selectedidx.append(str(term))
            append(term)
            if groups:
                for vref in term.iget_nodes(VariableRef):
                    if not vref in groups:
                        groups.append(vref)
        
def fix_selection(rqlst, selectedidx, needwrap, sorts, groups, having):
    if sorts:
        sort_term_selection(sorts, selectedidx, rqlst, not needwrap and groups)
    if needwrap:
        if groups:
            for vref in groups:
                if not vref.name in selectedidx:
                    selectedidx.append(vref.name)
                    rqlst.selection.append(vref)
        if having:
            for term in having:
                for vref in term.iget_nodes(VariableRef):
                    if not vref.name in selectedidx:
                        selectedidx.append(vref.name)
                        rqlst.selection.append(vref)

# IGenerator implementation for RQL->SQL ######################################


class StateInfo(object):
    def __init__(self, existssols, unstablevars):
        self.existssols = existssols
        self.unstablevars = unstablevars
        self.subtables = {}
        
    def reset(self, solution):
        """reset some visit variables"""
        self.solution = solution
        self.count = 0
        self.done = set()
        self.tables = self.subtables.copy()
        self.actual_tables = [[]]
        for _, tsql in self.tables.itervalues():
            self.actual_tables[-1].append(tsql)
        self.outer_tables = {}
        self.duplicate_switches = []
        self.attr_vars = {}
        self.aliases = {}
        self.restrictions = []
        self._restr_stack = []
        
    def add_restriction(self, restr):
        if restr:
            self.restrictions.append(restr)
            
    def iter_exists_sols(self, exists):
        if not exists in self.existssols:
            yield 1
            return
        thisexistssols, thisexistsvars = self.existssols[exists]
        origsol = self.solution
        origtables = self.tables
        done = self.done
        for thisexistssol in thisexistssols:
            for vname in self.unstablevars:
                if thisexistssol[vname] != origsol[vname] and vname in thisexistsvars:
                    break
            else:
                self.tables = origtables.copy()
                self.solution = thisexistssol
                yield 1
                # cleanup self.done from stuff specific to exists
                for var in thisexistsvars:
                    if var in done:
                        done.remove(var)
                for rel in exists.iget_nodes(Relation):
                    if rel in done:
                        done.remove(rel)
        self.solution = origsol
        self.tables = origtables

    def push_scope(self):
        self.actual_tables.append([])
        self._restr_stack.append(self.restrictions)
        self.restrictions = []

    def pop_scope(self):
        restrictions = self.restrictions
        self.restrictions = self._restr_stack.pop()
        return restrictions, self.actual_tables.pop()
    
    
class SQLGenerator(object):
    """
    generation of SQL from the fully expanded RQL syntax tree
    SQL is designed to be used with a CubicWeb SQL schema

    Groups and sort are not handled here since they should not be handled at
    this level (see cubicweb.server.querier)
    
    we should not have errors here !

    WARNING: a CubicWebSQLGenerator instance is not thread safe, but generate is
    protected by a lock
    """
    
    def __init__(self, schema, dbms_helper, dbencoding='UTF-8'):
        self.schema = schema
        self.dbms_helper = dbms_helper
        self.dbencoding = dbencoding
        self.keyword_map = {'NOW' : self.dbms_helper.sql_current_timestamp,
                            'TODAY': self.dbms_helper.sql_current_date,
                            }
        if not self.dbms_helper.union_parentheses_support:
            self.union_sql = self.noparen_union_sql
        self._lock = threading.Lock()
        
    def generate(self, union, args=None, varmap=None):
        """return SQL queries and a variable dictionnary from a RQL syntax tree

        :partrqls: a list of couple (rqlst, solutions)
        :args: optional dictionary with values of substitutions used in the query
        :varmap: optional dictionary mapping variable name to a special table
          name, in case the query as to fetch data from temporary tables

        return an sql string and a dictionary with substitutions values
        """
        if args is None:
            args = {}
        if varmap is None:
            varmap =  {}
        self._lock.acquire()
        self._args = args
        self._varmap = varmap
        self._query_attrs = {}
        self._state = None
        try:
            # union query for each rqlst / solution
            sql = self.union_sql(union)
            # we are done
            return sql, self._query_attrs
        finally:
            self._lock.release()

    def union_sql(self, union, needalias=False): # pylint: disable-msg=E0202
        if len(union.children) == 1:
            return self.select_sql(union.children[0], needalias)
        sqls = ('(%s)' % self.select_sql(select, needalias)
                for select in union.children)
        return '\nUNION ALL\n'.join(sqls)

    def noparen_union_sql(self, union, needalias=False):
        # needed for sqlite backend which doesn't like parentheses around
        # union query. This may cause bug in some condition (sort in one of
        # the subquery) but will work in most case
        # see http://www.sqlite.org/cvstrac/tktview?tn=3074
        sqls = (self.select_sql(select, needalias)
                for i, select in enumerate(union.children))
        return '\nUNION ALL\n'.join(sqls)
    
    def select_sql(self, select, needalias=False):
        """return SQL queries and a variable dictionnary from a RQL syntax tree

        :select: a selection statement of the syntax tree (`rql.stmts.Select`)
        :solution: a dictionnary containing variables binding.
          A solution's dictionnary has variable's names as key and variable's
          types as values
        :needwrap: boolean telling if the query will be wrapped in an outer
          query (to deal with aggregat and/or grouping)
        """
        distinct = selectsortterms = select.need_distinct
        sorts = select.orderby
        groups = select.groupby
        having = select.having
        # remember selection, it may be changed and have to be restored
        origselection = select.selection[:]
        # check if the query will have union subquery, if it need sort term
        # selection (union or distinct query) and wrapping (union with groups)
        needwrap = False
        sols = select.solutions
        if len(sols) > 1:
            # remove invariant from solutions
            sols, existssols, unstable = remove_unused_solutions(
                select, sols, self._varmap, self.schema)
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
        state = StateInfo(existssols, unstable)
        # treat subqueries
        self._subqueries_sql(select, state)
        # generate sql for this select node
        selectidx = [str(term) for term in select.selection]
        if needwrap:
            outerselection = origselection[:]
            if sorts and selectsortterms:
                outerselectidx = [str(term) for term in outerselection]
                if distinct:
                    sort_term_selection(sorts, outerselectidx,
                                        outerselection, groups)
            else:
                outerselectidx = selectidx[:]
        fix_selection(select, selectidx, needwrap,
                      selectsortterms and sorts, groups, having)
        if needwrap:
            fselectidx = outerselectidx
            fneedwrap = len(outerselection) != len(origselection)
        else:
            fselectidx = selectidx
            fneedwrap = len(select.selection) != len(origselection)
        if fneedwrap:
            needalias = True
        self._in_wrapping_query = False
        self._state = state
        try:
            sql = self._solutions_sql(select, sols, distinct, needalias or needwrap)
            # generate groups / having before wrapping query selection to
            # get correct column aliases
            self._in_wrapping_query = needwrap
            if groups:
                # no constant should be inserted in GROUP BY else the backend will
                # interpret it as a positional index in the selection
                groups = ','.join(vref.accept(self) for vref in groups
                                  if not isinstance(vref, Constant))
            if having:
                # filter out constants as for GROUP BY
                having = ','.join(vref.accept(self) for vref in having
                                  if not isinstance(vref, Constant))
            if needwrap:
                sql = '%s FROM (%s) AS T1' % (self._selection_sql(outerselection, distinct,
                                                                  needalias),
                                              sql)
            if groups:
                sql += '\nGROUP BY %s' % groups
            if having:
                sql += '\nHAVING %s' % having
            # sort
            if sorts:
                sql += '\nORDER BY %s' % ','.join(self._sortterm_sql(sortterm, 
                                                                     fselectidx)
                                                  for sortterm in sorts)
                if fneedwrap:
                    selection = ['T1.C%s' % i for i in xrange(len(origselection))]
                    sql = 'SELECT %s FROM (%s) AS T1' % (','.join(selection), sql)
        finally:
            select.selection = origselection
        # limit / offset
        limit = select.limit
        if limit:
            sql += '\nLIMIT %s' % limit
        offset = select.offset
        if offset:
            sql += '\nOFFSET %s' % offset
        return sql

    def _subqueries_sql(self, select, state):
        for i, subquery in enumerate(select.with_):
            sql = self.union_sql(subquery.query, needalias=True)
            tablealias = '_T%s' % i
            sql = '(%s) AS %s' % (sql, tablealias)
            state.subtables[tablealias] = (0, sql)
            for vref in subquery.aliases:
                alias = vref.variable
                alias._q_sqltable = tablealias
                alias._q_sql = '%s.C%s' % (tablealias, alias.colnum)

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
            # add required tables
            assert len(self._state.actual_tables) == 1, self._state.actual_tables
            tables = self._state.actual_tables[-1]
            if tables:
                # sort for test predictability
                sql.insert(1, 'FROM %s' % ', '.join(sorted(tables)))
            elif self._state.restrictions and self.dbms_helper.needs_from_clause:
                sql.insert(1, 'FROM (SELECT 1) AS _T')
            sqls.append('\n'.join(sql))
        if select.need_intersect:
            # XXX use getattr for lgc bw compat, remove once 0.37.3 is out
            if distinct or not getattr(self.dbms_helper, 'intersect_all_support', True):
                return '\nINTERSECT\n'.join(sqls)
            else:
                return '\nINTERSECT ALL\n'.join(sqls)
        elif distinct:
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
            sqlterm = str(selectidx.index(str(term)) + 1)
        except ValueError:
            # Constant node or non selected term
            sqlterm = str(term.accept(self))
        if sortterm.asc:
            return sqlterm
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
        self._state.push_scope()
        csql = node.children[0].accept(self)
        sqls, tables = self._state.pop_scope()
        if node in self._state.done or not csql:
            # already processed or no sql generated by children
            self._state.actual_tables[-1] += tables
            self._state.restrictions += sqls
            return csql
        if isinstance(node.children[0], Exists):
            assert not sqls, (sqls, str(node.stmt))
            assert not tables, (tables, str(node.stmt))
            return 'NOT %s' % csql
        sqls.append(csql)
        if tables:
            select = 'SELECT 1 FROM %s' % ','.join(tables)
        else:
            select = 'SELECT 1'
        if sqls:
            sql = 'NOT EXISTS(%s WHERE %s)' % (select, ' AND '.join(sqls))
        else:
            sql = 'NOT EXISTS(%s)' % select
        return sql

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
        self._state.push_scope()
        restriction = exists.children[0].accept(self)
        restrictions, tables = self._state.pop_scope()
        if restriction:
            restrictions.append(restriction)
        restriction = ' AND '.join(restrictions)
        if not restriction:
            return ''
        if not tables:
            # XXX could leave surrounding EXISTS() in this case no?
            sql = 'SELECT 1 WHERE %s' % restriction 
        else:
            sql = 'SELECT 1 FROM %s WHERE %s' % (', '.join(tables), restriction)
        return sql

    
    def visit_relation(self, relation):
        """generate SQL for a relation"""
        rtype = relation.r_type
        # don't care of type constraint statement (i.e. relation_type = 'is')
        if relation.is_types_restriction():
            return ''
        lhs, rhs = relation.get_parts()
        rschema = self.schema.rschema(rtype)
        if rschema.is_final():
            if rtype == 'eid' and lhs.variable._q_invariant and \
                   lhs.variable.stinfo['constnode']:
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
                if relation.neged(strict=True):
                    self._state.done.add(relation.parent)
                    sql = 'NOT (%s)' % sql
        else:
            if rtype == 'is' and rhs.operator == 'IS':
                # special case "C is NULL"
                if lhs.name in self._varmap:
                    lhssql = self._varmap[lhs.name]
                else:
                    lhssql = lhs.accept(self)
                return '%s%s' % (lhssql, rhs.accept(self))
            if '%s.%s' % (lhs, relation.r_type) in self._varmap:
                # relation has already been processed by a previous step
                return
            if relation.optional:
                # check it has not already been treaten (to get necessary
                # information to add an outer join condition)
                if relation in self._state.done:
                    return
                # OPTIONAL relation, generate a left|right outer join
                sql = self._visit_outer_join_relation(relation, rschema)
            elif rschema.inlined:
                sql = self._visit_inlined_relation(relation)
#             elif isinstance(relation.parent, Not):
#                 self._state.done.add(relation.parent)
#                 # NOT relation
#                 sql = self._visit_not_relation(relation, rschema)
            else:
                # regular (non final) relation
                sql = self._visit_relation(relation, rschema)
        return sql

    def _visit_inlined_relation(self, relation):
        lhsvar, _, rhsvar, rhsconst = relation_info(relation)
        # we are sure here to have a lhsvar
        assert lhsvar is not None
        lhssql = self._inlined_var_sql(lhsvar, relation.r_type)
        if isinstance(relation.parent, Not):
            self._state.done.add(relation.parent)
            sql = "%s IS NULL" % lhssql
            if rhsvar is not None and not rhsvar._q_invariant:
                sql = '(%s OR %s!=%s)' % (sql, lhssql, rhsvar.accept(self))
            return sql
        if rhsconst is not None:
            return '%s=%s' % (lhssql, rhsconst.accept(self))
        if isinstance(rhsvar, Variable) and not rhsvar.name in self._varmap:
            # if the rhs variable is only linked to this relation, this mean we
            # only want the relation to exists, eg NOT NULL in case of inlined
            # relation
            if len(rhsvar.stinfo['relations']) == 1 and rhsvar._q_invariant:
                return '%s IS NOT NULL' % lhssql
            if rhsvar._q_invariant:
                return self._extra_join_sql(relation, lhssql, rhsvar)
        return '%s=%s' % (lhssql, rhsvar.accept(self))

    def _process_relation_term(self, relation, rid, termvar, termconst, relfield):
        if termconst or isinstance(termvar, ColumnAlias) or not termvar._q_invariant:
            termsql = termconst and termconst.accept(self) or termvar.accept(self)
            yield '%s.%s=%s' % (rid, relfield, termsql)
        elif termvar._q_invariant:
            # if the variable is mapped, generate restriction anyway
            if termvar.name in self._varmap:
                termsql = termvar.accept(self)
                yield '%s.%s=%s' % (rid, relfield, termsql)
            extrajoin = self._extra_join_sql(relation, '%s.%s' % (rid, relfield), termvar)
            if extrajoin:
                yield extrajoin
        
    def _visit_relation(self, relation, rschema):
        """generate SQL for a relation

        implements optimization 1.
        """
        if relation.r_type == 'identity':
            # special case "X identity Y"
            lhs, rhs = relation.get_parts()
            if isinstance(relation.parent, Not):
                self._state.done.add(relation.parent)
                return 'NOT %s%s' % (lhs.accept(self), rhs.accept(self))
            return '%s%s' % (lhs.accept(self), rhs.accept(self))
        lhsvar, lhsconst, rhsvar, rhsconst = relation_info(relation)
        rid = self._relation_table(relation)
        sqls = []
        sqls += self._process_relation_term(relation, rid, lhsvar, lhsconst, 'eid_from')
        sqls += self._process_relation_term(relation, rid, rhsvar, rhsconst, 'eid_to')
        sql = ' AND '.join(sqls)
        if rschema.symetric:
            sql = '(%s OR %s)' % (sql, switch_relation_field(sql))
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
        lhsvar, lhsconst, rhsvar, rhsconst = relation_info(relation)
        if relation.optional == 'right':
            joinattr, restrattr = 'eid_from', 'eid_to'
        else:
            lhsvar, rhsvar = rhsvar, lhsvar
            lhsconst, rhsconst = rhsconst, lhsconst
            joinattr, restrattr = 'eid_to', 'eid_from'
        if relation.optional == 'both':
            outertype = 'FULL'
        else:
            outertype = 'LEFT'
        if rschema.inlined or relation.r_type == 'identity':
            self._state.done.add(relation)
            t1 = self._var_table(lhsvar)
            if relation.r_type == 'identity':
                attr = 'eid'
            else:
                attr = relation.r_type
            # reset lhs/rhs, we need the initial order now
            lhs, rhs = relation.get_variable_parts()
            if '%s.%s' % (lhs.name, attr) in self._varmap:
                lhssql = self._varmap['%s.%s' % (lhs.name, attr)]
            else:
                lhssql = '%s.%s' % (self._var_table(lhs.variable), attr)
            if not rhsvar is None:
                t2 = self._var_table(rhsvar)
                if t2 is None:
                    if rhsconst is not None:
                        # inlined relation with invariant as rhs
                        condition = '%s=%s' % (lhssql, rhsconst.accept(self))
                        if relation.r_type != 'identity':
                            condition = '(%s OR %s IS NULL)' % (condition, lhssql)
                        if not lhsvar.stinfo['optrelations']:
                            return condition
                        self.add_outer_join_condition(lhsvar, t1, condition)
                    return
            else:
                condition = '%s=%s' % (lhssql, rhsconst.accept(self))
                self.add_outer_join_condition(lhsvar, t1, condition)
            join = '%s OUTER JOIN %s ON (%s=%s)' % (
                outertype, self._state.tables[t2][1], lhssql, rhs.accept(self))
            self.replace_tables_by_outer_join(join, t1, t2)
            return ''
        lhssql = lhsconst and lhsconst.accept(self) or lhsvar.accept(self)
        rhssql = rhsconst and rhsconst.accept(self) or rhsvar.accept(self)
        rid = self._relation_table(relation)
        if not lhsvar:
            join = ''
            toreplace = []
            maintable = rid
        else:
            join = '%s OUTER JOIN %s ON (%s.%s=%s' % (
                outertype, self._state.tables[rid][1], rid, joinattr, lhssql)
            toreplace = [rid]
            maintable = self._var_table(lhsvar)
            if rhsconst:
                join += ' AND %s.%s=%s)' % (rid, restrattr, rhssql)
            else:
                join += ')'
        if not rhsconst:
            rhstable = rhsvar._q_sqltable
            if rhstable:
                assert rhstable is not None, rhsvar
                join += ' %s OUTER JOIN %s ON (%s.%s=%s)' % (
                    outertype, self._state.tables[rhstable][1], rid, restrattr, rhssql)
                toreplace.append(rhstable)
        self.replace_tables_by_outer_join(join, maintable, *toreplace)
        return ''

    def _visit_var_attr_relation(self, relation, rhs_vars):
        """visit an attribute relation with variable(s) in the RHS

        attribute variables are used either in the selection or for
        unification (eg X attr1 A, Y attr2 A). In case of selection,
        nothing to do here.
        """
        contextrels = {}
        attrvars = self._state.attr_vars
        for var in rhs_vars:
            try:
                contextrels[var.name] = attrvars[var.name]
            except KeyError:
                attrvars[var.name] = relation
        if not contextrels:
            relation.children[1].accept(self, contextrels)
            return ''
        # at least one variable is already in attr_vars, this means we have to
        # generate unification expression
        lhssql = self._inlined_var_sql(relation.children[0].variable,
                                       relation.r_type)
        return '%s%s' % (lhssql, relation.children[1].accept(self, contextrels))
    
    def _visit_attribute_relation(self, relation):
        """generate SQL for an attribute relation"""
        lhs, rhs = relation.get_parts()
        rhssql = rhs.accept(self)
        table = self._var_table(lhs.variable)
        if table is None:
            assert relation.r_type == 'eid'
            lhssql = lhs.accept(self)
        else:
            try:
                lhssql = self._varmap['%s.%s' % (lhs.name, relation.r_type)]
            except KeyError:
                lhssql = '%s.%s' % (table, relation.r_type)
        try:
            if relation._q_needcast == 'TODAY':
                sql = 'DATE(%s)%s' % (lhssql, rhssql)
            # XXX which cast function should be used
            #elif relation._q_needcast == 'NOW':
            #    sql = 'TIMESTAMP(%s)%s' % (lhssql, rhssql)
            else:
                sql = '%s%s' % (lhssql, rhssql)
        except AttributeError:
            sql = '%s%s' % (lhssql, rhssql)
        if lhs.variable.stinfo['optrelations']:
            self.add_outer_join_condition(lhs.variable, table, sql)
        else:
            return sql

    def _visit_has_text_relation(self, relation):
        """generate SQL for a has_text relation"""
        lhs, rhs = relation.get_parts()
        const = rhs.children[0]
        alias = self._fti_table(relation)
        jointo = lhs.accept(self)
        restriction = ''
        lhsvar = lhs.variable
        me_is_principal = lhsvar.stinfo.get('principal') is relation
        if me_is_principal:
            if not lhsvar.stinfo['typerels']:
                # the variable is using the fti table, no join needed
                jointo = None
            elif not lhsvar.name in self._varmap:
                # join on entities instead of etype's table to get result for
                # external entities on multisources configurations
                ealias = lhsvar._q_sqltable = lhsvar.name
                jointo = lhsvar._q_sql = '%s.eid' % ealias
                self.add_table('entities AS %s' % ealias, ealias)
                if not lhsvar._q_invariant or len(lhsvar.stinfo['possibletypes']) == 1:
                    restriction = " AND %s.type='%s'" % (ealias, self._state.solution[lhs.name])
                else:
                    etypes = ','.join("'%s'" % etype for etype in lhsvar.stinfo['possibletypes'])
                    restriction = " AND %s.type IN (%s)" % (ealias, etypes)
        if isinstance(relation.parent, Not):
            self._state.done.add(relation.parent)
            not_ = True
        else:
            not_ = False
        return self.dbms_helper.fti_restriction_sql(alias, const.eval(self._args),
                                                    jointo, not_) + restriction
        
    def visit_comparison(self, cmp, contextrels=None):
        """generate SQL for a comparaison"""
        if len(cmp.children) == 2:
            lhs, rhs = cmp.children
        else:
            lhs = None
            rhs = cmp.children[0]
        operator = cmp.operator
        if operator in ('IS', 'LIKE', 'ILIKE'):
            if operator == 'ILIKE' and not self.dbms_helper.ilike_support:
                operator = ' LIKE '
            else:
                operator = ' %s ' % operator
        elif isinstance(rhs, Function) and rhs.name == 'IN':
            assert operator == '='
            operator = ' '
        if lhs is None:
            return '%s%s'% (operator, rhs.accept(self, contextrels))
        return '%s%s%s'% (lhs.accept(self, contextrels), operator,
                          rhs.accept(self, contextrels))
            
    def visit_mathexpression(self, mexpr, contextrels=None):
        """generate SQL for a mathematic expression"""
        lhs, rhs = mexpr.get_parts()
        # check for string concatenation
        operator = mexpr.operator
        try:
            if mexpr.operator == '+' and mexpr.get_type(self._state.solution, self._args) == 'String':
                operator = '||'
        except CoercionError:
            pass
        return '(%s %s %s)'% (lhs.accept(self, contextrels), operator,
                              rhs.accept(self, contextrels))
        
    def visit_function(self, func, contextrels=None):
        """generate SQL name for a function"""
        # function_description will check function is supported by the backend
        self.dbms_helper.function_description(func.name) 
        return '%s(%s)' % (func.name, ', '.join(c.accept(self, contextrels)
                                                for c in func.children))

    def visit_constant(self, constant, contextrels=None):
        """generate SQL name for a constant"""
        value = constant.value
        if constant.type is None:
            return 'NULL'
        if constant.type == 'Int' and  isinstance(constant.parent, SortTerm):
            return constant.value
        if constant.type in ('Date', 'Datetime'):
            rel = constant.relation()
            if rel is not None:
                rel._q_needcast = value
            return self.keyword_map[value]()
        if constant.type == 'Substitute':
            _id = constant.value
            if isinstance(_id, unicode):
                _id = _id.encode()
        else:
            _id = str(id(constant)).replace('-', '', 1)
            if isinstance(value, unicode):
                value = value.encode(self.dbencoding)
            self._query_attrs[_id] = value
        return '%%(%s)s' % _id
        
    def visit_variableref(self, variableref, contextrels=None):
        """get the sql name for a variable reference"""
        # use accept, .variable may be a variable or a columnalias
        return variableref.variable.accept(self, contextrels)

    def visit_columnalias(self, colalias, contextrels=None):
        """get the sql name for a subquery column alias"""
        if colalias.name in self._varmap:
            sql = self._varmap[colalias.name]
            table = sql.split('.', 1)[0]
            colalias._q_sqltable = table
            colalias._q_sql = sql
            self.add_table(table)
            return sql
        return colalias._q_sql
    
    def visit_variable(self, variable, contextrels=None):
        """get the table name and sql string for a variable"""
        if contextrels is None and variable.name in self._state.done:
            if self._in_wrapping_query:
                return 'T1.%s' % self._state.aliases[variable.name]
            return variable._q_sql
        self._state.done.add(variable.name)
        vtablename = None
        if contextrels is None and variable.name in self._varmap:
            sql, vtablename = self._var_info(variable)            
        elif variable.stinfo['attrvar']:
            # attribute variable (systematically used in rhs of final
            # relation(s)), get table name and sql from any rhs relation
            sql = self._linked_var_sql(variable, contextrels)
        elif variable._q_invariant:
            # since variable is invariant, we know we won't found final relation
            principal = variable.stinfo['principal']
            if principal is None:
                vtablename = variable.name
                self.add_table('entities AS %s' % variable.name, vtablename)
                sql = '%s.eid' % vtablename
                if variable.stinfo['typerels']:
                    # add additional restriction on entities.type column
                    pts = variable.stinfo['possibletypes']
                    if len(pts) == 1:
                        etype = iter(variable.stinfo['possibletypes']).next()
                        restr = "%s.type='%s'" % (vtablename, etype)
                    else:
                        etypes = ','.join("'%s'" % et for et in pts)
                        restr = '%s.type IN (%s)' % (vtablename, etypes)
                    self._state.add_restriction(restr)
            elif principal.r_type == 'has_text':
                sql = '%s.%s' % (self._fti_table(principal),
                                 self.dbms_helper.fti_uid_attr)
            elif principal in variable.stinfo['rhsrelations']:
                if self.schema.rschema(principal.r_type).inlined:
                    sql = self._linked_var_sql(variable, contextrels)
                else:
                    sql = '%s.eid_to' % self._relation_table(principal)
            else:
                sql = '%s.eid_from' % self._relation_table(principal)
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
                # need a predicable result for tests
                return '%s=%s' % tuple(sorted((sql, var.accept(self))))
        except KeyError:
            # no principal defined, relation is necessarily the principal and
            # so nothing to return here
            pass
        return ''
    
    def _var_info(self, var):
        # if current var or one of its attribute is selected , it *must*
        # appear in the toplevel's FROM even if we're currently visiting
        # a EXISTS node
        if var.sqlscope is var.stmt:
            scope = 0
        else:
            scope = -1
        try:
            sql = self._varmap[var.name]
            table = sql.split('.', 1)[0]
            if scope == -1:
                scope = self._varmap_table_scope(var.stmt, table)
            self.add_table(table, scope=scope)
        except KeyError:
            etype = self._state.solution[var.name]
            # XXX this check should be moved in rql.stcheck
            if self.schema.eschema(etype).is_final():
                raise BadRQLQuery(var.stmt.root)
            table = var.name
            sql = '%s.eid' % table
            self.add_table('%s AS %s' % (etype, table), table, scope=scope)
        return sql, table
    
    def _inlined_var_sql(self, var, rtype):
        try:
            sql = self._varmap['%s.%s' % (var.name, rtype)]
            scope = var.sqlscope is var.stmt and 0 or -1
            self.add_table(sql.split('.', 1)[0], scope=scope)
        except KeyError:
            sql = '%s.%s' % (self._var_table(var), rtype)
            #self._state.done.add(var.name)
        return sql
        
    def _linked_var_sql(self, variable, contextrels=None):
        if contextrels is None:
            try:
                return self._varmap[variable.name]            
            except KeyError:
                pass
        rel = (contextrels and contextrels.get(variable.name) or 
               variable.stinfo.get('principal') or
               iter(variable.stinfo['rhsrelations']).next())
        linkedvar = rel.children[0].variable
        if rel.r_type == 'eid':
            return linkedvar.accept(self)
        if isinstance(linkedvar, ColumnAlias):
            raise BadRQLQuery('variable %s should be selected by the subquery'
                              % variable.name)
        try:
            sql = self._varmap['%s.%s' % (linkedvar.name, rel.r_type)]
        except KeyError:
            linkedvar.accept(self)            
            sql = '%s.%s' % (linkedvar._q_sqltable, rel.r_type)
        return sql

    # tables handling #########################################################

    def alias_and_add_table(self, tablename):
        alias = '%s%s' % (tablename, self._state.count)
        self._state.count += 1
        self.add_table('%s AS %s' % (tablename, alias), alias)
        return alias
        
    def add_table(self, table, key=None, scope=-1):
        if key is None:
            key = table
        if key in self._state.tables:
            return
        self._state.tables[key] = (len(self._state.actual_tables) - 1, table)
        self._state.actual_tables[scope].append(table)
    
    def replace_tables_by_outer_join(self, substitute, lefttable, *tables):
        for table in tables:
            try:
                scope, alias = self._state.tables[table]
                self._state.actual_tables[scope].remove(alias)
            except ValueError: # huum, not sure about what should be done here
                msg = "%s already used in an outer join, don't know what to do!"
                raise Exception(msg % table)
        try:
            tablealias = self._state.outer_tables[lefttable]
            actualtables = self._state.actual_tables[-1]
        except KeyError:
            tablescope, tablealias = self._state.tables[lefttable]
            actualtables = self._state.actual_tables[tablescope]
        outerjoin = '%s %s' % (tablealias, substitute)
        self._update_outer_tables(lefttable, actualtables, tablealias, outerjoin)
        for table in tables:
            self._state.outer_tables[table] = outerjoin

    def add_outer_join_condition(self, var, table, condition):
        try:
            tablealias = self._state.outer_tables[table]
            actualtables = self._state.actual_tables[-1]
        except KeyError:
            for rel in var.stinfo['optrelations']:
                self.visit_relation(rel)
            assert self._state.outer_tables
            self.add_outer_join_condition(var, table, condition)
            return
        before, after = tablealias.split(' AS %s ' % table, 1)
        beforep, afterp = after.split(')', 1)
        outerjoin = '%s AS %s %s AND %s) %s' % (before, table, beforep,
                                                condition, afterp)
        self._update_outer_tables(table, actualtables, tablealias, outerjoin)

    def _update_outer_tables(self, table, actualtables, oldalias, newalias):
        actualtables.remove(oldalias)
        actualtables.append(newalias)
        # some tables which have already been used as outer table and replaced
        # by <oldalias> may not be reused here, though their associated value
        # in the outer_tables dict has to be updated as well
        for table, outerexpr in self._state.outer_tables.iteritems():
            if outerexpr == oldalias:
                self._state.outer_tables[table] = newalias
        self._state.outer_tables[table] = newalias        
        
    def _var_table(self, var):
        var.accept(self)#.visit_variable(var)
        return var._q_sqltable

    def _relation_table(self, relation):
        """return the table alias used by the given relation"""
        if relation in self._state.done:
            return relation._q_sqltable
        assert not self.schema.rschema(relation.r_type).is_final(), relation.r_type
        rid = 'rel_%s%s' % (relation.r_type, self._state.count)
        # relation's table is belonging to the root scope if it is the principal
        # table of one of it's variable and if that variable belong's to parent 
        # scope
        for varref in relation.iget_nodes(VariableRef):
            var = varref.variable
            if isinstance(var, ColumnAlias):
                scope = 0
                break
            # XXX may have a principal without being invariant for this generation,
            #     not sure this is a pb or not
            if var.stinfo.get('principal') is relation and var.sqlscope is var.stmt:
                scope = 0
                break
        else:
            scope = -1
        self._state.count += 1
        self.add_table('%s_relation AS %s' % (relation.r_type, rid), rid, scope=scope)
        relation._q_sqltable = rid
        self._state.done.add(relation)
        return rid
    
    def _fti_table(self, relation):
        if relation in self._state.done:
            try:
                return relation._q_sqltable
            except AttributeError:
                pass
        self._state.done.add(relation)
        alias = self.alias_and_add_table(self.dbms_helper.fti_table)
        relation._q_sqltable = alias
        return alias
        
    def _varmap_table_scope(self, select, table):
        """since a varmap table may be used for multiple variable, its scope is
        the most outer scope of each variables
        """
        scope = -1
        for varname, alias in self._varmap.iteritems():
            # check '.' in varname since there are 'X.attribute' keys in varmap
            if not '.' in varname and alias.split('.', 1)[0] == table:
                if select.defined_vars[varname].sqlscope is select:
                    return 0
        return scope
