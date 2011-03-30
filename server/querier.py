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
"""Helper classes to execute RQL queries on a set of sources, performing
security checking and data aggregation.
"""

from __future__ import with_statement

__docformat__ = "restructuredtext en"

from itertools import repeat

from logilab.common.cache import Cache
from logilab.common.compat import any
from rql import RQLSyntaxError
from rql.stmts import Union, Select
from rql.nodes import (Relation, VariableRef, Constant, SubQuery, Function,
                       Exists, Not)

from cubicweb import ValidationError, Unauthorized, QueryError, UnknownEid
from cubicweb import server, typed_eid
from cubicweb.rset import ResultSet

from cubicweb.server.utils import cleanup_solutions
from cubicweb.server.rqlannotation import SQLGenAnnotator, set_qdata
from cubicweb.server.ssplanner import READ_ONLY_RTYPES, add_types_restriction
from cubicweb.server.edition import EditedEntity
from cubicweb.server.session import security_enabled

def empty_rset(rql, args, rqlst=None):
    """build an empty result set object"""
    return ResultSet([], rql, args, rqlst=rqlst)

def update_varmap(varmap, selected, table):
    """return a sql schema to store RQL query result"""
    for i, term in enumerate(selected):
        key = term.as_string()
        value = '%s.C%s' % (table, i)
        if varmap.get(key, value) != value:
            raise Exception('variable name conflict on %s: got %s / %s'
                            % (key, value, varmap))
        varmap[key] = value

# permission utilities ########################################################

def check_no_password_selected(rqlst):
    """check that Password entities are not selected"""
    for solution in rqlst.solutions:
        if 'Password' in solution.itervalues():
            raise Unauthorized('Password selection is not allowed')

def term_etype(session, term, solution, args):
    """return the entity type for the given term (a VariableRef or a Constant
    node)
    """
    try:
        return solution[term.name]
    except AttributeError:
        return session.describe(term.eval(args))[0]

def check_read_access(session, rqlst, solution, args):
    """check that the given user has credentials to access data read the
    query

    return a dict defining necessary local checks (due to use of rql expression
    in the schema), keys are variable names and values associated rql expression
    for the associated variable with the given solution
    """
    # use `term_etype` since we've to deal with rewritten constants here,
    # when used as an external source by another repository.
    # XXX what about local read security w/ those rewritten constants...
    schema = session.repo.schema
    if rqlst.where is not None:
        for rel in rqlst.where.iget_nodes(Relation):
            # XXX has_text may have specific perm ?
            if rel.r_type in READ_ONLY_RTYPES:
                continue
            rschema = schema.rschema(rel.r_type)
            if rschema.final:
                eschema = schema.eschema(term_etype(session, rel.children[0],
                                                    solution, args))
                rdef = eschema.rdef(rschema)
            else:
                rdef = rschema.rdef(term_etype(session, rel.children[0],
                                               solution, args),
                                    term_etype(session, rel.children[1].children[0],
                                               solution, args))
            if not session.user.matching_groups(rdef.get_groups('read')):
                # XXX rqlexpr not allowed
                raise Unauthorized('read', rel.r_type)
    localchecks = {}
    # iterate on defined_vars and not on solutions to ignore column aliases
    for varname in rqlst.defined_vars:
        eschema = schema.eschema(solution[varname])
        if eschema.final:
            continue
        if not session.user.matching_groups(eschema.get_groups('read')):
            erqlexprs = eschema.get_rqlexprs('read')
            if not erqlexprs:
                ex = Unauthorized('read', solution[varname])
                ex.var = varname
                raise ex
            # don't insert security on variable only referenced by 'NOT X relation Y' or
            # 'NOT EXISTS(X relation Y)'
            varinfo = rqlst.defined_vars[varname].stinfo
            if varinfo['selected'] or (
                len([r for r in varinfo['relations']
                     if (not schema.rschema(r.r_type).final
                         and ((isinstance(r.parent, Exists) and r.parent.neged(strict=True))
                              or isinstance(r.parent, Not)))])
                != len(varinfo['relations'])):
                localchecks[varname] = erqlexprs
    return localchecks

def add_noinvariant(noinvariant, restricted, select, nbtrees):
    # a variable can actually be invariant if it has not been restricted for
    # security reason or if security assertion hasn't modified the possible
    # solutions for the query
    if nbtrees != 1:
        for vname in restricted:
            try:
                noinvariant.add(select.defined_vars[vname])
            except KeyError:
                # this is an alias
                continue
    else:
        for vname in restricted:
            try:
                var = select.defined_vars[vname]
            except KeyError:
                # this is an alias
                continue
            if len(var.stinfo['possibletypes']) != 1:
                noinvariant.add(var)

