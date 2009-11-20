"""Helper classes to execute RQL queries on a set of sources, performing
security checking and data aggregation.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from itertools import repeat

from logilab.common.cache import Cache
from logilab.common.compat import any
from rql import RQLHelper, RQLSyntaxError
from rql.stmts import Union, Select
from rql.nodes import (Relation, VariableRef, Constant, SubQuery)

from cubicweb import Unauthorized, QueryError, UnknownEid, typed_eid
from cubicweb import server
from cubicweb.rset import ResultSet

from cubicweb.server.utils import cleanup_solutions
from cubicweb.server.rqlannotation import SQLGenAnnotator, set_qdata
from cubicweb.server.ssplanner import add_types_restriction

READ_ONLY_RTYPES = set(('eid', 'has_text', 'is', 'is_instance_of', 'identity'))

def empty_rset(session, rql, args, rqlst=None):
    """build an empty result set object"""
    return ResultSet([], rql, args, rqlst=rqlst)

def update_varmap(varmap, selected, table):
    """return a sql schema to store RQL query result"""
    for i, term in enumerate(selected):
        key = term.as_string()
        value = '%s.C%s' % (table, i)
        if varmap.get(key, value) != value:
            raise Exception('variable name conflict on %s' % key)
        varmap[key] = value

# permission utilities ########################################################

def var_kwargs(restriction, args):
    varkwargs = {}
    for rel in restriction.iget_nodes(Relation):
        cmp = rel.children[1]
        if rel.r_type == 'eid' and cmp.operator == '=' and \
               not rel.neged(strict=True) and \
               isinstance(cmp.children[0], Constant) and \
               cmp.children[0].type == 'Substitute':
            varkwargs[rel.children[0].name] = typed_eid(cmp.children[0].eval(args))
    return varkwargs

def check_no_password_selected(rqlst):
    """check that Password entities are not selected"""
    for solution in rqlst.solutions:
        if 'Password' in solution.itervalues():
            raise Unauthorized('Password selection is not allowed')

def check_read_access(schema, user, rqlst, solution):
    """check that the given user has credentials to access data read the
    query

    return a dict defining necessary local checks (due to use of rql expression
    in the schema), keys are variable names and values associated rql expression
    for the associated variable with the given solution
    """
    if rqlst.where is not None:
        for rel in rqlst.where.iget_nodes(Relation):
            # XXX has_text may have specific perm ?
            if rel.r_type in READ_ONLY_RTYPES:
                continue
            rschema = schema.rschema(rel.r_type)
            if rschema.final:
                eschema = schema.eschema(solution[rel.children[0].name])
                rdef = eschema.rdef(rschema)
            else:
                rdef = rschema.rdef(solution[rel.children[0].name],
                                    solution[rel.children[1].children[0].name])
            if not user.matching_groups(rdef.get_groups('read')):
                raise Unauthorized('read', rel.r_type)
    localchecks = {}
    # iterate on defined_vars and not on solutions to ignore column aliases
    for varname in rqlst.defined_vars:
        etype = solution[varname]
        eschema = schema.eschema(etype)
        if eschema.final:
            continue
        if not user.matching_groups(eschema.get_groups('read')):
            erqlexprs = eschema.get_rqlexprs('read')
            if not erqlexprs:
                ex = Unauthorized('read', etype)
                ex.var = varname
                raise ex
            #assert len(erqlexprs) == 1
            localchecks[varname] = tuple(erqlexprs)
    return localchecks

def noinvariant_vars(restricted, select, nbtrees):
    # a variable can actually be invariant if it has not been restricted for
    # security reason or if security assertion hasn't modified the possible
    # solutions for the query
    if nbtrees != 1:
        for vname in restricted:
            try:
                yield select.defined_vars[vname]
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
                yield var

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
        noinvariant = set()
        if security and not self.session.is_super_session:
            self._insert_security(union, noinvariant)
        self.rqlhelper.simplify(union)
        self.sqlannotate(union)
        set_qdata(self.schema.rschema, union, noinvariant)
        if union.has_text_query:
            self.cache_key = None

    def _insert_security(self, union, noinvariant):
        rh = self.rqlhelper
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
                        newselect.set_orderby([s.copy(newselect) for s in select.orderby])
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
                    lcheckdef = [((varmap, 'X'), rqlexprs)
                                 for varmap, rqlexprs in lcheckdef]
                    rewrite(myrqlst, lcheckdef, lchecksolutions, self.args)
                    noinvariant.update(noinvariant_vars(restricted, myrqlst, nbtrees))
                if () in localchecks:
                    select.set_possible_types(localchecks[()])
                    add_types_restriction(self.schema, select)
                    noinvariant.update(noinvariant_vars(restricted, select, nbtrees))

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
        assert not self.session.is_super_session
        user = self.session.user
        schema = self.schema
        msgs = []
        # dictionnary of variables restricted for security reason
        localchecks = {}
        if rqlst.where is not None:
            varkwargs = var_kwargs(rqlst.where, self.args)
            neweids = self.session.transaction_data.get('neweids', ())
        else:
            varkwargs = None
        restricted_vars = set()
        newsolutions = []
        for solution in rqlst.solutions:
            try:
                localcheck = check_read_access(schema, user, rqlst, solution)
            except Unauthorized, ex:
                msg = 'remove %s from solutions since %s has no %s access to %s'
                msg %= (solution, user.login, ex.args[0], ex.args[1])
                msgs.append(msg)
                LOGGER.info(msg)
            else:
                newsolutions.append(solution)
                if varkwargs:
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
                            if rqlexpr.check(self.session, eid):
                                break
                        else:
                            raise Unauthorized()
                restricted_vars.update(localcheck)
                localchecks.setdefault(tuple(localcheck.iteritems()), []).append(solution)
        # raise Unautorized exception if the user can't access to any solution
        if not newsolutions:
            raise Unauthorized('\n'.join(msgs))
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
        # list of new or updated entities definition (utils.Entity)
        self.e_defs = [[]]
        # list of new relation definition (3-uple (from_eid, r_type, to_eid)
        self.r_defs = []
        # indexes to track entity definitions bound to relation definitions
        self._r_subj_index = {}
        self._r_obj_index = {}
        self._expanded_r_defs = {}

    def relation_definitions(self, rqlst, to_build):
        """add constant values to entity def, mark variables to be selected
        """
        to_select = {}
        for relation in rqlst.main_relations:
            lhs, rhs = relation.get_variable_parts()
            rtype = relation.r_type
            if rtype in READ_ONLY_RTYPES:
                raise QueryError("can't assign to %s" % rtype)
            try:
                edef = to_build[str(lhs)]
            except KeyError:
                # lhs var is not to build, should be selected and added as an
                # object relation
                edef = to_build[str(rhs)]
                to_select.setdefault(edef, []).append((rtype, lhs, 1))
            else:
                if isinstance(rhs, Constant) and not rhs.uid:
                    # add constant values to entity def
                    value = rhs.eval(self.args)
                    eschema = edef.e_schema
                    attrtype = eschema.subjrels[rtype].objects(eschema)[0]
                    if attrtype == 'Password' and isinstance(value, unicode):
                        value = value.encode('UTF8')
                    edef[rtype] = value
                elif to_build.has_key(str(rhs)):
                    # create a relation between two newly created variables
                    self.add_relation_def((edef, rtype, to_build[rhs.name]))
                else:
                    to_select.setdefault(edef, []).append( (rtype, rhs, 0) )
        return to_select


    def add_entity_def(self, edef):
        """add an entity definition to build"""
        edef.querier_pending_relations = {}
        self.e_defs[-1].append(edef)

    def add_relation_def(self, rdef):
        """add an relation definition to build"""
        self.r_defs.append(rdef)
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
            for edef in edefs[1:]:
                row = samplerow[:]
                row[colidx] = edef
                self.e_defs.append(row)
        # now, see if this entity def is referenced as subject in some relation
        # definition
        if self._r_subj_index.has_key(edef):
            for rdef in self._r_subj_index[edef]:
                expanded = self._expanded(rdef)
                result = []
                for exp_rdef in expanded:
                    for edef in edefs:
                        result.append( (edef, exp_rdef[1], exp_rdef[2]) )
                self._expanded_r_defs[rdef] = result
        # and finally, see if this entity def is referenced as object in some
        # relation definition
        if self._r_obj_index.has_key(edef):
            for rdef in self._r_obj_index[edef]:
                expanded = self._expanded(rdef)
                result = []
                for exp_rdef in expanded:
                    for edef in edefs:
                        result.append( (exp_rdef[0], exp_rdef[1], edef) )
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
                subj = subj.eid
            if isinstance(obj, basestring):
                obj = typed_eid(obj)
            elif not isinstance(obj, (int, long)):
                obj = obj.eid
            if repo.schema.rschema(rtype).inlined:
                entity = session.entity_from_eid(subj)
                entity[rtype] = obj
                repo.glob_update_entity(session, entity, set((rtype,)))
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
        # rql parsing / analysing helper
        self.solutions = repo.vreg.solutions
        self._rql_cache = Cache(repo.config['rql-cache-size'])
        self.cache_hit, self.cache_miss = 0, 0
        # rql planner
        # note: don't use repo.sources, may not be built yet, and also "admin"
        #       isn't an actual source
        rqlhelper = repo.vreg.rqlhelper
        self._parse = rqlhelper.parse
        self._annotate = rqlhelper.annotate
        if len([uri for uri in repo.config.sources() if uri != 'admin']) < 2:
            from cubicweb.server.ssplanner import SSPlanner
            self._planner = SSPlanner(schema, rqlhelper)
        else:
            from cubicweb.server.msplanner import MSPlanner
            self._planner = MSPlanner(schema, rqlhelper)
        # sql generation annotator
        self.sqlgen_annotate = SQLGenAnnotator(schema).annotate

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

    def execute(self, session, rql, args=None, eid_key=None, build_descr=True):
        """execute a rql query, return resulting rows and their description in
        a `ResultSet` object

        * `rql` should be an unicode string or a plain ascii string
        * `args` the optional parameters dictionary associated to the query
        * `build_descr` is a boolean flag indicating if the description should
          be built on select queries (if false, the description will be en empty
          list)
        * `eid_key` must be both a key in args and a substitution in the rql
          query. It should be used to enhance cacheability of rql queries.
          It may be a tuple for keys in args.
          eid_key must be providen in case where a eid substitution is providen
          and resolve some ambiguity in the possible solutions infered for each
          variable in the query.

        on INSERT queries, there will be on row with the eid of each inserted
        entity

        result for DELETE and SET queries is undefined yet

        to maximize the rql parsing/analyzing cache performance, you should
        always use substitute arguments in queries (eg avoid query such as
        'Any X WHERE X eid 123'!)
        """
        if server.DEBUG & (server.DBG_RQL | server.DBG_SQL):
            if server.DEBUG & (server.DBG_MORE | server.DBG_SQL):
                print '*'*80
            print 'querier input', rql, args
        # parse the query and binds variables
        if eid_key is not None:
            if not isinstance(eid_key, (tuple, list)):
                eid_key = (eid_key,)
            cachekey = [rql]
            for key in eid_key:
                try:
                    etype = self._repo.type_from_eid(args[key], session)
                except KeyError:
                    raise QueryError('bad cache key %s (no value)' % key)
                except TypeError:
                    raise QueryError('bad cache key %s (value: %r)' % (
                        key, args[key]))
                except UnknownEid:
                    # we want queries such as "Any X WHERE X eid 9999"
                    # return an empty result instead of raising UnknownEid
                    return empty_rset(session, rql, args)
                cachekey.append(etype)
                # ensure eid is correctly typed in args
                args[key] = typed_eid(args[key])
            cachekey = tuple(cachekey)
        else:
            cachekey = rql
        try:
            rqlst = self._rql_cache[cachekey]
            self.cache_hit += 1
        except KeyError:
            self.cache_miss += 1
            rqlst = self.parse(rql)
            try:
                self.solutions(session, rqlst, args)
            except UnknownEid:
                # we want queries such as "Any X WHERE X eid 9999"
                # return an empty result instead of raising UnknownEid
                return empty_rset(session, rql, args, rqlst)
            self._rql_cache[cachekey] = rqlst
        orig_rqlst = rqlst
        if not rqlst.TYPE == 'select':
            if not session.is_super_session:
                check_no_password_selected(rqlst)
            # write query, ensure session's mode is 'write' so connections
            # won't be released until commit/rollback
            session.mode = 'write'
            cachekey = None
        else:
            if not session.is_super_session:
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
        except Unauthorized:
            # XXX this could be done in security's after_add_relation hooks
            # since it's actually realy only needed there (other relations
            # security is done *before* actual changes, and add/update entity
            # security is done after changes but in an operation, and exception
            # generated in operation's events  properly generate a rollback on
            # the session). Even though, this is done here for a better
            # consistency: getting an Unauthorized exception means the
            # transaction has been rollbacked
            session.rollback()
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
        return ResultSet(results, rql, args, descr, eid_key, orig_rqlst)

from logging import getLogger
from cubicweb import set_log_methods
LOGGER = getLogger('cubicweb.querier')
set_log_methods(QuerierHelper, LOGGER)
