# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
__docformat__ = "restructuredtext en"

from itertools import repeat

from logilab.common.compat import any
from rql import RQLSyntaxError, CoercionError
from rql.stmts import Union
from rql.nodes import ETYPE_PYOBJ_MAP, etype_from_pyobj, Relation, Exists, Not
from yams import BASE_TYPES

from cubicweb import ValidationError, Unauthorized, UnknownEid
from cubicweb import Binary, server
from cubicweb.rset import ResultSet

from cubicweb.utils import QueryCache, RepeatList
from cubicweb.server.rqlannotation import SQLGenAnnotator, set_qdata
from cubicweb.server.ssplanner import READ_ONLY_RTYPES, add_types_restriction
from cubicweb.server.edition import EditedEntity


ETYPE_PYOBJ_MAP[Binary] = 'Bytes'


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
        for var, etype in solution.iteritems():
            if etype == 'Password':
                raise Unauthorized('Password selection is not allowed (%s)' % var)

def term_etype(session, term, solution, args):
    """return the entity type for the given term (a VariableRef or a Constant
    node)
    """
    try:
        return solution[term.name]
    except AttributeError:
        return session.describe(term.eval(args))[0]

def check_read_access(session, rqlst, solution, args):
    """Check that the given user has credentials to access data read by the
    query and return a dict defining necessary "local checks" (i.e. rql
    expression in read permission defined in the schema) where no group grants
    him the permission.

    Returned dictionary's keys are variable names and values the rql expressions
    for this variable (with the given solution).
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
        self.syssource = session.cnxset.source('system')
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
                with self.session.security_enabled(read=False):
                    noinvariant = self._insert_security(union)
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

    def _insert_security(self, union):
        noinvariant = set()
        for select in union.children[:]:
            for subquery in select.with_:
                self._insert_security(subquery.query)
            localchecks, restricted = self._check_permissions(select)
            if any(localchecks):
                self.session.rql_rewriter.insert_local_checks(
                    select, self.args, localchecks, restricted, noinvariant)
        return noinvariant

    def _check_permissions(self, rqlst):
        """Return a dict defining "local checks", i.e. RQLExpression defined in
        the schema that should be inserted in the original query, together with
        a set of variable names which requires some security to be inserted.

        Solutions where a variable has a type which the user can't definitly
        read are removed, else if the user *may* read it (i.e. if an rql
        expression is defined for the "read" permission of the related type),
        the local checks dict is updated.

        The local checks dict has entries for each different local check
        necessary, with associated solutions as value, a local check being
        defined by a list of 2-uple (variable name, rql expressions) for each
        variable which has to be checked. Solutions which don't require local
        checks will be associated to the empty tuple key.

        Note rqlst should not have been simplified at this point.
        """
        session = self.session
        msgs = []
        # dict(varname: eid), allowing to check rql expression for variables
        # which have a known eid
        varkwargs = {}
        if not session.transaction_data.get('security-rqlst-cache'):
            for var in rqlst.defined_vars.itervalues():
                if var.stinfo['constnode'] is not None:
                    eid = var.stinfo['constnode'].eval(self.args)
                    varkwargs[var.name] = int(eid)
        # dictionary of variables restricted for security reason
        localchecks = {}
        restricted_vars = set()
        newsolutions = []
        for solution in rqlst.solutions:
            try:
                localcheck = check_read_access(session, rqlst, solution, self.args)
            except Unauthorized as ex:
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
                    # if entity has been added in the current transaction, the
                    # user can read it whatever rql expressions are associated
                    # to its type
                    if session.added_in_transaction(eid):
                        continue
                    for rqlexpr in rqlexprs:
                        if rqlexpr.check(session, eid):
                            break
                    else:
                        raise Unauthorized('No read acces on %r with eid %i.' % (var, eid))
                # mark variables protected by an rql expression
                restricted_vars.update(localcheck)
                # turn local check into a dict key
                localcheck = tuple(sorted(localcheck.iteritems()))
                localchecks.setdefault(localcheck, []).append(solution)
        # raise Unautorized exception if the user can't access to any solution
        if not newsolutions:
            raise Unauthorized('\n'.join(msgs))
        # if there is some message, solutions have been modified and must be
        # reconsidered by the syntax treee
        if msgs:
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
        if edef in self._r_subj_index:
            for rdef in self._r_subj_index[edef]:
                expanded = self._expanded(rdef)
                result = []
                for exp_rdef in expanded:
                    for edef_ in edefs:
                        result.append( (edef_, exp_rdef[1], exp_rdef[2]) )
                self._expanded_r_defs[rdef] = result
        # and finally, see if this entity def is referenced as object in some
        # relation definition
        if edef in self._r_obj_index:
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
        for rdefs in self._expanded_r_defs.itervalues():
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
        edited_entities = {}
        relations = {}
        for subj, rtype, obj in self.relation_defs():
            # if a string is given into args instead of an int, we get it here
            if isinstance(subj, basestring):
                subj = int(subj)
            elif not isinstance(subj, (int, long)):
                subj = subj.entity.eid
            if isinstance(obj, basestring):
                obj = int(obj)
            elif not isinstance(obj, (int, long)):
                obj = obj.entity.eid
            if repo.schema.rschema(rtype).inlined:
                if subj not in edited_entities:
                    entity = session.entity_from_eid(subj)
                    edited = EditedEntity(entity)
                    edited_entities[subj] = edited
                else:
                    edited = edited_entities[subj]
                edited.edited_attribute(rtype, obj)
            else:
                if rtype in relations:
                    relations[rtype].append((subj, obj))
                else:
                    relations[rtype] = [(subj, obj)]
        repo.glob_add_relations(session, relations)
        for edited in edited_entities.itervalues():
            repo.glob_update_entity(session, edited)


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
        self._rql_cache = QueryCache(repo.config['rql-cache-size'])
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
            print 'querier input', repr(rql), repr(args)
        # parse the query and binds variables
        cachekey = (rql,)
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
            if args and rql not in self._rql_ck_cache:
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
            if args:
                # different SQL generated when some argument is None or not (IS
                # NULL). This should be considered when computing sql cache key
                cachekey += tuple(sorted([k for k, v in args.iteritems()
                                          if v is None]))
        # make an execution plan
        plan = self.plan_factory(rqlst, args, session)
        plan.cache_key = cachekey
        self._planner.build_plan(plan)
        # execute the plan
        try:
            results = plan.execute()
        except (Unauthorized, ValidationError):
            # getting an Unauthorized/ValidationError exception means the
            # transaction must be rolled back
            #
            # notes:
            # * we should not reset the connections set here, since we don't want the
            #   session to loose it during processing
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
                if len(rqlst.children) == 1 and len(rqlst.children[0].solutions) == 1:
                    # easy, all lines are identical
                    selected = rqlst.children[0].selection
                    solution = rqlst.children[0].solutions[0]
                    description = _make_description(selected, args, solution)
                    descr = RepeatList(len(results), tuple(description))
                else:
                    # hard, delegate the work :o)
                    descr = manual_build_descr(session, rqlst, args, results)
            elif rqlst.TYPE == 'insert':
                # on insert plan, some entities may have been auto-casted,
                # so compute description manually even if there is only
                # one solution
                basedescr = [None] * len(plan.selected)
                todetermine = zip(xrange(len(plan.selected)), repeat(False))
                descr = _build_descr(session, results, basedescr, todetermine)
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


def manual_build_descr(tx, rqlst, args, result):
    """build a description for a given result by analysing each row

    XXX could probably be done more efficiently during execution of query
    """
    # not so easy, looks for variable which changes from one solution
    # to another
    unstables = rqlst.get_variable_indices()
    basedescr = []
    todetermine = []
    for i in xrange(len(rqlst.children[0].selection)):
        ttype = _selection_idx_type(i, rqlst, args)
        if ttype is None or ttype == 'Any':
            ttype = None
            isfinal = True
        else:
            isfinal = ttype in BASE_TYPES
        if ttype is None or i in unstables:
            basedescr.append(None)
            todetermine.append( (i, isfinal) )
        else:
            basedescr.append(ttype)
    if not todetermine:
        return RepeatList(len(result), tuple(basedescr))
    return _build_descr(tx, result, basedescr, todetermine)

def _build_descr(tx, result, basedescription, todetermine):
    description = []
    etype_from_eid = tx.describe
    todel = []
    for i, row in enumerate(result):
        row_descr = basedescription[:]
        for index, isfinal in todetermine:
            value = row[index]
            if value is None:
                # None value inserted by an outer join, no type
                row_descr[index] = None
                continue
            if isfinal:
                row_descr[index] = etype_from_pyobj(value)
            else:
                try:
                    row_descr[index] = etype_from_eid(value)[0]
                except UnknownEid:
                    tx.error('wrong eid %s in repository, you should '
                             'db-check the database' % value)
                    todel.append(i)
                    break
        else:
            description.append(tuple(row_descr))
    for i in reversed(todel):
        del result[i]
    return description

def _make_description(selected, args, solution):
    """return a description for a result set"""
    description = []
    for term in selected:
        description.append(term.get_type(solution, args))
    return description

def _selection_idx_type(i, rqlst, args):
    """try to return type of term at index `i` of the rqlst's selection"""
    for select in rqlst.children:
        term = select.selection[i]
        for solution in select.solutions:
            try:
                ttype = term.get_type(solution, args)
                if ttype is not None:
                    return ttype
            except CoercionError:
                return None