def _expand_selection(terms, selected, aliases, select, newselect):
    for term in terms:
        for vref in term.iget_nodes(VariableRef):
            if not vref.name in selected:
                select.append_selected(vref)
                colalias = newselect.get_variable(vref.name, len(aliases))
                aliases.append(VariableRef(colalias))
                selected.add(vref.name)

# Plans #######################################################################

class ExecutionPlan(object):
    """the execution model of a rql query, composed of querier steps"""

    def __init__(self, querier, rqlst, args, session):
        # original rql syntax tree
        self.rqlst = rqlst
        self.args = args or {}
        # session executing the query
        self.session = session
        # quick reference to the system source
        self.syssource = session.pool.source('system')
        # execution steps
        self.steps = []
        # index of temporary tables created during execution
        self.temp_tables = {}
        # various resource accesors
        self.querier = querier
        self.schema = querier.schema
        self.sqlannotate = querier.sqlgen_annotate
        self.rqlhelper = session.vreg.rqlhelper

    def annotate_rqlst(self):
        if not self.rqlst.annotated:
            self.rqlhelper.annotate(self.rqlst)

    def add_step(self, step):
        """add a step to the plan"""
        self.steps.append(step)

    def clean(self):
        """remove temporary tables"""
        self.syssource.clean_temp_data(self.session, self.temp_tables)

    def sqlexec(self, sql, args=None):
        return self.syssource.sqlexec(self.session, sql, args)

    def execute(self):
        """execute a plan and return resulting rows"""
        try:
            for step in self.steps:
                result = step.execute()
            # the latest executed step contains the full query result
            return result
        finally:
            self.clean()

    def make_temp_table_name(self, table):
        """
        return a temp table name according to db backend
        """
        return self.syssource.make_temp_table_name(table)


    def init_temp_table(self, table, selected, sol):
        """initialize sql schema and variable map for a temporary table which
        will be used to store result for the given rqlst
        """
        try:
            outputmap, sqlschema, _ = self.temp_tables[table]
            update_varmap(outputmap, selected, table)
        except KeyError:
            sqlschema, outputmap = self.syssource.temp_table_def(selected, sol,
                                                                 table)
            self.temp_tables[table] = [outputmap, sqlschema, False]
        return outputmap

    def create_temp_table(self, table):
        """create a temporary table to store result for the given rqlst"""
        if not self.temp_tables[table][-1]:
            sqlschema = self.temp_tables[table][1]
            self.syssource.create_temp_table(self.session, table, sqlschema)
            self.temp_tables[table][-1] = True

    def preprocess(self, union, security=True):
        """insert security when necessary then annotate rql st for sql generation

        return rqlst to actually execute
        """
        cached = None
        if security and self.session.read_security:
            # ensure security is turned of when security is inserted,
            # else we may loop for ever...
            if self.session.transaction_data.get('security-rqlst-cache'):
                key = self.cache_key
            else:
                key = None
            if key is not None and key in self.session.transaction_data:
                cachedunion, args = self.session.transaction_data[key]
                union.children[:] = []
                for select in cachedunion.children:
                    union.append(select)
                union.has_text_query = cachedunion.has_text_query
                args.update(self.args)
                self.args = args
                cached = True
            else:
                noinvariant = set()
                with security_enabled(self.session, read=False):
                    self._insert_security(union, noinvariant)
                if key is not None:
                    self.session.transaction_data[key] = (union, self.args)
        else:
            noinvariant = ()
        if cached is None:
            self.rqlhelper.simplify(union)
            self.sqlannotate(union)
            set_qdata(self.schema.rschema, union, noinvariant)
        if union.has_text_query:
            self.cache_key = None

    def _insert_security(self, union, noinvariant):
        for select in union.children[:]:
            for subquery in select.with_:
                self._insert_security(subquery.query, noinvariant)
            localchecks, restricted = self._check_permissions(select)
            if any(localchecks):
                rewrite = self.session.rql_rewriter.rewrite
                nbtrees = len(localchecks)
                myunion = union
                # transform in subquery when len(localchecks)>1 and groups
                if nbtrees > 1 and (select.orderby or select.groupby or
                                    select.having or select.has_aggregat or
                                    select.distinct or
                                    select.limit or select.offset):
                    newselect = Select()
                    # only select variables in subqueries
                    origselection = select.selection
                    select.select_only_variables()
                    select.has_aggregat = False
                    # create subquery first so correct node are used on copy
                    # (eg ColumnAlias instead of Variable)
                    aliases = [VariableRef(newselect.get_variable(vref.name, i))
                               for i, vref in enumerate(select.selection)]
                    selected = set(vref.name for vref in aliases)
                    # now copy original selection and groups
                    for term in origselection:
                        newselect.append_selected(term.copy(newselect))
                    if select.orderby:
                        sortterms = []
                        for sortterm in select.orderby:
                            sortterms.append(sortterm.copy(newselect))
                            for fnode in sortterm.get_nodes(Function):
                                if fnode.name == 'FTIRANK':
                                    # we've to fetch the has_text relation as well
                                    var = fnode.children[0].variable
                                    rel = iter(var.stinfo['ftirels']).next()
                                    assert not rel.ored(), 'unsupported'
                                    newselect.add_restriction(rel.copy(newselect))
                                    # remove relation from the orig select and
                                    # cleanup variable stinfo
                                    rel.parent.remove(rel)
                                    var.stinfo['ftirels'].remove(rel)
                                    var.stinfo['relations'].remove(rel)
                                    # XXX not properly re-annotated after security insertion?
                                    newvar = newselect.get_variable(var.name)
                                    newvar.stinfo.setdefault('ftirels', set()).add(rel)
                                    newvar.stinfo.setdefault('relations', set()).add(rel)
                        newselect.set_orderby(sortterms)
                        _expand_selection(select.orderby, selected, aliases, select, newselect)
                        select.orderby = () # XXX dereference?
                    if select.groupby:
                        newselect.set_groupby([g.copy(newselect) for g in select.groupby])
                        _expand_selection(select.groupby, selected, aliases, select, newselect)
                        select.groupby = () # XXX dereference?
                    if select.having:
                        newselect.set_having([g.copy(newselect) for g in select.having])
                        _expand_selection(select.having, selected, aliases, select, newselect)
                        select.having = () # XXX dereference?
                    if select.limit:
                        newselect.limit = select.limit
                        select.limit = None
                    if select.offset:
                        newselect.offset = select.offset
                        select.offset = 0
                    myunion = Union()
                    newselect.set_with([SubQuery(aliases, myunion)], check=False)
                    newselect.distinct = select.distinct
                    solutions = [sol.copy() for sol in select.solutions]
                    cleanup_solutions(newselect, solutions)
                    newselect.set_possible_types(solutions)
                    # if some solutions doesn't need rewriting, insert original
                    # select as first union subquery
                    if () in localchecks:
                        myunion.append(select)
                    # we're done, replace original select by the new select with
                    # subqueries (more added in the loop below)
                    union.replace(select, newselect)
                elif not () in localchecks:
                    union.remove(select)
                for lcheckdef, lchecksolutions in localchecks.iteritems():
                    if not lcheckdef:
                        continue
                    myrqlst = select.copy(solutions=lchecksolutions)
                    myunion.append(myrqlst)
                    # in-place rewrite + annotation / simplification
                    lcheckdef = [({var: 'X'}, rqlexprs) for var, rqlexprs in lcheckdef]
                    rewrite(myrqlst, lcheckdef, lchecksolutions, self.args)
                    add_noinvariant(noinvariant, restricted, myrqlst, nbtrees)
                if () in localchecks:
                    select.set_possible_types(localchecks[()])
                    add_types_restriction(self.schema, select)
                    add_noinvariant(noinvariant, restricted, select, nbtrees)
                self.rqlhelper.annotate(union)

    def _check_permissions(self, rqlst):
        """return a dict defining "local checks", e.g. RQLExpression defined in
        the schema that should be inserted in the original query

        solutions where a variable has a type which the user can't definitly read
        are removed, else if the user may read it (eg if an rql expression is
        defined for the "read" permission of the related type), the local checks
        dict for the solution is updated

        return a dict with entries for each different local check necessary,
        with associated solutions as value. A local check is defined by a list
        of 2-uple, with variable name as first item and the necessary rql
        expression as second item for each variable which has to be checked.
        So solutions which don't require local checks will be associated to
        the empty tuple key.

        note: rqlst should not have been simplified at this point
        """
        session = self.session
        msgs = []
        neweids = session.transaction_data.get('neweids', ())
        varkwargs = {}
        if not session.transaction_data.get('security-rqlst-cache'):
            for var in rqlst.defined_vars.itervalues():
                if var.stinfo['constnode'] is not None:
                    eid = var.stinfo['constnode'].eval(self.args)
                    varkwargs[var.name] = typed_eid(eid)
        # dictionnary of variables restricted for security reason
        localchecks = {}
        restricted_vars = set()
        newsolutions = []
        for solution in rqlst.solutions:
            try:
                localcheck = check_read_access(session, rqlst, solution, self.args)
            except Unauthorized, ex:
                msg = 'remove %s from solutions since %s has no %s access to %s'
                msg %= (solution, session.user.login, ex.args[0], ex.args[1])
                msgs.append(msg)
                LOGGER.info(msg)
            else:
                newsolutions.append(solution)
                # try to benefit of rqlexpr.check cache for entities which
                # are specified by eid in query'args
                for varname, eid in varkwargs.iteritems():
                    try:
                        rqlexprs = localcheck.pop(varname)
                    except KeyError:
                        continue
                    if eid in neweids:
                        continue
                    for rqlexpr in rqlexprs:
                        if rqlexpr.check(session, eid):
                            break
                    else:
                        raise Unauthorized()
                restricted_vars.update(localcheck)
                localchecks.setdefault(tuple(localcheck.iteritems()), []).append(solution)
        # raise Unautorized exception if the user can't access to any solution
        if not newsolutions:
            raise Unauthorized('\n'.join(msgs))
        if msgs:
            # (else solutions have not been modified)
            rqlst.set_possible_types(newsolutions)
        return localchecks, restricted_vars

    def finalize(self, select, solutions, insertedvars):
        rqlst = Union()
        rqlst.append(select)
        for mainvarname, rschema, newvarname in insertedvars:
            nvartype = str(rschema.objects(solutions[0][mainvarname])[0])
            for sol in solutions:
                sol[newvarname] = nvartype
        select.clean_solutions(solutions)
        add_types_restriction(self.schema, select)
        self.rqlhelper.annotate(rqlst)
        self.preprocess(rqlst, security=False)
        return rqlst


class InsertPlan(ExecutionPlan):
    """an execution model specific to the INSERT rql query
    """

    def __init__(self, querier, rqlst, args, session):
        ExecutionPlan.__init__(self, querier, rqlst, args, session)
        # save originaly selected variable, we may modify this
        # dictionary for substitution (query parameters)
        self.selected = rqlst.selection
        # list of rows of entities definition (ssplanner.EditedEntity)
        self.e_defs = [[]]
        # list of new relation definition (3-uple (from_eid, r_type, to_eid)
        self.r_defs = set()
        # indexes to track entity definitions bound to relation definitions
        self._r_subj_index = {}
        self._r_obj_index = {}
        self._expanded_r_defs = {}

    def add_entity_def(self, edef):
        """add an entity definition to build"""
        self.e_defs[-1].append(edef)

    def add_relation_def(self, rdef):
        """add an relation definition to build"""
        self.r_defs.add(rdef)
        if not isinstance(rdef[0], int):
            self._r_subj_index.setdefault(rdef[0], []).append(rdef)
        if not isinstance(rdef[2], int):
            self._r_obj_index.setdefault(rdef[2], []).append(rdef)

    def substitute_entity_def(self, edef, edefs):
        """substitute an incomplete entity definition by a list of complete
        equivalents

        e.g. on queries such as ::
          INSERT Personne X, Societe Y: X nom N, Y nom 'toto', X travaille Y
          WHERE U login 'admin', U login N

        X will be inserted as many times as U exists, and so the X travaille Y
        relations as to be added as many time as X is inserted
        """
        if not edefs or not self.e_defs:
            # no result, no entity will be created
            self.e_defs = ()
            return
        # first remove the incomplete entity definition
        colidx = self.e_defs[0].index(edef)
        for i, row in enumerate(self.e_defs[:]):
            self.e_defs[i][colidx] = edefs[0]
            samplerow = self.e_defs[i]
            for edef_ in edefs[1:]:
                row = [ed.clone() for i, ed in enumerate(samplerow)
                       if i != colidx]
                row.insert(colidx, edef_)
                self.e_defs.append(row)
        # now, see if this entity def is referenced as subject in some relation
        # definition
        if self._r_subj_index.has_key(edef):
            for rdef in self._r_subj_index[edef]:
                expanded = self._expanded(rdef)
                result = []
                for exp_rdef in expanded:
                    for edef_ in edefs:
                        result.append( (edef_, exp_rdef[1], exp_rdef[2]) )
                self._expanded_r_defs[rdef] = result
        # and finally, see if this entity def is referenced as object in some
        # relation definition
        if self._r_obj_index.has_key(edef):
            for rdef in self._r_obj_index[edef]:
                expanded = self._expanded(rdef)
                result = []
                for exp_rdef in expanded:
                    for edef_ in edefs:
                        result.append( (exp_rdef[0], exp_rdef[1], edef_) )
                self._expanded_r_defs[rdef] = result

    def _expanded(self, rdef):
        """return expanded value for the given relation definition"""
        try:
            return self._expanded_r_defs[rdef]
        except KeyError:
            self.r_defs.remove(rdef)
            return [rdef]

    def relation_defs(self):
        """return the list for relation definitions to insert"""
        for rdefs in self._expanded_r_defs.values():
            for rdef in rdefs:
                yield rdef
        for rdef in self.r_defs:
            yield rdef

    def insert_entity_defs(self):
        """return eids of inserted entities in a suitable form for the resulting
        result set, e.g.:

        e.g. on queries such as ::
          INSERT Personne X, Societe Y: X nom N, Y nom 'toto', X travaille Y
          WHERE U login 'admin', U login N

        if there is two entities matching U, the result set will look like
        [(eidX1, eidY1), (eidX2, eidY2)]
        """
        session = self.session
        repo = session.repo
        results = []
        for row in self.e_defs:
            results.append([repo.glob_add_entity(session, edef)
                            for edef in row])
        return results

    def insert_relation_defs(self):
        session = self.session
        repo = session.repo
        for subj, rtype, obj in self.relation_defs():
            # if a string is given into args instead of an int, we get it here
            if isinstance(subj, basestring):
                subj = typed_eid(subj)
            elif not isinstance(subj, (int, long)):
                subj = subj.entity.eid
            if isinstance(obj, basestring):
                obj = typed_eid(obj)
            elif not isinstance(obj, (int, long)):
                obj = obj.entity.eid
            if repo.schema.rschema(rtype).inlined:
                entity = session.entity_from_eid(subj)
                edited = EditedEntity(entity)
                edited.edited_attribute(rtype, obj)
                repo.glob_update_entity(session, edited)
            else:
                repo.glob_add_relation(session, subj, rtype, obj)


class QuerierHelper(object):
    """helper class to execute rql queries, putting all things together"""

    def __init__(self, repo, schema):
        # system info helper
        self._repo = repo
        # instance schema
        self.set_schema(schema)

    def set_schema(self, schema):
        self.schema = schema
        repo = self._repo
        # rql st and solution cache.
        self._rql_cache = Cache(repo.config['rql-cache-size'])
        # rql cache key cache. Don't bother using a Cache instance: we should
        # have a limited number of queries in there, since there are no entries
        # in this cache for user queries (which have no args)
        self._rql_ck_cache = {}
        # some cache usage stats
        self.cache_hit, self.cache_miss = 0, 0
        # rql parsing / analysing helper
        self.solutions = repo.vreg.solutions
        rqlhelper = repo.vreg.rqlhelper
        # set backend on the rql helper, will be used for function checking
        rqlhelper.backend = repo.config.sources()['system']['db-driver']
        self._parse = rqlhelper.parse
        self._annotate = rqlhelper.annotate
        # rql planner
        if len(repo.sources) < 2:
            from cubicweb.server.ssplanner import SSPlanner
            self._planner = SSPlanner(schema, rqlhelper)
        else:
            from cubicweb.server.msplanner import MSPlanner
            self._planner = MSPlanner(schema, rqlhelper)
        # sql generation annotator
        self.sqlgen_annotate = SQLGenAnnotator(schema).annotate

    def set_planner(self):
        if len(self._repo.sources) < 2:
            from cubicweb.server.ssplanner import SSPlanner
            self._planner = SSPlanner(self.schema, self._repo.vreg.rqlhelper)
        else:
            from cubicweb.server.msplanner import MSPlanner
            self._planner = MSPlanner(self.schema, self._repo.vreg.rqlhelper)

    def parse(self, rql, annotate=False):
        """return a rql syntax tree for the given rql"""
        try:
            return self._parse(unicode(rql), annotate=annotate)
        except UnicodeError:
            raise RQLSyntaxError(rql)

    def plan_factory(self, rqlst, args, session):
        """create an execution plan for an INSERT RQL query"""
        if rqlst.TYPE == 'insert':
            return InsertPlan(self, rqlst, args, session)
        return ExecutionPlan(self, rqlst, args, session)

    def execute(self, session, rql, args=None, build_descr=True):
        """execute a rql query, return resulting rows and their description in
        a `ResultSet` object

        * `rql` should be an Unicode string or a plain ASCII string
        * `args` the optional parameters dictionary associated to the query
        * `build_descr` is a boolean flag indicating if the description should
          be built on select queries (if false, the description will be en empty
          list)

        on INSERT queries, there will be one row with the eid of each inserted
        entity

        result for DELETE and SET queries is undefined yet

        to maximize the rql parsing/analyzing cache performance, you should
        always use substitute arguments in queries (i.e. avoid query such as
        'Any X WHERE X eid 123'!)
        """
        if server.DEBUG & (server.DBG_RQL | server.DBG_SQL):
            if server.DEBUG & (server.DBG_MORE | server.DBG_SQL):
                print '*'*80
            print 'querier input', rql, args
        # parse the query and binds variables
        cachekey = rql
        try:
            if args:
                # search for named args in query which are eids (hence
                # influencing query's solutions)
                eidkeys = self._rql_ck_cache[rql]
                if eidkeys:
                    # if there are some, we need a better cache key, eg (rql +
                    # entity type of each eid)
                    try:
                        cachekey = self._repo.querier_cache_key(session, rql,
                                                                args, eidkeys)
                    except UnknownEid:
                        # we want queries such as "Any X WHERE X eid 9999"
                        # return an empty result instead of raising UnknownEid
                        return empty_rset(rql, args)
            rqlst = self._rql_cache[cachekey]
            self.cache_hit += 1
        except KeyError:
            self.cache_miss += 1
            rqlst = self.parse(rql)
            try:
                # compute solutions for rqlst and return named args in query
                # which are eids. Notice that if you may not need `eidkeys`, we
                # have to compute solutions anyway (kept as annotation on the
                # tree)
                eidkeys = self.solutions(session, rqlst, args)
            except UnknownEid:
                # we want queries such as "Any X WHERE X eid 9999" return an
                # empty result instead of raising UnknownEid
                return empty_rset(rql, args, rqlst)
            if args and not rql in self._rql_ck_cache:
                self._rql_ck_cache[rql] = eidkeys
                if eidkeys:
                    cachekey = self._repo.querier_cache_key(session, rql, args,
                                                            eidkeys)
            self._rql_cache[cachekey] = rqlst
        orig_rqlst = rqlst
        if rqlst.TYPE != 'select':
            if session.read_security:
                check_no_password_selected(rqlst)
            # write query, ensure session's mode is 'write' so connections won't
            # be released until commit/rollback
            session.mode = 'write'
            cachekey = None
        else:
            if session.read_security:
                for select in rqlst.children:
                    check_no_password_selected(select)
            # on select query, always copy the cached rqlst so we don't have to
            # bother modifying it. This is not necessary on write queries since
            # a new syntax tree is built from them.
            rqlst = rqlst.copy()
            self._annotate(rqlst)
        # make an execution plan
        plan = self.plan_factory(rqlst, args, session)
        plan.cache_key = cachekey
        self._planner.build_plan(plan)
        # execute the plan
        try:
            results = plan.execute()
        except (Unauthorized, ValidationError):
            # getting an Unauthorized/ValidationError exception means the
            # transaction must been rollbacked
            #
            # notes:
            # * we should not reset the pool here, since we don't want the
            #   session to loose its pool during processing
            # * don't rollback if we're in the commit process, will be handled
            #   by the session
            if session.commit_state is None:
                session.commit_state = 'uncommitable'
            raise
        # build a description for the results if necessary
        descr = ()
        if build_descr:
            if rqlst.TYPE == 'select':
                # sample selection
                descr = session.build_description(orig_rqlst, args, results)
            elif rqlst.TYPE == 'insert':
                # on insert plan, some entities may have been auto-casted,
                # so compute description manually even if there is only
                # one solution
                basedescr = [None] * len(plan.selected)
                todetermine = zip(xrange(len(plan.selected)), repeat(False))
                descr = session._build_descr(results, basedescr, todetermine)
            # FIXME: get number of affected entities / relations on non
            # selection queries ?
        # return a result set object
        return ResultSet(results, rql, args, descr, orig_rqlst)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

from logging import getLogger
from cubicweb import set_log_methods
LOGGER = getLogger('cubicweb.querier')
set_log_methods(QuerierHelper, LOGGER)
